"""Phase 1, Step 3: Quote-to-Delivery management report (summary, project table,
stage-wise section, historical and operational delivery, filters, permissions, export)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook
from sqlalchemy import event, select

from app.models.enums import (
    ExecutionStatus,
    MilestoneStatus,
    ProjectClassification,
    ProjectStage,
)
from app.models.models import Project, ProjectBaselineRevision, User
from app.services.engineering_metrics_service import build_engineering_metrics_batch
from tests.conftest import IDS, login
from tests.test_engineering_metrics import _book, _d, _project
from tests.test_stage_delivery_metrics import _completed, _estimate, _milestone, _staged

URL = "/api/v1/reports/quote-to-delivery"
MAY = {"period_type": "custom", "start_date": "2025-05-01", "end_date": "2025-05-31"}
PRE, MID = ProjectStage.preliminary, ProjectStage.intermediate
ISOLATE = IDS["user_junior_designer"]


def _qtd(client, headers=None, expect: int = 200, **params):
    query = {**MAY, "page_size": 100, **params}
    response = client.get(URL, params=query, headers=headers or client.auth_headers)
    assert response.status_code == expect, response.text
    return response.json()


def _codes(body) -> list[str]:
    return sorted(row["code"] for row in body["projects"]["items"])


def _by_code(body) -> dict[str, dict]:
    return {row["code"]: row for row in body["projects"]["items"]}


def _revision(session, project, number: int, previous: date | None, new: date) -> None:
    session.add(
        ProjectBaselineRevision(
            project_id=project.id, revision_number=number, previous_completion_date=previous,
            new_completion_date=new, reason="test", revised_at=datetime(2025, 4, 1),
        )
    )


def _seed_hours(session):
    p1 = _completed(session, "QA-1", completed=datetime(2025, 5, 5, 10))
    p1.quoted_hours = Decimal("120")
    _staged(session, p1, {PRE: "100"}, {PRE: "50"})  # 50 % used
    p2 = _completed(session, "QA-2", completed=datetime(2025, 5, 6, 10))
    p2.quoted_hours = Decimal("15")
    _staged(session, p2, {PRE: "10"}, {PRE: "20"})  # 200 % used
    p3 = _completed(session, "QA-3", completed=datetime(2025, 5, 7, 10))
    p3.quoted_hours = Decimal("50")
    _book(session, p3.id, "30")  # quoted hours only: no approved estimate
    p4 = _completed(session, "QA-4", completed=datetime(2025, 5, 8, 10))
    _staged(session, p4, {PRE: "40"}, {})  # completed, no hours: actual missing
    session.commit()
    return p1, p2, p3, p4


# ----------------------------------------------------------------- A: KPI calculations


def test_summary_sums_hours_and_never_averages_percentages(client, session):
    _seed_hours(session)
    body = _qtd(client)
    s = body["summary"]
    assert s["eligible_projects"] == 4
    assert _d(s["quoted_hours_total"]) == Decimal("185")  # 120 + 15 + 50, kept separate
    assert s["projects_with_quoted_hours"] == 3
    assert _d(s["current_estimate_total"]) == Decimal("150")  # 100 + 10 + 40; quoted-only excluded
    assert s["projects_with_current_estimate"] == 3
    assert s["estimate_source_counts"] == {"stage_estimates": 3, "quoted_hours": 1}
    assert _d(s["actual_hours_total"]) == Decimal("100")  # 50 + 20 + 30; missing is not zero
    assert s["projects_with_actual_hours"] == 3
    assert s["projects_actual_missing"] == 1
    assert s["comparable_projects"] == 2
    assert _d(s["comparable_estimate_hours"]) == Decimal("110")
    assert _d(s["comparable_actual_hours"]) == Decimal("70")
    assert _d(s["variance_hours"]) == Decimal("-40")
    assert _d(s["utilization_percent"]) == Decimal("63.64")  # 70 / 110, not (50 % + 200 %) / 2
    assert (s["projects_over_estimate"], s["projects_under_estimate"], s["projects_on_estimate"]) == (1, 1, 0)
    assert s["projects_not_comparable"] == 2
    assert s["projects_metrics_unavailable"] == 1
    codes = {w["code"] for w in body["warnings"]}
    assert {"actual_hours_missing", "estimate_from_quoted_hours"} <= codes
    assert {d["key"] for d in body["definitions"]} >= {
        "quoted_hours_total", "current_estimate_total", "utilization_percent", "metrics_incomplete",
    }


def test_rows_reconcile_with_project_metrics_endpoint(client, session):
    _seed_hours(session)
    rows = _by_code(_qtd(client))
    for code, row in rows.items():
        page = client.get(
            f"/api/v1/projects/{row['project_id']}/engineering-metrics", headers=client.auth_headers
        ).json()
        assert _d(row["current_estimate_hours"]) == _d(page["estimate"]["current_estimate_hours"]), code
        assert _d(row["quoted_hours"]) == _d(page["estimate"]["quoted_hours"]), code
        assert _d(row["actual_hours"]) == _d(page["actual"]["total_hours"]), code
        assert _d(row["variance_hours"]) == _d(page["variance_hours"]["value"]), code
        assert _d(row["utilization_percent"]) == _d(page["utilization_percent"]["value"]), code
        assert row["data_quality_status"] == page["data_quality_status"], code
        assert row["delivery_status"] == page["delivery"]["project"]["status"], code
    assert rows["QA-4"]["actual_hours"] is None and rows["QA-4"]["actual_status"] == "missing"
    assert rows["QA-3"]["comparable"] is False and rows["QA-3"]["estimate_source"] == "quoted_hours"


def test_summary_drilldowns_match_counts(client, session):
    _seed_hours(session)
    assert _codes(_qtd(client, segment="over_estimate")) == ["QA-2"]
    assert _codes(_qtd(client, segment="under_estimate")) == ["QA-1"]
    assert _codes(_qtd(client, segment="not_comparable")) == ["QA-3", "QA-4"]
    incomplete = _qtd(client, segment="metrics_incomplete")
    assert "QA-4" in _codes(incomplete)
    # Aggregates always describe the whole population, not the drill-down.
    assert incomplete["summary"]["eligible_projects"] == 4


# ----------------------------------------------------------------- B: filters


def test_period_selects_by_actual_completion_date_inclusive(client, session):
    inside_start = _completed(session, "QB-START", completed=datetime(2025, 5, 1, 0, 0, 0))
    inside_end = _completed(session, "QB-END", completed=datetime(2025, 5, 31, 23, 59, 59))
    _completed(session, "QB-BEFORE", completed=datetime(2025, 4, 30, 23, 59, 59))
    after = _completed(session, "QB-AFTER", completed=datetime(2025, 6, 1, 0, 0, 0))
    after.due_date = date(2025, 5, 15)  # target in May does not pull it into May
    session.commit()
    body = _qtd(client)
    assert _codes(body) == ["QB-END", "QB-START"]
    assert "actual completion date" in body["period"]["applies_to"]
    rows = _by_code(body)
    assert rows["QB-END"]["actual_completion_date"] == "2025-05-31"
    assert rows["QB-START"]["actual_completion_date"] == "2025-05-01"
    assert inside_start.id and inside_end.id


def test_active_population_uses_status_and_targets_not_period(client, session):
    today = date.today()
    late = _project(session, quoted="10", code="QB-LATE")
    late.due_date = today - timedelta(days=3)
    hold = _project(session, quoted="10", code="QB-HOLD", status=ExecutionStatus.on_hold)
    hold.due_date = today + timedelta(days=10)
    done = _completed(session, "QB-DONE", completed=datetime(2025, 5, 3, 9))
    for row in (late, hold, done):
        row.designer_id = ISOLATE
    session.commit()

    may = _qtd(client, population="active", designer_id=str(ISOLATE))
    other = _qtd(client, population="active", designer_id=str(ISOLATE),
                 start_date="2019-01-01", end_date="2019-01-31")
    assert _codes(may) == _codes(other) == ["QB-HOLD", "QB-LATE"]  # period ignored
    assert may["population"]["key"] == "active"
    assert "current target" in may["population"]["date_basis"]
    assert _by_code(may)["QB-LATE"]["delivery_status"] == "overdue"
    assert _by_code(may)["QB-LATE"]["delivery_variance_days"] is None  # not a historical result
    on_hold = _qtd(client, population="active", designer_id=str(ISOLATE), status="on_hold")
    assert _codes(on_hold) == ["QB-HOLD"]
    _qtd(client, population="active", status="completed", expect=422)
    _qtd(client, population="completed", status="on_hold", expect=422)


def test_filters_intersect_and_empty_result_is_not_an_error(client, session):
    a = _completed(session, "QB-A", completed=datetime(2025, 5, 4, 9))
    a.project_classification = ProjectClassification.small_task
    b = _completed(session, "QB-B", completed=datetime(2025, 5, 4, 9))
    b.project_classification = ProjectClassification.small_task
    b.designer_id = ISOLATE
    c = _completed(session, "QB-C", completed=datetime(2025, 5, 4, 9))
    c.project_classification = ProjectClassification.full_design
    c.designer_id = ISOLATE
    session.commit()
    assert _codes(_qtd(client, project_classification="small_task")) == ["QB-A", "QB-B"]
    both = _qtd(client, project_classification="small_task", designer_id=str(ISOLATE))
    assert _codes(both) == ["QB-B"]
    assert both["filters"]["classification"] == "Small task"
    assert _codes(_qtd(client, search="qb-c")) == ["QB-C"]
    empty = _qtd(client, project_classification="unclassified", designer_id=str(ISOLATE))
    assert empty["projects"]["items"] == [] and empty["projects"]["total"] == 0
    assert empty["summary"]["eligible_projects"] == 0
    assert empty["summary"]["variance_hours"] is None
    assert empty["empty_message"] == "No projects were completed during the selected period."


def test_invalid_parameters_are_rejected(client):
    _qtd(client, population="forecast", expect=422)
    _qtd(client, segment="at_risk", expect=422)
    _qtd(client, segment="stage_over", expect=422)  # needs a stage
    _qtd(client, segment="overdue_milestones", expect=422)  # operational segment on history
    _qtd(client, sort="profit", expect=422)
    _qtd(client, page_size=500, expect=422)
    _qtd(client, period_type="custom", start_date="2025-06-01", end_date="2025-05-01", expect=422)


# ----------------------------------------------------------------- C: stage report


def test_stage_section_counts_only_eligible_projects(client, session):
    p1 = _completed(session, "QC-1", completed=datetime(2025, 5, 5, 10))
    _staged(session, p1, {PRE: "40", MID: "30"}, {PRE: "30", MID: "36"})
    p2 = _completed(session, "QC-2", completed=datetime(2025, 5, 6, 10))
    _staged(session, p2, {PRE: "40", MID: "30"}, {PRE: "50", MID: "30"})
    p3 = _completed(session, "QC-3", completed=datetime(2025, 5, 7, 10))
    _staged(session, p3, {PRE: "40"}, {PRE: "20"}, unattributed="10")  # partial attribution
    p4 = _completed(session, "QC-4", completed=datetime(2025, 5, 8, 10))
    p4.quoted_hours = Decimal("100")
    feas = _milestone(session, p4.id, "Feasibility", ProjectStage.feasibility, 1)
    _book(session, p4.id, "6", milestone_id=feas.id)
    session.commit()

    body = _qtd(client)
    rows = {row["key"]: row for row in body["stages"]["rows"]}
    assert list(rows) == ["feasibility", "preliminary", "intermediate"]
    pre = rows["preliminary"]
    assert (pre["projects_in_plan"], pre["eligible_projects"]) == (3, 2)
    assert _d(pre["estimate_hours"]) == Decimal("80") and _d(pre["actual_hours"]) == Decimal("80")
    assert _d(pre["variance_hours"]) == Decimal("0") and _d(pre["utilization_percent"]) == Decimal("100")
    assert pre["projects_over_estimate"] == 1 and pre["projects_missing_attribution"] == 1
    assert "not fully attributed" in pre["explanation"]
    mid = rows["intermediate"]
    assert _d(mid["estimate_hours"]) == Decimal("60") and _d(mid["actual_hours"]) == Decimal("66")
    assert _d(mid["utilization_percent"]) == Decimal("110")
    feasibility = rows["feasibility"]
    assert feasibility["eligible_projects"] == 0 and feasibility["estimate_hours"] is None
    assert feasibility["projects_without_estimate"] == 1  # quoted 100 h never split into stages
    assert "approved estimate" in feasibility["explanation"]
    assert "never inferred" in body["stages"]["eligibility_rule"]

    assert _codes(_qtd(client, segment="stage_over", stage="preliminary")) == ["QC-2"]
    assert _codes(_qtd(client, segment="stage_missing_attribution", stage="preliminary")) == ["QC-3"]
    assert _codes(_qtd(client, segment="stage_eligible", stage="intermediate")) == ["QC-1", "QC-2"]
    assert _codes(_qtd(client, segment="stage_no_estimate", stage="feasibility")) == ["QC-4"]


# ----------------------------------------------------------------- D: delivery


def test_historical_delivery_counts_only_original_baselines(client, session):
    early = _completed(session, "QD-EARLY", completed=datetime(2025, 5, 8, 10))
    early.baseline_completion_date = date(2025, 5, 10)
    _revision(session, early, 1, None, date(2025, 5, 10))
    late = _completed(session, "QD-LATE", completed=datetime(2025, 5, 12, 10))
    late.baseline_completion_date = date(2025, 5, 20)  # revised later; original was 10 May
    _revision(session, late, 1, None, date(2025, 5, 10))
    _revision(session, late, 2, date(2025, 5, 10), date(2025, 5, 20))
    edge = _completed(session, "QD-EDGE", completed=datetime(2025, 5, 10, 23, 59, 59))
    edge.baseline_completion_date = date(2025, 5, 10)
    _revision(session, edge, 1, None, date(2025, 5, 10))
    unverified = _completed(session, "QD-UNVER", completed=datetime(2025, 5, 9, 10))
    unverified.baseline_completion_date = date(2025, 5, 1)
    due_only = _completed(session, "QD-DUE", completed=datetime(2025, 5, 9, 10))
    due_only.due_date = date(2025, 5, 1)
    _completed(session, "QD-NONE", completed=datetime(2025, 5, 9, 10))
    undated = _completed(session, "QD-UNDATED", completed=None)
    undated.completed_at = None
    session.commit()

    body = _qtd(client)
    h = body["delivery"]["historical"]
    assert h["completed_projects"] == 6
    assert h["eligible_projects"] == 3
    assert (h["on_or_before_baseline"], h["after_baseline"]) == (2, 1)
    assert h["average_variance_days"] == 0.0  # (-2 + 2 + 0) / 3
    assert h["median_variance_days"] == 0.0
    assert (h["excluded_baseline_unverified"], h["excluded_due_date_only"], h["excluded_no_reference"]) == (1, 1, 1)
    assert h["completed_without_completion_date"] == 1
    assert "QD-UNDATED" in {c for w in body["warnings"] for c in w["project_codes"]}
    rows = _by_code(body)
    assert rows["QD-LATE"]["delivery_variance_days"] == 2  # vs original, not the revised 20 May
    assert rows["QD-EARLY"]["delivery_variance_days"] == -2
    assert rows["QD-EDGE"]["delivery_variance_days"] == 0  # 23:59:59 is still the 10th
    assert rows["QD-UNVER"]["delivery_variance_days"] is None
    assert rows["QD-DUE"]["delivery_variance_days"] is None
    assert _codes(_qtd(client, segment="delivered_after")) == ["QD-LATE"]
    assert _codes(_qtd(client, segment="delivery_not_evaluable")) == ["QD-DUE", "QD-NONE", "QD-UNVER"]


def test_operational_overdue_work_is_separate_from_history(client, session):
    today = date.today()
    open_late = _project(session, quoted="10", code="QD-OPEN-LATE")
    open_late.due_date = today - timedelta(days=1)
    _milestone(session, open_late.id, "Overdue step", PRE, 1, due_date=today - timedelta(days=2))
    _milestone(session, open_late.id, "Done step", PRE, 2, due_date=today - timedelta(days=5),
               status=MilestoneStatus.completed, completed_date=today - timedelta(days=6))
    open_ok = _project(session, quoted="10", code="QD-OPEN-OK")
    _milestone(session, open_ok.id, "Future step", PRE, 1, due_date=today + timedelta(days=5))
    no_target = _project(session, quoted="10", code="QD-NO-TARGET")
    no_target.due_date = None
    done = _completed(session, "QD-DONE", completed=datetime(2025, 5, 2, 9))
    _milestone(session, done.id, "Old open step", PRE, 1, due_date=date(2025, 4, 1))
    for row in (open_late, open_ok, no_target, done):
        row.designer_id = ISOLATE
    session.commit()

    body = _qtd(client, designer_id=str(ISOLATE))
    o = body["delivery"]["operational"]
    assert o["as_of"] == today.isoformat()
    assert o["active_projects"] == 3
    assert o["projects_with_overdue_milestones"] == 1 and o["overdue_milestones"] == 1
    assert o["projects_past_current_target"] == 1
    assert o["projects_without_current_target"] == 1
    assert body["delivery"]["historical"]["completed_projects"] == 1  # completed work never overdue
    active = _qtd(client, population="active", designer_id=str(ISOLATE), segment="overdue_milestones")
    assert _codes(active) == ["QD-OPEN-LATE"]
    assert _codes(_qtd(client, population="active", designer_id=str(ISOLATE), segment="no_target")) == [
        "QD-NO-TARGET"
    ]


# ----------------------------------------------------------------- E: permissions


def _scoped_designer(session, *, export: bool) -> None:
    designer = session.get(User, IDS["user_binil"])
    designer.module_access = '["dashboard", "projects", "timesheets", "reports"]'
    designer.special_permissions = '["export_reports"]' if export else "[]"
    session.commit()


def _seed_scope(session):
    mine = _completed(session, "QE-MINE", completed=datetime(2025, 5, 5, 9))
    mine.designer_id = IDS["user_binil"]
    hidden = _completed(session, "QE-HIDDEN", completed=datetime(2025, 5, 5, 9))
    hidden.designer_id = IDS["user_ranjith"]
    hidden.design_leader_id = IDS["user_pm"]
    session.commit()
    return mine, hidden


def test_filters_cannot_widen_project_scope(client, session):
    mine, hidden = _seed_scope(session)
    _scoped_designer(session, export=False)
    headers = login(client, "binil@prosohm.com")
    body = _qtd(client, headers=headers)
    codes = _codes(body)
    assert "QE-MINE" in codes and "QE-HIDDEN" not in codes
    for params in (
        {"designer_id": str(IDS["user_ranjith"])},
        {"design_leader_id": str(IDS["user_pm"])},
        {"customer_id": str(IDS["customer"])},
        {"search": "QE-HIDDEN"},
    ):
        assert "QE-HIDDEN" not in _codes(_qtd(client, headers=headers, **params)), params
    links = {row["project_id"] for row in body["projects"]["items"]}
    assert str(hidden.id) not in links
    blocked = client.get(f"/api/v1/projects/{hidden.id}/engineering-metrics", headers=headers)
    assert blocked.status_code in {403, 404}


def test_reports_module_and_export_permission_are_enforced(client, session):
    _seed_scope(session)
    designer = session.get(User, IDS["user_binil"])
    designer.module_access = '["dashboard", "projects", "timesheets"]'
    designer.special_permissions = "[]"
    session.commit()
    headers = login(client, "binil@prosohm.com")
    denied = client.get(URL, params=MAY, headers=headers)
    assert denied.status_code == 403 and "Reports" in denied.json()["detail"]
    assert client.get(f"{URL}/export.xlsx", params=MAY, headers=headers).status_code == 403

    _scoped_designer(session, export=False)
    assert client.get(f"{URL}/export.xlsx", params=MAY, headers=headers).status_code == 403

    _scoped_designer(session, export=True)
    response = client.get(f"{URL}/export.xlsx", params=MAY, headers=headers)
    assert response.status_code == 200, response.text
    sheet = load_workbook(BytesIO(response.content))["Projects"]
    exported = [sheet.cell(row=r, column=1).value for r in range(2, sheet.max_row + 1)]
    assert "QE-MINE" in exported and "QE-HIDDEN" not in exported


# ----------------------------------------------------------------- F: export, performance, regression


def test_export_contains_every_matching_row_not_just_the_page(client, session):
    for index in range(30):
        project = _completed(session, f"QF-{index:02d}", completed=datetime(2025, 5, 10, 9))
        project.designer_id = ISOLATE
        _estimate(session, project.id, PRE, "10")
        _book(session, project.id, "4")
    session.commit()
    params = {**MAY, "designer_id": str(ISOLATE)}
    page = client.get(URL, params={**params, "page_size": 25}, headers=client.auth_headers).json()
    assert page["projects"]["total"] == 30 and len(page["projects"]["items"]) == 25
    assert page["projects"]["pages"] == 2
    second = client.get(URL, params={**params, "page_size": 25, "page": 2}, headers=client.auth_headers).json()
    assert len(second["projects"]["items"]) == 5

    response = client.get(f"{URL}/export.xlsx", params=params, headers=client.auth_headers)
    assert response.status_code == 200, response.text
    assert "Quote_to_Delivery_20250501-20250531.xlsx" in response.headers["content-disposition"]
    workbook = load_workbook(BytesIO(response.content))
    assert workbook.sheetnames == ["Summary", "Projects", "Stages", "Delivery", "Definitions"]
    projects = workbook["Projects"]
    headers = [projects.cell(row=1, column=c).value for c in range(1, projects.max_column + 1)]
    assert {"Quoted (h)", "Current estimate (h)", "Actual (h)", "Utilization (%)", "Data quality"} <= set(headers)
    codes = [projects.cell(row=r, column=1).value for r in range(2, 32)]
    assert sorted(codes) == [f"QF-{i:02d}" for i in range(30)]
    actual_col = headers.index("Actual (h)") + 1
    assert sum(projects.cell(row=r, column=actual_col).value for r in range(2, 32)) == float(
        page["summary"]["actual_hours_total"]
    )
    summary_text = " ".join(
        str(cell.value) for row in workbook["Summary"].iter_rows() for cell in row if cell.value
    )
    assert "all 30 project row(s)" in summary_text

    drill = client.get(
        f"{URL}/export.xlsx", params={**params, "search": "QF-0"}, headers=client.auth_headers
    )
    drill_sheet = load_workbook(BytesIO(drill.content))["Projects"]
    drilled = [drill_sheet.cell(row=r, column=1).value for r in range(2, drill_sheet.max_row + 1)]
    assert sorted(c for c in drilled if c and c.startswith("QF-")) == [f"QF-0{i}" for i in range(10)]


def test_batch_metrics_use_a_constant_number_of_queries(client, session):
    projects = []
    for index in range(10):
        project = _completed(session, f"QN-{index}", completed=datetime(2025, 5, 10, 9))
        _staged(session, project, {PRE: "10"}, {PRE: "4"})
        projects.append(project)
    session.commit()
    ids = [p.id for p in projects]
    loaded = {p.id: p for p in session.scalars(select(Project).where(Project.id.in_(ids)))}
    projects = [loaded[pid] for pid in ids]  # the report loads projects in one query too
    engine = session.get_bind()
    counts = []
    for subset in (projects[:3], projects):
        statements: list[str] = []

        def _count(conn, cursor, statement, *args):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", _count)
        try:
            batch = build_engineering_metrics_batch(session, subset, finance_details_visible=False)
        finally:
            event.remove(engine, "before_cursor_execute", _count)
        assert len(batch) == len(subset)
        counts.append(len(statements))
    assert counts[0] == counts[1], counts


def test_engineering_performance_report_still_serves(client, session):
    _seed_hours(session)
    response = client.get(
        "/api/v1/reports/engineering-performance", params=MAY, headers=client.auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["summary"]["projects_completed"] == 4
    assert session.scalar(select(Project).where(Project.code == "QA-1")) is not None
