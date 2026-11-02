"""Phase 1, Step 2: stage-wise actual hours, stage estimate variance, delivery variance
and the historical stage comparison in the Engineering Performance report."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook
from sqlalchemy import select

from app.models.enums import (
    ExecutionStatus,
    MilestoneStatus,
    ProjectStage,
    TimesheetStatus,
)
from app.models.models import (
    Milestone,
    Project,
    ProjectBaselineRevision,
    ProjectStageEstimate,
    TaskType,
    TimesheetEntry,
)
from app.services.delivery_variance_service import baseline_histories, project_delivery
from app.services.engineering_metrics_service import build_project_engineering_metrics
from tests.conftest import IDS
from tests.test_engineering_management import _create_redoe_project, _next_monday
from tests.test_engineering_metrics import _book, _d, _get, _project, _stage_milestone


def _milestone(session, project_id, name: str, stage: ProjectStage | None, sort: int, **extra) -> Milestone:
    row = Milestone(
        id=uuid.uuid4(),
        project_id=project_id,
        name=name,
        project_stage=stage,
        sort_order=sort,
        status=extra.pop("status", MilestoneStatus.not_started),
        **extra,
    )
    session.add(row)
    session.flush()
    return row


def _estimate(session, project_id, stage: ProjectStage, hours: str) -> None:
    session.add(
        ProjectStageEstimate(
            project_id=project_id, stage=stage,
            original_hours=Decimal(hours), current_hours=Decimal(hours),
        )
    )
    session.flush()


def _rows(body) -> dict[str, dict]:
    return {row["key"]: row for row in body["stage_attribution"]["rows"]}


# ----------------------------------------------------------------- A: stage actual hours


def test_stage_rows_and_unattributed_hours_reconcile_to_total(client, session):
    created = _create_redoe_project(client, session)
    project_id = uuid.UUID(created["id"])
    blockout = _stage_milestone(session, project_id, ProjectStage.preliminary)
    roughing = session.scalar(
        select(Milestone).where(Milestone.project_id == project_id, Milestone.name == "Roughing")
    )
    intermediate = _stage_milestone(session, project_id, ProjectStage.intermediate)
    adhoc = _milestone(session, project_id, "Ad hoc support", None, 99)
    _book(session, project_id, "16", milestone_id=blockout.id)
    _book(session, project_id, "8", week_offset=1, milestone_id=roughing.id)  # same stage, 2nd milestone
    _book(session, project_id, "12", week_offset=2, status=TimesheetStatus.rejected,
          milestone_id=intermediate.id)
    _book(session, project_id, "5", week_offset=3, milestone_id=adhoc.id)
    _book(session, project_id, "3", week_offset=4)
    _book(session, project_id, "9", week_offset=5, milestone_id=blockout.id, deleted=True)
    session.commit()

    body = _get(client, project_id)
    total = _d(body["actual"]["total_hours"])
    assert total == Decimal("32")  # approved only: deleted 9 h and rejected 12 h excluded
    stage = body["stage_attribution"]
    rows = _rows(body)
    assert list(rows) == ["preliminary", "intermediate", "final"]  # no Feasibility: not in plan
    assert _d(rows["preliminary"]["actual_hours"]) == Decimal("24")  # two milestones, no double count
    assert _d(rows["intermediate"]["actual_hours"]) == Decimal("0")
    assert _d(rows["final"]["actual_hours"]) == Decimal("0")
    assert _d(rows["preliminary"]["percent_of_project_actual"]) == Decimal("75.00")
    assert stage["status"] == "partial"
    assert _d(stage["no_stage_hours"]) == Decimal("5")
    assert _d(stage["no_milestone_hours"]) == Decimal("3")
    assert _d(stage["unattributed_hours"]) == Decimal("8")
    assert _d(stage["total_hours"]) == total
    assert sum(_d(r["actual_hours"]) for r in rows.values()) + _d(stage["unattributed_hours"]) == total
    assert all(r["data_quality"] == "limited" for r in rows.values())
    assert "may be understated" in rows["preliminary"]["data_quality_notes"][0]
    assert stage["source"].startswith("Timesheet entry")


def test_stage_without_estimate_and_configurable_stage_set(client, session):
    project = _project(session, quoted="100")
    feasibility = _milestone(session, project.id, "Feasibility", ProjectStage.feasibility, 1)
    blockout = _milestone(session, project.id, "Blockout", ProjectStage.preliminary, 2)
    _book(session, project.id, "6", milestone_id=feasibility.id)
    _book(session, project.id, "10", week_offset=1, milestone_id=blockout.id)
    session.commit()

    body = _get(client, project.id)
    rows = _rows(body)
    assert list(rows) == ["feasibility", "preliminary"]  # only the stages this project has
    assert body["stage_attribution"]["status"] == "complete"
    assert _d(body["stage_attribution"]["coverage_percent"]) == Decimal("100")
    assert _d(body["stage_attribution"]["other_stage_hours"]) == Decimal("6")
    feas = rows["feasibility"]
    assert _d(feas["actual_hours"]) == Decimal("6")
    assert feas["has_approved_estimate"] is False
    assert feas["current_estimate_hours"] is None
    for key in ("variance", "utilization_percent", "remaining_hours"):
        assert feas[key]["status"] == "unavailable" and feas[key]["value"] is None
    assert "Blockout, Intermediate Design and Final Design only" in feas["variance"]["reason"]
    # The project's quoted 100 h is never split into stage estimates.
    assert rows["preliminary"]["current_estimate_hours"] is None
    assert rows["preliminary"]["variance"]["status"] == "unavailable"
    assert body["estimate"]["estimate_source"] == "quoted_hours"


def test_template_without_stages_has_no_stage_rows(client, session):
    project = _project(session, quoted="20")
    review = _milestone(session, project.id, "Concept Review", None, 1)
    _book(session, project.id, "7", milestone_id=review.id)
    session.commit()
    body = _get(client, project.id)
    assert body["stage_attribution"]["status"] == "unavailable"
    assert body["stage_attribution"]["rows"] == []
    issue = {i["code"]: i for i in body["issues"]}["stage_attribution_unavailable"]
    assert "carry no engineering stage" in issue["message"]
    assert _d(body["actual"]["total_hours"]) == Decimal("7")


def test_missing_actual_hours_are_not_zero_in_stage_rows(client, session):
    project = _project(session, quoted="40", status=ExecutionStatus.completed,
                       completed_at=datetime(2025, 3, 1, 9))
    _milestone(session, project.id, "Blockout", ProjectStage.preliminary, 1)
    _estimate(session, project.id, ProjectStage.preliminary, "40")
    session.commit()
    rows = _rows(_get(client, project.id))
    assert rows["preliminary"]["actual_hours"] is None
    assert rows["preliminary"]["data_quality"] == "unavailable"
    assert rows["preliminary"]["variance"]["status"] == "unavailable"


# ----------------------------------------------------------------- B: stage estimate variance


def test_stage_under_and_over_estimate(client, session):
    under = _create_redoe_project(client, session)  # Blockout estimate 40 h
    over = _create_redoe_project(client, session)
    _book(session, uuid.UUID(under["id"]), "30",
          milestone_id=_stage_milestone(session, uuid.UUID(under["id"]), ProjectStage.preliminary).id)
    over_blockout = _stage_milestone(session, uuid.UUID(over["id"]), ProjectStage.preliminary)
    _book(session, uuid.UUID(over["id"]), "40", milestone_id=over_blockout.id)
    _book(session, uuid.UUID(over["id"]), "10", week_offset=1, milestone_id=over_blockout.id)
    session.commit()

    row = _rows(_get(client, under["id"]))["preliminary"]
    assert _d(row["current_estimate_hours"]) == Decimal("40")
    assert _d(row["variance"]["value"]) == Decimal("-10")
    assert _d(row["variance_hours"]) == Decimal("-10")
    assert _d(row["utilization_percent"]["value"]) == Decimal("75")
    assert _d(row["remaining_hours"]["value"]) == Decimal("10")
    assert row["data_quality"] == "complete"

    row = _rows(_get(client, over["id"]))["preliminary"]
    assert _d(row["variance"]["value"]) == Decimal("10")
    assert _d(row["utilization_percent"]["value"]) == Decimal("125")
    assert _d(row["remaining_hours"]["value"]) == Decimal("-10")


def test_zero_stage_estimate_has_no_utilization(client, session):
    project = _project(session, quoted="0")
    blockout = _milestone(session, project.id, "Blockout", ProjectStage.preliminary, 1)
    _estimate(session, project.id, ProjectStage.preliminary, "0")
    _book(session, project.id, "3", milestone_id=blockout.id)
    session.commit()
    row = _rows(_get(client, project.id))["preliminary"]
    assert _d(row["variance"]["value"]) == Decimal("3")
    assert row["utilization_percent"]["status"] == "not_applicable"
    assert row["utilization_percent"]["value"] is None
    assert row["data_quality"] == "limited"


def test_stage_estimate_revision_keeps_original(client, session):
    created = _create_redoe_project(client, session)
    response = client.post(
        f"/api/v1/projects/{created['id']}/stage-estimates/revisions",
        json={"stage": "preliminary", "new_hours": "60", "reason": "Customer added ribs"},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    row = _rows(_get(client, created["id"]))["preliminary"]
    assert _d(row["original_estimate_hours"]) == Decimal("40")
    assert _d(row["current_estimate_hours"]) == Decimal("60")


# ----------------------------------------------------------------- C: delivery variance


def test_revised_baseline_never_replaces_the_original(client, session):
    created = _create_redoe_project(client, session)
    project_id = uuid.UUID(created["id"])
    original_completion = date.fromisoformat(created["baseline_completion_date"])
    milestones = session.scalars(
        select(Milestone).where(Milestone.project_id == project_id).order_by(Milestone.sort_order)
    ).all()
    original_finish = {m.id: m.baseline_finish_date for m in milestones}
    assert all(original_finish.values())

    response = client.post(
        f"/api/v1/projects/{project_id}/baseline-revisions",
        json={"reason": "Customer delayed data",
              "new_start_date": (_next_monday() + timedelta(days=14)).isoformat()},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text

    body = _get(client, project_id)
    delivery = body["delivery"]["project"]
    assert delivery["reference_source"] == "original_baseline"
    assert delivery["original_baseline_completion_date"] == original_completion.isoformat()
    current = date.fromisoformat(delivery["current_baseline_completion_date"])
    assert current > original_completion
    assert delivery["baseline_revision_count"] == 2
    # Step 1's readiness block now reports the true original as well.
    assert body["milestones"]["original_baseline_completion_date"] == original_completion.isoformat()
    for row in body["delivery"]["milestones"]:
        milestone_id = uuid.UUID(row["milestone_id"])
        assert row["original_baseline_finish_date"] == original_finish[milestone_id].isoformat()
        assert date.fromisoformat(row["current_baseline_finish_date"]) > original_finish[milestone_id]
        assert row["reference_source"] == "original_baseline"


def test_completed_milestones_classified_against_original_baseline(client, session):
    created = _create_redoe_project(client, session)
    project_id = uuid.UUID(created["id"])
    client.post(
        f"/api/v1/projects/{project_id}/baseline-revisions",
        json={"reason": "Customer delayed data",
              "new_start_date": (_next_monday() + timedelta(days=21)).isoformat()},
        headers=client.auth_headers,
    )
    session.expire_all()
    first, second, third = session.scalars(
        select(Milestone).where(Milestone.project_id == project_id).order_by(Milestone.sort_order)
    ).all()[:3]
    body = _get(client, project_id)
    original = {
        uuid.UUID(r["milestone_id"]): date.fromisoformat(r["original_baseline_finish_date"])
        for r in body["delivery"]["milestones"]
    }
    for milestone, offset in ((first, -2), (second, 0), (third, 3)):
        milestone.status = MilestoneStatus.completed
        milestone.completed_date = original[milestone.id] + timedelta(days=offset)
    session.commit()

    rows = {uuid.UUID(r["milestone_id"]): r for r in _get(client, project_id)["delivery"]["milestones"]}
    assert (rows[first.id]["status"], rows[first.id]["schedule_variance_days"]) == ("early", -2)
    assert (rows[second.id]["status"], rows[second.id]["schedule_variance_days"]) == ("on_time", 0)
    # Late against the original baseline even though the revised target is 21 days later.
    assert (rows[third.id]["status"], rows[third.id]["schedule_variance_days"]) == ("late", 3)
    assert date.fromisoformat(rows[third.id]["current_target_date"]) > date.fromisoformat(
        rows[third.id]["actual_completion_date"]
    )
    assert rows[third.id]["days_overdue"] is None


def test_overdue_only_after_current_target_date(session):
    project = _project(session, quoted="10")
    due = date(2025, 6, 10)
    project.due_date = due
    milestone = _milestone(session, project.id, "Blockout", ProjectStage.preliminary, 1, due_date=due)
    session.commit()

    on_day = build_project_engineering_metrics(session, project, finance_details_visible=False, today=due)
    assert on_day.delivery.project.status == "not_due"
    assert on_day.delivery.milestones[0].status == "not_due"
    assert on_day.milestones.open_overdue == 0

    next_day = build_project_engineering_metrics(
        session, project, finance_details_visible=False, today=due + timedelta(days=1)
    )
    assert next_day.delivery.project.status == "overdue"
    assert next_day.delivery.project.days_overdue == 1
    assert next_day.delivery.project.schedule_variance_days is None
    row = next_day.delivery.milestones[0]
    assert (row.status, row.days_overdue, row.milestone_id) == ("overdue", 1, milestone.id)
    assert next_day.milestones.open_overdue == 1


def test_completed_project_is_never_overdue(session):
    project = _project(session, quoted="10", status=ExecutionStatus.completed,
                       completed_at=datetime(2025, 6, 13, 16))
    project.due_date = date(2025, 6, 10)
    session.commit()
    result = build_project_engineering_metrics(
        session, project, finance_details_visible=False, today=date(2026, 1, 1)
    )
    delivery = result.delivery.project
    assert delivery.status == "late"
    assert delivery.days_overdue is None
    assert delivery.schedule_variance_days == 3
    assert delivery.reference_source == "current_due_date"
    assert "original commitment unknown" in delivery.reference_label

    project.completed_at = datetime(2025, 6, 8, 9)
    session.commit()
    early = build_project_engineering_metrics(
        session, project, finance_details_visible=False, today=date(2026, 1, 1)
    ).delivery.project
    assert (early.status, early.schedule_variance_days) == ("early", -2)


def test_missing_delivery_data_is_reported(client, session):
    project = _project(session, quoted="10")
    project.due_date = None
    _milestone(session, project.id, "Blockout", ProjectStage.preliminary, 1)
    _milestone(session, project.id, "Final", ProjectStage.final, 2, status=MilestoneStatus.completed,
               due_date=date(2025, 5, 1))
    session.commit()
    body = _get(client, project.id)
    assert body["delivery"]["project"]["status"] == "no_target"
    assert body["delivery"]["project"]["reference_source"] == "none"
    statuses = [row["status"] for row in body["delivery"]["milestones"]]
    assert statuses == ["no_target", "completion_date_missing"]
    codes = {issue["code"] for issue in body["issues"]}
    assert {"original_commitment_unavailable", "milestone_delivery_dates_missing"} <= codes
    assert "Negative is early" in body["delivery"]["sign_convention"]

    unverified = _project(session, quoted="10")
    unverified.baseline_completion_date = date(2025, 7, 1)
    session.commit()
    body = _get(client, unverified.id)
    assert body["delivery"]["project"]["reference_source"] == "baseline_unverified"
    assert "baseline_history_missing" in {issue["code"] for issue in body["issues"]}


def test_completion_dates_follow_stored_calendar_date(session):
    project = _project(session, quoted="10", status=ExecutionStatus.completed,
                       completed_at=datetime(2025, 3, 10, 23, 30))
    project.due_date = date(2025, 3, 10)
    late_evening = _milestone(
        session, project.id, "Blockout", ProjectStage.preliminary, 1,
        status=MilestoneStatus.completed, due_date=date(2025, 3, 10),
        completed_at=datetime(2025, 3, 10, 23, 30, tzinfo=timezone.utc),
    )
    explicit = _milestone(
        session, project.id, "Final", ProjectStage.final, 2,
        status=MilestoneStatus.completed, due_date=date(2025, 3, 10),
        completed_at=datetime(2025, 3, 10, 9, tzinfo=timezone.utc), completed_date=date(2025, 3, 11),
    )
    session.commit()
    result = build_project_engineering_metrics(session, project, finance_details_visible=False)
    assert result.delivery.project.actual_completion_date == date(2025, 3, 10)
    assert result.delivery.project.status == "on_time"
    rows = {row.milestone_id: row for row in result.delivery.milestones}
    assert (rows[late_evening.id].actual_completion_date, rows[late_evening.id].status) == (
        date(2025, 3, 10), "on_time")
    assert (rows[explicit.id].actual_completion_date, rows[explicit.id].status) == (
        date(2025, 3, 11), "late")


def test_baseline_history_predating_revisions_is_unverified(session):
    project = _project(session, quoted="10")
    project.baseline_completion_date = date(2025, 9, 1)
    session.add(ProjectBaselineRevision(
        project_id=project.id, revision_number=1,
        previous_start_date=date(2025, 1, 1), previous_completion_date=date(2025, 8, 1),
        new_start_date=date(2025, 2, 1), new_completion_date=date(2025, 9, 1),
        reason="Imported", revised_at=datetime(2025, 2, 1),
    ))
    session.commit()
    history = baseline_histories(session, [project.id])[project.id]
    delivery = project_delivery(project, history, date(2025, 1, 1))
    assert delivery.reference_source == "baseline_unverified"
    assert delivery.original_baseline_completion_date == date(2025, 8, 1)


# ----------------------------------------------------------------- D: historical comparison


def _completed(session, code: str, *, completed: datetime, status=ExecutionStatus.completed,
               designer=None) -> Project:
    project = _project(session, quoted="0", status=status, completed_at=completed, code=code)
    project.due_date = None
    if designer:
        project.designer_id = designer
    session.flush()
    return project


def _staged(session, project: Project, estimates: dict[ProjectStage, str],
            hours: dict[ProjectStage, str], unattributed: str | None = None) -> None:
    for sort, stage in enumerate(estimates, start=1):
        milestone = _milestone(session, project.id, stage.value, stage, sort)
        _estimate(session, project.id, stage, estimates[stage])
        if stage in hours:
            _book(session, project.id, hours[stage], week_offset=sort, milestone_id=milestone.id)
    if unattributed:
        _book(session, project.id, unattributed, week_offset=9)


def _report(client, **params):
    response = client.get(
        "/api/v1/reports/engineering-performance",
        params={"period_type": "custom", "start_date": "2025-05-01", "end_date": "2025-05-31", **params},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _seed_history(session):
    pre, mid = ProjectStage.preliminary, ProjectStage.intermediate
    p1 = _completed(session, "HS-1", completed=datetime(2025, 5, 5, 10), designer=IDS["user_ranjith"])
    _staged(session, p1, {pre: "40", mid: "30"}, {pre: "30", mid: "36"})
    p1.due_date = date(2025, 5, 7)

    p2 = _completed(session, "HS-2", completed=datetime(2025, 5, 12, 10))
    _staged(session, p2, {pre: "40", mid: "30"}, {pre: "50", mid: "30"})
    p2.baseline_completion_date = date(2025, 5, 20)  # current (revised) baseline
    for number, previous, new in ((1, None, date(2025, 5, 10)), (2, date(2025, 5, 10), date(2025, 5, 20))):
        session.add(ProjectBaselineRevision(
            project_id=p2.id, revision_number=number, previous_completion_date=previous,
            new_completion_date=new, reason="test", revised_at=datetime(2025, 4, 1),
        ))

    p3 = _completed(session, "HS-3", completed=datetime(2025, 5, 15, 10))
    _staged(session, p3, {pre: "40"}, {pre: "20"}, unattributed="10")  # partial: excluded

    p4 = _completed(session, "HS-4", completed=datetime(2025, 5, 18, 10))
    _staged(session, p4, {pre: "40"}, {})  # no hours recorded: missing, not zero

    p5 = _completed(session, "HS-5", completed=datetime(2025, 5, 19, 10), status=ExecutionStatus.cancelled)
    _staged(session, p5, {pre: "40"}, {pre: "100"})
    p6 = _completed(session, "HS-6", completed=datetime(2025, 6, 2, 10))
    _staged(session, p6, {pre: "40"}, {pre: "100"})

    task_type = session.scalar(select(TaskType).where(TaskType.stream_id == IDS["stream"]))
    entry = session.scalar(select(TimesheetEntry).where(TimesheetEntry.project_id == p1.id))
    entry.task_type_id = task_type.id
    session.commit()
    return p1, p2


def test_historical_stage_comparison_counts_and_rules(client, session):
    _seed_history(session)
    report = _report(client)
    assert report["summary"]["projects_completed"] == 4  # cancelled and June project excluded
    stage = report["stage_performance"]
    assert stage["projects_with_stage_plan"] == 4
    assert stage["complete_attribution_projects"] == 2
    assert stage["partial_attribution_projects"] == 1
    assert stage["unattributed_projects"] == 1
    assert "all timesheet hours attributed" in stage["eligibility_rule"]
    rows = {row["stage"]: row for row in stage["rows"]}
    pre, mid = rows["preliminary"], rows["intermediate"]
    assert pre["eligible_projects"] == 2
    assert (pre["average_variance_hours"], pre["median_variance_hours"]) == (0.0, 0.0)
    assert (pre["projects_over_estimate"], pre["percent_over_estimate"]) == (1, 50.0)
    assert mid["eligible_projects"] == 2
    assert (mid["average_variance_hours"], mid["median_variance_hours"]) == (3.0, 3.0)
    assert mid["projects_over_estimate"] == 1
    assert pre["actual_share_percent"] == 54.79  # 80 of 146 attributed hours
    assert rows["final"]["eligible_projects"] == 0
    assert rows["final"]["average_variance_hours"] is None
    # Existing totals are unchanged: all four staged projects, attributed hours only.
    assert pre["projects"] == 4 and pre["actual_hours"] == 100.0


def test_historical_delivery_variance_uses_original_baseline(client, session):
    _seed_history(session)
    report = _report(client)
    by_code = {row["code"]: row for row in report["projects"]}
    hs2 = by_code["HS-2"]
    assert hs2["delivery_reference_source"] == "original_baseline"
    assert hs2["original_baseline_completion_date"] == "2025-05-10"
    assert hs2["current_baseline_completion_date"] == "2025-05-20"
    assert (hs2["delivery_status"], hs2["delivery_variance_days"]) == ("late", 2)
    assert hs2["on_time"] is True  # existing KPI keeps its current-baseline definition
    hs1 = by_code["HS-1"]
    assert (hs1["delivery_reference_source"], hs1["delivery_variance_days"]) == ("current_due_date", -2)
    assert by_code["HS-3"]["delivery_status"] == "no_target"
    summary = report["summary"]
    assert summary["delivery_evaluable_projects"] == 2
    assert (summary["delivered_early"], summary["delivered_late"]) == (1, 1)
    assert summary["average_delivery_variance_days"] == 0.0
    assert summary["delivery_reference_counts"] == {
        "current_due_date": 1, "original_baseline": 1, "none": 2,
    }


def test_historical_filters_and_totals_reconcile(client, session):
    _seed_history(session)
    report = _report(client)
    actual = report["summary"]["actual_hours"]
    assert sum(row["actual_hours"] for row in report["projects"]) == actual
    effort = report["effort_by_classification"]
    assert round(sum(row["hours"] for row in effort), 2) == actual
    assert {row["key"] for row in effort} >= {"unclassified"}
    assert len(effort) == 2  # one entry carries a task type

    filtered = _report(client, designer_id=str(IDS["user_ranjith"]))
    assert filtered["summary"]["projects_completed"] == 1
    rows = {row["stage"]: row for row in filtered["stage_performance"]["rows"]}
    assert rows["preliminary"]["eligible_projects"] == 1
    assert rows["preliminary"]["average_variance_hours"] == -10.0


def test_export_includes_stage_comparison_and_delivery_columns(client, session):
    _seed_history(session)
    response = client.get(
        "/api/v1/reports/engineering-performance/export.xlsx",
        params={"period_type": "custom", "start_date": "2025-05-01", "end_date": "2025-05-31"},
        headers=client.auth_headers,
    )
    assert response.status_code == 200, response.text
    workbook = load_workbook(BytesIO(response.content))
    stage_headers = [cell.value for cell in workbook["Stage Performance"][3]]
    assert {"Eligible projects", "Median variance h", "% over estimate"} <= set(stage_headers)
    details = workbook["Project Details"]
    headers = [cell.value for cell in details[1]]
    assert headers.index("Actual h") == 22  # existing columns keep their positions
    assert "Delivery variance days" in headers and "Original baseline completion" in headers
