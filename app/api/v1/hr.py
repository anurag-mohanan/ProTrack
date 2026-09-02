"""Human Resources module — team visibility, timesheets, and performance reviews."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from app.schemas.hr_process_audit import ProcessAuditItem, ProcessAuditRead
from app.schemas.training import (
    TrainingAssignRequest,
    TrainingAssignmentRead,
    TrainingCourseCreate,
    TrainingCourseRead,
)
from app.services import hr_process_audit_service as process_audit
from app.schemas.skill_matrix import (
    SkillMatrixRead,
    SkillMatrixUpsertRequest,
    SkillMatrixUpsertResponse,
)
from app.services.skill_matrix_service import build_team_skill_matrix, upsert_skill_ratings
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.access_control import MODULE_HUMAN_RESOURCES, MODULE_PERFORMANCE
from app.core.module_actions import (
    MODULE_ACTION_CREATE,
    MODULE_ACTION_EDIT,
    MODULE_ACTION_EDIT_REVIEWS,
    MODULE_ACTION_MANAGE_TEMPLATES,
    MODULE_ACTION_OPEN_CYCLES,
    MODULE_ACTION_VIEW,
    user_has_module_action,
)
from app.core.permissions import get_role_name, is_admin
from app.core.field_security import can_view_salary
from app.core.team_access import get_accessible_team_ids, team_member_user_ids
from app.models.enums import ProjectComplexity, TeamRelationshipType, TimesheetStatus
from app.models.models import (
    CompensationChangeRequest,
    PerformanceReviewCycle,
    PerformanceReviewItem,
    PerformanceReviewProject,
    PerformanceReviewSection,
    PerformanceReviewSheet,
    PerformanceReviewTemplate,
    Project,
    Role,
    Team,
    TeamMember,
    Timesheet,
    TimesheetEntry,
    User,
    WorkingModel,
)
from app.schemas.performance_review import (
    PerformanceReviewCreate,
    PerformanceReviewCycleCreate,
    PerformanceReviewCycleRead,
    PerformanceReviewItemRead,
    PerformanceReviewProjectRead,
    PerformanceReviewProjectSuggestionRead,
    PerformanceReviewRead,
    PerformanceReviewSectionRead,
    PerformanceReviewTeamMemberRead,
    PerformanceReviewTemplateCatalogRead,
    PerformanceReviewTemplateCreate,
    PerformanceReviewTemplateRead,
    PerformanceReviewUpdate,
    PerformanceReviewWorkflowAction,
)
from app.schemas.enterprise import (
    LearningPlanCreateFromGaps,
    LearningPlanItemRead,
    LearningPlanItemStatusUpdate,
    LearningPlanRead,
    SkillGapRead,
)
from app.services.performance_review_service import (
    DEFAULT_REVIEW_TEMPLATE,
    FORM_CODE,
    FORM_REVISION,
    FORM_TITLE,
    PP_HRD_FO_20_TEMPLATE,
    RATING_SCALE,
    REVIEW_CYCLE_MONTH,
    current_review_year,
    default_period_label,
    discover_employee_projects,
    format_tenure,
    rating_label,
    review_period_bounds,
    seed_review_projects,
    section_average_score,
    sheet_completion_ratio,
    sheet_overall_score,
    user_can_create_performance_review,
    user_can_edit_performance_review,
    user_can_edit_review_as_employee,
    user_can_edit_review_as_manager,
    user_can_manage_team_reviews,
    user_can_view_review,
)
from app.services.assignment_skill_fit_service import (
    evaluate_assignment_skill_fit,
    evaluate_multi_role_fit,
)
from app.services.review_engine_service import (
    STAGE_ACKNOWLEDGED,
    STAGE_CALIBRATION,
    STAGE_FINAL,
    STAGE_MANAGER,
    STAGE_SELF,
    advance_sheet_stage,
    build_performance_dashboard,
    ensure_default_annual_template,
    ensure_default_quarterly_template,
    get_active_template,
    list_templates,
    parse_json_list,
    template_to_dict,
)
from app.services.timesheet_compliance_service import get_missing_timesheet_rows
from app.services.user_team_service import get_user_team_ids
from app.services import compensation_change_service as comp_service
from app.services import user_change_service
from app.schemas.compensation_change import (
    CompensationChangeCreate,
    CompensationChangeRead,
    CompensationChangeWorkflowAction,
)
from app.schemas.user_lifecycle import (
    BillingChangeRequest,
    PromoteRequest,
    TransferRequest,
    UserJobEventRead,
    UserLifecycleHistoryRead,
    WorkingModelPeriodRead,
)
from app.models.models import UserJobEvent, UserWorkingModelPeriod
from app.core.exceptions import ProTrackValidationError

router = APIRouter(prefix="/hr", tags=["human-resources"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _require_performance_view(db: Session, user: User) -> None:
    if not user_has_module_action(
        user, get_role_name(db, user), MODULE_PERFORMANCE, MODULE_ACTION_VIEW
    ):
        raise HTTPException(status_code=403, detail="Performance module access required")


def _has_performance_action(db: Session, user: User, action: str) -> bool:
    return user_has_module_action(user, get_role_name(db, user), MODULE_PERFORMANCE, action)


def _require_hr_view(db: Session, user: User) -> None:
    role_name = get_role_name(db, user)
    if not user_has_module_action(user, role_name, MODULE_HUMAN_RESOURCES, MODULE_ACTION_VIEW):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Human Resources access required",
        )


def _scoped_member_ids(db: Session, current_user: User) -> tuple[list, set]:
    accessible = get_accessible_team_ids(db, current_user)
    if accessible is None:
        team_ids = list(db.scalars(select(Team.id).where(Team.is_active.is_(True))).all())
    else:
        team_ids = list(accessible)
    member_ids = team_member_user_ids(db, team_ids) if team_ids else set()
    member_ids.add(current_user.id)
    return team_ids, member_ids


def _managed_team_ids(db: Session, current_user: User) -> list:
    if is_admin(db, current_user):
        return list(db.scalars(select(Team.id).where(Team.is_active.is_(True))).all())
    if _has_performance_action(db, current_user, MODULE_ACTION_EDIT_REVIEWS) or _has_performance_action(
        db, current_user, MODULE_ACTION_CREATE
    ) or _has_performance_action(db, current_user, MODULE_ACTION_EDIT):
        accessible = get_accessible_team_ids(db, current_user)
        if accessible is None:
            return list(db.scalars(select(Team.id).where(Team.is_active.is_(True))).all())
        return list(accessible)
    if user_has_module_action(
        current_user,
        get_role_name(db, current_user),
        MODULE_HUMAN_RESOURCES,
        MODULE_ACTION_VIEW,
    ):
        accessible = get_accessible_team_ids(db, current_user)
        if accessible is None:
            return list(db.scalars(select(Team.id).where(Team.is_active.is_(True))).all())
        return list(accessible)
    team_ids = set(
        db.scalars(
            select(Team.id).where(Team.team_lead_id == current_user.id, Team.is_active.is_(True))
        ).all()
    )
    team_ids.update(
        db.scalars(
            select(TeamMember.team_id).where(
                TeamMember.user_id == current_user.id,
                TeamMember.relationship_type.in_(
                    (
                        TeamRelationshipType.team_leader,
                        TeamRelationshipType.engineering_manager,
                        TeamRelationshipType.reviewer,
                    )
                ),
            )
        ).all()
    )
    return list(team_ids)


def _review_load_options():
    return (
        selectinload(PerformanceReviewSheet.employee).selectinload(User.department),
        selectinload(PerformanceReviewSheet.employee).selectinload(User.role),
        selectinload(PerformanceReviewSheet.reviewer),
        selectinload(PerformanceReviewSheet.team),
        selectinload(PerformanceReviewSheet.cycle),
        selectinload(PerformanceReviewSheet.template),
        selectinload(PerformanceReviewSheet.sections).selectinload(
            PerformanceReviewSection.items
        ),
        selectinload(PerformanceReviewSheet.projects),
    )


def _section_notes_label(title: str) -> str | None:
    for section_row in PP_HRD_FO_20_TEMPLATE:
        if section_row["title"] == title:
            return section_row.get("employee_notes_label")
    return None


def _build_section_read(section: PerformanceReviewSection) -> PerformanceReviewSectionRead:
    rated_count = sum(1 for item in section.items if item.rating is not None)
    return PerformanceReviewSectionRead(
        id=section.id,
        title=section.title,
        description=section.description,
        employee_notes=section.employee_notes,
        reviewer_notes=section.reviewer_notes,
        employee_notes_label=_section_notes_label(section.title),
        average_score=section_average_score(section),
        rated_count=rated_count,
        total_count=len(section.items),
        sort_order=section.sort_order,
        items=[
            PerformanceReviewItemRead(
                id=item.id,
                prompt=item.prompt,
                guidance=item.guidance,
                rating=item.rating,
                rating_label=rating_label(item.rating),
                employee_comment=item.employee_comment,
                manager_comment=item.manager_comment,
                sort_order=item.sort_order,
            )
            for item in sorted(section.items, key=lambda row: row.sort_order)
        ],
    )


def _review_to_read(db: Session, sheet: PerformanceReviewSheet, current_user: User) -> PerformanceReviewRead:
    employee_name = f"{sheet.employee.first_name} {sheet.employee.last_name}".strip()
    reviewer_name = f"{sheet.reviewer.first_name} {sheet.reviewer.last_name}".strip()
    can_manage = user_can_manage_team_reviews(db, current_user, sheet.team_id)
    is_self = sheet.employee_id == current_user.id
    rated_count, total_count = sheet_completion_ratio(sheet)
    completion_percent = int(round((rated_count / total_count) * 100)) if total_count else 0
    department_name = None
    if sheet.employee.department is not None:
        department_name = sheet.employee.department.name
    role_name = None
    if sheet.employee.role is not None:
        role_name = sheet.employee.role.name
    company_auto = format_tenure(sheet.employee.joining_date)
    industry_auto = format_tenure(sheet.employee.first_job_date)
    company_experience = sheet.total_experience or company_auto
    industry_experience = sheet.industry_experience or industry_auto
    can_manage = bool(can_manage or sheet.reviewer_id == current_user.id)
    stage = sheet.stage or STAGE_SELF
    can_edit_employee = user_can_edit_review_as_employee(db, current_user, sheet)
    can_edit_manager = user_can_edit_review_as_manager(db, current_user, sheet)
    is_editable = can_edit_employee or can_edit_manager
    return PerformanceReviewRead(
        id=sheet.id,
        cycle_id=sheet.cycle_id,
        cycle_title=sheet.cycle.title if sheet.cycle is not None else None,
        employee_id=sheet.employee_id,
        employee_name=employee_name,
        employee_department=department_name,
        employee_designation=sheet.employee.designation or role_name,
        employee_role=role_name,
        employee_joining_date=sheet.employee.joining_date,
        employee_first_job_date=sheet.employee.first_job_date,
        company_experience=company_experience,
        reviewer_id=sheet.reviewer_id,
        reviewer_name=reviewer_name,
        team_id=sheet.team_id,
        team_name=sheet.team.name if sheet.team is not None else None,
        period_label=sheet.period_label,
        status=sheet.status,
        review_date=sheet.review_date,
        due_date=sheet.due_date,
        review_period_start=sheet.review_period_start,
        review_period_end=sheet.review_period_end,
        total_experience=sheet.total_experience or company_experience,
        industry_experience=industry_experience,
        overall_score=sheet.overall_score,
        overall_score_label=rating_label(sheet.overall_score),
        completion_percent=completion_percent,
        employee_summary=sheet.employee_summary,
        manager_summary=sheet.manager_summary,
        strengths_summary=sheet.strengths_summary,
        improvement_summary=sheet.improvement_summary,
        career_goals=sheet.career_goals,
        submitted_at=sheet.submitted_at,
        acknowledged_at=sheet.acknowledged_at,
        stage=stage,
        template_id=sheet.template_id,
        template_version=sheet.template_version,
        cycle_kind=sheet.cycle.kind if sheet.cycle is not None else None,
        calibration_required=bool(sheet.cycle.calibration_required) if sheet.cycle else False,
        calibration_notes=sheet.calibration_notes,
        acknowledgement_signature=sheet.acknowledgement_signature,
        self_submitted_at=sheet.self_submitted_at,
        manager_submitted_at=sheet.manager_submitted_at,
        calibrated_at=sheet.calibrated_at,
        finalized_at=sheet.finalized_at,
        is_published=bool(getattr(sheet, "is_published", False)),
        published_at=getattr(sheet, "published_at", None),
        published_by_id=getattr(sheet, "published_by_id", None),
        sections=[_build_section_read(section) for section in sorted(sheet.sections, key=lambda row: row.sort_order)],
        projects=[
            PerformanceReviewProjectRead.model_validate(project)
            for project in sorted(sheet.projects, key=lambda row: row.sort_order)
        ],
        is_editable=is_editable,
        can_edit_employee_section=can_edit_employee,
        can_edit_manager_section=can_edit_manager,
        can_acknowledge=bool(
            not bool(getattr(sheet, "is_published", False))
            and is_self
            and stage == STAGE_FINAL
            and sheet.status == "submitted"
        ),
        can_submit_self=bool(
            not bool(getattr(sheet, "is_published", False)) and is_self and stage == STAGE_SELF
        ),
        can_submit_manager=bool(
            not bool(getattr(sheet, "is_published", False))
            and can_manage
            and stage == STAGE_MANAGER
        ),
        can_calibrate=bool(
            not bool(getattr(sheet, "is_published", False))
            and can_manage
            and stage == STAGE_CALIBRATION
        ),
        can_publish=bool(can_manage and not bool(getattr(sheet, "is_published", False))),
        can_delete=bool(can_manage and not bool(getattr(sheet, "is_published", False))),
    )


def _sync_project_complexity(db: Session, project_id: UUID | None, complexity: str | None) -> None:
    if project_id is None or not complexity:
        return
    project = db.get(Project, project_id)
    if project is None:
        return
    try:
        project.complexity = ProjectComplexity(complexity)
    except ValueError:
        return


def _apply_projects(sheet: PerformanceReviewSheet, projects: list, db: Session | None = None) -> None:
    sheet.projects.clear()
    for index, project_row in enumerate(projects):
        complexity = getattr(project_row, "complexity", None)
        sheet.projects.append(
            PerformanceReviewProject(
                project_id=project_row.project_id,
                tool_number=project_row.tool_number,
                part_description=project_row.part_description,
                customer_name=project_row.customer_name,
                assignment_role=project_row.assignment_role,
                hours_logged=project_row.hours_logged,
                execution_status=project_row.execution_status,
                project_stage=project_row.project_stage,
                completed_at=project_row.completed_at,
                contribution_summary=project_row.contribution_summary,
                achievement_notes=project_row.achievement_notes,
                ownership_type=getattr(project_row, "ownership_type", None) or "owned",
                tasks_summary=getattr(project_row, "tasks_summary", None),
                complexity=complexity,
                is_auto_imported=project_row.is_auto_imported,
                sort_order=project_row.sort_order if project_row.sort_order else index,
            )
        )
        if db is not None:
            _sync_project_complexity(db, project_row.project_id, complexity)


def _apply_employee_project_updates(sheet: PerformanceReviewSheet, projects: list) -> None:
    project_by_id = {project.id: project for project in sheet.projects}
    for project_row in projects:
        project = project_by_id.get(project_row.id) if project_row.id is not None else None
        if project is None:
            continue
        if project_row.achievement_notes is not None:
            project.achievement_notes = project_row.achievement_notes
        if project_row.contribution_summary is not None:
            project.contribution_summary = project_row.contribution_summary


def _seed_sections(sheet: PerformanceReviewSheet, structure: list | None = None) -> None:
    template_rows = structure if structure is not None else DEFAULT_REVIEW_TEMPLATE
    for section_index, section_row in enumerate(template_rows):
        section = PerformanceReviewSection(
            sheet=sheet,
            title=str(section_row["title"]),
            description=section_row.get("description"),
            sort_order=section_index,
        )
        for item_index, item_row in enumerate(section_row.get("items", [])):
            if isinstance(item_row, dict):
                section.items.append(
                    PerformanceReviewItem(
                        prompt=str(item_row["prompt"]),
                        guidance=item_row.get("guidance"),
                        sort_order=item_index,
                    )
                )
            else:
                section.items.append(
                    PerformanceReviewItem(
                        prompt=str(item_row),
                        sort_order=item_index,
                    )
                )
        sheet.sections.append(section)


def _apply_manager_sections(sheet: PerformanceReviewSheet, sections: list) -> None:
    """Replace sections wholesale (create / template rebuild paths)."""
    sheet.sections.clear()
    for section_row in sections:
        section = PerformanceReviewSection(
            title=section_row.title,
            description=section_row.description,
            employee_notes=section_row.employee_notes,
            reviewer_notes=section_row.reviewer_notes,
            sort_order=section_row.sort_order,
        )
        for item_row in section_row.items:
            section.items.append(
                PerformanceReviewItem(
                    prompt=item_row.prompt,
                    guidance=item_row.guidance,
                    rating=item_row.rating,
                    employee_comment=item_row.employee_comment,
                    manager_comment=item_row.manager_comment,
                    sort_order=item_row.sort_order,
                )
            )
        sheet.sections.append(section)
    sheet.overall_score = sheet_overall_score(sheet)


def _apply_manager_section_updates(sheet: PerformanceReviewSheet, sections: list) -> None:
    """Persist manager edits on an existing review without replacing section rows."""
    section_by_id = {section.id: section for section in sheet.sections}
    for section_row in sections:
        section = section_by_id.get(section_row.id) if section_row.id is not None else None
        if section is None:
            continue
        if section_row.employee_notes is not None:
            section.employee_notes = section_row.employee_notes
        if section_row.reviewer_notes is not None:
            section.reviewer_notes = section_row.reviewer_notes
        if section_row.title:
            section.title = section_row.title
        if section_row.description is not None:
            section.description = section_row.description
        section.sort_order = section_row.sort_order
        item_by_id = {item.id: item for item in section.items}
        for item_row in section_row.items:
            item = item_by_id.get(item_row.id) if item_row.id is not None else None
            if item is None:
                continue
            if item_row.employee_comment is not None:
                item.employee_comment = item_row.employee_comment
            if item_row.manager_comment is not None:
                item.manager_comment = item_row.manager_comment
            if item_row.rating is not None:
                item.rating = item_row.rating
    sheet.overall_score = sheet_overall_score(sheet)


def _apply_employee_section_updates(sheet: PerformanceReviewSheet, sections: list) -> None:
    section_by_id = {section.id: section for section in sheet.sections}
    for section_row in sections:
        section = section_by_id.get(section_row.id) if section_row.id is not None else None
        if section is None:
            continue
        if section_row.employee_notes is not None:
            section.employee_notes = section_row.employee_notes
        if section_row.reviewer_notes is not None:
            section.reviewer_notes = section_row.reviewer_notes
        item_by_id = {item.id: item for item in section.items}
        for item_row in section_row.items:
            item = item_by_id.get(item_row.id) if item_row.id is not None else None
            if item is None:
                continue
            if item_row.employee_comment is not None:
                item.employee_comment = item_row.employee_comment
            if item_row.rating is not None:
                item.rating = item_row.rating


@router.get("/reviews/template", response_model=PerformanceReviewTemplateRead)
def performance_review_template(
    kind: str | None = Query(default="annual"),
    template_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_default_annual_template(db)
    ensure_default_quarterly_template(db)
    db.commit()
    tmpl = None
    if template_id is not None:
        tmpl = db.get(PerformanceReviewTemplate, template_id)
    elif kind:
        tmpl = get_active_template(db, kind=kind)
    if tmpl is None:
        return PerformanceReviewTemplateRead(
            form_code=FORM_CODE,
            form_title=FORM_TITLE,
            form_revision=FORM_REVISION,
            review_cycle_month=REVIEW_CYCLE_MONTH,
            rating_scale=RATING_SCALE,
            sections=PP_HRD_FO_20_TEMPLATE,
            kind="annual",
            version=1,
        )
    data = template_to_dict(tmpl)
    return PerformanceReviewTemplateRead(
        form_code=data["code"],
        form_title=data["name"],
        form_revision=data["form_revision"],
        review_cycle_month=REVIEW_CYCLE_MONTH,
        rating_scale=data["rating_scale"],
        sections=data["structure"],
        template_id=tmpl.id,
        kind=tmpl.kind,
        version=tmpl.version,
    )


@router.get("/performance/templates", response_model=list[PerformanceReviewTemplateCatalogRead])
def list_performance_templates(
    kind: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_performance_view(db, current_user)
    rows = list_templates(db, kind=kind)
    out: list[PerformanceReviewTemplateCatalogRead] = []
    for row in rows:
        data = template_to_dict(row)
        out.append(
            PerformanceReviewTemplateCatalogRead(
                id=row.id,
                code=row.code,
                name=row.name,
                version=row.version,
                kind=row.kind,
                is_active=row.is_active,
                rating_scale=data["rating_scale"],
                structure=data["structure"],
                form_code=row.code,
                form_title=row.name,
                form_revision=f"v{row.version}",
            )
        )
    db.commit()
    return out


@router.post("/performance/templates", response_model=PerformanceReviewTemplateCatalogRead)
def create_performance_template(
    payload: PerformanceReviewTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _has_performance_action(db, current_user, MODULE_ACTION_MANAGE_TEMPLATES):
        raise HTTPException(status_code=403, detail="Template management access required")
    import json

    row = PerformanceReviewTemplate(
        code=payload.code.strip(),
        name=payload.name.strip(),
        version=payload.version,
        kind=payload.kind,
        is_active=True,
        rating_scale_json=json.dumps([item.model_dump() for item in payload.rating_scale] or RATING_SCALE),
        structure_json=json.dumps([section.model_dump() for section in payload.structure]),
        created_by_id=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    data = template_to_dict(row)
    return PerformanceReviewTemplateCatalogRead(
        id=row.id,
        code=row.code,
        name=row.name,
        version=row.version,
        kind=row.kind,
        is_active=row.is_active,
        rating_scale=data["rating_scale"],
        structure=data["structure"],
        form_code=row.code,
        form_title=row.name,
        form_revision=f"v{row.version}",
    )


@router.get("/performance/dashboard")
def performance_dashboard(
    user_id: UUID | None = Query(default=None),
    team_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_performance_view(db, current_user)
    subject_id = user_id or current_user.id
    subject = db.get(User, subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="User not found")
    if subject.id != current_user.id:
        # Managers/HR can view team members
        managed = _managed_team_ids(db, current_user)
        member_ids = team_member_user_ids(db, managed) if managed else set()
        if subject.id not in member_ids and not (
            _has_performance_action(db, current_user, MODULE_ACTION_EDIT_REVIEWS)
            or user_has_module_action(
                current_user,
                get_role_name(db, current_user),
                MODULE_HUMAN_RESOURCES,
                MODULE_ACTION_VIEW,
            )
        ):
            raise HTTPException(status_code=403, detail="Performance dashboard access denied")
    ensure_default_annual_template(db)
    payload = build_performance_dashboard(
        db, subject=subject, viewer=current_user, team_id=team_id
    )
    db.commit()
    return payload


def _can_view_performance_subject(db: Session, current_user: User, subject: User) -> bool:
    if subject.id == current_user.id:
        return True
    managed = _managed_team_ids(db, current_user)
    member_ids = team_member_user_ids(db, managed) if managed else set()
    if subject.id in member_ids:
        return True
    return bool(
        _has_performance_action(db, current_user, MODULE_ACTION_EDIT_REVIEWS)
        or user_has_module_action(
            current_user,
            get_role_name(db, current_user),
            MODULE_HUMAN_RESOURCES,
            MODULE_ACTION_VIEW,
        )
    )


@router.get("/performance/dossier")
def performance_cycle_dossier(
    user_id: UUID | None = Query(default=None),
    review_year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """July–June quantified cycle dossier for an individual (Gate 0 performance dossier)."""
    from app.services.performance_dossier_service import build_performance_dossier

    _require_performance_view(db, current_user)
    subject_id = user_id or current_user.id
    subject = db.get(User, subject_id)
    if subject is None or subject.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")
    if not _can_view_performance_subject(db, current_user, subject):
        raise HTTPException(status_code=403, detail="Performance dossier access denied")
    return build_performance_dossier(
        db, subject=subject, viewer=current_user, review_year=review_year
    )


@router.get("/performance/dossier-roster")
def performance_cycle_dossier_roster(
    team_id: UUID | None = Query(default=None),
    review_year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Headline cycle KPIs for people the viewer can manage (team / org)."""
    from app.services.performance_dossier_service import build_dossier_roster
    from app.services.performance_review_service import current_review_year

    _require_performance_view(db, current_user)
    managed = _managed_team_ids(db, current_user)
    if team_id is not None:
        if team_id not in managed and not _has_performance_action(
            db, current_user, MODULE_ACTION_EDIT_REVIEWS
        ):
            raise HTTPException(status_code=403, detail="Team access denied")
        team_ids = [team_id]
    else:
        team_ids = managed
    member_ids = list(team_member_user_ids(db, team_ids)) if team_ids else []
    # Leaders always see their own row too when managing a team
    if current_user.id not in member_ids and team_ids:
        member_ids.append(current_user.id)
    if not member_ids:
        member_ids = [current_user.id]
    resolved_year = review_year or current_review_year()
    return {
        "review_year": resolved_year,
        "items": build_dossier_roster(
            db, member_ids=member_ids, review_year=resolved_year
        ),
    }


@router.get("/performance/assignment-fit")
def performance_assignment_fit(
    complexity: str = Query(default="medium"),
    designer_id: UUID | None = Query(default=None),
    surfacer_id: UUID | None = Query(default=None),
    design_leader_id: UUID | None = Query(default=None),
    user_id: UUID | None = Query(default=None),
    role: str = Query(default="designer"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Skill-matrix vs project-complexity fit check for assignment confirmations."""
    _require_performance_view(db, current_user)
    if user_id is not None:
        return evaluate_assignment_skill_fit(
            db, user_id=user_id, complexity=complexity, role=role
        )
    return evaluate_multi_role_fit(
        db,
        complexity=complexity,
        designer_id=designer_id,
        surfacer_id=surfacer_id,
        design_leader_id=design_leader_id,
    )


@router.get("/reviews/suggested-projects", response_model=list[PerformanceReviewProjectSuggestionRead])
def suggested_review_projects(
    employee_id: UUID,
    review_year: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = db.get(User, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    can_view = employee_id == current_user.id
    if not can_view:
        team_ids = list(
            db.scalars(
                select(TeamMember.team_id).where(TeamMember.user_id == employee_id)
            ).all()
        )
        can_view = any(user_can_manage_team_reviews(db, current_user, team_id) for team_id in team_ids)
    if not can_view:
        raise HTTPException(status_code=403, detail="Performance review access denied")
    year = review_year or current_review_year()
    period_start, period_end = review_period_bounds(year)
    rows = discover_employee_projects(
        db,
        employee_id,
        period_start=period_start,
        period_end=period_end,
    )
    return [PerformanceReviewProjectSuggestionRead.model_validate(row) for row in rows]


@router.get("/process-audit", response_model=ProcessAuditRead)
def hr_process_audit(
    sla_days: int = Query(default=14, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Flag incomplete onboarding, missing exit, orphan placement, and access gaps."""
    from app.services import onboarding_checklist_service as onboard

    if not onboard.can_manage_onboarding(db, current_user):
        _require_hr_view(db, current_user)
    raw = process_audit.build_process_audit(db, sla_days=sla_days)
    items: list[ProcessAuditItem] = []
    for row in raw["items"]:
        items.append(
            ProcessAuditItem(
                flag=row["flag"],
                severity=row.get("severity") or "medium",
                title=row["title"],
                subject_name=row["subject_name"],
                subject_user_id=UUID(row["subject_user_id"])
                if row.get("subject_user_id")
                else None,
                checklist_id=UUID(row["checklist_id"]) if row.get("checklist_id") else None,
                exit_interview_id=UUID(row["exit_interview_id"])
                if row.get("exit_interview_id")
                else None,
                detail=row["detail"],
                deep_link=row["deep_link"],
                anchor_date=row.get("anchor_date"),
            )
        )
    return ProcessAuditRead(
        as_of=raw["as_of"],
        sla_days=raw["sla_days"],
        total=raw["total"],
        counts=raw["counts"],
        items=items,
    )


def _training_assignment_read(row) -> TrainingAssignmentRead:
    course = row.course
    return TrainingAssignmentRead(
        id=row.id,
        course_id=row.course_id,
        user_id=row.user_id,
        status=row.status,
        due_date=row.due_date,
        assigned_by_id=row.assigned_by_id,
        completed_at=row.completed_at,
        completed_by_id=row.completed_by_id,
        notes=row.notes,
        onboarding_checklist_id=row.onboarding_checklist_id,
        course_title=course.title if course else None,
        course_code=course.code if course else None,
        estimated_minutes=course.estimated_minutes if course else None,
        external_url=course.external_url if course else None,
        is_required_for_onboarding=bool(course.is_required_for_onboarding) if course else False,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/training/courses", response_model=list[TrainingCourseRead])
def list_training_courses(
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services import onboarding_checklist_service as onboard
    from app.services import training_service as training

    if not onboard.can_manage_onboarding(db, current_user):
        _require_hr_view(db, current_user)
    return [
        TrainingCourseRead.model_validate(row)
        for row in training.list_courses(db, active_only=active_only)
    ]


@router.post("/training/courses", response_model=TrainingCourseRead, status_code=201)
def create_training_course(
    payload: TrainingCourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services import onboarding_checklist_service as onboard
    from app.services import training_service as training

    if not onboard.can_manage_onboarding(db, current_user):
        raise HTTPException(status_code=403, detail="Training course management denied")
    try:
        course = training.create_course(
            db,
            code=payload.code,
            title=payload.title,
            description=payload.description,
            owner_department=payload.owner_department,
            estimated_minutes=payload.estimated_minutes,
            external_url=payload.external_url,
            is_required_for_onboarding=payload.is_required_for_onboarding,
            sort_order=payload.sort_order,
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    db.commit()
    db.refresh(course)
    return TrainingCourseRead.model_validate(course)


@router.get("/training/assignments", response_model=list[TrainingAssignmentRead])
def list_training_assignments(
    user_id: UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services import onboarding_checklist_service as onboard
    from app.services import training_service as training

    can_manage = onboard.can_manage_onboarding(db, current_user)
    if can_manage:
        target = user_id
    else:
        _require_hr_view(db, current_user)
        target = user_id
    rows = training.list_assignments(db, user_id=target, status=status_filter)
    return [_training_assignment_read(row) for row in rows]


@router.get("/training/my-assignments", response_model=list[TrainingAssignmentRead])
def my_training_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services import training_service as training

    rows = training.list_assignments(db, user_id=current_user.id)
    return [_training_assignment_read(row) for row in rows]


@router.post("/training/assign", response_model=list[TrainingAssignmentRead])
def assign_training(
    payload: TrainingAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.training import TrainingCourse
    from app.services import onboarding_checklist_service as onboard
    from app.services import training_service as training

    if not onboard.can_manage_onboarding(db, current_user):
        raise HTTPException(status_code=403, detail="Training assignment denied")
    course = db.get(TrainingCourse, payload.course_id)
    if course is None or not course.is_active:
        raise HTTPException(status_code=404, detail="Course not found")
    rows = training.assign_course_to_users(
        db,
        course=course,
        user_ids=payload.user_ids,
        assigned_by=current_user,
        due_date=payload.due_date,
    )
    db.commit()
    return [_training_assignment_read(row) for row in rows]


@router.post(
    "/training/assignments/{assignment_id}/complete",
    response_model=TrainingAssignmentRead,
)
def complete_training_assignment(
    assignment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.training import TrainingAssignment
    from app.services import onboarding_checklist_service as onboard
    from app.services import training_service as training

    row = db.get(TrainingAssignment, assignment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    can_manage = onboard.can_manage_onboarding(db, current_user)
    if row.user_id != current_user.id and not can_manage:
        raise HTTPException(status_code=403, detail="Cannot complete this training")
    training.complete_assignment(db, assignment=row, actor=current_user)
    db.commit()
    loaded = db.scalar(
        select(TrainingAssignment)
        .where(TrainingAssignment.id == assignment_id)
        .options(selectinload(TrainingAssignment.course))
    )
    return _training_assignment_read(loaded or row)


from app.schemas.past_employees import PastEmployeeRead
from app.services.past_employees_service import list_past_employees as list_past_employees_svc


@router.get("/past-employees", response_model=list[PastEmployeeRead])
def list_past_employees(
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Employees with a last working day — HR historical roster (history retained)."""
    _require_hr_view(db, current_user)
    rows = list_past_employees_svc(db, search=search)
    return [PastEmployeeRead.model_validate(row) for row in rows]


@router.get("/dashboard")
def hr_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_hr_view(db, current_user)
    team_ids, member_ids = _scoped_member_ids(db, current_user)

    pending_timesheets = int(
        db.scalar(
            select(func.count())
            .select_from(Timesheet)
            .where(
                Timesheet.user_id.in_(member_ids),
                Timesheet.status.in_((TimesheetStatus.draft, TimesheetStatus.submitted)),
            )
        )
        or 0
    )
    teams = db.scalars(select(Team).where(Team.id.in_(team_ids))).all() if team_ids else []
    users = (
        db.scalars(
            select(User).where(
                User.id.in_(member_ids),
                User.is_active.is_(True),
                User.is_deleted.is_(False),
            ).order_by(User.last_name, User.first_name)
        ).all()
        if member_ids
        else []
    )

    missing = [
        row
        for row in get_missing_timesheet_rows(db, min_missing_days=1, limit=200)
        if row.user_id in member_ids
    ]

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    user_status = []
    for user in users:
        latest = db.scalar(
            select(Timesheet)
            .where(Timesheet.user_id == user.id)
            .order_by(Timesheet.week_start.desc())
            .limit(1)
        )
        hours_this_week = db.scalar(
            select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
            .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
            .where(
                Timesheet.user_id == user.id,
                TimesheetEntry.is_deleted.is_(False),
                TimesheetEntry.entry_date >= week_start,
                TimesheetEntry.entry_date <= today,
            )
        )
        missing_row = next((row for row in missing if row.user_id == user.id), None)
        user_status.append(
            {
                "id": str(user.id),
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email,
                "team_ids": [str(tid) for tid in get_user_team_ids(db, user.id)],
                "latest_timesheet_status": latest.status.value if latest else "none",
                "latest_week_start": latest.week_start.isoformat() if latest else None,
                "hours_this_week": float(hours_this_week or 0),
                "missing_days": missing_row.missing_days if missing_row else 0,
                "last_entry_date": (
                    missing_row.last_entry_date.isoformat()
                    if missing_row and missing_row.last_entry_date
                    else None
                ),
                "needs_attention": bool(
                    missing_row and missing_row.missing_days >= 3
                )
                or (latest is not None and latest.status == TimesheetStatus.draft),
            }
        )

    attention = [row for row in user_status if row["needs_attention"]]
    attention.sort(key=lambda row: (-row["missing_days"], row["name"]))

    return {
        "teams_managed": len(teams),
        "team_members": len(users),
        "pending_timesheets": pending_timesheets,
        "users_needing_attention": len(attention),
        "leave_placeholder": "Attendance and leave remain in GreytHR (ProTrack module deferred)",
        "onboarding_placeholder": None,
        "onboarding_url": "/hr/onboarding",
        "onboarding_status": "live",
        "teams": [{"id": str(team.id), "name": team.name} for team in teams],
        "users": user_status,
        "timesheet_attention": attention,
    }


@router.get("/timesheet-compliance")
def hr_timesheet_compliance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List users in accessible teams who are behind on timesheet entry."""
    _require_hr_view(db, current_user)
    _, member_ids = _scoped_member_ids(db, current_user)
    rows = [
        {
            "user_id": str(row.user_id),
            "employee_name": row.employee_name,
            "last_entry_date": row.last_entry_date.isoformat() if row.last_entry_date else None,
            "missing_days": row.missing_days,
        }
        for row in get_missing_timesheet_rows(db, min_missing_days=1, limit=200)
        if row.user_id in member_ids
    ]
    return {"items": rows, "total": len(rows)}


@router.get("/teams")
def hr_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_hr_view(db, current_user)
    accessible = get_accessible_team_ids(db, current_user)
    query = select(Team).where(Team.is_active.is_(True)).order_by(Team.name)
    if accessible is not None:
        if not accessible:
            return []
        query = query.where(Team.id.in_(accessible))
    return [
        {"id": str(team.id), "name": team.name, "colour": team.colour}
        for team in db.scalars(query).all()
    ]


@router.get("/performance/skill-matrix", response_model=SkillMatrixRead)
def get_team_skill_matrix(
    team_id: UUID | None = Query(default=None),
    stream_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accessible = get_accessible_team_ids(db, current_user)
    if team_id is not None:
        can_manage = user_can_manage_team_reviews(db, current_user, team_id)
        if accessible is not None and team_id not in accessible and not can_manage:
            raise HTTPException(status_code=403, detail="Team skill matrix access denied")
        matrix = build_team_skill_matrix(db, team_id=team_id, stream_id=stream_id)
    else:
        if accessible is None:
            scope_ids = list(db.scalars(select(Team.id).where(Team.is_active.is_(True))).all())
        else:
            scope_ids = list(accessible)
        if not scope_ids:
            raise HTTPException(status_code=403, detail="Team skill matrix access denied")
        matrix = build_team_skill_matrix(db, team_ids=scope_ids, stream_id=stream_id)
    db.commit()
    return SkillMatrixRead.model_validate(matrix)


@router.get("/performance/skill-gaps", response_model=list[SkillGapRead])
def get_skill_gaps(
    user_id: UUID = Query(...),
    target_proficiency: str = Query("proficient"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.learning_plan_service import skill_gaps_for_user

    _require_performance_view(db, current_user)
    gaps = skill_gaps_for_user(db, user_id, target=target_proficiency)
    return [SkillGapRead.model_validate(gap) for gap in gaps]


@router.get("/performance/learning-plans", response_model=list[LearningPlanRead])
def get_learning_plans(
    user_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.models import StreamSkill
    from app.services.learning_plan_service import list_plans_for_user

    _require_performance_view(db, current_user)
    plans = list_plans_for_user(db, user_id)
    skill_names = {
        row.id: row.name
        for row in db.scalars(select(StreamSkill)).all()
    }
    result: list[LearningPlanRead] = []
    for plan in plans:
        items = [
            LearningPlanItemRead(
                id=item.id,
                plan_id=item.plan_id,
                stream_skill_id=item.stream_skill_id,
                skill_name=skill_names.get(item.stream_skill_id),
                current_proficiency=item.current_proficiency,
                target_proficiency=item.target_proficiency,
                status=item.status,
                due_date=item.due_date,
                notes=item.notes,
                sort_order=item.sort_order,
            )
            for item in plan.items
        ]
        result.append(
            LearningPlanRead(
                id=plan.id,
                user_id=plan.user_id,
                title=plan.title,
                status=plan.status,
                created_by_id=plan.created_by_id,
                items=items,
                created_at=plan.created_at,
                updated_at=plan.updated_at,
            )
        )
    return result


@router.post("/performance/learning-plans/from-gaps", response_model=LearningPlanRead)
def create_learning_plan_from_gaps(
    payload: LearningPlanCreateFromGaps,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.models import StreamSkill
    from app.services.learning_plan_service import create_plan_from_gaps, list_plans_for_user

    _require_performance_view(db, current_user)
    plan = create_plan_from_gaps(
        db,
        user_id=payload.user_id,
        created_by=current_user,
        title=payload.title,
        target=payload.target_proficiency,
    )
    plans = list_plans_for_user(db, payload.user_id)
    loaded = next((row for row in plans if row.id == plan.id), plan)
    skill_names = {
        row.id: row.name
        for row in db.scalars(select(StreamSkill)).all()
    }
    items = [
        LearningPlanItemRead(
            id=item.id,
            plan_id=item.plan_id,
            stream_skill_id=item.stream_skill_id,
            skill_name=skill_names.get(item.stream_skill_id),
            current_proficiency=item.current_proficiency,
            target_proficiency=item.target_proficiency,
            status=item.status,
            due_date=item.due_date,
            notes=item.notes,
            sort_order=item.sort_order,
        )
        for item in getattr(loaded, "items", []) or []
    ]
    return LearningPlanRead(
        id=loaded.id,
        user_id=loaded.user_id,
        title=loaded.title,
        status=loaded.status,
        created_by_id=loaded.created_by_id,
        items=items,
        created_at=loaded.created_at,
        updated_at=loaded.updated_at,
    )


@router.patch("/performance/learning-plan-items/{item_id}", response_model=LearningPlanItemRead)
def patch_learning_plan_item(
    item_id: UUID,
    payload: LearningPlanItemStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.learning_plan_service import update_plan_item_status

    _require_performance_view(db, current_user)
    item = update_plan_item_status(db, item_id=item_id, status=payload.status)
    if item is None:
        raise HTTPException(status_code=404, detail="Learning plan item not found")
    return LearningPlanItemRead.model_validate(item)


@router.put("/performance/skill-matrix", response_model=SkillMatrixUpsertResponse)
def save_team_skill_matrix(
    payload: SkillMatrixUpsertRequest,
    team_id: UUID | None = Query(default=None),
    stream_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accessible = get_accessible_team_ids(db, current_user)
    if team_id is not None:
        if not user_can_manage_team_reviews(db, current_user, team_id):
            raise HTTPException(status_code=403, detail="Team skill matrix edit denied")
        scope_team_id = team_id
        scope_team_ids = None
    else:
        managed = _managed_team_ids(db, current_user)
        if not managed:
            raise HTTPException(status_code=403, detail="Team skill matrix edit denied")
        if accessible is not None:
            managed = [row for row in managed if row in accessible]
        if not managed:
            raise HTTPException(status_code=403, detail="Team skill matrix edit denied")
        scope_team_id = None
        scope_team_ids = managed

    updated = upsert_skill_ratings(
        db,
        ratings=[row.model_dump() for row in payload.ratings],
        assessed_by_id=current_user.id,
    )
    db.commit()
    matrix = build_team_skill_matrix(
        db,
        team_id=scope_team_id,
        team_ids=scope_team_ids,
        stream_id=stream_id,
    )
    db.commit()
    return SkillMatrixUpsertResponse(
        updated_count=updated,
        matrix=SkillMatrixRead.model_validate(matrix),
    )


@router.get("/review-cycles", response_model=list[PerformanceReviewCycleRead])
def list_review_cycles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    managed = _managed_team_ids(db, current_user)
    if not managed and not user_has_module_action(
        current_user,
        get_role_name(db, current_user),
        MODULE_HUMAN_RESOURCES,
        MODULE_ACTION_VIEW,
    ):
        return []
    return db.scalars(
        select(PerformanceReviewCycle)
        .where(PerformanceReviewCycle.is_active.is_(True))
        .order_by(PerformanceReviewCycle.review_year.desc(), PerformanceReviewCycle.title)
    ).all()


@router.post("/review-cycles", response_model=PerformanceReviewCycleRead)
def create_review_cycle(
    payload: PerformanceReviewCycleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_cycle_admin(db, current_user)
    kind = (payload.kind or "annual").strip().lower()
    if kind not in ("annual", "quarterly"):
        raise HTTPException(status_code=400, detail="kind must be annual or quarterly")
    ensure_default_annual_template(db)
    ensure_default_quarterly_template(db)
    template_id = payload.template_id
    if template_id is None:
        default_tmpl = (
            ensure_default_annual_template(db)
            if kind == "annual"
            else ensure_default_quarterly_template(db)
        )
        template_id = default_tmpl.id
    else:
        tmpl = db.get(PerformanceReviewTemplate, template_id)
        if tmpl is None:
            raise HTTPException(status_code=404, detail="Review template not found")
    cycle = PerformanceReviewCycle(
        title=payload.title,
        review_year=payload.review_year,
        kind=kind,
        template_id=template_id,
        calibration_required=bool(payload.calibration_required),
        start_date=payload.start_date,
        end_date=payload.end_date,
        due_date=payload.due_date,
        status=payload.status or "draft",
        created_by_id=current_user.id,
        is_active=True,
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def _get_cycle_or_404(db: Session, cycle_id: UUID) -> PerformanceReviewCycle:
    cycle = db.get(PerformanceReviewCycle, cycle_id)
    if cycle is None or not cycle.is_active:
        raise HTTPException(status_code=404, detail="Review cycle not found")
    return cycle


def _require_cycle_admin(db: Session, user: User) -> None:
    if not (
        _has_performance_action(db, user, MODULE_ACTION_OPEN_CYCLES)
        or user_has_module_action(
            user,
            get_role_name(db, user),
            MODULE_HUMAN_RESOURCES,
            MODULE_ACTION_EDIT,
        )
    ):
        raise HTTPException(status_code=403, detail="Cycle administration access required")


@router.post("/review-cycles/{cycle_id}/open", response_model=PerformanceReviewCycleRead)
def open_review_cycle(
    cycle_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_cycle_admin(db, current_user)
    cycle = _get_cycle_or_404(db, cycle_id)
    if cycle.status not in ("draft", "open"):
        raise HTTPException(status_code=400, detail="Only draft cycles can be opened")
    cycle.status = "open"
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


@router.post("/review-cycles/{cycle_id}/start-calibration", response_model=PerformanceReviewCycleRead)
def start_cycle_calibration(
    cycle_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_cycle_admin(db, current_user)
    cycle = _get_cycle_or_404(db, cycle_id)
    if not cycle.calibration_required:
        raise HTTPException(status_code=400, detail="Calibration is not required for this cycle")
    if cycle.status not in ("open", "in_calibration"):
        raise HTTPException(status_code=400, detail="Cycle must be open before calibration")
    cycle.status = "in_calibration"
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


@router.post("/review-cycles/{cycle_id}/close", response_model=PerformanceReviewCycleRead)
def close_review_cycle(
    cycle_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_cycle_admin(db, current_user)
    cycle = _get_cycle_or_404(db, cycle_id)
    if cycle.status == "closed":
        return cycle
    cycle.status = "closed"
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


@router.get("/reviews/me", response_model=list[PerformanceReviewRead])
def my_performance_reviews(
    review_year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(PerformanceReviewSheet)
        .options(*_review_load_options())
        .where(
            PerformanceReviewSheet.employee_id == current_user.id,
            PerformanceReviewSheet.is_active.is_(True),
        )
        .order_by(PerformanceReviewSheet.created_at.desc())
    )
    if review_year is not None:
        period_start, period_end = review_period_bounds(review_year)
        stmt = stmt.where(
            PerformanceReviewSheet.review_period_start == period_start,
            PerformanceReviewSheet.review_period_end == period_end,
        )
    rows = db.scalars(stmt).all()
    return [_review_to_read(db, row, current_user) for row in rows]


@router.get("/reviews/team-members", response_model=list[PerformanceReviewTeamMemberRead])
def review_team_members(
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    managed_ids = _managed_team_ids(db, current_user)
    if team_id is not None:
        if team_id not in managed_ids and not user_can_manage_team_reviews(db, current_user, team_id):
            raise HTTPException(status_code=403, detail="Team review access denied")
        team_ids = [team_id]
    else:
        team_ids = managed_ids
    if not team_ids:
        return []

    teams = {team.id: team for team in db.scalars(select(Team).where(Team.id.in_(team_ids))).all()}
    user_ids = team_member_user_ids(db, team_ids)
    if not user_ids:
        return []
    review_counts = {
        row[0]: int(row[1] or 0)
        for row in db.execute(
            select(
                PerformanceReviewSheet.employee_id,
                func.count(PerformanceReviewSheet.id),
            )
            .where(
                PerformanceReviewSheet.employee_id.in_(user_ids),
                PerformanceReviewSheet.is_active.is_(True),
            )
            .group_by(PerformanceReviewSheet.employee_id)
        ).all()
    }
    members = db.scalars(
        select(User)
        .where(User.id.in_(user_ids), User.is_deleted.is_(False))
        .order_by(User.last_name, User.first_name)
    ).all()
    rows: list[PerformanceReviewTeamMemberRead] = []
    for member in members:
        member_team_id = next((tid for tid in team_ids if tid in get_user_team_ids(db, member.id)), None)
        if member_team_id is None:
            continue
        team = teams.get(member_team_id)
        rows.append(
            PerformanceReviewTeamMemberRead(
                user_id=member.id,
                name=f"{member.first_name} {member.last_name}".strip(),
                email=member.email,
                team_id=member_team_id,
                team_name=team.name if team is not None else "Team",
                review_count=review_counts.get(member.id, 0),
            )
        )
    return rows


@router.get("/reviews/team", response_model=list[PerformanceReviewRead])
def team_performance_reviews(
    team_id: UUID | None = None,
    kind: str | None = Query(default=None),
    review_year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    managed_ids = _managed_team_ids(db, current_user)
    if team_id is not None:
        if team_id not in managed_ids and not user_can_manage_team_reviews(db, current_user, team_id):
            raise HTTPException(status_code=403, detail="Team review access denied")
        allowed = [team_id]
    else:
        allowed = managed_ids
    if not allowed:
        return []
    stmt = (
        select(PerformanceReviewSheet)
        .options(*_review_load_options())
        .where(
            PerformanceReviewSheet.team_id.in_(allowed),
            PerformanceReviewSheet.is_active.is_(True),
        )
        .order_by(PerformanceReviewSheet.created_at.desc())
    )
    if review_year is not None:
        period_start, period_end = review_period_bounds(review_year)
        stmt = stmt.where(
            PerformanceReviewSheet.review_period_start == period_start,
            PerformanceReviewSheet.review_period_end == period_end,
        )
    rows = list(db.scalars(stmt).all())
    if kind:
        kind_norm = kind.strip().lower()
        rows = [
            row
            for row in rows
            if (row.cycle.kind if row.cycle is not None else "annual") == kind_norm
            or (row.template is not None and row.template.kind == kind_norm)
        ]
    return [_review_to_read(db, row, current_user) for row in rows]


@router.get("/reviews/{review_id}", response_model=PerformanceReviewRead)
def get_performance_review(
    review_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sheet = db.scalar(
        select(PerformanceReviewSheet)
        .options(*_review_load_options())
        .where(PerformanceReviewSheet.id == review_id, PerformanceReviewSheet.is_active.is_(True))
    )
    if sheet is None:
        raise HTTPException(status_code=404, detail="Performance review not found")
    if not user_can_view_review(db, current_user, sheet):
        raise HTTPException(status_code=403, detail="Performance review access denied")
    return _review_to_read(db, sheet, current_user)


@router.post("/reviews", response_model=PerformanceReviewRead)
def create_performance_review(
    payload: PerformanceReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not user_can_create_performance_review(db, current_user, payload.team_id):
        raise HTTPException(status_code=403, detail="Performance review create access denied")
    employee = db.get(User, payload.employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    reviewer = db.get(User, payload.reviewer_id or current_user.id)
    if reviewer is None:
        raise HTTPException(status_code=404, detail="Reviewer not found")

    ensure_default_annual_template(db)
    ensure_default_quarterly_template(db)

    cycle = db.get(PerformanceReviewCycle, payload.cycle_id) if payload.cycle_id else None
    tmpl = None
    if payload.template_id is not None:
        tmpl = db.get(PerformanceReviewTemplate, payload.template_id)
    elif cycle is not None and cycle.template_id is not None:
        tmpl = db.get(PerformanceReviewTemplate, cycle.template_id)
    if tmpl is None:
        kind = cycle.kind if cycle is not None else "annual"
        tmpl = get_active_template(db, kind=kind) or ensure_default_annual_template(db)

    review_year = payload.review_year or current_review_year()
    period_start, period_end = review_period_bounds(review_year)
    period_label = payload.period_label or default_period_label(review_year)

    company_auto = format_tenure(employee.joining_date)
    industry_auto = format_tenure(employee.first_job_date)
    total_experience = payload.total_experience or company_auto
    industry_experience = payload.industry_experience or industry_auto

    initial_stage = STAGE_SELF
    if payload.status == "submitted":
        initial_stage = STAGE_MANAGER

    sheet = PerformanceReviewSheet(
        cycle_id=payload.cycle_id,
        employee_id=payload.employee_id,
        reviewer_id=reviewer.id,
        team_id=payload.team_id,
        template_id=tmpl.id if tmpl is not None else None,
        template_version=tmpl.version if tmpl is not None else None,
        stage=initial_stage,
        period_label=period_label,
        status=payload.status,
        review_date=payload.review_date,
        due_date=payload.due_date,
        review_period_start=period_start,
        review_period_end=period_end,
        total_experience=total_experience,
        industry_experience=industry_experience,
        overall_score=payload.overall_score,
        employee_summary=payload.employee_summary,
        manager_summary=payload.manager_summary,
        strengths_summary=payload.strengths_summary,
        improvement_summary=payload.improvement_summary,
        career_goals=payload.career_goals,
        is_active=True,
    )
    structure = parse_json_list(tmpl.structure_json) if tmpl is not None else None
    if payload.sections:
        _apply_manager_sections(sheet, payload.sections)
    else:
        _seed_sections(sheet, structure)
        sheet.overall_score = sheet_overall_score(sheet)
    if payload.projects:
        _apply_projects(sheet, payload.projects, db)
    else:
        seed_review_projects(
            sheet,
            db,
            period_start=period_start,
            period_end=period_end,
        )
    if sheet.status == "submitted":
        sheet.submitted_at = _utcnow()
        sheet.manager_submitted_at = sheet.submitted_at
    db.add(sheet)
    db.commit()
    db.refresh(sheet)
    sheet = db.scalar(
        select(PerformanceReviewSheet)
        .options(*_review_load_options())
        .where(PerformanceReviewSheet.id == sheet.id)
    )
    assert sheet is not None
    return _review_to_read(db, sheet, current_user)


@router.patch("/reviews/{review_id}", response_model=PerformanceReviewRead)
def update_performance_review(
    review_id: UUID,
    payload: PerformanceReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sheet = db.scalar(
        select(PerformanceReviewSheet)
        .options(*_review_load_options())
        .where(PerformanceReviewSheet.id == review_id, PerformanceReviewSheet.is_active.is_(True))
    )
    if sheet is None:
        raise HTTPException(status_code=404, detail="Performance review not found")
    can_edit_employee = user_can_edit_review_as_employee(db, current_user, sheet)
    can_edit_manager = user_can_edit_review_as_manager(db, current_user, sheet)
    is_self = sheet.employee_id == current_user.id
    stage = sheet.stage or STAGE_SELF
    can_acknowledge_only = bool(
        payload.acknowledged
        and not bool(getattr(sheet, "is_published", False))
        and is_self
        and stage == STAGE_FINAL
        and sheet.status == "submitted"
    )
    if not (can_edit_employee or can_edit_manager or can_acknowledge_only):
        raise HTTPException(status_code=403, detail="Performance review edit access denied")

    if can_edit_manager:
        for field in (
            "review_date",
            "due_date",
            "overall_score",
            "total_experience",
            "industry_experience",
            "employee_summary",
            "manager_summary",
            "strengths_summary",
            "improvement_summary",
            "career_goals",
            "period_label",
            "status",
        ):
            value = getattr(payload, field)
            if value is not None:
                setattr(sheet, field, value)
        if payload.reviewer_id is not None:
            sheet.reviewer_id = payload.reviewer_id
        if payload.team_id is not None:
            if not user_can_manage_team_reviews(db, current_user, payload.team_id):
                raise HTTPException(status_code=403, detail="Target team review access denied")
            sheet.team_id = payload.team_id
        if payload.sections is not None:
            _apply_manager_section_updates(sheet, payload.sections)
        if payload.projects is not None:
            _apply_projects(sheet, payload.projects, db)
        elif payload.import_suggested_projects:
            period_start = sheet.review_period_start
            period_end = sheet.review_period_end
            if period_start is None or period_end is None:
                year = current_review_year()
                period_start, period_end = review_period_bounds(year)
                sheet.review_period_start = period_start
                sheet.review_period_end = period_end
            existing_ids = {row.project_id for row in sheet.projects if row.project_id is not None}
            suggestions = discover_employee_projects(
                db,
                sheet.employee_id,
                period_start=period_start,
                period_end=period_end,
            )
            next_order = len(sheet.projects)
            for row in suggestions:
                if row.get("project_id") in existing_ids:
                    continue
                sheet.projects.append(
                    PerformanceReviewProject(
                        project_id=row.get("project_id"),
                        tool_number=str(row.get("tool_number") or ""),
                        part_description=row.get("part_description"),
                        customer_name=row.get("customer_name"),
                        assignment_role=row.get("assignment_role"),
                        hours_logged=row.get("hours_logged"),
                        execution_status=row.get("execution_status"),
                        project_stage=row.get("project_stage"),
                        completed_at=row.get("completed_at"),
                        contribution_summary=row.get("contribution_summary"),
                        achievement_notes=row.get("achievement_notes"),
                        ownership_type=str(row.get("ownership_type") or "owned"),
                        tasks_summary=row.get("tasks_summary"),
                        complexity=row.get("complexity"),
                        is_auto_imported=True,
                        sort_order=next_order,
                    )
                )
                next_order += 1
        if payload.status == "submitted":
            sheet.submitted_at = _utcnow()
            if (sheet.stage or STAGE_SELF) in (STAGE_SELF, STAGE_MANAGER, STAGE_CALIBRATION):
                sheet.stage = STAGE_FINAL
                sheet.finalized_at = sheet.submitted_at
                if sheet.manager_submitted_at is None:
                    sheet.manager_submitted_at = sheet.submitted_at
    else:
        if can_edit_employee:
            if payload.employee_summary is not None:
                sheet.employee_summary = payload.employee_summary
            if payload.career_goals is not None:
                sheet.career_goals = payload.career_goals
            if payload.sections is not None:
                _apply_employee_section_updates(sheet, payload.sections)
            if payload.projects is not None:
                _apply_employee_project_updates(sheet, payload.projects)
        if payload.acknowledged and can_acknowledge_only:
            # Legacy path: allow acknowledge when manager already submitted
            if (sheet.stage or STAGE_SELF) not in (STAGE_FINAL, STAGE_ACKNOWLEDGED) and sheet.status == "submitted":
                sheet.stage = STAGE_FINAL
                sheet.finalized_at = sheet.finalized_at or _utcnow()
            try:
                advance_sheet_stage(
                    sheet,
                    action="acknowledge",
                    actor=current_user,
                    acknowledgement_signature=payload.acknowledgement_signature,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(sheet)
    db.commit()
    db.refresh(sheet)
    sheet = db.scalar(
        select(PerformanceReviewSheet)
        .options(*_review_load_options())
        .where(PerformanceReviewSheet.id == review_id)
    )
    assert sheet is not None
    return _review_to_read(db, sheet, current_user)


@router.post("/reviews/{review_id}/workflow", response_model=PerformanceReviewRead)
def performance_review_workflow(
    review_id: UUID,
    payload: PerformanceReviewWorkflowAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sheet = db.scalar(
        select(PerformanceReviewSheet)
        .options(*_review_load_options())
        .where(PerformanceReviewSheet.id == review_id, PerformanceReviewSheet.is_active.is_(True))
    )
    if sheet is None:
        raise HTTPException(status_code=404, detail="Performance review not found")

    can_manage = sheet.team_id is not None and user_can_manage_team_reviews(
        db, current_user, sheet.team_id
    )
    can_manage = bool(can_manage or sheet.reviewer_id == current_user.id)
    is_self = sheet.employee_id == current_user.id
    action = payload.action.strip().lower()

    if action == "submit-self" and not is_self:
        raise HTTPException(status_code=403, detail="Only the employee can submit self-review")
    if action in ("submit-manager", "calibrate", "finalize", "reopen") and not can_manage:
        if action == "reopen":
            if not user_has_module_action(
                current_user,
                get_role_name(db, current_user),
                MODULE_HUMAN_RESOURCES,
                MODULE_ACTION_EDIT,
            ):
                raise HTTPException(status_code=403, detail="Reopen requires manager or HR access")
        else:
            raise HTTPException(status_code=403, detail="Manager access required for this action")
    if action == "acknowledge" and not is_self:
        raise HTTPException(status_code=403, detail="Only the employee can acknowledge")

    try:
        advance_sheet_stage(
            sheet,
            action=action,
            actor=current_user,
            calibration_notes=payload.calibration_notes,
            acknowledgement_signature=payload.acknowledgement_signature,
            skip_calibration=payload.skip_calibration,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if action in ("submit-manager", "calibrate", "finalize"):
        sheet.overall_score = sheet_overall_score(sheet)

    db.add(sheet)
    db.commit()
    sheet = db.scalar(
        select(PerformanceReviewSheet)
        .options(*_review_load_options())
        .where(PerformanceReviewSheet.id == review_id)
    )
    assert sheet is not None
    return _review_to_read(db, sheet, current_user)


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_performance_review(
    review_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sheet = db.scalar(
        select(PerformanceReviewSheet).where(
            PerformanceReviewSheet.id == review_id,
            PerformanceReviewSheet.is_active.is_(True),
        )
    )
    if sheet is None:
        raise HTTPException(status_code=404, detail="Performance review not found")
    can_manage = sheet.team_id is not None and user_can_manage_team_reviews(
        db, current_user, sheet.team_id
    )
    is_reviewer = sheet.reviewer_id == current_user.id
    if not (can_manage or is_reviewer):
        raise HTTPException(status_code=403, detail="Performance review delete access denied")
    try:
        from app.services.hr_form_publish import assert_can_delete

        assert_can_delete(sheet, document_label="performance review")
        sheet.is_active = False
        db.add(sheet)
        db.commit()
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return None


@router.post("/reviews/{review_id}/publish", response_model=PerformanceReviewRead)
def publish_performance_review(
    review_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sheet = db.scalar(
        select(PerformanceReviewSheet)
        .options(*_review_load_options())
        .where(
            PerformanceReviewSheet.id == review_id,
            PerformanceReviewSheet.is_active.is_(True),
        )
    )
    if sheet is None:
        raise HTTPException(status_code=404, detail="Performance review not found")
    can_manage = sheet.team_id is not None and user_can_manage_team_reviews(
        db, current_user, sheet.team_id
    )
    is_reviewer = sheet.reviewer_id == current_user.id
    if not (can_manage or is_reviewer):
        raise HTTPException(status_code=403, detail="Performance review publish access denied")
    try:
        from app.services.hr_form_publish import publish_document

        publish_document(sheet, user=current_user)
        db.commit()
        sheet = db.scalar(
            select(PerformanceReviewSheet)
            .options(*_review_load_options())
            .where(PerformanceReviewSheet.id == review_id)
        )
        assert sheet is not None
        return _review_to_read(db, sheet, current_user)
    except ProTrackValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Compensation change requests (hike / promotion) — 2-level approval
# ---------------------------------------------------------------------------
def _person_name(user: User | None) -> str | None:
    if user is None:
        return None
    return " ".join(part for part in (user.first_name, user.last_name) if part).strip() or None


def _comp_to_read(
    db: Session, request: CompensationChangeRequest, current_user: User
) -> CompensationChangeRead:
    employee = db.get(User, request.user_id)
    suggested_by = (
        db.get(User, request.suggested_by_id) if request.suggested_by_id else None
    )
    l1 = db.get(User, request.l1_approver_id) if request.l1_approver_id else None
    l2 = db.get(User, request.l2_approver_id) if request.l2_approver_id else None
    role = db.get(Role, request.new_role_id) if request.new_role_id else None
    wm = (
        db.get(WorkingModel, request.new_working_model_id)
        if request.new_working_model_id
        else None
    )

    can_l1 = (
        request.stage == comp_service.STAGE_SUGGESTED
        and current_user.id != request.suggested_by_id
        and employee is not None
        and comp_service.can_approve_l1(db, current_user, employee)
    )
    can_l2 = (
        request.stage == comp_service.STAGE_L1_APPROVED
        and current_user.id not in {request.suggested_by_id, request.l1_approver_id}
        and employee is not None
        and comp_service.can_approve_l2(db, current_user, employee)
    )
    can_withdraw = request.stage in (
        comp_service.STAGE_SUGGESTED,
        comp_service.STAGE_L1_APPROVED,
    ) and (
        current_user.id == request.suggested_by_id or _user_is_admin(db, current_user)
    )

    # Field-level security: hide actual salary figures from viewers who may act
    # on the request workflow but are not permitted to see compensation amounts.
    show_salary = can_view_salary(current_user, get_role_name(db, current_user))
    hike_pct = request.hike_pct if show_salary else None
    current_salary = request.current_monthly_salary if show_salary else None
    proposed_salary = request.proposed_monthly_salary if show_salary else None

    return CompensationChangeRead(
        id=request.id,
        user_id=request.user_id,
        employee_name=_person_name(employee),
        request_type=request.request_type,
        stage=request.stage,
        status=request.status,
        suggested_by_id=request.suggested_by_id,
        suggested_by_name=_person_name(suggested_by),
        hike_pct=hike_pct,
        currency_code=request.currency_code,
        current_monthly_salary=current_salary,
        proposed_monthly_salary=proposed_salary,
        new_role_id=request.new_role_id,
        new_role_name=role.name if role else None,
        new_designation=request.new_designation,
        new_working_model_id=request.new_working_model_id,
        new_working_model_name=wm.name if wm else None,
        effective_date=request.effective_date,
        justification=request.justification,
        l1_approver_id=request.l1_approver_id,
        l1_approver_name=_person_name(l1),
        l1_at=request.l1_at,
        l2_approver_id=request.l2_approver_id,
        l2_approver_name=_person_name(l2),
        l2_at=request.l2_at,
        applied_at=request.applied_at,
        rejection_reason=request.rejection_reason,
        created_at=request.created_at,
        can_approve_l1=bool(can_l1),
        can_approve_l2=bool(can_l2),
        can_withdraw=bool(can_withdraw),
    )


def _user_is_admin(db: Session, user: User) -> bool:
    from app.core.permissions import is_admin

    return is_admin(db, user)


@router.post(
    "/performance/comp-requests",
    response_model=CompensationChangeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_compensation_request(
    payload: CompensationChangeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_performance_view(db, current_user)
    employee = db.get(User, payload.user_id)
    if employee is None or not employee.is_active:
        raise HTTPException(status_code=404, detail="Employee not found")
    try:
        request = comp_service.create_request(
            db,
            employee=employee,
            actor=current_user,
            request_type=payload.request_type,
            hike_pct=payload.hike_pct,
            effective_date=payload.effective_date,
            justification=payload.justification,
            new_role_id=payload.new_role_id,
            new_designation=payload.new_designation,
            new_working_model_id=payload.new_working_model_id,
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(request)
    return _comp_to_read(db, request, current_user)


@router.get(
    "/performance/comp-requests",
    response_model=list[CompensationChangeRead],
)
def list_compensation_requests(
    stage: str | None = Query(default=None),
    user_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_performance_view(db, current_user)
    query = select(CompensationChangeRequest).order_by(
        CompensationChangeRequest.created_at.desc()
    )
    if stage:
        query = query.where(CompensationChangeRequest.stage == stage)
    if user_id:
        query = query.where(CompensationChangeRequest.user_id == user_id)
    rows = db.scalars(query).all()

    is_admin_user = _user_is_admin(db, current_user)
    result: list[CompensationChangeRead] = []
    for row in rows:
        read = _comp_to_read(db, row, current_user)
        visible = (
            is_admin_user
            or row.suggested_by_id == current_user.id
            or read.can_approve_l1
            or read.can_approve_l2
            or (
                row.l1_approver_id == current_user.id
                or row.l2_approver_id == current_user.id
            )
        )
        if visible:
            result.append(read)
    return result


@router.post(
    "/performance/comp-requests/{request_id}/workflow",
    response_model=CompensationChangeRead,
)
def compensation_request_workflow(
    request_id: UUID,
    payload: CompensationChangeWorkflowAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_performance_view(db, current_user)
    request = db.get(CompensationChangeRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Compensation request not found")
    try:
        comp_service.advance_request(
            db,
            request=request,
            action=payload.action,
            actor=current_user,
            rejection_reason=payload.rejection_reason,
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(request)
    return _comp_to_read(db, request, current_user)


# ---------------------------------------------------------------------------
# Person-level lifecycle actions (promote / billing change / transfer)
# ---------------------------------------------------------------------------
def _require_lifecycle_manage(db: Session, user: User) -> None:
    from app.core.permissions import has_role, is_admin, ENGINEERING_MANAGER

    if is_admin(db, user):
        return
    if has_role(db, user, ENGINEERING_MANAGER):
        return
    if get_role_name(db, user) in comp_service.DIRECTOR_ROLES:
        return
    raise HTTPException(
        status_code=403, detail="Lifecycle changes require manager or admin access"
    )


@router.get(
    "/users/{user_id}/lifecycle",
    response_model=UserLifecycleHistoryRead,
)
def get_user_lifecycle(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_performance_view(db, current_user)
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    events = db.scalars(
        select(UserJobEvent)
        .where(UserJobEvent.user_id == user_id)
        .order_by(UserJobEvent.effective_date.desc())
    ).all()
    periods = db.scalars(
        select(UserWorkingModelPeriod)
        .where(UserWorkingModelPeriod.user_id == user_id)
        .order_by(UserWorkingModelPeriod.effective_from.desc())
    ).all()

    event_reads = [
        UserJobEventRead(
            id=ev.id,
            event_type=ev.event_type,
            effective_date=ev.effective_date,
            from_value=ev.from_value,
            to_value=ev.to_value,
            applied_at=ev.applied_at,
            created_by_name=_person_name(
                db.get(User, ev.created_by_id) if ev.created_by_id else None
            ),
            created_at=ev.created_at,
        )
        for ev in events
    ]
    period_reads = [
        WorkingModelPeriodRead(
            id=p.id,
            working_model_id=p.working_model_id,
            working_model_name=(
                db.get(WorkingModel, p.working_model_id).name
                if p.working_model_id
                and db.get(WorkingModel, p.working_model_id) is not None
                else None
            ),
            effective_from=p.effective_from,
            effective_to=p.effective_to,
            notes=p.notes,
        )
        for p in periods
    ]
    return UserLifecycleHistoryRead(
        events=event_reads, working_model_periods=period_reads
    )


@router.post("/users/{user_id}/promote", status_code=status.HTTP_201_CREATED)
def promote_user(
    user_id: UUID,
    payload: PromoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_lifecycle_manage(db, current_user)
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        user_change_service.record_promotion(
            db,
            user=user,
            new_role_id=payload.new_role_id,
            new_designation=payload.new_designation,
            effective_date=payload.effective_date,
            created_by=current_user,
            notes=payload.notes,
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {"status": "ok"}


@router.post("/users/{user_id}/billing-change", status_code=status.HTTP_201_CREATED)
def change_user_billing(
    user_id: UUID,
    payload: BillingChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_lifecycle_manage(db, current_user)
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        user_change_service.record_billing_change(
            db,
            user=user,
            new_working_model_id=payload.new_working_model_id,
            effective_date=payload.effective_date,
            created_by=current_user,
            notes=payload.notes,
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {"status": "ok"}


@router.post("/users/{user_id}/transfer", status_code=status.HTTP_201_CREATED)
def transfer_user(
    user_id: UUID,
    payload: TransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_lifecycle_manage(db, current_user)
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        user_change_service.record_transfer(
            db,
            user=user,
            target_team_id=payload.target_team_id,
            effective_date=payload.effective_date,
            created_by=current_user,
            update_reporting_manager=payload.update_reporting_manager,
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {"status": "ok"}
