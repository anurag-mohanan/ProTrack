"""Resolve dynamic report header metadata (customer, managers, period labels)."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.crud.foundation import get_or_create_company_settings
from app.models.enums import TeamRelationshipType
from app.models.models import Contact, Customer, OrgDepartment, Team, TeamMember, User
from app.schemas.reporting import (
    DesignerProductivityRow,
    ReportContextMeta,
    ReportPeriod,
    ReportTeamManagerRow,
    ToolHoursRow,
)
from app.services.reporting.excel.template import format_period_month_year
from app.services.reporting.report_scope import ReportScope


def _user_display_name(user: User | None) -> str | None:
    if user is None:
        return None
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return name or user.email


def _primary_contact(db: Session, customer_id: UUID) -> Contact | None:
    primary = db.scalar(
        select(Contact)
        .where(
            Contact.customer_id == customer_id,
            Contact.is_active.is_(True),
            Contact.is_primary.is_(True),
        )
        .limit(1)
    )
    if primary is not None:
        return primary
    return db.scalar(
        select(Contact)
        .where(Contact.customer_id == customer_id, Contact.is_active.is_(True))
        .order_by(Contact.created_at.asc())
        .limit(1)
    )


def _resolve_customer_meta(
    db: Session,
    *,
    customer_id: UUID | None,
    projects: list[ToolHoursRow],
) -> tuple[str, str | None, str | None, str | None]:
    if customer_id is not None:
        customer = db.get(Customer, customer_id)
        if customer is None:
            return "Not Available", None, None, None
        contact = _primary_contact(db, customer.id)
        contact_name = None
        email = None
        phone = None
        if contact is not None:
            contact_name = f"{contact.first_name} {contact.last_name}".strip() or None
            email = contact.email
            phone = contact.phone
        return customer.name, contact_name, email, phone

    names = sorted(
        {
            (row.customer_name or "").strip()
            for row in projects
            if (row.customer_name or "").strip()
        }
    )
    if not names:
        return "All Customers", None, None, None
    if len(names) == 1:
        # Single customer inferred from project data — still load contact if possible.
        customer = db.scalar(select(Customer).where(Customer.name == names[0]).limit(1))
        if customer is not None:
            contact = _primary_contact(db, customer.id)
            if contact is not None:
                return (
                    customer.name,
                    f"{contact.first_name} {contact.last_name}".strip() or None,
                    contact.email,
                    contact.phone,
                )
        return names[0], None, None, None
    return "Multiple Customers", None, None, None


def _team_engineering_managers(
    db: Session, team_ids: list[UUID]
) -> dict[UUID, str | None]:
    if not team_ids:
        return {}
    teams = db.scalars(
        select(Team)
        .where(Team.id.in_(team_ids))
        .options(selectinload(Team.team_lead), selectinload(Team.org_department))
    ).all()
    members = db.scalars(
        select(TeamMember)
        .where(TeamMember.team_id.in_(team_ids))
        .options(selectinload(TeamMember.user))
    ).all()

    em_by_team: dict[UUID, UUID] = {}
    for member in members:
        if member.relationship_type == TeamRelationshipType.engineering_manager:
            em_by_team.setdefault(member.team_id, member.user_id)

    user_ids = set(em_by_team.values()) | {
        team.team_lead_id for team in teams if team.team_lead_id
    }
    users = {
        user.id: user
        for user in db.scalars(select(User).where(User.id.in_(user_ids))).all()
    } if user_ids else {}

    result: dict[UUID, str | None] = {}
    for team in teams:
        em_id = em_by_team.get(team.id) or team.team_lead_id
        result[team.id] = _user_display_name(users.get(em_id)) if em_id else None
    return result


def build_timesheet_report_context(
    db: Session,
    *,
    current_user: User,
    period: ReportPeriod,
    designers: list[DesignerProductivityRow],
    projects: list[ToolHoursRow],
    scope: ReportScope,
    customer_id: UUID | None = None,
    team_id: UUID | None = None,
) -> ReportContextMeta:
    company = get_or_create_company_settings(db)
    month_name, year, period_display = format_period_month_year(
        period.start_date, period.end_date
    )

    effective_customer_id = scope.customer_id or customer_id
    customer_label, contact_name, contact_email, contact_phone = _resolve_customer_meta(
        db, customer_id=effective_customer_id, projects=projects
    )

    # Resolve teams represented in the report.
    team_names = sorted(
        {(row.team_name or "").strip() for row in designers if (row.team_name or "").strip()}
    )
    team_rows: list[Team] = []
    if team_id is not None:
        team = db.get(Team, team_id)
        if team is not None:
            team_rows = [team]
    elif scope.team_ids:
        team_rows = list(
            db.scalars(select(Team).where(Team.id.in_(list(scope.team_ids)))).all()
        )
    elif team_names:
        team_rows = list(
            db.scalars(select(Team).where(Team.name.in_(team_names))).all()
        )

    managers = _team_engineering_managers(db, [team.id for team in team_rows])
    dept_ids = {team.org_department_id for team in team_rows if team.org_department_id}
    departments = {
        dept.id: dept.name
        for dept in db.scalars(
            select(OrgDepartment).where(OrgDepartment.id.in_(dept_ids))
        ).all()
    } if dept_ids else {}

    team_manager_rows: list[ReportTeamManagerRow] = []
    for team in sorted(team_rows, key=lambda row: row.name.lower()):
        team_manager_rows.append(
            ReportTeamManagerRow(
                team_name=team.name,
                engineering_manager=managers.get(team.id),
                department_name=departments.get(team.org_department_id)
                if team.org_department_id
                else None,
            )
        )

    # Fallback: designers reference team names not resolved as Team rows.
    known_names = {row.team_name for row in team_manager_rows}
    for name in team_names:
        if name not in known_names:
            team_manager_rows.append(
                ReportTeamManagerRow(team_name=name, engineering_manager=None)
            )

    manager_names = [
        row.engineering_manager
        for row in team_manager_rows
        if row.engineering_manager
    ]
    unique_managers = list(dict.fromkeys(manager_names))
    if len(unique_managers) == 1:
        manager_summary = unique_managers[0]
    elif len(unique_managers) > 1:
        manager_summary = "\n".join(
            f"{row.team_name}: {row.engineering_manager}"
            for row in team_manager_rows
            if row.engineering_manager
        )
    else:
        manager_summary = "Not Assigned"

    dept_names = list(
        dict.fromkeys(
            row.department_name for row in team_manager_rows if row.department_name
        )
    )
    department_summary = (
        dept_names[0]
        if len(dept_names) == 1
        else (", ".join(dept_names) if dept_names else None)
    )

    productive = sum((row.productive_hours for row in designers), Decimal("0"))
    non_productive = sum((row.non_productive_hours for row in designers), Decimal("0"))
    leave_days = sum((row.leave_days for row in designers), Decimal("0"))
    total_available = sum((row.available_hours for row in designers), Decimal("0"))
    if total_available > 0:
        avg_util = (productive / total_available * Decimal("100")).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
    else:
        avg_util = Decimal("0")

    generated_by = _user_display_name(current_user)

    return ReportContextMeta(
        period_month=month_name,
        period_year=year,
        period_display=period_display,
        customer_label=customer_label,
        customer_contact_name=contact_name,
        customer_contact_email=contact_email,
        customer_contact_phone=contact_phone,
        teams=team_manager_rows,
        engineering_manager_summary=manager_summary or "Not Assigned",
        department_summary=department_summary,
        generated_by_name=generated_by,
        timezone_name=company.timezone or "Asia/Kolkata",
        audience="customer" if effective_customer_id is not None else "internal",
        total_productive_hours=productive,
        total_non_productive_hours=non_productive,
        total_leave_days=leave_days,
        average_utilization_percent=avg_util.quantize(Decimal("0.1")),
    )
