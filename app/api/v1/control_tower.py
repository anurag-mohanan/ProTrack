"""Engineering Control Tower API: read findings, trigger an evaluation, acknowledge, triage, convert."""

from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from app.api.auth_deps import get_current_user
from app.api.deps import APIRouter, Depends, Query, Session, get_db
from app.core.access_control import SPECIAL_EDIT_PROJECTS
from app.core.permissions import can_view_reports, user_holds_special
from app.core.team_access import project_visibility_clause
from app.models.control_tower import OPEN_FINDING_STATUSES, ProjectRiskFinding
from app.models.models import Project, User
from app.schemas.control_tower import (
    AcknowledgeRequest,
    Category,
    ControlTowerFilters,
    ControlTowerResponse,
    ControlTowerView,
    ConvertRequest,
    ConvertResult,
    EvaluationRunRead,
    FindingDetail,
    FindingStatus,
    Severity,
    TriageFilter,
    TriageRequest,
)
from app.services import control_tower_service as ct
from app.services.reporting.report_scope import (
    ReportScopeForbidden,
    resolve_report_scope,
)


def _require_report_access(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if not can_view_reports(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to Reports. Ask an administrator for the Reports module.",
        )
    return current_user


router = APIRouter(
    prefix="/control-tower",
    tags=["control-tower"],
    dependencies=[Depends(_require_report_access)],
)


def _scope(db: Session, user: User) -> ct.FindingScope:
    try:
        report_scope = resolve_report_scope(db, user)
    except ReportScopeForbidden as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ct.FindingScope(
        visibility_clause=project_visibility_clause(db, user),
        team_ids=report_scope.team_ids,
    )


def _can_manage(db: Session, user: User) -> bool:
    return user_holds_special(db, user, SPECIAL_EDIT_PROJECTS)


def _visible_finding(db: Session, user: User, finding_id: UUID) -> tuple[ProjectRiskFinding, Project]:
    row = db.execute(
        _scope(db, user)
        .apply(select(ProjectRiskFinding, Project))
        .where(ProjectRiskFinding.id == finding_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")
    return row[0], row[1]


@router.get("", response_model=ControlTowerResponse)
def get_control_tower(
    view: ControlTowerView = Query("risks"),
    severity: Severity | None = Query(None),
    category: Category | None = Query(None),
    status_filter: FindingStatus | None = Query(None, alias="status"),
    project_id: UUID | None = Query(None),
    owner_id: str | None = Query(None, max_length=40),
    search: str | None = Query(None, max_length=100),
    triage: TriageFilter | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read-only: never evaluates or writes. Findings are clipped to the caller's projects."""
    if owner_id not in (None, "unassigned"):
        try:
            UUID(owner_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="owner_id must be a user id or 'unassigned'",
            ) from exc
    if view == "resolved" and status_filter in ("active", "not_assessable"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="status must be 'resolved' (or omitted) for the resolved view",
        )
    if view != "resolved" and status_filter == "resolved":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Use view=resolved to list resolved findings",
        )
    today = date.today()
    scope = _scope(db, current_user)
    can_manage = _can_manage(db, current_user)
    query = ct.FindingQuery(
        view=view,
        severity=severity,
        category=category,
        status=status_filter,
        project_id=project_id,
        owner_id=owner_id,
        search=search.strip() if search and search.strip() else None,
        triage=triage,
    )
    findings, total = ct.list_findings(db, scope, query, page=page, page_size=page_size)
    latest, succeeded = ct.latest_runs(db)
    state, message = ct.control_tower_state(latest, succeeded, today)
    owners, projects = ct.filter_options(db, scope)
    empty_message = None
    if total == 0:
        if succeeded is None:
            empty_message = "No evaluation has succeeded yet, so there are no findings to show."
        elif any([severity, category, status_filter, project_id, owner_id, query.search, triage]):
            empty_message = "No findings match these filters."
        elif view == "resolved":
            empty_message = "No findings have been resolved yet."
        elif view == "predictive":
            empty_message = (
                "No open forecast findings in your projects. Forecasts need recent predictions; projects without "
                "enough comparable history get no forecast and therefore no finding."
            )
        elif view == "data_quality":
            empty_message = "No open data-quality findings in your projects at the last successful evaluation."
        else:
            empty_message = "No open risk findings in your projects at the last successful evaluation."
    return ControlTowerResponse(
        state=state,  # type: ignore[arg-type]
        state_message=message,
        evaluation_date=succeeded.evaluation_date if succeeded else None,
        latest_run=ct.run_read(latest, include_error=can_manage),
        last_successful_run=ct.run_read(succeeded, include_error=can_manage),
        can_evaluate=can_manage,
        can_acknowledge=can_manage,
        summary=ct.build_summary(db, scope, today),
        filters=ControlTowerFilters(
            view=view,
            severity=severity,
            category=category,
            status=status_filter,
            project_id=project_id,
            owner_id=owner_id,
            search=query.search,
            triage=triage,
        ),
        findings=findings,
        total=total,
        page=page,
        page_size=page_size,
        owner_options=owners,
        project_options=projects,
        rules=ct.rule_catalog(),
        deferred_rules=list(ct.DEFERRED_RULES),
        empty_message=empty_message,
    )


@router.post("/evaluate", response_model=EvaluationRunRead)
def evaluate_control_tower(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-evaluate every open project. Writes only Control Tower findings."""
    if not _can_manage(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires the 'edit_projects' permission.",
        )
    try:
        run = ct.run_evaluation(db, trigger="manual", user_id=current_user.id)
    except ct.EvaluationInProgress as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The evaluation failed. Existing findings were kept and are marked as out of date.",
        ) from exc
    return ct.run_read(run, include_error=True)


@router.get("/findings/{finding_id}", response_model=FindingDetail)
def get_finding(
    finding_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    finding, project = _visible_finding(db, current_user, finding_id)
    read = ct.to_reads(db, [(finding, project)])[0]
    return FindingDetail(**read.model_dump(), events=ct.finding_events(db, finding.id))


@router.post("/findings/{finding_id}/acknowledge", response_model=FindingDetail)
def acknowledge_finding(
    finding_id: UUID,
    payload: AcknowledgeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Records who has seen the finding. Does not change the condition or resolve it."""
    if not _can_manage(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires the 'edit_projects' permission.",
        )
    finding, project = _visible_finding(db, current_user, finding_id)
    if finding.status not in OPEN_FINDING_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resolved findings cannot be acknowledged.")
    if finding.acknowledged_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This finding is already acknowledged.")
    finding = ct.acknowledge_finding(db, finding, user_id=current_user.id, note=payload.note)
    read = ct.to_reads(db, [(finding, project)])[0]
    return FindingDetail(**read.model_dump(), events=ct.finding_events(db, finding.id))


def _require_manage(db: Session, user: User) -> None:
    if not _can_manage(db, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires the 'edit_projects' permission.")


@router.post("/findings/{finding_id}/triage", response_model=FindingDetail)
def triage_finding(
    finding_id: UUID,
    payload: TriageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark as investigating or dismissed (with a reason), or clear the mark. Never resolves the finding."""
    _require_manage(db, current_user)
    finding, project = _visible_finding(db, current_user, finding_id)
    try:
        finding = ct.triage_finding(db, finding, user=current_user, action=payload.action, note=payload.note)
    except ct.FindingActionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    read = ct.to_reads(db, [(finding, project)])[0]
    return FindingDetail(**read.model_dump(), events=ct.finding_events(db, finding.id))


@router.post("/findings/{finding_id}/convert", response_model=ConvertResult)
def convert_finding(
    finding_id: UUID,
    payload: ConvertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record the finding as a recommendation in the review queue. Nothing is executed."""
    _require_manage(db, current_user)
    finding, _project = _visible_finding(db, current_user, finding_id)
    try:
        recommendation = ct.convert_finding(db, finding, user=current_user, note=payload.note)
    except ct.FindingActionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ConvertResult(recommendation_id=recommendation.id, status=recommendation.status, title=recommendation.title)
