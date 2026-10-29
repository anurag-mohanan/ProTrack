"""Engineering metrics: approved estimate, actual hours, variance and data quality."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.models.enums import (
    PLANNED_STAGES,
    ExecutionStatus,
    ProjectStage,
    TimesheetStatus,
    WorkCategory,
)
from app.models.finance import Quote, QuoteRevision
from app.models.models import (
    Milestone,
    Project,
    ProjectStageEstimate,
    Team,
    Timesheet,
    TimesheetEntry,
)
from app.services.engineering_metrics_service import hour_metrics
from app.services.project_calculation_service import calculate_hours
from app.services.project_contributor_service import get_project_contributors
from tests.conftest import IDS, login
from tests.test_engineering_management import _create_redoe_project


def _url(project_id) -> str:
    return f"/api/v1/projects/{project_id}/engineering-metrics"


def _project(session, *, quoted: str = "100", status=ExecutionStatus.currently_being_worked_on,
             completed_at: datetime | None = None, team_id=None, code: str | None = None) -> Project:
    row = Project(
        id=uuid.uuid4(),
        tool_number=f"EMX-{uuid.uuid4().hex[:6]}",
        part_description="Metrics part",
        customer_id=IDS["customer"],
        customer_contact_id=IDS["contact"],
        design_leader_id=IDS["user_anurag"],
        designer_id=IDS["user_binil"],
        stream_id=IDS["stream"],
        team_id=team_id,
        code=code or f"EMX-{uuid.uuid4().hex[:6]}",
        quoted_hours=Decimal(quoted),
        actual_hours=Decimal("0"),
        due_date=date.today() + timedelta(days=30),
        execution_status=status,
        completed_at=completed_at,
    )
    session.add(row)
    session.flush()
    return row


def _sheet(session, user_id, week_start: date, status: TimesheetStatus) -> Timesheet:
    sheet = session.scalar(
        select(Timesheet).where(Timesheet.user_id == user_id, Timesheet.week_start == week_start)
    )
    if sheet is None:
        sheet = Timesheet(id=uuid.uuid4(), user_id=user_id, week_start=week_start, status=status)
        session.add(sheet)
        session.flush()
    return sheet


def _book(session, project_id, hours: str, *, user_id=None, week_offset: int = 0,
          status=TimesheetStatus.approved, milestone_id=None, deleted: bool = False) -> None:
    """Book ``hours`` as up-to-8-hour entries on consecutive days of one week."""
    monday = date(2025, 1, 6) + timedelta(weeks=week_offset)
    sheet = _sheet(session, user_id or IDS["user_binil"], monday, status)
    remaining = Decimal(hours)
    day = 0
    while remaining > 0:
        chunk = min(remaining, Decimal("8"))
        session.add(
            TimesheetEntry(
                timesheet_id=sheet.id,
                entry_date=monday + timedelta(days=day),
                hours=chunk,
                work_category=WorkCategory.productive,
                is_billable=True,
                customer_id=IDS["customer"],
                project_id=project_id,
                milestone_id=milestone_id,
                is_deleted=deleted,
            )
        )
        remaining -= chunk
        day += 1
    session.flush()


def _stage_milestone(session, project_id, stage: ProjectStage) -> Milestone:
    row = session.scalar(
        select(Milestone)
        .where(Milestone.project_id == project_id, Milestone.project_stage == stage)
        .order_by(Milestone.sort_order)
    )
    assert row is not None, stage
    return row


def _get(client, project_id, headers=None):
    response = client.get(_url(project_id), headers=headers or client.auth_headers)
    assert response.status_code == 200, response.text
    return response.json()


def _d(value) -> Decimal | None:
    return None if value is None else Decimal(str(value))


# ----------------------------------------------------------------- calculation rules


def test_under_estimate_produces_negative_variance():
    variance, utilization, remaining = hour_metrics(Decimal("100"), Decimal("80"))
    assert variance.value == Decimal("-20.00")
    assert utilization.value == Decimal("80.00")
    assert remaining.value == Decimal("20.00")


def test_over_estimate_keeps_negative_remaining():
    variance, utilization, remaining = hour_metrics(Decimal("100"), Decimal("120"))
    assert variance.value == Decimal("20.00")
    assert utilization.value == Decimal("120.00")
    assert remaining.value == Decimal("-20.00")


def test_missing_estimate_is_unavailable_not_zero():
    for metric in hour_metrics(None, Decimal("10")):
        assert metric.status == "unavailable"
        assert metric.value is None


def test_zero_estimate_does_not_divide():
    variance, utilization, remaining = hour_metrics(Decimal("0"), Decimal("3"))
    assert variance.value == Decimal("3.00")
    assert utilization.status == "not_applicable" and utilization.value is None
    assert remaining.value == Decimal("-3.00")


def test_missing_actual_is_distinct_from_zero_actual():
    missing = hour_metrics(Decimal("50"), None)
    assert all(metric.status == "unavailable" for metric in missing)
    zero = hour_metrics(Decimal("50"), Decimal("0"))
    assert zero[0].value == Decimal("-50.00")
    assert zero[1].value == Decimal("0.00")


def test_decimal_hours_round_half_up():
    variance, utilization, remaining = hour_metrics(Decimal("37.5"), Decimal("12.25"))
    assert variance.value == Decimal("-25.25")
    assert utilization.value == Decimal("32.67")
    assert remaining.value == Decimal("25.25")


# ----------------------------------------------------------------- API: complete data


def test_complete_project_metrics_and_stage_hours(client, session):
    created = _create_redoe_project(client, session)
    project_id = uuid.UUID(created["id"])
    blockout = _stage_milestone(session, project_id, ProjectStage.preliminary)
    intermediate = _stage_milestone(session, project_id, ProjectStage.intermediate)
    _book(session, project_id, "30", milestone_id=blockout.id)
    _book(session, project_id, "20", week_offset=1, status=TimesheetStatus.submitted,
          milestone_id=intermediate.id)
    session.commit()

    body = _get(client, project_id)
    assert body["estimate"]["estimate_source"] == "stage_estimates"
    assert _d(body["estimate"]["original_estimate_hours"]) == Decimal("90")
    assert _d(body["estimate"]["current_estimate_hours"]) == Decimal("90")
    assert body["actual"]["status"] == "recorded"
    assert _d(body["actual"]["total_hours"]) == Decimal("50")
    assert _d(body["actual"]["approved_hours"]) == Decimal("30")
    assert _d(body["actual"]["submitted_hours"]) == Decimal("20")
    assert _d(body["variance_hours"]["value"]) == Decimal("-40")
    assert _d(body["utilization_percent"]["value"]) == Decimal("55.56")
    assert _d(body["remaining_hours"]["value"]) == Decimal("40")

    stage = body["stage_attribution"]
    assert stage["status"] == "complete"
    assert _d(stage["coverage_percent"]) == Decimal("100")
    by_key = {row["key"]: row for row in stage["rows"]}
    assert _d(by_key["preliminary"]["actual_hours"]) == Decimal("30")
    assert _d(by_key["preliminary"]["variance_hours"]) == Decimal("-10")
    assert _d(by_key["intermediate"]["actual_hours"]) == Decimal("20")
    assert _d(by_key["final"]["actual_hours"]) == Decimal("0")

    codes = {issue["code"] for issue in body["issues"]}
    assert "includes_unapproved_hours" in codes
    assert "quote_unlinked" in codes
    assert body["data_quality_status"] == "available"
    assert body["milestones"]["baseline_completion_date"] is not None
    assert {d["key"] for d in body["definitions"]} >= {"variance", "utilization", "remaining"}


def test_revision_keeps_original_estimate_separate(client, session):
    created = _create_redoe_project(client, session)
    response = client.post(
        f"/api/v1/projects/{created['id']}/stage-estimates/revisions",
        json={"stage": "preliminary", "new_hours": "60", "reason": "Customer added ribs"},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    body = _get(client, created["id"])
    assert _d(body["estimate"]["original_estimate_hours"]) == Decimal("90")
    assert _d(body["estimate"]["current_estimate_hours"]) == Decimal("110")
    assert _d(body["estimate"]["quoted_hours"]) == Decimal("90")
    assert body["estimate"]["revision_count"] == 1


# ----------------------------------------------------------------- timesheet aggregation


def test_status_rules_deleted_entries_and_join_duplication(client, session):
    created = _create_redoe_project(client, session)
    project_id = uuid.UUID(created["id"])
    blockout = _stage_milestone(session, project_id, ProjectStage.preliminary)
    final = _stage_milestone(session, project_id, ProjectStage.final)
    _book(session, project_id, "30", milestone_id=blockout.id)
    _book(session, project_id, "12.5", user_id=IDS["user_ranjith"], milestone_id=final.id)
    _book(session, project_id, "5", week_offset=2, status=TimesheetStatus.rejected)
    _book(session, project_id, "7", milestone_id=blockout.id, deleted=True)
    _book(session, project_id, "4.25", week_offset=3, status=TimesheetStatus.draft)
    for revision in ("A", "B"):
        quote = Quote(
            id=uuid.uuid4(),
            customer_id=IDS["customer"],
            project_id=project_id,
            tool_number=created["tool_number"],
            currency_code="USD",
            current_revision=revision,
            is_active=True,
        )
        session.add(quote)
        session.flush()
        session.add(QuoteRevision(
            id=uuid.uuid4(), quote_id=quote.id, version=1, revision=revision,
            quoted_hours=Decimal("90"), fx_date=date(2025, 1, 1),
        ))
    session.commit()

    body = _get(client, project_id)
    expected_total = Decimal("51.75")  # 30 + 12.5 + 5 rejected + 4.25 draft; deleted 7 excluded
    assert _d(body["actual"]["total_hours"]) == expected_total
    assert _d(body["actual"]["rejected_hours"]) == Decimal("5")
    assert _d(body["actual"]["draft_hours"]) == Decimal("4.25")
    status_sum = sum(
        _d(body["actual"][key]) for key in
        ("approved_hours", "submitted_hours", "draft_hours", "rejected_hours")
    )
    assert status_sum == expected_total
    assert body["actual"]["entry_count"] == 8  # 4 + 2 + 1 + 1 daily entries

    # Same rule as the project page and the contributors panel.
    session.expire_all()
    project = session.get(Project, project_id)
    assert calculate_hours(session, project).actual == expected_total
    contributors = get_project_contributors(session, project_id)
    assert sum(Decimal(str(c.total_hours)) for c in contributors) == expected_total

    stage = body["stage_attribution"]
    assert stage["status"] == "partial"
    stage_sum = sum(_d(row["actual_hours"]) for row in stage["rows"])
    unattributed = sum(
        _d(stage[key]) for key in
        ("other_stage_hours", "no_stage_hours", "no_milestone_hours", "invalid_milestone_hours")
    )
    assert stage_sum == Decimal("42.5")
    assert stage_sum + unattributed == expected_total
    assert _d(stage["no_milestone_hours"]) == Decimal("9.25")

    codes = {issue["code"]: issue for issue in body["issues"]}
    assert codes["includes_rejected_hours"]["severity"] == "warning"
    assert "stage_attribution_partial" in codes
    assert "quote_link_ambiguous" in codes
    assert body["quote_linkage"]["status"] == "ambiguous"
    assert body["data_quality_status"] == "available_with_limitations"


def test_entry_on_another_projects_milestone_is_not_staged(client, session):
    created = _create_redoe_project(client, session)
    other = _create_redoe_project(client, session)
    project_id = uuid.UUID(created["id"])
    foreign = _stage_milestone(session, uuid.UUID(other["id"]), ProjectStage.preliminary)
    _book(session, project_id, "6", milestone_id=foreign.id)
    session.commit()
    body = _get(client, project_id)
    assert _d(body["stage_attribution"]["invalid_milestone_hours"]) == Decimal("6")
    assert body["stage_attribution"]["status"] == "unavailable"
    assert body["stage_attribution"]["rows"] == []
    assert _d(body["actual"]["total_hours"]) == Decimal("6")
    assert "invalid_milestone_link" in {issue["code"] for issue in body["issues"]}


def test_quoted_hours_project_under_and_over_estimate(client, session):
    project = _project(session, quoted="100")
    _book(session, project.id, "8")
    for week in range(1, 10):
        _book(session, project.id, "8", week_offset=week)
    session.commit()
    body = _get(client, project.id)
    assert body["estimate"]["estimate_source"] == "quoted_hours"
    assert _d(body["actual"]["total_hours"]) == Decimal("80")
    assert _d(body["variance_hours"]["value"]) == Decimal("-20")
    assert _d(body["utilization_percent"]["value"]) == Decimal("80")
    assert _d(body["remaining_hours"]["value"]) == Decimal("20")

    for week in range(10, 15):
        _book(session, project.id, "8", week_offset=week)
    session.commit()
    body = _get(client, project.id)
    assert _d(body["actual"]["total_hours"]) == Decimal("120")
    assert _d(body["variance_hours"]["value"]) == Decimal("20")
    assert _d(body["utilization_percent"]["value"]) == Decimal("120")
    assert _d(body["remaining_hours"]["value"]) == Decimal("-20")
    assert body["stage_attribution"]["status"] == "unavailable"


# ----------------------------------------------------------------- missing data


def test_legacy_completed_project_reports_missing_data(client, session):
    project = _project(
        session, quoted="0", status=ExecutionStatus.completed,
        completed_at=datetime(2025, 3, 1, 10),
    )
    session.commit()
    body = _get(client, project.id)
    assert body["estimate"]["estimate_source"] == "none"
    assert body["estimate"]["current_estimate_hours"] is None
    assert body["actual"]["status"] == "missing"
    assert body["actual"]["total_hours"] is None
    for key in ("variance_hours", "utilization_percent", "remaining_hours"):
        assert body[key]["status"] == "unavailable"
        assert body[key]["value"] is None
    codes = {issue["code"] for issue in body["issues"]}
    assert {"estimate_unavailable", "actual_hours_missing"} <= codes
    assert body["data_quality_status"] == "unavailable"


def test_not_started_project_has_genuine_zero_hours(client, session):
    project = _project(session, quoted="40", status=ExecutionStatus.planning)
    session.commit()
    body = _get(client, project.id)
    assert body["actual"]["status"] == "none_recorded"
    assert _d(body["actual"]["total_hours"]) == Decimal("0")
    assert _d(body["variance_hours"]["value"]) == Decimal("-40")
    assert _d(body["utilization_percent"]["value"]) == Decimal("0")
    assert body["stage_attribution"]["status"] == "unavailable"


def test_zero_stage_estimate_is_not_applicable(client, session):
    project = _project(session, quoted="0")
    for stage in PLANNED_STAGES:
        session.add(ProjectStageEstimate(
            project_id=project.id, stage=stage,
            original_hours=Decimal("0"), current_hours=Decimal("0"),
        ))
    _book(session, project.id, "3")
    session.commit()
    body = _get(client, project.id)
    assert _d(body["estimate"]["current_estimate_hours"]) == Decimal("0")
    assert _d(body["variance_hours"]["value"]) == Decimal("3")
    assert body["utilization_percent"]["status"] == "not_applicable"
    assert _d(body["remaining_hours"]["value"]) == Decimal("-3")
    assert "estimate_zero" in {issue["code"] for issue in body["issues"]}


# ----------------------------------------------------------------- quote selection


def _quote(session, project_id, *, active: bool, revisions: dict[str, str], current: str) -> Quote:
    quote = Quote(
        id=uuid.uuid4(),
        customer_id=IDS["customer"],
        project_id=project_id,
        tool_number="Q-TOOL",
        external_quote_number=f"QN-{uuid.uuid4().hex[:4]}",
        currency_code="USD",
        current_version=1,
        current_revision=current,
        is_active=active,
    )
    session.add(quote)
    session.flush()
    for revision, hours in revisions.items():
        session.add(QuoteRevision(
            id=uuid.uuid4(), quote_id=quote.id, version=1, revision=revision,
            quoted_hours=Decimal(hours), fx_date=date(2025, 1, 1),
        ))
    session.flush()
    return quote


def test_inactive_quotes_are_never_selected(client, session):
    project = _project(session, quoted="100")
    _quote(session, project.id, active=False, revisions={"A": "500"}, current="A")
    session.commit()
    body = _get(client, project.id)
    assert body["quote_linkage"]["status"] == "unlinked"
    assert body["quote_linkage"]["active_quote_count"] == 0
    assert _d(body["estimate"]["current_estimate_hours"]) == Decimal("100")


def test_current_quote_revision_follows_pointer_and_never_replaces_estimate(client, session):
    project = _project(session, quoted="100")
    _quote(session, project.id, active=True, revisions={"A": "90", "B": "110"}, current="B")
    session.commit()
    body = _get(client, project.id)
    linkage = body["quote_linkage"]
    assert linkage["status"] == "linked"
    assert linkage["details_visible"] is True
    assert _d(linkage["quote_hours"]) == Decimal("110")
    assert linkage["quote_revision"] == "B"
    assert _d(body["estimate"]["current_estimate_hours"]) == Decimal("100")
    assert "quote_hours_differ" in {issue["code"] for issue in body["issues"]}

    designer = login(client, "binil@prosohm.com")
    hidden = _get(client, project.id, headers=designer)["quote_linkage"]
    assert hidden["status"] == "linked"
    assert hidden["details_visible"] is False
    assert hidden["quote_hours"] is None
    assert hidden["quote_reference"] is None


# ----------------------------------------------------------------- permissions & errors


def test_other_team_project_is_forbidden(client, session):
    team = Team(id=uuid.uuid4(), name=f"Metrics Other {uuid.uuid4().hex[:4]}", is_active=True)
    session.add(team)
    session.flush()
    other = Project(
        id=uuid.uuid4(),
        tool_number=f"EMX-OT-{uuid.uuid4().hex[:4]}",
        part_description="Other team",
        customer_id=IDS["customer"],
        team_id=team.id,
        quoted_hours=Decimal("10"),
        actual_hours=Decimal("0"),
        execution_status=ExecutionStatus.planning,
    )
    session.add(other)
    session.commit()
    leader = login(client, "anurag@prosohm.com")
    response = client.get(_url(other.id), headers=leader)
    assert response.status_code in (403, 404), response.text


def test_invalid_and_unknown_projects(client, session):
    assert client.get(_url(uuid.uuid4()), headers=client.auth_headers).status_code == 404
    assert client.get(_url("not-a-uuid"), headers=client.auth_headers).status_code == 422
    deleted = _project(session)
    deleted.is_deleted = True
    session.commit()
    assert client.get(_url(deleted.id), headers=client.auth_headers).status_code == 404
    assert client.get(_url(IDS["project"])).status_code == 401


# ----------------------------------------------------------------- reconciliation & safety


def test_metrics_reconcile_with_engineering_performance_report(client, session):
    project = _project(
        session, quoted="100", status=ExecutionStatus.completed,
        completed_at=datetime(2025, 5, 10, 12), code="EMX-REC",
    )
    for week in range(10):
        _book(session, project.id, "8", week_offset=week)
    session.commit()
    report = client.get(
        "/api/v1/reports/engineering-performance",
        params={"period_type": "monthly", "anchor": "2025-05-15"},
        headers=client.auth_headers,
    ).json()
    row = next(r for r in report["projects"] if r["code"] == "EMX-REC")
    metrics = _get(client, project.id)
    assert Decimal(str(row["current_planned_hours"])) == _d(metrics["estimate"]["current_estimate_hours"])
    assert Decimal(str(row["original_planned_hours"])) == _d(metrics["estimate"]["original_estimate_hours"])
    assert Decimal(str(row["actual_hours"])) == _d(metrics["actual"]["total_hours"])
    assert Decimal(str(row["variance_hours"])) == _d(metrics["variance_hours"]["value"])
    assert row["plan_source"] == metrics["estimate"]["estimate_source"]


def test_reading_metrics_does_not_modify_source_records(client, session):
    created = _create_redoe_project(client, session)
    project_id = uuid.UUID(created["id"])
    _book(session, project_id, "9.5", milestone_id=_stage_milestone(session, project_id, ProjectStage.final).id)
    session.commit()

    def snapshot():
        session.expire_all()
        project = session.get(Project, project_id)
        entries = session.execute(
            select(func.count(TimesheetEntry.id), func.sum(TimesheetEntry.hours))
            .where(TimesheetEntry.project_id == project_id)
        ).one()
        estimates = sorted(
            (row.stage.value, row.original_hours, row.current_hours)
            for row in session.scalars(
                select(ProjectStageEstimate).where(ProjectStageEstimate.project_id == project_id)
            )
        )
        return (
            project.quoted_hours, project.actual_hours, project.updated_at,
            project.health, tuple(entries), estimates,
        )

    before = snapshot()
    _get(client, project_id)
    _get(client, project_id)
    assert snapshot() == before
