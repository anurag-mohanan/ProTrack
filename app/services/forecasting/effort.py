"""Remaining-effort forecast and backtest. Read-only; reuses the shared engineering metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from statistics import median
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ExecutionStatus
from app.models.models import Project
from app.schemas.engineering_metrics import ProjectEngineeringMetrics
from app.schemas.forecasting import (
    EffortBacktest,
    EffortHistorySummary,
    EngineeringForecastResponse,
    EngineeringForecastSummary,
    ForecastStatus,
    ProjectEffortForecast,
)
from app.services.engineering_metrics_service import build_engineering_metrics_batch
from app.services.forecasting.definitions import (
    COMPLETION_DEFERRED_REASON,
    EFFORT_METHOD_VERSION,
    STAGE_DEFERRED_REASON,
    metadata,
)
from app.services.reporting.quote_to_delivery import (
    APPROVED_ESTIMATE_SOURCES,
    OPEN_STATUSES,
)

MIN_HISTORY = 5
_HOURS = Decimal("0.01")
_FACTOR = Decimal("0.0001")

HISTORY_BASIS = (
    "Completed projects (completion date on or before the as-of date) with an approved estimate "
    "(stage estimates or milestone planned hours) above zero and recorded actual hours above zero. "
    "Factor = median of actual ÷ original approved estimate."
)
BACKTEST_METHOD = (
    "Time-ordered: each completed project is predicted with the factor fitted only on projects "
    "completed strictly earlier (at least the minimum sample), as original approved estimate × "
    "factor, and compared with its final actual hours. The naive baseline is the original approved "
    "estimate itself. Error = predicted − actual (positive = over-forecast)."
)


@dataclass(frozen=True)
class EffortSample:
    project_id: UUID
    completed_on: date
    original_estimate: Decimal
    actual: Decimal

    @property
    def ratio(self) -> Decimal:
        return self.actual / self.original_estimate


@dataclass(frozen=True)
class FactorFit:
    factor: Decimal | None
    status: ForecastStatus
    reason: str | None
    sample_size: int


def fit_factor(samples: list[EffortSample]) -> FactorFit:
    n = len(samples)
    if n == 0:
        return FactorFit(
            None,
            "unavailable",
            "No completed project has both an approved estimate and recorded actual hours, so "
            "there is no history to adjust the plan with.",
            0,
        )
    factor = Decimal(str(median(sample.ratio for sample in samples))).quantize(_FACTOR)
    if n < MIN_HISTORY:
        return FactorFit(
            factor,
            "preliminary",
            f"Only {n} comparable completed project(s); {MIN_HISTORY} are needed for an available "
            "forecast.",
            n,
        )
    return FactorFit(factor, "available", None, n)


def backtest(samples: list[EffortSample], minimum: int = MIN_HISTORY) -> EffortBacktest:
    ordered = sorted(samples, key=lambda s: (s.completed_on, str(s.project_id)))
    errors: list[tuple[Decimal, Decimal, Decimal]] = []
    for sample in ordered:
        prior = [p for p in ordered if p.completed_on < sample.completed_on]
        if len(prior) < minimum:
            continue
        fit = fit_factor(prior)
        predicted = sample.original_estimate * fit.factor  # type: ignore[operator]
        errors.append((predicted - sample.actual, sample.original_estimate - sample.actual, sample.actual))
    if not errors:
        return EffortBacktest(
            status="not_possible",
            reason=(
                f"{len(samples)} comparable completed project(s). Evaluation needs at least one "
                f"project with {minimum} earlier completions to learn from."
            ),
            candidate_count=len(samples),
            method=BACKTEST_METHOD,
        )
    n = Decimal(len(errors))

    def mae(index: int) -> Decimal:
        return (sum((abs(row[index]) for row in errors), Decimal("0")) / n).quantize(_HOURS)

    def mape(index: int) -> Decimal:
        return (
            sum((abs(row[index]) / row[2] * 100 for row in errors), Decimal("0")) / n
        ).quantize(_HOURS)

    return EffortBacktest(
        status="evaluated",
        candidate_count=len(samples),
        evaluated_count=len(errors),
        mean_absolute_error_hours=mae(0),
        mean_absolute_percentage_error=mape(0),
        mean_signed_error_hours=(sum((row[0] for row in errors), Decimal("0")) / n).quantize(_HOURS),
        naive_mean_absolute_error_hours=mae(1),
        naive_mean_absolute_percentage_error=mape(1),
        method=BACKTEST_METHOD,
    )


def sample_from_metrics(project: Project, metrics: ProjectEngineeringMetrics) -> EffortSample | None:
    if project.completed_at is None:
        return None
    if metrics.estimate.estimate_source not in APPROVED_ESTIMATE_SOURCES:
        return None
    original = metrics.estimate.original_estimate_hours
    actual = metrics.actual.total_hours
    if metrics.actual.status != "recorded" or original is None or original <= 0 or not actual or actual <= 0:
        return None
    return EffortSample(project.id, project.completed_at.date(), Decimal(original), Decimal(actual))


def load_history(db: Session, as_of: date) -> list[tuple[Project, EffortSample]]:
    """Org-wide history so the factor does not depend on who is asking; no project after ``as_of``."""
    cutoff = datetime.combine(as_of, time.max)
    projects = list(
        db.scalars(
            select(Project).where(
                Project.is_deleted.is_(False),
                Project.execution_status == ExecutionStatus.completed,
                Project.completed_at.is_not(None),
                Project.completed_at <= cutoff,
            )
        ).all()
    )
    metrics = build_engineering_metrics_batch(db, projects, finance_details_visible=False, today=as_of)
    rows = []
    for project in projects:
        sample = sample_from_metrics(project, metrics[project.id])
        if sample is not None:
            rows.append((project, sample))
    return rows


def project_forecast(project: Project, metrics: ProjectEngineeringMetrics, fit: FactorFit) -> ProjectEffortForecast:
    source = metrics.estimate.estimate_source
    approved = source in APPROVED_ESTIMATE_SOURCES
    original = metrics.estimate.original_estimate_hours
    actual = metrics.actual.total_hours
    status: ForecastStatus = "unavailable"
    reason: str | None
    eac = remaining = None
    if not approved:
        reason = (
            "No approved estimate (stage estimates or milestone planned hours). Quoted hours are a "
            "commercial figure and are not forecast from."
        )
    elif metrics.actual.status == "missing":
        reason = "Actual hours are missing although work is recorded as complete."
    elif original is None or original <= 0:
        reason = "The original approved estimate is zero or missing."
    elif fit.factor is None:
        reason = fit.reason
    else:
        eac = (Decimal(original) * fit.factor).quantize(_HOURS)
        done = Decimal(actual or 0)
        if done >= eac:
            reason = (
                f"Actual hours ({done} h) already reach the history-based estimate at completion "
                f"({eac} h); remaining effort cannot be derived from history."
            )
            eac = None
        else:
            remaining = (eac - done).quantize(_HOURS)
            status = fit.status
            reason = fit.reason
    delivery = metrics.delivery.project
    original_commitment = (
        delivery.reference_date
        if delivery.reference_source in ("original_baseline", "baseline_unverified")
        else None
    )
    return ProjectEffortForecast(
        project_id=project.id,
        code=project.code,
        tool_number=project.tool_number,
        execution_status=metrics.execution_status,
        quoted_hours=metrics.estimate.quoted_hours,
        estimate_source=source,
        approved_original_estimate_hours=original if approved else None,
        approved_current_estimate_hours=metrics.estimate.current_estimate_hours if approved else None,
        actual_hours=actual,
        actual_status=metrics.actual.status,
        actual_unapproved_hours=metrics.actual.draft_hours + metrics.actual.submitted_hours,
        actual_rejected_hours=metrics.actual.rejected_hours,
        approved_remaining_hours=metrics.remaining_hours.value if approved else None,
        forecast_status=status,
        forecast_reason=reason,
        forecast_at_completion_hours=eac,
        forecast_remaining_hours=remaining,
        original_commitment_date=original_commitment,
        original_commitment_source=delivery.reference_source,
        current_target_date=delivery.current_target_date,
        target_moved_days=delivery.target_moved_days,
        provisional_schedule_date=project.forecast_completion_date,
        provisional_schedule_status=project.forecast_status,
        completion_forecast_reason=COMPLETION_DEFERRED_REASON,
        stage_forecast_reason=STAGE_DEFERRED_REASON,
        data_quality_codes=[issue.code for issue in metrics.issues],
    )


def open_projects(db: Session, *, visibility_clause=None, team_ids: frozenset[UUID] | None = None) -> list[Project]:
    stmt = select(Project).where(
        Project.is_deleted.is_(False),
        Project.is_archived.is_(False),
        Project.execution_status.in_(OPEN_STATUSES),
    )
    if visibility_clause is not None:
        stmt = stmt.where(visibility_clause)
    if team_ids is not None:
        stmt = stmt.where(Project.team_id.in_(team_ids) if team_ids else Project.id.is_(None))
    return list(db.scalars(stmt.order_by(Project.tool_number)).all())


def build_engineering_forecast(
    db: Session,
    *,
    as_of: date | None = None,
    visibility_clause=None,
    team_ids: frozenset[UUID] | None = None,
) -> EngineeringForecastResponse:
    as_of = as_of or date.today()
    history = load_history(db, as_of)
    samples = [sample for _, sample in history]
    fit = fit_factor(samples)
    projects = open_projects(db, visibility_clause=visibility_clause, team_ids=team_ids)
    metrics = build_engineering_metrics_batch(db, projects, finance_details_visible=False, today=as_of)
    rows = [project_forecast(project, metrics[project.id], fit) for project in projects]

    visible_history = _visible_ids(db, [p.id for p, _ in history], visibility_clause, team_ids)
    counts = {s: sum(1 for r in rows if r.forecast_status == s) for s in ("available", "preliminary", "unavailable")}
    forecastable = [r for r in rows if r.forecast_remaining_hours is not None]
    approved_remaining = sum(
        (max(r.approved_remaining_hours, Decimal("0")) for r in rows if r.approved_remaining_hours is not None),
        Decimal("0"),
    )
    all_forecast = bool(rows) and len(forecastable) == sum(
        1 for r in rows if r.estimate_source in APPROVED_ESTIMATE_SOURCES
    )
    summary = EngineeringForecastSummary(
        projects=len(rows),
        available=counts["available"],
        preliminary=counts["preliminary"],
        unavailable=counts["unavailable"],
        approved_remaining_hours=approved_remaining.quantize(_HOURS),
        forecast_remaining_hours=(
            sum((r.forecast_remaining_hours for r in forecastable), Decimal("0")).quantize(_HOURS)
            if forecastable
            else None
        ),
        forecast_remaining_note=(
            "No project could be forecast."
            if not forecastable
            else "Sum over every project with an approved estimate."
            if all_forecast
            else "Partial: only projects with a forecast are summed; projects without one are excluded, not counted as zero."
        ),
    )
    if counts["available"]:
        overall: ForecastStatus = "available"
    elif counts["preliminary"]:
        overall = "preliminary"
    else:
        overall = "unavailable"
    status_reason = None
    if overall != "available":
        status_reason = fit.reason if fit.factor is None or fit.status != "available" else (
            "No open project in scope has an approved estimate that can be forecast."
        )
    return EngineeringForecastResponse(
        metadata=metadata(
            forecast_type="remaining_effort",
            method_version=EFFORT_METHOD_VERSION,
            as_of=as_of,
            status=overall,
            status_reason=status_reason,
            sources=[
                "Shared engineering metrics (approved estimate, actual hours, delivery dates)",
                "Completed-project history up to the as-of date",
                "Existing provisional stage-plan schedule (shown, not used)",
            ],
            assumptions=[
                "Actual hours follow the current project rule: draft, submitted and rejected hours count; the split is shown per project.",
                "Future projects overrun or underrun their original approved estimate in the same median proportion as past completed projects.",
                "Milestone completion percentage is not used as effort completion.",
            ],
            limitations=[
                "The factor is not segmented by customer, working model or complexity.",
                "Milestone planned hours are not revision-tracked, so their original and current values are the same.",
                "The backtest evaluates the estimate at completion from the project start; it does not test mid-project updates.",
                COMPLETION_DEFERRED_REASON,
                STAGE_DEFERRED_REASON,
            ],
        ),
        history=EffortHistorySummary(
            sample_size=fit.sample_size,
            minimum_sample=MIN_HISTORY,
            factor=fit.factor,
            factor_status=fit.status,
            factor_reason=fit.reason,
            basis=HISTORY_BASIS,
            visible_sample_project_ids=[p.id for p, _ in history if p.id in visible_history],
        ),
        backtest=backtest(samples),
        summary=summary,
        projects=rows,
    )


def _visible_ids(db: Session, ids: list[UUID], visibility_clause, team_ids: frozenset[UUID] | None) -> set[UUID]:
    if not ids:
        return set()
    stmt = select(Project.id).where(Project.id.in_(ids))
    if visibility_clause is not None:
        stmt = stmt.where(visibility_clause)
    if team_ids is not None:
        stmt = stmt.where(Project.team_id.in_(team_ids) if team_ids else Project.id.is_(None))
    return set(db.scalars(stmt).all())
