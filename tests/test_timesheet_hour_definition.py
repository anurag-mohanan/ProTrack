"""Official actual hours = approved timesheets only (docs/PROTRACK_TIMESHEET_HOUR_DEFINITION.md).

Submitted hours are provisional, draft and rejected hours are excluded, billable is a subset of
the total, and every consumer (project page, metrics, reports, forecasts, Control Tower, Phase 7)
reads the same figure.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.models.enums import ProjectStage, TimesheetStatus, WorkCategory
from app.models.finance import Quote, QuoteRevision
from app.models.models import Project, TimesheetEntry
from app.models.prediction import OUTCOME_EVALUATED, OUTCOME_PENDING, PREDICTED, Prediction
from app.services.actual_hours import official_entry_clause, provisional_entry_clause
from app.services.control_tower_service import detect_all
from app.services.engineering_metrics_service import build_engineering_metrics_batch
from app.services.forecasting.effort import build_engineering_forecast
from app.services.predictive.evaluation import HOURS_SETTLE_DAYS, evaluate_outcomes
from app.services.predictive.inputs import load_facts
from app.services.project_calculation_service import batch_calculate_hours, calculate_hours, recalculate_project
from app.services.project_contributor_service import get_project_contributors
from tests.conftest import IDS
from tests.test_engineering_metrics import _book, _project, _sheet
from tests.test_stage_delivery_metrics import _estimate

MONDAY = date(2025, 1, 6)
AS_OF = date(2025, 3, 3)


def _entry(session, project_id, hours: str, *, week: int, status=TimesheetStatus.approved, billable=True,
           user_id=None, day: int = 0) -> None:
    sheet = _sheet(session, user_id or IDS["user_binil"], MONDAY + timedelta(weeks=week), status)
    session.add(TimesheetEntry(
        timesheet_id=sheet.id, entry_date=sheet.week_start + timedelta(days=day), hours=Decimal(hours),
        work_category=WorkCategory.productive, is_billable=billable, customer_id=IDS["customer"],
        project_id=project_id,
    ))
    session.flush()


def _official(session, project_id) -> Decimal:
    return Decimal(session.scalar(select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
        TimesheetEntry.project_id == project_id, official_entry_clause())) or 0)


def _provisional(session, project_id) -> Decimal:
    return Decimal(session.scalar(select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
        TimesheetEntry.project_id == project_id, provisional_entry_clause())) or 0)


def _actual(session, project):
    return build_engineering_metrics_batch(session, [project], finance_details_visible=False, today=AS_OF)[project.id].actual


# ----------------------------------------------------------------- one status at a time


def test_approved_hours_are_official(session):
    project = _project(session)
    _book(session, project.id, "16")
    session.commit()
    actual = _actual(session, project)
    assert actual.status == "recorded" and actual.total_hours == Decimal("16.00")
    assert calculate_hours(session, project).actual == Decimal("16.00")


def test_draft_hours_are_not_actual_hours(session):
    project = _project(session)
    _book(session, project.id, "16", status=TimesheetStatus.draft)
    session.commit()
    actual = _actual(session, project)
    assert actual.status == "none_recorded" and actual.total_hours == Decimal("0.00")
    assert actual.draft_hours == Decimal("16.00") and actual.entry_count == 0
    assert calculate_hours(session, project).actual == Decimal("0.00")


def test_rejected_hours_are_not_actual_hours(session):
    project = _project(session)
    _book(session, project.id, "16", status=TimesheetStatus.rejected)
    session.commit()
    actual = _actual(session, project)
    assert actual.total_hours == Decimal("0.00") and actual.rejected_hours == Decimal("16.00")
    assert calculate_hours(session, project).actual == Decimal("0.00")


def test_submitted_hours_are_provisional_not_official(session):
    project = _project(session)
    _book(session, project.id, "16", status=TimesheetStatus.submitted)
    session.commit()
    actual = _actual(session, project)
    assert actual.total_hours == Decimal("0.00") and actual.submitted_hours == Decimal("16.00")
    assert _provisional(session, project.id) == Decimal("16") and _official(session, project.id) == Decimal("0")
    issues = {i.code: i for i in build_engineering_metrics_batch(
        session, [project], finance_details_visible=False, today=AS_OF)[project.id].issues}
    assert "provisional_hours_pending" in issues and "not included" in issues["provisional_hours_pending"].message


def test_mixed_statuses_count_only_approved(session):
    project = _project(session)
    _book(session, project.id, "20")
    _book(session, project.id, "8", week_offset=1, status=TimesheetStatus.submitted)
    _book(session, project.id, "4", week_offset=2, status=TimesheetStatus.draft)
    _book(session, project.id, "2", week_offset=3, status=TimesheetStatus.rejected)
    _book(session, project.id, "6", week_offset=4, deleted=True)
    session.commit()
    actual = _actual(session, project)
    assert actual.total_hours == Decimal("20.00") == actual.approved_hours
    assert (actual.submitted_hours, actual.draft_hours, actual.rejected_hours) == (
        Decimal("8.00"), Decimal("4.00"), Decimal("2.00"))
    assert {i.code for i in build_engineering_metrics_batch(
        session, [project], finance_details_visible=False, today=AS_OF)[project.id].issues} >= {
        "provisional_hours_pending", "unapproved_hours_excluded"}


def test_completed_project_with_only_unapproved_hours_is_missing_not_zero(session):
    from app.models.enums import ExecutionStatus

    project = _project(session, status=ExecutionStatus.completed)
    _book(session, project.id, "12", status=TimesheetStatus.submitted)
    session.commit()
    metrics = build_engineering_metrics_batch(session, [project], finance_details_visible=False, today=AS_OF)[project.id]
    assert metrics.actual.status == "missing" and metrics.actual.total_hours is None
    assert metrics.variance_hours.status == "unavailable"


# ----------------------------------------------------------------- billable and duplicates


def test_billable_is_a_subset_of_total_effort(session):
    project = _project(session)
    _entry(session, project.id, "10", week=0, billable=True)
    _entry(session, project.id, "4", week=0, billable=False, day=1)
    _entry(session, project.id, "5", week=1, billable=True, status=TimesheetStatus.submitted)
    session.commit()
    actual = _actual(session, project)
    assert actual.total_hours == Decimal("14.00")
    assert actual.billable_hours == Decimal("10.00")


def test_approval_moves_hours_from_provisional_to_official_without_double_counting(session):
    project = _project(session)
    _book(session, project.id, "12", status=TimesheetStatus.submitted)
    session.commit()
    assert (_official(session, project.id), _provisional(session, project.id)) == (Decimal("0"), Decimal("12"))
    sheet = _sheet(session, IDS["user_binil"], MONDAY, TimesheetStatus.submitted)
    sheet.status = TimesheetStatus.approved
    session.commit()
    assert (_official(session, project.id), _provisional(session, project.id)) == (Decimal("12"), Decimal("0"))
    assert _actual(session, project).total_hours == Decimal("12.00")


def test_joins_do_not_duplicate_hours(session):
    """Two active quotes, two people and milestone links must not multiply any entry."""
    project = _project(session)
    _book(session, project.id, "10")
    _book(session, project.id, "6", user_id=IDS["user_ranjith"])
    for revision in ("A", "B"):
        quote = Quote(id=uuid.uuid4(), customer_id=IDS["customer"], project_id=project.id,
                      tool_number=project.tool_number, currency_code="USD", current_revision=revision, is_active=True)
        session.add(quote)
        session.flush()
        session.add(QuoteRevision(id=uuid.uuid4(), quote_id=quote.id, version=1, revision=revision,
                                  quoted_hours=Decimal("90"), fx_date=date(2025, 1, 1)))
    session.commit()
    assert _actual(session, project).total_hours == Decimal("16.00")
    assert sum(Decimal(str(c.total_hours)) for c in get_project_contributors(session, project.id)) == Decimal("16")


# ----------------------------------------------------------------- every consumer reads the same figure


def test_reports_forecasts_control_tower_and_predictions_agree(session):
    project = _project(session, quoted="45")
    _estimate(session, project.id, ProjectStage.preliminary, "45")
    _book(session, project.id, "40")
    _book(session, project.id, "30", week_offset=1, status=TimesheetStatus.submitted)
    _book(session, project.id, "20", week_offset=2, status=TimesheetStatus.draft)
    _book(session, project.id, "10", week_offset=3, status=TimesheetStatus.rejected)
    session.commit()

    official = Decimal("40.00")
    assert calculate_hours(session, project).actual == official
    assert batch_calculate_hours(session, [project])[project.id].actual == official
    assert _actual(session, project).total_hours == official
    assert sum(Decimal(str(c.total_hours)) for c in get_project_contributors(session, project.id)) == official

    forecast = build_engineering_forecast(session, as_of=AS_OF)
    [row] = [r for r in forecast.projects if r.project_id == project.id]
    assert row.actual_hours == official

    facts = load_facts(session, [project], AS_OF)[project.id]
    assert facts.actual_hours == official
    assert facts.unapproved_hours == Decimal("50.00") and facts.rejected_hours == Decimal("10.00")

    _, detections = detect_all(session, AS_OF)
    overruns = [d for d in detections if d.project_id == project.id and d.rule_id == "estimate_overrun_realized"]
    assert overruns == []  # 40 approved h are within 45; all statuses (100 h) would have been an overrun

    recalculate_project(session, project.id)
    assert session.get(Project, project.id).actual_hours == official


def test_demand_outcome_waits_for_pending_approval(session):
    project = _project(session)
    _book(session, project.id, "24", week_offset=1)  # 2025-01-13 … 15, approved
    _entry(session, project.id, "6", week=0, status=TimesheetStatus.submitted, day=4)  # 2025-01-10
    row = Prediction(
        prediction_type="resource_demand", model_version="demand-1", subject_type="person",
        subject_key=f"person:{IDS['user_binil']}:2w", subject_label="Binil — next 2 weeks",
        as_of=date(2025, 1, 5), horizon_start=date(2025, 1, 6), horizon_end=date(2025, 1, 19),
        status=PREDICTED, predicted_value=Decimal("30"), unit="hours",
    )
    session.add(row)
    session.commit()
    evaluate_outcomes(session, date(2025, 1, 20))
    assert row.outcome_status == OUTCOME_PENDING
    evaluate_outcomes(session, date(2025, 1, 19) + timedelta(days=HOURS_SETTLE_DAYS))
    assert row.outcome_status == OUTCOME_EVALUATED and row.actual_value == Decimal("24.00")
    assert "6.00 h on draft or submitted timesheets" in row.outcome_note
