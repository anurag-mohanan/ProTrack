"""Human Resources module — team visibility, timesheets, and performance reviews."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

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
from app.core.access_control import MODULE_HUMAN_RESOURCES
from app.core.module_actions import MODULE_ACTION_VIEW, user_has_module_action
from app.core.permissions import get_role_name
from app.core.team_access import get_accessible_team_ids, team_member_user_ids
from app.models.enums import ProjectComplexity, TeamRelationshipType, TimesheetStatus
from app.models.models import (
    PerformanceReviewCycle,
    PerformanceReviewItem,
    PerformanceReviewProject,
    PerformanceReviewSection,
    PerformanceReviewSheet,
    Project,
    Team,
    TeamMember,
    Timesheet,
    TimesheetEntry,
    User,
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
    PerformanceReviewTemplateRead,
    PerformanceReviewUpdate,
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
    user_can_manage_team_reviews,
    user_can_view_review,
)
from app.services.timesheet_compliance_service import get_missing_timesheet_rows
from app.services.user_team_service import get_user_team_ids

router = APIRouter(prefix="/hr", tags=["human-resources"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
    can_manage = sheet.team_id is not None and user_can_manage_team_reviews(
        db, current_user, sheet.team_id
    )
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
        sections=[_build_section_read(section) for section in sorted(sheet.sections, key=lambda row: row.sort_order)],
        projects=[
            PerformanceReviewProjectRead.model_validate(project)
            for project in sorted(sheet.projects, key=lambda row: row.sort_order)
        ],
        is_editable=bool(can_manage or sheet.reviewer_id == current_user.id),
        can_acknowledge=bool(is_self and sheet.status == "submitted"),
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


def _seed_sections(sheet: PerformanceReviewSheet) -> None:
    for section_index, section_row in enumerate(DEFAULT_REVIEW_TEMPLATE):
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


def _apply_employee_section_updates(sheet: PerformanceReviewSheet, sections: list) -> None:
    section_by_id = {section.id: section for section in sheet.sections}
    for section_row in sections:
        section = section_by_id.get(section_row.id) if section_row.id is not None else None
        if section is None:
            continue
        if section_row.employee_notes is not None:
            section.employee_notes = section_row.employee_notes
        item_by_id = {item.id: item for item in section.items}
        for item_row in section_row.items:
            item = item_by_id.get(item_row.id) if item_row.id is not None else None
            if item is None:
                continue
            if item_row.employee_comment is not None:
                item.employee_comment = item_row.employee_comment


@router.get("/reviews/template", response_model=PerformanceReviewTemplateRead)
def performance_review_template(
    current_user: User = Depends(get_current_user),
):
    return PerformanceReviewTemplateRead(
        form_code=FORM_CODE,
        form_title=FORM_TITLE,
        form_revision=FORM_REVISION,
        review_cycle_month=REVIEW_CYCLE_MONTH,
        rating_scale=RATING_SCALE,
        sections=PP_HRD_FO_20_TEMPLATE,
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
        "leave_placeholder": "Attendance and leave modules coming soon",
        "onboarding_placeholder": "Onboarding module coming soon",
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
    if not user_has_module_action(
        current_user,
        get_role_name(db, current_user),
        MODULE_HUMAN_RESOURCES,
        MODULE_ACTION_EDIT,
    ):
        raise HTTPException(status_code=403, detail="HR edit access required")
    cycle = PerformanceReviewCycle(
        title=payload.title,
        review_year=payload.review_year,
        start_date=payload.start_date,
        end_date=payload.end_date,
        due_date=payload.due_date,
        status=payload.status,
        created_by_id=current_user.id,
        is_active=True,
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


@router.get("/reviews/me", response_model=list[PerformanceReviewRead])
def my_performance_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.scalars(
        select(PerformanceReviewSheet)
        .options(*_review_load_options())
        .where(
            PerformanceReviewSheet.employee_id == current_user.id,
            PerformanceReviewSheet.is_active.is_(True),
        )
        .order_by(PerformanceReviewSheet.created_at.desc())
    ).all()
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
    rows = db.scalars(
        select(PerformanceReviewSheet)
        .options(*_review_load_options())
        .where(
            PerformanceReviewSheet.team_id.in_(allowed),
            PerformanceReviewSheet.is_active.is_(True),
        )
        .order_by(PerformanceReviewSheet.created_at.desc())
    ).all()
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
    if not user_can_manage_team_reviews(db, current_user, payload.team_id):
        raise HTTPException(status_code=403, detail="Team review access denied")
    employee = db.get(User, payload.employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    reviewer = db.get(User, payload.reviewer_id or current_user.id)
    if reviewer is None:
        raise HTTPException(status_code=404, detail="Reviewer not found")

    review_year = payload.review_year or current_review_year()
    period_start, period_end = review_period_bounds(review_year)
    period_label = payload.period_label or default_period_label(review_year)

    company_auto = format_tenure(employee.joining_date)
    industry_auto = format_tenure(employee.first_job_date)
    total_experience = payload.total_experience or company_auto
    industry_experience = payload.industry_experience or industry_auto

    sheet = PerformanceReviewSheet(
        cycle_id=payload.cycle_id,
        employee_id=payload.employee_id,
        reviewer_id=reviewer.id,
        team_id=payload.team_id,
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
    if payload.sections:
        _apply_manager_sections(sheet, payload.sections)
    else:
        _seed_sections(sheet)
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
    can_manage = sheet.team_id is not None and user_can_manage_team_reviews(
        db, current_user, sheet.team_id
    )
    is_reviewer = sheet.reviewer_id == current_user.id
    is_self = sheet.employee_id == current_user.id
    if not (can_manage or is_reviewer or is_self):
        raise HTTPException(status_code=403, detail="Performance review access denied")

    if can_manage or is_reviewer:
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
            _apply_manager_sections(sheet, payload.sections)
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
    else:
        if payload.employee_summary is not None:
            sheet.employee_summary = payload.employee_summary
        if payload.career_goals is not None:
            sheet.career_goals = payload.career_goals
        if payload.sections is not None:
            _apply_employee_section_updates(sheet, payload.sections)
        if payload.projects is not None:
            _apply_employee_project_updates(sheet, payload.projects)
        if payload.acknowledged:
            sheet.status = "acknowledged"
            sheet.acknowledged_at = _utcnow()

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
    sheet.is_active = False
    db.add(sheet)
    db.commit()
    return None
