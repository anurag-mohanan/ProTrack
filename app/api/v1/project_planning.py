"""Stage estimates, baselines, forecasts and schedule overrides for one project."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.access_control import SPECIAL_APPROVE_BASELINES, SPECIAL_REVISE_ESTIMATES
from app.core.exceptions import ProTrackValidationError
from app.core.permissions import can_read_project, can_update_project, user_holds_special
from app.models.enums import PLANNED_STAGE_LABELS, ActivityAction, EntityType
from app.models.models import (
    Milestone,
    Project,
    ProjectBaselineRevision,
    ProjectEstimateRevision,
    User,
)
from app.schemas.project_planning import (
    BaselineRevisionCreate,
    BaselineRevisionRead,
    EstimateRevisionRead,
    MilestoneOverrideRequest,
    ProjectStagePlanRead,
    StageEstimateRevisionCreate,
    StageEstimatesConfigure,
    StagePlanMilestone,
    StagePlanStage,
)
from app.services.activity_service import log_activity
from app.services.milestone_workspace_service import recalculate_project_planned_hours
from app.services.project_calculation_service import recalculate_project
from app.services.project_estimate_service import (
    configure_stage_estimates,
    revise_stage_estimate,
    stage_breakdown,
)
from app.services.scheduling_service import (
    apply_baseline,
    load_effort_assumption,
    parse_id_list,
    recalculate_forecast,
    revise_baseline,
)

router = APIRouter(prefix="/projects", tags=["project-planning"])


def _q2(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _load_project(db: Session, project_id: UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _readable(db: Session, user: User, project_id: UUID) -> Project:
    project = _load_project(db, project_id)
    if not can_read_project(db, user, project):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return project


def _editable(db: Session, user: User, project_id: UUID, special: str | None = None) -> Project:
    project = _load_project(db, project_id)
    if not can_update_project(db, user, project):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if special is not None and not user_holds_special(db, user, special):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires the '{special}' permission.",
        )
    return project


def _user_names(db: Session, ids: set[UUID]) -> dict[UUID, str]:
    if not ids:
        return {}
    users = db.scalars(select(User).where(User.id.in_(ids))).all()
    return {
        user.id: (f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email)
        for user in users
    }


def _unprocessable(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc.detail))


def _build_plan(db: Session, project: Project) -> ProjectStagePlanRead:
    lines = stage_breakdown(db, project)
    stages: list[StagePlanStage] = []
    for line in lines:
        mismatch = (
            line.current_hours is not None
            and line.milestones
            and _q2(line.milestone_planned_hours) != _q2(line.current_hours)
        )
        stages.append(
            StagePlanStage(
                key=line.key,
                label=line.label,
                configured=line.configured,
                original_hours=line.original_hours,
                current_hours=line.current_hours,
                milestone_planned_hours=line.milestone_planned_hours,
                actual_hours=line.actual_hours,
                forecast_remaining_hours=line.forecast_remaining,
                eac_hours=line.eac,
                variance_hours=line.variance,
                variance_percent=line.variance_percent,
                allocation_mismatch=bool(mismatch),
                milestones=[
                    StagePlanMilestone(
                        id=item.milestone.id,
                        name=item.milestone.name,
                        sort_order=item.milestone.sort_order,
                        status=item.milestone.status,
                        is_required=item.milestone.is_required,
                        original_planned_hours=item.milestone.original_planned_hours,
                        planned_hours=_q2(item.milestone.planned_hours or 0),
                        actual_hours=item.actual_hours,
                        forecast_remaining_hours=item.forecast_remaining,
                        estimate_basis=item.milestone.estimate_basis,
                        baseline_start_date=item.milestone.baseline_start_date,
                        baseline_finish_date=item.milestone.baseline_finish_date,
                        forecast_start_date=item.milestone.forecast_start_date,
                        forecast_finish_date=item.milestone.forecast_finish_date,
                        actual_start_date=item.milestone.actual_start_date,
                        actual_finish_date=item.milestone.completed_date
                        or (
                            item.milestone.completed_at.date()
                            if item.milestone.completed_at
                            else None
                        ),
                        due_date=item.milestone.due_date,
                        override_start_date=item.milestone.override_start_date,
                        override_finish_date=item.milestone.override_finish_date,
                        override_reason=item.milestone.override_reason,
                        depends_on=[UUID(v) for v in parse_id_list(item.milestone.depends_on_ids)],
                        overdue=item.overdue,
                        forecast_late=item.forecast_late,
                    )
                    for item in line.milestones
                ],
            )
        )

    configured = any(line.configured for line in lines if line.key != "other")
    planned_lines = [line for line in lines if line.key != "other"]
    original_total = (
        _q2(sum((line.original_hours or Decimal("0")) for line in planned_lines))
        if configured
        else None
    )
    current_total = (
        _q2(sum((line.current_hours or Decimal("0")) for line in planned_lines))
        if configured
        else None
    )
    actual_total = _q2(sum((line.actual_hours for line in lines), Decimal("0")))
    remaining_total = _q2(sum((line.forecast_remaining for line in lines), Decimal("0")))
    eac_total = _q2(actual_total + remaining_total)
    other_planned = sum(
        (line.milestone_planned_hours for line in lines if line.key == "other"), Decimal("0")
    )
    reference = (
        (current_total + other_planned)
        if current_total is not None
        else sum((line.milestone_planned_hours for line in lines), Decimal("0"))
    )
    variance = _q2(eac_total - reference)
    variance_percent = _q2(variance / reference * Decimal("100")) if reference > 0 else None

    estimate_rows = db.scalars(
        select(ProjectEstimateRevision)
        .where(ProjectEstimateRevision.project_id == project.id)
        .order_by(ProjectEstimateRevision.revised_at.desc())
    ).all()
    baseline_rows = db.scalars(
        select(ProjectBaselineRevision)
        .where(ProjectBaselineRevision.project_id == project.id)
        .order_by(ProjectBaselineRevision.revision_number.desc())
    ).all()
    names = _user_names(
        db,
        {row.revised_by_id for row in estimate_rows if row.revised_by_id}
        | {row.revised_by_id for row in baseline_rows if row.revised_by_id},
    )
    effort = load_effort_assumption(db)
    return ProjectStagePlanRead(
        project_id=project.id,
        start_date=project.start_date,
        baseline_start_date=project.baseline_start_date,
        baseline_completion_date=project.baseline_completion_date,
        baseline_version=project.baseline_version or 0,
        forecast_completion_date=project.forecast_completion_date,
        forecast_status=project.forecast_status,
        forecast_note=project.forecast_note,
        forecast_calculated_at=project.forecast_calculated_at,
        actual_start_date=project.actual_start_date,
        actual_completion_date=project.completed_at.date() if project.completed_at else None,
        due_date=project.due_date,
        stage_estimates_configured=configured,
        original_total_hours=original_total,
        current_total_hours=current_total,
        actual_total_hours=actual_total,
        forecast_remaining_hours=remaining_total,
        eac_hours=eac_total,
        variance_hours=variance,
        variance_percent=variance_percent,
        stages=stages,
        estimate_revisions=[
            EstimateRevisionRead(
                id=row.id,
                stage=row.stage,
                stage_label=PLANNED_STAGE_LABELS.get(row.stage, row.stage.value),
                previous_hours=row.previous_hours,
                new_hours=row.new_hours,
                reason=row.reason,
                revised_by_id=row.revised_by_id,
                revised_by_name=names.get(row.revised_by_id) if row.revised_by_id else None,
                revised_at=row.revised_at,
            )
            for row in estimate_rows
        ],
        baseline_revisions=[
            BaselineRevisionRead(
                id=row.id,
                revision_number=row.revision_number,
                previous_start_date=row.previous_start_date,
                previous_completion_date=row.previous_completion_date,
                new_start_date=row.new_start_date,
                new_completion_date=row.new_completion_date,
                reason=row.reason,
                revised_by_id=row.revised_by_id,
                revised_by_name=names.get(row.revised_by_id) if row.revised_by_id else None,
                revised_at=row.revised_at,
            )
            for row in baseline_rows
        ],
        effort_hours_per_day=effort.hours_per_day,
        effort_source=effort.source,
    )


@router.get("/{project_id}/stage-plan", response_model=ProjectStagePlanRead)
def get_stage_plan(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _readable(db, current_user, project_id)
    # Forecasts move with "today"; refresh before reading so the page is current.
    recalculate_forecast(db, project)
    db.commit()
    db.refresh(project)
    return _build_plan(db, project)


@router.post("/{project_id}/stage-estimates", response_model=ProjectStagePlanRead)
def configure_project_stage_estimates(
    project_id: UUID,
    payload: StageEstimatesConfigure,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _editable(db, current_user, project_id)
    try:
        configure_stage_estimates(db, project, payload.stage_hours.as_stage_map(), user=current_user)
        db.flush()
        recalculate_project_planned_hours(db, project.id)
        apply_baseline(db, project, set_due_dates=False, actor_id=current_user.id)
        db.commit()
    except ProTrackValidationError as exc:
        db.rollback()
        raise _unprocessable(exc) from exc
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.project,
        entity_id=project.id,
        action=ActivityAction.project_updated,
        new_value=f"Stage estimates configured: total {payload.stage_hours.total} h",
        module="projects",
        outcome="success",
    )
    recalculate_project(db, project.id)
    return _build_plan(db, _load_project(db, project_id))


@router.post("/{project_id}/stage-estimates/revisions", response_model=ProjectStagePlanRead)
def revise_project_stage_estimate(
    project_id: UUID,
    payload: StageEstimateRevisionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _editable(db, current_user, project_id, SPECIAL_REVISE_ESTIMATES)
    try:
        revision = revise_stage_estimate(
            db,
            project,
            stage=payload.stage,
            new_hours=payload.new_hours,
            reason=payload.reason,
            user=current_user,
        )
        db.commit()
    except ProTrackValidationError as exc:
        db.rollback()
        raise _unprocessable(exc) from exc
    recalculate_project_planned_hours(db, project.id)
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.project,
        entity_id=project.id,
        action=ActivityAction.project_updated,
        old_value=f"{PLANNED_STAGE_LABELS[payload.stage]}: {revision.previous_hours} h",
        new_value=f"{PLANNED_STAGE_LABELS[payload.stage]}: {revision.new_hours} h ({payload.reason})",
        module="projects",
        outcome="success",
    )
    recalculate_project(db, project.id)
    return _build_plan(db, _load_project(db, project_id))


@router.post("/{project_id}/baseline-revisions", response_model=ProjectStagePlanRead)
def revise_project_baseline(
    project_id: UUID,
    payload: BaselineRevisionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _editable(db, current_user, project_id, SPECIAL_APPROVE_BASELINES)
    try:
        revision = revise_baseline(
            db,
            project,
            reason=payload.reason,
            new_start_date=payload.new_start_date,
            actor_id=current_user.id,
        )
        db.commit()
    except ProTrackValidationError as exc:
        db.rollback()
        raise _unprocessable(exc) from exc
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.project,
        entity_id=project.id,
        action=ActivityAction.project_updated,
        old_value=f"Baseline completion {revision.previous_completion_date}",
        new_value=(
            f"Baseline v{revision.revision_number} completion {revision.new_completion_date} "
            f"({payload.reason})"
        ),
        module="projects",
        outcome="success",
    )
    recalculate_project(db, project.id)
    return _build_plan(db, _load_project(db, project_id))


@router.put(
    "/{project_id}/milestones/{milestone_id}/schedule-override",
    response_model=ProjectStagePlanRead,
)
def set_milestone_schedule_override(
    project_id: UUID,
    milestone_id: UUID,
    payload: MilestoneOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _editable(db, current_user, project_id)
    milestone = db.get(Milestone, milestone_id)
    if milestone is None or milestone.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    clearing = payload.override_start_date is None and payload.override_finish_date is None
    milestone.override_start_date = payload.override_start_date
    milestone.override_finish_date = payload.override_finish_date
    milestone.override_reason = None if clearing else (payload.reason or "").strip()
    milestone.override_by_id = None if clearing else current_user.id
    milestone.override_at = None if clearing else datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(milestone)
    db.commit()
    log_activity(
        db,
        user=current_user,
        entity_type=EntityType.project,
        entity_id=project.id,
        action=ActivityAction.project_updated,
        new_value=(
            f"Schedule override cleared for {milestone.name}"
            if clearing
            else (
                f"Schedule override for {milestone.name}: "
                f"{payload.override_start_date or '-'} to {payload.override_finish_date or '-'} "
                f"({milestone.override_reason})"
            )
        ),
        module="projects",
        outcome="success",
    )
    recalculate_project(db, project.id)
    return _build_plan(db, _load_project(db, project_id))
