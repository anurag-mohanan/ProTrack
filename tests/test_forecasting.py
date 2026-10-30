"""Phase 3 forecasting: remaining effort, backtest, capacity supply, billing and collections."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models.enums import (
    ExecutionStatus,
    ProjectStage,
    UserAvailabilityStatus,
    UserType,
)
from app.models.finance import (
    Quote,
    QuoteInvoiceLine,
    QuotePaymentLine,
    QuotePaymentMilestone,
    QuoteRevision,
)
from app.models.foundation import Holiday
from app.models.models import Project, Team, User
from app.models.resource_shifts import ResourceShift, ResourceShiftAssignment
from app.services.forecasting.capacity import build_capacity_forecast, day_capacity
from app.services.forecasting.definitions import build_periods
from app.services.forecasting.effort import (
    MIN_HISTORY,
    EffortSample,
    backtest,
    build_engineering_forecast,
    fit_factor,
)
from app.services.forecasting.finance import build_finance_forecast
from app.services.resource_planning_service import _daily_capacity
from tests.conftest import IDS, login
from tests.test_engineering_metrics import _book, _project
from tests.test_stage_delivery_metrics import _completed, _estimate, _staged

PRE = ProjectStage.preliminary


def _sample(day: int, estimate: str, actual: str) -> EffortSample:
    return EffortSample(uuid.uuid4(), date(2001, 1, day), Decimal(estimate), Decimal(actual))


# ----------------------------------------------------------------- effort: pure rules


def test_factor_status_follows_sample_size():
    assert fit_factor([]).status == "unavailable" and fit_factor([]).factor is None
    few = fit_factor([_sample(1, "100", "120"), _sample(2, "100", "140")])
    assert few.status == "preliminary" and few.factor == Decimal("1.3000")
    enough = fit_factor([_sample(i, "100", str(100 + i * 10)) for i in range(1, MIN_HISTORY + 1)])
    assert enough.status == "available" and enough.factor == Decimal("1.3000")  # median of 1.1..1.5


def test_backtest_uses_only_earlier_completions():
    history = [_sample(i, "100", "100") for i in range(1, 6)]
    outlier = _sample(6, "100", "200")
    same_day = _sample(6, "100", "100")
    later = _sample(7, "100", "100")
    result = backtest(history + [outlier, same_day, later])
    assert result.status == "evaluated"
    # outlier and same_day are each predicted from the 5 earlier projects only (factor 1.0);
    # later sees 7 earlier projects whose median is still 1.0.
    assert result.evaluated_count == 3
    assert result.mean_absolute_error_hours == Decimal("33.33")
    assert result.mean_signed_error_hours == Decimal("-33.33")
    assert result.naive_mean_absolute_error_hours == Decimal("33.33")


def test_backtest_reports_not_possible_with_small_sample():
    result = backtest([_sample(i, "100", "110") for i in range(1, 6)])
    assert result.status == "not_possible"
    assert result.evaluated_count == 0 and result.candidate_count == 5
    assert result.mean_absolute_error_hours is None


# ----------------------------------------------------------------- effort: integration


def _seed_effort_history(session, count: int = MIN_HISTORY) -> None:
    for i in range(count):
        project = _completed(session, f"FH-{i}", completed=datetime(2001, 3, 1 + i, 12))
        _staged(session, project, {PRE: "100"}, {PRE: "120"})


def _open_staged(session, estimate: str, actual: str) -> Project:
    project = _project(session, quoted="300")
    _estimate(session, project.id, PRE, estimate)
    if actual != "0":
        _book(session, project.id, actual, week_offset=20)
    return project


def _row(result, project_id):
    return next(r for r in result.projects if r.project_id == project_id)


def test_remaining_effort_uses_history_and_keeps_plan_separate(session):
    _seed_effort_history(session)
    project = _open_staged(session, "100", "40")
    quoted_only = _project(session, quoted="80")
    session.commit()

    result = build_engineering_forecast(session, as_of=date(2001, 12, 31))
    assert result.history.sample_size == MIN_HISTORY and result.history.factor == Decimal("1.2000")
    row = _row(result, project.id)
    assert row.forecast_status == "available"
    assert row.forecast_at_completion_hours == Decimal("120.00")
    assert row.forecast_remaining_hours == Decimal("80.00")
    assert row.approved_remaining_hours == Decimal("60.00")  # plan, not forecast
    assert row.actual_hours == Decimal("40.00")
    assert row.completion_forecast_status == "unavailable"
    assert row.stage_forecast_status == "unavailable"

    other = _row(result, quoted_only.id)
    assert other.forecast_status == "unavailable"
    assert other.forecast_remaining_hours is None and other.approved_remaining_hours is None
    assert other.quoted_hours == Decimal("80.00")
    assert result.metadata.method_version == "effort-1"
    assert result.metadata.confidence is None
    assert result.summary.forecast_remaining_hours == Decimal("80.00")
    assert result.backtest.status == "not_possible"  # 5 samples, none has 5 predecessors


def test_history_after_as_of_is_not_used(session):
    _seed_effort_history(session)
    project = _open_staged(session, "100", "40")
    session.commit()
    result = build_engineering_forecast(session, as_of=date(2001, 2, 28))
    assert result.history.sample_size == 0
    row = _row(result, project.id)
    assert row.forecast_status == "unavailable" and row.forecast_remaining_hours is None
    assert row.approved_remaining_hours == Decimal("60.00")


def test_preliminary_with_small_history_and_unavailable_past_eac(session):
    _seed_effort_history(session, count=2)
    on_track = _open_staged(session, "100", "40")
    burnt = _open_staged(session, "100", "130")
    session.commit()
    result = build_engineering_forecast(session, as_of=date(2001, 12, 31))
    assert _row(result, on_track.id).forecast_status == "preliminary"
    past = _row(result, burnt.id)
    assert past.forecast_status == "unavailable" and past.forecast_remaining_hours is None
    assert "already reach" in (past.forecast_reason or "")
    assert result.metadata.status == "preliminary"


def test_engineering_forecast_is_read_only(session):
    _seed_effort_history(session)
    project = _open_staged(session, "100", "40")
    session.commit()
    before = (project.forecast_completion_date, project.forecast_status, project.actual_hours)
    build_engineering_forecast(session, as_of=date(2001, 12, 31))
    assert not (session.new or session.dirty or session.deleted)
    session.refresh(project)
    assert (project.forecast_completion_date, project.forecast_status, project.actual_hours) == before


# ----------------------------------------------------------------- capacity


def _person(session, team: Team, *, user_type=UserType.employee, **extra) -> User:
    user = User(
        id=uuid.uuid4(),
        role_id=IDS["role_designer"],
        email=f"cap-{uuid.uuid4().hex[:8]}@example.test",
        password_hash="x",
        first_name="Cap",
        last_name=uuid.uuid4().hex[:4],
        is_active=True,
        team_id=team.id,
        user_type=user_type,
        **extra,
    )
    session.add(user)
    session.flush()
    return user


def test_day_capacity_components():
    user = User(id=uuid.uuid4(), working_days="Mon,Tue,Wed,Thu,Fri", working_hours_per_day=Decimal("8"),
                availability_status=UserAvailabilityStatus.available, max_allocation_percent=50,
                joining_date=date(2030, 3, 6))
    monday, wednesday, thursday, saturday = date(2030, 3, 4), date(2030, 3, 6), date(2030, 3, 7), date(2030, 3, 9)
    before_join, _ = day_capacity(user, monday, set(), {})
    assert before_join["scheduled_hours"] == 8 and before_join["outside_employment_hours"] == 8
    assert before_join["available_hours"] == 0
    holiday, _ = day_capacity(user, thursday, {thursday}, {})
    assert holiday["holiday_hours"] == 8 and holiday["available_hours"] == 0
    shift, source = day_capacity(user, wednesday, set(), {user.id: {wednesday: Decimal("7")}})
    assert source == "shift" and shift["available_hours"] == 7 and shift["allocatable_hours"] == Decimal("3.5")
    weekend, source = day_capacity(user, saturday, set(), {})
    assert source is None and weekend["scheduled_hours"] == 0
    user.availability_status = UserAvailabilityStatus.on_leave
    flagged, _ = day_capacity(user, wednesday, set(), {})
    assert flagged["status_unavailable_hours"] == 8 and flagged["available_hours"] == 0


def test_capacity_forecast_reconciles_and_matches_grid(session):
    team = Team(id=uuid.uuid4(), name="Forecast Cap Team", is_active=True)
    session.add(team)
    session.flush()
    steady = _person(session, team)
    leaver = _person(session, team, leaving_date=date(2030, 3, 13), max_allocation_percent=50)
    _person(session, team, user_type=UserType.virtual)
    session.add(Holiday(name="Test holiday", holiday_date=date(2030, 3, 5)))
    shift = ResourceShift(code="FCT", name="Forecast test", start_time="14:00", end_time="22:00", break_minutes=60)
    session.add(shift)
    session.flush()
    session.add(ResourceShiftAssignment(user_id=steady.id, shift_id=shift.id, effective_from=date(2030, 3, 11)))
    session.commit()

    result = build_capacity_forecast(session, start=date(2030, 3, 4), granularity="week", periods=2,
                                     team_ids={team.id}, as_of=date(2030, 3, 4))
    assert {p.user_id for p in result.people} == {steady.id, leaver.id}  # virtual user excluded
    people = {p.user_id: p for p in result.people}
    week1, week2 = (p.key for p in result.periods)

    s1, s2 = people[steady.id].periods
    assert (s1.scheduled_hours, s1.holiday_hours, s1.available_hours) == (Decimal("40"), Decimal("8"), Decimal("32"))
    assert s2.available_hours == Decimal("35.00") and people[steady.id].hours_source == "mixed"

    l1, l2 = people[leaver.id].periods
    assert l2.outside_employment_hours == Decimal("16.00") and l2.available_hours == Decimal("24.00")
    assert l2.allocatable_hours == Decimal("12.00")

    for period_total in result.totals:
        rows = [next(c for c in p.periods if c.period_key == period_total.period_key) for p in result.people]
        assert period_total.available_hours == sum((r.available_hours for r in rows), Decimal("0"))
        assert period_total.available_hours == (
            period_total.scheduled_hours - period_total.holiday_hours
            - period_total.outside_employment_hours - period_total.status_unavailable_hours
        )
    assert result.teams[0].total.available_hours == result.grand_total.available_hours

    # Same daily rule as the Resource Planning grid for a person without an employment window.
    from app.services.holiday_service import load_holiday_dates
    from app.services.resource_shift_service import shift_hours_for_range

    holidays = load_holiday_dates(session, date(2030, 3, 4), date(2030, 3, 17))
    shifts = shift_hours_for_range(session, [steady.id], date(2030, 3, 4), date(2030, 3, 17))
    grid = sum((_daily_capacity(steady, date(2030, 3, 4) + timedelta(days=i), holidays, shifts) for i in range(14)), Decimal("0"))
    assert people[steady.id].total.available_hours == grid
    assert result.metadata.status == "preliminary"
    assert result.gap_analysis_status == "unavailable" and result.skill_demand_status == "unavailable"
    assert {week1, week2} == {"2030-W10", "2030-W11"}


def test_capacity_demand_is_unphased_approved_plan(session):
    team = Team(id=uuid.uuid4(), name="Demand Team", is_active=True)
    session.add(team)
    session.flush()
    approved = _project(session, quoted="500", team_id=team.id)
    _estimate(session, approved.id, PRE, "100")
    _book(session, approved.id, "30")
    _project(session, quoted="200", team_id=team.id)
    session.commit()
    result = build_capacity_forecast(session, start=date(2030, 3, 4), team_ids={team.id}, as_of=date(2030, 3, 4))
    assert result.demand.value_kind == "approved_plan"
    assert result.demand.approved_remaining_hours == Decimal("70.00")
    assert result.demand.projects_with_approved_estimate == 1
    assert result.demand.projects_without_approved_estimate == 1
    assert result.demand.phasing_status == "unavailable"


# ----------------------------------------------------------------- finance


def _quote(session, team: Team, *, awarded: str, project_id=None, currency="INR") -> Quote:
    quote = Quote(id=uuid.uuid4(), customer_id=IDS["customer"], team_id=team.id, project_id=project_id,
                  tool_number=f"FQ-{uuid.uuid4().hex[:6]}", currency_code=currency, is_active=True)
    session.add(quote)
    session.flush()
    session.add(QuoteRevision(
        id=uuid.uuid4(), quote_id=quote.id, version=1, revision="A", quoted_hours=Decimal("10"),
        estimated_cost=Decimal("0"), quoted_revenue=Decimal(awarded), margin=Decimal("0"),
        margin_percent=Decimal("0"), base_estimated_cost_inr=Decimal("0"),
        base_quoted_revenue_inr=Decimal(awarded), fx_rate=Decimal("1"), fx_date=date(2030, 1, 1),
    ))
    session.flush()
    return quote


def _invoice(session, quote: Quote, amount: str, invoiced: date, due: date | None, **extra) -> QuoteInvoiceLine:
    line = QuoteInvoiceLine(quote_id=quote.id, amount=Decimal(amount), line_date=invoiced, due_date=due, **extra)
    session.add(line)
    session.flush()
    return line


def _milestone(session, quote: Quote, seq: int, pct: str, trigger: str, status="NOT_YET_TRIGGERED") -> QuotePaymentMilestone:
    row = QuotePaymentMilestone(quote_id=quote.id, sequence=seq, name=f"M{seq}", percentage=Decimal(pct),
                                trigger_type=trigger, trigger_status=status)
    session.add(row)
    session.flush()
    return row


def _finance_team(session) -> Team:
    team = Team(id=uuid.uuid4(), name=f"Fin {uuid.uuid4().hex[:4]}", is_active=True)
    session.add(team)
    session.flush()
    return team


AS_OF = date(2030, 3, 15)


def test_collections_follow_fifo_and_due_dates(session):
    team = _finance_team(session)
    quote = _quote(session, team, awarded="1000")
    _invoice(session, quote, "100", date(2030, 1, 10), date(2030, 2, 10))  # fully paid by FIFO
    _invoice(session, quote, "200", date(2030, 2, 1), date(2030, 4, 20))
    _invoice(session, quote, "50", date(2030, 2, 5), None)
    overdue = _quote(session, team, awarded="300")
    _invoice(session, overdue, "300", date(2030, 1, 1), date(2030, 2, 1))
    session.add(QuotePaymentLine(quote_id=quote.id, amount=Decimal("120"), line_date=date(2030, 2, 20)))
    session.commit()

    result = build_finance_forecast(session, as_of=AS_OF, team_id=team.id)
    totals = result.totals[0]
    assert totals.outstanding == Decimal("530.00")  # 350 − 120 + 300
    assert totals.outstanding_scheduled == Decimal("180.00")
    assert totals.outstanding_no_due_date == Decimal("50.00")
    assert totals.outstanding_overdue == Decimal("300.00")
    assert totals.collections_by_period == {"2030-04": Decimal("180.00")}
    timings = sorted((c.timing, c.outstanding) for c in result.collections)
    assert timings == [("no_due_date", Decimal("50.00")), ("overdue", Decimal("300.00")), ("scheduled", Decimal("180.00"))]
    assert result.reconciliation.outstanding_matches_ledger is True
    # Unlinked quotes are not billed forward, but their issued invoices are still collected.
    assert {e.reason[:24] for e in result.excluded} == {"Not linked to a project."}
    assert totals.excluded_remaining_to_invoice == Decimal("650.00")
    assert result.billing == []


def test_billing_splits_remaining_without_double_counting(session):
    team = _finance_team(session)
    project = _project(session, quoted="100", team_id=team.id)
    project.due_date = date(2030, 5, 20)
    quote = _quote(session, team, awarded="1000", project_id=project.id)
    _invoice(session, quote, "350", date(2030, 2, 1), date(2030, 3, 31))
    completion = _milestone(session, quote, 1, "30", "PROJECT_COMPLETION")
    _milestone(session, quote, 2, "20", "DESIGN_MILESTONE", status="READY_TO_INVOICE")
    _milestone(session, quote, 3, "10", "FINAL_REVIEW")
    session.commit()

    result = build_finance_forecast(session, as_of=AS_OF, team_id=team.id)
    totals = result.totals[0]
    assert totals.remaining_to_invoice == Decimal("650.00")
    by_kind = {(i.kind, i.date_status): i for i in result.billing}
    dated = by_kind[("milestone", "dated_by_target")]
    assert dated.milestone_id == completion.id and dated.amount == Decimal("300.00")
    assert dated.expected_invoice_date == date(2030, 5, 20) and dated.depends_on_delivery
    assert by_kind[("milestone", "ready_to_invoice")].amount == Decimal("200.00")
    assert by_kind[("milestone", "undated")].amount == Decimal("100.00")
    assert by_kind[("unscheduled_remaining", "undated")].amount == Decimal("50.00")
    assert sum((i.amount for i in result.billing), Decimal("0")) == totals.remaining_to_invoice
    assert (totals.billing_ready, totals.billing_dated, totals.billing_undated) == (
        Decimal("200.00"), Decimal("300.00"), Decimal("150.00"))
    assert totals.billing_by_period == {"2030-05": Decimal("300.00")}
    assert result.reconciliation.billing_matches_remaining is True


def test_billing_schedule_exceeding_remaining_is_flagged_not_counted_twice(session):
    team = _finance_team(session)
    project = _project(session, quoted="100", team_id=team.id)
    quote = _quote(session, team, awarded="1000", project_id=project.id)
    _invoice(session, quote, "600", date(2030, 2, 1), date(2030, 4, 1))  # not linked to any milestone
    _milestone(session, quote, 1, "50", "PROJECT_COMPLETION")
    _milestone(session, quote, 2, "50", "FINAL_REVIEW")
    session.commit()
    result = build_finance_forecast(session, as_of=AS_OF, team_id=team.id)
    assert [(i.kind, i.amount) for i in result.billing] == [("unscheduled_remaining", Decimal("400.00"))]
    assert any("needs review" in w for w in result.warnings)
    assert result.reconciliation.billing_matches_remaining is True


def test_finance_forecast_never_changes_milestone_status_and_splits_currency(session):
    team = _finance_team(session)
    project = _project(session, quoted="100", team_id=team.id)
    quote = _quote(session, team, awarded="1000", project_id=project.id)
    milestone = _milestone(session, quote, 1, "40", "DESIGN_MILESTONE")
    _invoice(session, quote, "400", date(2030, 2, 1), date(2030, 4, 1), payment_milestone_id=milestone.id)
    cancelled = _project(session, quoted="100", team_id=team.id, status=ExecutionStatus.cancelled)
    _quote(session, team, awarded="500", project_id=cancelled.id, currency="USD")
    session.commit()

    result = build_finance_forecast(session, as_of=AS_OF, team_id=team.id)
    assert not (session.new or session.dirty or session.deleted)
    session.expire_all()
    assert session.get(QuotePaymentMilestone, milestone.id).trigger_status == "NOT_YET_TRIGGERED"
    assert all(i.milestone_id != milestone.id for i in result.billing)  # already invoiced
    assert [t.currency for t in result.totals] == ["INR", "USD"]
    usd = result.totals[1]
    assert usd.excluded_remaining_to_invoice == Decimal("500.00") and usd.remaining_to_invoice == Decimal("500.00")
    assert any(e.reason == "The linked project is cancelled." for e in result.excluded)


def test_periods_are_calendar_aligned():
    weeks = build_periods(date(2030, 3, 6), "week", 2)
    assert weeks[0].start_date == date(2030, 3, 4) and weeks[1].end_date == date(2030, 3, 17)
    months = build_periods(date(2030, 12, 15), "month", 2)
    assert [m.key for m in months] == ["2030-12", "2031-01"]


# ----------------------------------------------------------------- performance


def _count_queries(session, fn) -> int:
    from sqlalchemy import event

    engine = session.get_bind()
    statements: list[str] = []

    def _count(conn, cursor, statement, *args):
        statements.append(statement)

    session.expire_all()
    event.listen(engine, "before_cursor_execute", _count)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", _count)
    return len(statements)


def test_engineering_and_capacity_use_a_constant_number_of_queries(session):
    team = Team(id=uuid.uuid4(), name="Perf Team", is_active=True)
    session.add(team)
    session.flush()

    def _seed(count: int) -> None:
        for _ in range(count):
            project = _open_staged(session, "50", "8")
            project.team_id = team.id
            _person(session, team)
            done = _completed(session, f"PF-{uuid.uuid4().hex[:4]}", completed=datetime(2001, 3, 1, 12))
            _staged(session, done, {PRE: "10"}, {PRE: "12"})
        session.commit()

    def _run() -> None:
        build_engineering_forecast(session, as_of=date(2001, 12, 31))
        build_capacity_forecast(session, start=date(2030, 3, 4), team_ids={team.id}, as_of=date(2030, 3, 4))

    _seed(2)
    small = _count_queries(session, _run)
    _seed(8)
    assert _count_queries(session, _run) == small


# ----------------------------------------------------------------- API and permissions


def test_forecast_endpoints_for_admin(client):
    headers = client.auth_headers
    catalog = client.get("/api/v1/forecasts", headers=headers)
    assert catalog.status_code == 200, catalog.text
    body = catalog.json()
    assert body["can_view_engineering"] and body["can_view_capacity"] and body["can_view_finance"]
    deferred = {d["key"] for d in body["definitions"] if d["deferred"]}
    assert deferred == {"completion_date", "stage_forecast", "capacity_gap", "scenarios"}
    for path in ("engineering", "capacity?granularity=month&periods=3", "finance"):
        response = client.get(f"/api/v1/forecasts/{path}", headers=headers)
        assert response.status_code == 200, (path, response.text)
        assert response.json()["metadata"]["confidence"] is None


def test_forecast_endpoints_enforce_permissions(client):
    designer = login(client, "binil@prosohm.com")
    catalog = client.get("/api/v1/forecasts", headers=designer).json()
    assert not catalog["can_view_finance"] and not catalog["can_view_capacity"]
    assert client.get("/api/v1/forecasts/finance", headers=designer).status_code == 403
    assert client.get("/api/v1/forecasts/capacity", headers=designer).status_code == 403
    expected_engineering = 200 if catalog["can_view_engineering"] else 403
    assert client.get("/api/v1/forecasts/engineering", headers=designer).status_code == expected_engineering
    assert client.get("/api/v1/forecasts/engineering").status_code == 401


def test_capacity_rejects_out_of_scope_and_unknown_team(client):
    response = client.get(f"/api/v1/forecasts/capacity?team_id={uuid.uuid4()}", headers=client.auth_headers)
    assert response.status_code == 400
    assert client.get("/api/v1/forecasts/capacity?periods=99", headers=client.auth_headers).status_code == 422


def test_engineering_forecast_respects_project_scope(client, session):
    mine = _project(session, quoted="100")
    hidden = _project(session, quoted="100")
    hidden.designer_id = IDS["user_ranjith"]
    hidden.design_leader_id = IDS["user_pm"]
    designer = session.get(User, IDS["user_binil"])
    designer.module_access = '["dashboard", "projects", "timesheets", "reports"]'
    session.commit()

    headers = login(client, "binil@prosohm.com")
    response = client.get("/api/v1/forecasts/engineering", headers=headers)
    assert response.status_code == 200, response.text
    ids = {row["project_id"] for row in response.json()["projects"]}
    assert str(mine.id) in ids and str(hidden.id) not in ids
    assert client.get("/api/v1/forecasts/finance", headers=headers).status_code == 403

    admin = client.get("/api/v1/forecasts/engineering", headers=client.auth_headers).json()
    assert str(hidden.id) in {row["project_id"] for row in admin["projects"]}
    assert session.scalar(select(Project.id).where(Project.id == hidden.id)) is not None
