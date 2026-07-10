"""Project Command Center data assembly."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.crud.foundation import get_or_create_file_path_settings
from app.crud.project_metrics import build_project_read
from app.core.field_normalization import normalize_optional_text
from app.models.enums import (
    EngineeringChangeStatus,
    ExecutionStatus,
    MilestoneStatus,
    ProjectRiskType,
    TimelineStepStatus,
    TimesheetStatus,
)
from app.models.intelligence import EngineeringChange, ProjectDecision
from app.models.models import Contact, Milestone, Project, Team, Timesheet, TimesheetEntry, User
from app.schemas.command_center import (
    CommandCenterHeader,
    CustomerProjectSummary,
    EngineeringChangeRead,
    EngineeringChangeSummary,
    ProjectCommandCenter,
    ProjectDecisionRead,
    ProjectFolderPaths,
    ProjectKpis,
    ProjectRiskItem,
    ProjectTeamSummary,
    TeamMemberCapacity,
    TimelineStep,
)
from app.schemas.timesheet import TimesheetEntryRead
from app.services.project_calculation_service import calculate_hours, get_milestone_summary
from app.services.project_contributor_service import get_project_contributors
from app.services.working_model.engine import WorkingModelEngine


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _user_name(user: User | None) -> str | None:
    if user is None:
        return None
    first = normalize_optional_text(user.first_name) or ""
    last = normalize_optional_text(user.last_name) or ""
    name = f"{first} {last}".strip()
    return name or None


def _days_remaining(due_date: date, today: date) -> int:
    return (due_date - today).days


def _current_milestone_name(milestones: list[Milestone]) -> str | None:
    for milestone in milestones:
        if milestone.status == MilestoneStatus.in_progress:
            return milestone.name
    for milestone in milestones:
        if milestone.status != MilestoneStatus.completed:
            return milestone.name
    return milestones[-1].name if milestones else None


def _build_timeline(milestones: list[Milestone], today: date) -> list[TimelineStep]:
    steps: list[TimelineStep] = []
    current_found = False

    for milestone in milestones:
        if milestone.status == MilestoneStatus.completed:
            status = TimelineStepStatus.completed
        elif milestone.status == MilestoneStatus.in_progress:
            status = TimelineStepStatus.current
            current_found = True
        elif (
            milestone.due_date is not None
            and milestone.due_date < today
            and milestone.status != MilestoneStatus.completed
        ):
            status = TimelineStepStatus.delayed
        elif not current_found and milestone.status != MilestoneStatus.completed:
            status = TimelineStepStatus.current
            current_found = True
        else:
            status = TimelineStepStatus.upcoming

        steps.append(
            TimelineStep(
                milestone_id=milestone.id,
                name=milestone.name,
                sort_order=milestone.sort_order,
                status=status,
                due_date=milestone.due_date,
                completed_at=milestone.completed_at,
            )
        )
    return steps


def _format_folder_template(
    template: str | None,
    *,
    customer_code: str,
    tool_number: str,
    project_code: str,
) -> str | None:
    if not template:
        return None
    return (
        template.replace("{customer_code}", customer_code or "")
        .replace("{tool_number}", tool_number or "")
        .replace("{project_code}", project_code or "")
        .replace("{customer}", customer_code or "")
        .strip()
    )


def _resolve_folders(db: Session, project: Project) -> ProjectFolderPaths:
    settings = get_or_create_file_path_settings(db)
    customer = project.customer
    customer_code = customer.code or customer.name.replace(" ", "")[:20]

    return ProjectFolderPaths(
        project_folder_path=project.project_folder_path,
        cad_folder_path=project.cad_folder_path,
        released_folder_path=project.released_folder_path,
        suggested_project_folder=_format_folder_template(
            settings.project_root_folder,
            customer_code=customer_code,
            tool_number=project.tool_number,
            project_code=project.code,
        ),
        suggested_cad_folder=_format_folder_template(
            settings.design_folder_template,
            customer_code=customer_code,
            tool_number=project.tool_number,
            project_code=project.code,
        ),
        suggested_released_folder=_format_folder_template(
            settings.drawing_folder_template,
            customer_code=customer_code,
            tool_number=project.tool_number,
            project_code=project.code,
        ),
    )


def _designer_allocated_hours(db: Session, user_id: UUID) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(Project.quoted_hours), 0)).where(
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
            Project.execution_status.in_(
                (
                    ExecutionStatus.currently_being_worked_on,
                    ExecutionStatus.on_hold,
                )
            ),
            or_(Project.designer_id == user_id, Project.design_leader_id == user_id),
        )
    )
    return _decimal(total)


def _member_capacity(db: Session, user: User, role: str) -> TeamMemberCapacity:
    working_days = user.working_days or "Mon,Tue,Wed,Thu,Fri"
    day_count = len([day for day in working_days.split(",") if day.strip()])
    weekly_capacity = _decimal(user.working_hours_per_day or 8) * Decimal(day_count)
    allocated = _designer_allocated_hours(db, user.id)
    available = max(weekly_capacity - allocated, Decimal("0"))
    return TeamMemberCapacity(
        user_id=user.id,
        name=_user_name(user) or "Unknown",
        role=role,
        capacity_hours=_round(weekly_capacity),
        allocated_hours=_round(allocated),
        available_hours=_round(available),
        availability_status=(
            user.availability_status.value if user.availability_status else "available"
        ),
    )


def _build_team_summary(db: Session, project: Project) -> ProjectTeamSummary:
    team = db.get(Team, project.team_id) if project.team_id else None
    engineering_manager = (
        db.get(User, team.team_lead_id) if team and team.team_lead_id else None
    )
    design_leader = db.get(User, project.design_leader_id)
    designer = db.get(User, project.designer_id) if project.designer_id else None
    surfacer = db.get(User, project.surfacer_id) if project.surfacer_id else None

    members: list[TeamMemberCapacity] = []
    if design_leader:
        members.append(_member_capacity(db, design_leader, "Design Leader"))
    if designer and designer.id != design_leader.id:
        members.append(_member_capacity(db, designer, "Designer"))
    if surfacer:
        members.append(_member_capacity(db, surfacer, "Surfacer"))

    return ProjectTeamSummary(
        engineering_manager_name=_user_name(engineering_manager),
        design_leader_name=_user_name(design_leader),
        designer_name=_user_name(designer),
        surfacer_name=_user_name(surfacer),
        team_name=team.name if team else None,
        team_colour=team.colour if team else None,
        members=members,
    )


def _build_customer_summary(db: Session, customer) -> CustomerProjectSummary:
    active = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.customer_id == customer.id,
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                Project.execution_status.notin_(
                    (ExecutionStatus.completed, ExecutionStatus.cancelled)
                ),
            )
        )
        or 0
    )
    completed = int(
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.customer_id == customer.id,
                Project.is_deleted.is_(False),
                Project.execution_status == ExecutionStatus.completed,
            )
        )
        or 0
    )
    avg_hours = _decimal(
        db.scalar(
            select(func.avg(Project.actual_hours)).where(
                Project.customer_id == customer.id,
                Project.is_deleted.is_(False),
                Project.actual_hours > 0,
            )
        )
    )

    primary_contact = db.scalar(
        select(Contact)
        .where(Contact.customer_id == customer.id, Contact.is_primary.is_(True))
        .limit(1)
    )
    if primary_contact is None:
        primary_contact = db.scalar(
            select(Contact)
            .where(Contact.customer_id == customer.id, Contact.is_active.is_(True))
            .order_by(Contact.created_at)
            .limit(1)
        )

    return CustomerProjectSummary(
        customer_id=customer.id,
        customer_name=customer.name,
        customer_code=customer.code,
        primary_contact_name=(
            f"{primary_contact.first_name} {primary_contact.last_name}"
            if primary_contact
            else None
        ),
        primary_contact_email=primary_contact.email if primary_contact else None,
        active_projects=active,
        completed_projects=completed,
        average_hours=_round(avg_hours),
    )


def _detect_risks(db: Session, project: Project, milestones: list[Milestone], hours, today: date):
    risks: list[ProjectRiskItem] = []
    engine = WorkingModelEngine(db)
    allowed_risks = engine.applicable_risk_types(project)

    if ProjectRiskType.overdue in allowed_risks and project.due_date < today and project.execution_status not in (
        ExecutionStatus.completed,
        ExecutionStatus.cancelled,
    ):
        risks.append(
            ProjectRiskItem(
                risk_type=ProjectRiskType.overdue,
                severity="critical",
                title="Project overdue",
                detail=f"Due date was {project.due_date.isoformat()}",
            )
        )

    if (
        ProjectRiskType.hours_over_quote in allowed_risks
        and engine.should_flag_hours_over_quote(project, hours)
    ):
        risks.append(
            ProjectRiskItem(
                risk_type=ProjectRiskType.hours_over_quote,
                severity="high",
                title="Hours exceeding quote",
                detail=f"Actual {hours.actual}h vs quoted {hours.quoted}h",
            )
        )

    if ProjectRiskType.milestone_delay in allowed_risks:
        for milestone in milestones:
            if (
                milestone.due_date is not None
                and milestone.due_date < today
                and milestone.status != MilestoneStatus.completed
            ):
                risks.append(
                    ProjectRiskItem(
                        risk_type=ProjectRiskType.milestone_delay,
                        severity="high",
                        title=f"Delayed milestone: {milestone.name}",
                        detail=f"Due {milestone.due_date.isoformat()}",
                    )
                )

    if ProjectRiskType.missing_approvals in allowed_risks:
        pending_approvals = int(
            db.scalar(
                select(func.count(func.distinct(Timesheet.id)))
                .join(TimesheetEntry, TimesheetEntry.timesheet_id == Timesheet.id)
                .where(
                    TimesheetEntry.project_id == project.id,
                    Timesheet.status == TimesheetStatus.submitted,
                )
            )
            or 0
        )
        if pending_approvals > 0:
            risks.append(
                ProjectRiskItem(
                    risk_type=ProjectRiskType.missing_approvals,
                    severity="medium",
                    title="Pending timesheet approvals",
                    detail=f"{pending_approvals} submitted timesheet(s) awaiting approval",
                )
            )

    if ProjectRiskType.designer_overloaded in allowed_risks and project.designer_id:
        active_count = int(
            db.scalar(
                select(func.count())
                .select_from(Project)
                .where(
                    Project.designer_id == project.designer_id,
                    Project.id != project.id,
                    Project.is_deleted.is_(False),
                    Project.is_archived.is_(False),
                    Project.execution_status
                    == ExecutionStatus.currently_being_worked_on,
                )
            )
            or 0
        )
        if active_count >= 1:
            risks.append(
                ProjectRiskItem(
                    risk_type=ProjectRiskType.designer_overloaded,
                    severity="medium",
                    title="Designer has multiple active projects",
                    detail=f"{active_count + 1} active projects assigned",
                )
            )

    return risks


def _decision_to_read(db: Session, decision: ProjectDecision) -> ProjectDecisionRead:
    user = db.get(User, decision.user_id)
    milestone_name = None
    if decision.milestone_id:
        milestone = db.get(Milestone, decision.milestone_id)
        milestone_name = milestone.name if milestone else None
    return ProjectDecisionRead(
        id=decision.id,
        project_id=decision.project_id,
        user_id=decision.user_id,
        user_name=_user_name(user),
        category=decision.category,
        comment=decision.comment,
        milestone_id=decision.milestone_id,
        milestone_name=milestone_name,
        created_at=decision.created_at,
        updated_at=decision.updated_at,
    )


def get_project_command_center(db: Session, project_id: UUID) -> ProjectCommandCenter | None:
    project = db.get(Project, project_id)
    if project is None:
        return None

    today = date.today()
    customer = project.customer
    completed, remaining, progress = get_milestone_summary(db, project_id)
    hours = calculate_hours(db, project)

    milestones = db.scalars(
        select(Milestone)
        .where(Milestone.project_id == project_id)
        .order_by(Milestone.sort_order)
    ).all()

    current_milestone = _current_milestone_name(milestones)
    days_remaining = _days_remaining(project.due_date, today)
    wm_engine = WorkingModelEngine(db)
    wm_kpis = wm_engine.calculate_kpis(project, hours=hours, today=today)
    if wm_kpis is None:
        budget_pct = (
            _round((hours.actual / hours.quoted) * Decimal("100"))
            if hours.quoted > 0
            else Decimal("0")
        )
        variance_pct = (
            _round((hours.variance / hours.quoted) * Decimal("100"))
            if hours.quoted > 0
            else Decimal("0")
        )
        kpis = ProjectKpis(
            completion_percent=progress,
            quoted_hours=hours.quoted,
            actual_hours=hours.actual,
            remaining_hours=hours.remaining,
            variance=hours.variance,
            variance_percent=variance_pct,
            budget_consumption_percent=budget_pct,
            days_remaining=days_remaining,
            current_milestone=current_milestone,
        )
    else:
        kpis = ProjectKpis(
            completion_percent=progress,
            quoted_hours=wm_kpis.quoted_hours,
            actual_hours=wm_kpis.actual_hours,
            remaining_hours=wm_kpis.remaining_hours,
            variance=wm_kpis.variance,
            variance_percent=wm_kpis.variance_percent,
            budget_consumption_percent=wm_kpis.budget_consumption_percent,
            days_remaining=days_remaining,
            current_milestone=current_milestone,
            working_model_id=wm_kpis.working_model_id,
            working_model_code=wm_kpis.working_model_code,
            working_model_name=wm_kpis.working_model_name,
            strategy_key=wm_kpis.strategy_key.value,
            show_quoted_variance=wm_kpis.show_quoted_variance,
            show_over_budget_indicators=wm_kpis.show_over_budget_indicators,
            model_metrics=wm_kpis.model_metrics,
        )

    recent_entries = db.scalars(
        select(TimesheetEntry)
        .where(TimesheetEntry.project_id == project_id)
        .order_by(TimesheetEntry.entry_date.desc(), TimesheetEntry.created_at.desc())
        .limit(10)
    ).all()

    ec_rows = db.scalars(
        select(EngineeringChange)
        .where(EngineeringChange.project_id == project_id)
        .order_by(EngineeringChange.created_at.desc())
    ).all()
    open_count = sum(1 for row in ec_rows if row.status == EngineeringChangeStatus.open)
    closed_count = sum(1 for row in ec_rows if row.status == EngineeringChangeStatus.closed)
    ec_hours = sum((row.hours for row in ec_rows), Decimal("0"))

    decisions = db.scalars(
        select(ProjectDecision)
        .where(ProjectDecision.project_id == project_id)
        .order_by(ProjectDecision.created_at.desc())
        .limit(50)
    ).all()

    team = db.get(Team, project.team_id) if project.team_id else None
    designer = db.get(User, project.designer_id) if project.designer_id else None

    return ProjectCommandCenter(
        project=build_project_read(db, project),
        header=CommandCenterHeader(
            tool_number=project.tool_number,
            part_description=project.part_description,
            customer_name=customer.name,
            team_name=team.name if team else None,
            designer_name=_user_name(designer),
            project_stage=project.project_stage,
            execution_status=project.execution_status,
            current_milestone=current_milestone,
            completion_percent=progress,
            health=project.health,
            priority=project.priority,
            days_remaining=days_remaining,
        ),
        timeline=_build_timeline(milestones, today),
        kpis=kpis,
        team=_build_team_summary(db, project),
        customer_summary=_build_customer_summary(db, customer),
        decisions=[_decision_to_read(db, row) for row in decisions],
        recent_timesheets=[
            TimesheetEntryRead.model_validate(entry, from_attributes=True)
            for entry in recent_entries
        ],
        engineering_changes=EngineeringChangeSummary(
            open_count=open_count,
            closed_count=closed_count,
            total_hours=_round(ec_hours),
            items=[
                EngineeringChangeRead.model_validate(row, from_attributes=True)
                for row in ec_rows[:20]
            ],
        ),
        risks=_detect_risks(db, project, milestones, hours, today),
        folders=_resolve_folders(db, project),
        hours={
            "quoted": hours.quoted,
            "actual": hours.actual,
            "remaining": hours.remaining,
            "variance": hours.variance,
        },
        milestone_summary={
            "completed": completed,
            "remaining": remaining,
            "progress_percent": progress,
        },
        contributors=get_project_contributors(db, project_id),
    )
