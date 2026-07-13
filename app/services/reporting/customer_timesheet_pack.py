"""Customer-facing weekly/monthly timesheet pack (Prosohm-style)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.non_productive_categories import is_leave_entry
from app.core.team_access import get_accessible_team_ids
from app.crud.dashboard import _decimal, _round_hours
from app.crud.foundation import get_or_create_company_settings
from app.models.enums import TimesheetStatus, WorkCategory, WorkingModelCode
from app.models.models import (
    Customer,
    Project,
    Role,
    Timesheet,
    TimesheetEntry,
    User,
    WorkingModel,
)
from app.schemas.reporting import (
    CustomerTimesheetAssociateRow,
    CustomerTimesheetPackPayload,
    CustomerTimesheetToolRow,
    ReportPeriod,
)
from app.services.holiday_service import load_holiday_dates
from app.services.kpi_participation import engineering_productivity_users
from app.services.reporting.periods import build_report_period
from app.services.user_team_service import get_user_team_ids

_CUSTOMER_FACING_STATUSES = frozenset(
    {
        TimesheetStatus.submitted,
        TimesheetStatus.approved,
    }
)


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return (numerator * Decimal("100") / denominator).quantize(Decimal("0.01"))


def _iso_week_number(start: date) -> int:
    return int(start.isocalendar()[1])


def build_customer_timesheet_pack(
    db: Session,
    *,
    customer_id: UUID,
    current_user: User,
    period_type: str = "weekly",
    anchor: date | None = None,
    team_id: UUID | None = None,
) -> CustomerTimesheetPackPayload:
    if period_type not in ("weekly", "monthly"):
        period_type = "weekly"

    customer = db.get(Customer, customer_id)
    if customer is None:
        raise KeyError(f"Customer not found: {customer_id}")

    holidays = load_holiday_dates(
        db,
        (anchor or date.today()).replace(day=1) if period_type == "monthly" else (anchor or date.today()),
        anchor or date.today(),
    )
    period = build_report_period(period_type, anchor=anchor, holidays=holidays)
    company = get_or_create_company_settings(db)
    daily_hours = _decimal(company.default_working_hours_per_day)
    working_hours_target = _round_hours(Decimal(period.working_days) * daily_hours)

    scoped_user_ids = _scoped_engineering_user_ids(db, current_user, team_id=team_id)
    entries = _load_customer_entries(
        db,
        customer_id=customer_id,
        period=period,
        user_ids=scoped_user_ids,
    )

    associates = _build_associates(db, entries, working_hours_target)
    tools = _build_tool_rollup(entries)

    total_productive = sum((row.productive_hours for row in associates), Decimal("0"))
    total_np = sum((row.non_productive_hours for row in associates), Decimal("0"))
    total_hours = total_productive + total_np
    expected_capacity = working_hours_target * Decimal(max(len(associates), 1))
    overall_util = _pct(total_hours, expected_capacity)

    title = "WEEKLY TIME SHEET" if period_type == "weekly" else "MONTHLY TIME SHEET"
    return CustomerTimesheetPackPayload(
        report_id="customer-timesheet-pack",
        title=title,
        company_name=company.company_name or "Prosohm",
        customer_id=customer.id,
        customer_name=customer.name,
        period=period,
        week_number=_iso_week_number(period.start_date) if period_type == "weekly" else None,
        working_hours_target=working_hours_target,
        associates=associates,
        tools=tools,
        total_productive_hours=_round_hours(total_productive),
        total_non_productive_hours=_round_hours(total_np),
        total_hours=_round_hours(total_hours),
        overall_utilization_percent=overall_util,
    )


def _scoped_engineering_user_ids(
    db: Session,
    current_user: User,
    *,
    team_id: UUID | None,
) -> set[UUID] | None:
    """None = org-wide; set = restrict to these user IDs."""
    accessible = get_accessible_team_ids(db, current_user)
    if accessible is not None and team_id is not None and team_id not in accessible:
        return set()
    if accessible is None and team_id is None:
        return None

    team_filter: set[UUID] | None
    if team_id is not None:
        team_filter = {team_id}
    else:
        team_filter = accessible

    if team_filter is None:
        return None

    user_ids: set[UUID] = set()
    for uid in engineering_productivity_users(db):
        user_team_ids = set(get_user_team_ids(db, uid.id))
        if uid.team_id:
            user_team_ids.add(uid.team_id)
        if user_team_ids & team_filter:
            user_ids.add(uid.id)
    return user_ids


def _load_customer_entries(
    db: Session,
    *,
    customer_id: UUID,
    period: ReportPeriod,
    user_ids: set[UUID] | None,
) -> list[tuple[TimesheetEntry, User, Project | None]]:
    stmt = (
        select(TimesheetEntry, User, Project)
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .join(User, Timesheet.user_id == User.id)
        .outerjoin(Project, TimesheetEntry.project_id == Project.id)
        .where(
            TimesheetEntry.is_deleted.is_(False),
            TimesheetEntry.entry_date >= period.start_date,
            TimesheetEntry.entry_date <= period.end_date,
            TimesheetEntry.customer_id == customer_id,
            Timesheet.status.in_(tuple(_CUSTOMER_FACING_STATUSES)),
            User.is_active.is_(True),
        )
        .order_by(User.first_name, User.last_name, TimesheetEntry.entry_date)
    )
    if user_ids is not None:
        if not user_ids:
            return []
        stmt = stmt.where(User.id.in_(user_ids))

    rows = db.execute(stmt).all()
    overhead_user_ids = _overhead_user_ids(db)
    return [
        (entry, user, project)
        for entry, user, project in rows
        if user.id not in overhead_user_ids
    ]


def _overhead_user_ids(db: Session) -> set[UUID]:
    overhead_model_ids = set(
        db.scalars(
            select(WorkingModel.id).where(
                WorkingModel.strategy_key == WorkingModelCode.overheads,
            )
        ).all()
    )
    if not overhead_model_ids:
        return set()
    return set(
        db.scalars(
            select(User.id).where(User.default_working_model_id.in_(overhead_model_ids))
        ).all()
    )


def _build_associates(
    db: Session,
    entries: list[tuple[TimesheetEntry, User, Project | None]],
    working_hours_target: Decimal,
) -> list[CustomerTimesheetAssociateRow]:
    by_user: dict[UUID, dict] = {}
    role_names = {
        role.id: role.name
        for role in db.scalars(select(Role)).all()
    }

    for entry, user, _project in entries:
        bucket = by_user.setdefault(
            user.id,
            {
                "user": user,
                "productive": Decimal("0"),
                "np": Decimal("0"),
                "remarks": [],
            },
        )
        hours = _decimal(entry.hours)
        if is_leave_entry(entry):
            bucket["np"] += hours
            if entry.description:
                bucket["remarks"].append(entry.description.strip())
            continue
        if entry.work_category == WorkCategory.non_productive:
            bucket["np"] += hours
            if entry.description:
                bucket["remarks"].append(entry.description.strip())
        else:
            bucket["productive"] += hours
            if entry.description:
                bucket["remarks"].append(entry.description.strip())

    rows: list[CustomerTimesheetAssociateRow] = []
    for index, (_user_id, data) in enumerate(
        sorted(
            by_user.items(),
            key=lambda item: (
                item[1]["user"].first_name or "",
                item[1]["user"].last_name or "",
            ),
        ),
        start=1,
    ):
        user: User = data["user"]
        productive = _round_hours(data["productive"])
        np_hours = _round_hours(data["np"])
        total = _round_hours(productive + np_hours)
        designation = (user.designation or "").strip() or role_names.get(user.role_id, "")
        remarks = "; ".join(dict.fromkeys(r for r in data["remarks"] if r))[:500] or None
        rows.append(
            CustomerTimesheetAssociateRow(
                serial_no=index,
                user_id=user.id,
                associate_name=f"{user.first_name} {user.last_name}".strip(),
                designation=designation or None,
                productive_hours=productive,
                non_productive_hours=np_hours,
                total_hours=total,
                utilization_percent=_pct(total, working_hours_target),
                remarks=remarks,
            )
        )
    return rows


def _build_tool_rollup(
    entries: list[tuple[TimesheetEntry, User, Project | None]],
) -> list[CustomerTimesheetToolRow]:
    hours_by_tool: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    comments_by_tool: dict[str, list[str]] = defaultdict(list)

    for entry, _user, project in entries:
        if is_leave_entry(entry):
            tool = "LEAVE"
        elif entry.work_category == WorkCategory.non_productive and project is None:
            tool = "NON-PRODUCTIVE"
        else:
            tool = (project.tool_number if project is not None else None) or "UNASSIGNED"
        hours_by_tool[tool] += _decimal(entry.hours)
        if entry.description and entry.description.strip():
            comments_by_tool[tool].append(entry.description.strip())

    rows: list[CustomerTimesheetToolRow] = []
    for tool in sorted(hours_by_tool.keys()):
        comments = "; ".join(dict.fromkeys(comments_by_tool[tool]))[:500] or None
        rows.append(
            CustomerTimesheetToolRow(
                tool_number=tool,
                hours=_round_hours(hours_by_tool[tool]),
                comments=comments,
            )
        )
    return rows
