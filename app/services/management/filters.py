"""Management reporting filters and periods (Indian financial year, April–March, by default).

One filter object drives every section and export so the same population is used everywhere.
The financial year start month comes from company settings (``fy_calendar_service``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ProjectClassification
from app.models.finance import Quote
from app.models.models import Customer, Project, Team, User
from app.services.finance.fy_calendar_service import company_fy_start_month, fy_month_windows
from app.services.management.access import ManagementAccess, ManagementForbidden
from app.services.reporting.engineering_performance import PerformanceFilters
from app.services.reporting.periods import financial_period_bounds, financial_year_label, financial_year_start


@dataclass(frozen=True)
class Period:
    start: date
    end: date
    label: str
    fy_start_month: int
    fy_start_year: int | None = None

    def as_dict(self) -> dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "label": self.label,
            "fy_start_year": self.fy_start_year,
            "fy_start_month": self.fy_start_month,
        }

    def months(self) -> list[tuple[date, date, str]]:
        """Calendar months overlapping the period, clipped to it."""
        out = []
        cursor = date(self.start.year, self.start.month, 1)
        while cursor <= self.end:
            nxt = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
            out.append((max(cursor, self.start), min(nxt - timedelta(days=1), self.end), cursor.strftime("%b %Y")))
            cursor = nxt
        return out

    def previous(self) -> Period:
        """The period of equal length immediately before this one."""
        length = (self.end - self.start).days
        end = self.start - timedelta(days=1)
        start = end - timedelta(days=length)
        return Period(start, end, f"Previous period ({start:%d %b %Y} – {end:%d %b %Y})", self.fy_start_month)


def fy_period(fy_start_year: int, fy_start_month: int) -> Period:
    start = date(fy_start_year, fy_start_month, 1)
    end = date(fy_start_year + 1, fy_start_month, 1) - timedelta(days=1)
    return Period(start, end, financial_year_label(start, fy_start_month), fy_start_month, fy_start_year)


def sub_period(fy_start_year: int, fy_start_month: int, period_type: str, index: int | None) -> Period:
    """Annual, quarterly (index 1–4) or monthly (index 1–12) window inside a financial year."""
    fy = fy_period(fy_start_year, fy_start_month)
    if period_type == "annual":
        return fy
    windows = fy_month_windows(fy.start)
    if period_type == "quarterly":
        if index is None or not 1 <= index <= 4:
            raise ValueError("A quarterly period needs a quarter between 1 and 4")
        first, last = windows[(index - 1) * 3], windows[(index - 1) * 3 + 2]
        return Period(first["month_start"], last["month_end"], f"Q{index} {fy.label}", fy_start_month, fy_start_year)
    if period_type == "monthly":
        if index is None or not 1 <= index <= 12:
            raise ValueError("A monthly period needs a month between 1 and 12")
        window = windows[index - 1]
        return Period(window["month_start"], window["month_end"], f"{window['label']} ({fy.label})",
                      fy_start_month, fy_start_year)
    raise ValueError("period_type must be annual, quarterly or monthly")


def resolve_period(
    db: Session,
    *,
    fy_start_year: int | None = None,
    start: date | None = None,
    end: date | None = None,
    today: date | None = None,
) -> Period:
    """Explicit date range wins; otherwise the requested (or current) financial year."""
    fy_month = company_fy_start_month(db)
    if start is not None or end is not None:
        lo, hi, label = financial_period_bounds("custom", fy_start_month=fy_month, start_date=start, end_date=end)
        return Period(lo, hi, label, fy_month)
    if fy_start_year is None:
        fy_start_year = financial_year_start(today or date.today(), fy_month).year
    if not 2000 <= fy_start_year <= 2100:
        raise ValueError("Financial year is out of range")
    return fy_period(fy_start_year, fy_month)


@dataclass(frozen=True)
class CockpitFilters:
    period: Period
    customer_id: UUID | None = None
    classification: ProjectClassification | None = None
    manager_id: UUID | None = None
    team_id: UUID | None = None
    business_unit: str | None = None
    labels: dict = field(default_factory=dict, compare=False)

    @property
    def narrows_projects(self) -> bool:
        return self.classification is not None or self.manager_id is not None

    def as_dict(self) -> dict:
        return {
            "period": self.period.as_dict(),
            "customer_id": str(self.customer_id) if self.customer_id else None,
            "classification": self.classification.value if self.classification else None,
            "manager_id": str(self.manager_id) if self.manager_id else None,
            "team_id": str(self.team_id) if self.team_id else None,
            "business_unit": self.business_unit,
            "labels": self.labels,
        }

    def with_period(self, period: Period) -> CockpitFilters:
        return CockpitFilters(period, self.customer_id, self.classification, self.manager_id, self.team_id,
                              self.business_unit, self.labels)


def build_filters(
    db: Session,
    access: ManagementAccess,
    *,
    period: Period,
    customer_id: UUID | None = None,
    classification: str | None = None,
    manager_id: UUID | None = None,
    team_id: UUID | None = None,
    business_unit: str | None = None,
) -> CockpitFilters:
    labels: dict[str, str | None] = {"period": period.label}
    parsed: ProjectClassification | None = None
    if classification:
        try:
            parsed = ProjectClassification(classification)
        except ValueError as exc:
            raise ValueError("Unknown project classification") from exc
        labels["classification"] = parsed.value.replace("_", " ").capitalize()
    if customer_id is not None:
        customer = db.get(Customer, customer_id)
        if customer is None:
            raise ValueError("Unknown customer")
        labels["customer"] = customer.name
    if manager_id is not None:
        manager = db.get(User, manager_id)
        if manager is None:
            raise ValueError("Unknown project manager")
        labels["project_manager"] = f"{manager.first_name or ''} {manager.last_name or ''}".strip() or manager.email
    if team_id is not None:
        if access.report_team_ids is not None and team_id not in access.report_team_ids:
            raise ManagementForbidden("Team is outside your reporting scope")
        team = db.get(Team, team_id)
        if team is None:
            raise ValueError("Unknown team")
        labels["team"] = team.name
    bu = (business_unit or "").strip() or None
    if bu:
        labels["business_unit"] = bu
    return CockpitFilters(period, customer_id, parsed, manager_id, team_id, bu, labels)


def effective_team_ids(db: Session, filters: CockpitFilters, access: ManagementAccess) -> frozenset[UUID] | None:
    """Report scope ∩ team filter ∩ business-unit teams (``None`` means every team)."""
    ids = access.report_team_ids
    if filters.team_id is not None:
        ids = frozenset({filters.team_id}) if ids is None else ids & {filters.team_id}
    if filters.business_unit:
        bu = frozenset(db.scalars(select(Team.id).where(Team.business_unit == filters.business_unit)).all())
        ids = bu if ids is None else ids & bu
    return ids


def project_conditions(db: Session, filters: CockpitFilters, access: ManagementAccess) -> list:
    conditions: list = [Project.is_deleted.is_(False)]
    if access.visibility_clause is not None:
        conditions.append(access.visibility_clause)
    teams = effective_team_ids(db, filters, access)
    if teams is not None:
        conditions.append(Project.team_id.in_(teams) if teams else Project.id.is_(None))
    if filters.customer_id is not None:
        conditions.append(Project.customer_id == filters.customer_id)
    if filters.classification is not None:
        conditions.append(Project.project_classification == filters.classification)
    if filters.manager_id is not None:
        conditions.append(Project.design_leader_id == filters.manager_id)
    return conditions


def performance_filters(db: Session, filters: CockpitFilters, access: ManagementAccess) -> PerformanceFilters:
    """The quote-to-delivery / engineering-performance filter for the same population."""
    return PerformanceFilters(
        period_type="custom",
        start_date=filters.period.start,
        end_date=filters.period.end,
        customer_id=filters.customer_id,
        team_ids=effective_team_ids(db, filters, access),
        design_leader_id=filters.manager_id,
        visibility_clause=access.visibility_clause,
    )


def quote_statement(db: Session, filters: CockpitFilters, access: ManagementAccess):
    """Active quotes for the Finance figures. Project-only filters keep quotes linked to matching projects."""
    stmt = select(Quote).where(Quote.is_active.is_(True))
    if filters.customer_id is not None:
        stmt = stmt.where(Quote.customer_id == filters.customer_id)
    teams = effective_team_ids(db, filters, access) if (filters.team_id or filters.business_unit) else None
    if teams is not None:
        stmt = stmt.where(Quote.team_id.in_(teams) if teams else Quote.id.is_(None))
    if filters.narrows_projects:
        projects = select(Project.id).where(*project_conditions(db, filters, access))
        stmt = stmt.where(Quote.project_id.in_(projects))
    return stmt


def filter_options(db: Session, access: ManagementAccess, today: date | None = None) -> dict:
    today = today or date.today()
    fy_month = company_fy_start_month(db)
    current = financial_year_start(today, fy_month).year
    visible = select(Project).where(Project.is_deleted.is_(False))
    if access.visibility_clause is not None:
        visible = visible.where(access.visibility_clause)
    projects = list(db.scalars(visible).all())
    customer_ids = {p.customer_id for p in projects}
    if access.finance:
        customer_ids |= set(db.scalars(select(Quote.customer_id).where(Quote.is_active.is_(True))).all())
    customers = (
        db.scalars(select(Customer).where(Customer.id.in_(customer_ids)).order_by(Customer.name)).all()
        if customer_ids else []
    )
    manager_ids = {p.design_leader_id for p in projects if p.design_leader_id}
    managers = db.scalars(select(User).where(User.id.in_(manager_ids))).all() if manager_ids else []
    teams_stmt = select(Team).where(Team.is_active.is_(True)).order_by(Team.name)
    if access.report_team_ids is not None:
        teams_stmt = teams_stmt.where(Team.id.in_(access.report_team_ids))
    teams = list(db.scalars(teams_stmt).all())
    units = sorted({t.business_unit for t in teams if t.business_unit})
    return {
        "financial_years": [
            {"start_year": y, "label": financial_year_label(date(y, fy_month, 1), fy_month), "is_current": y == current}
            for y in range(current, current - 6, -1)
        ],
        "fy_start_month": fy_month,
        "customers": [{"id": str(c.id), "name": c.name} for c in customers],
        "classifications": [
            {"value": c.value, "label": c.value.replace("_", " ").capitalize()} for c in ProjectClassification
        ],
        "project_managers": sorted(
            ({"id": str(u.id), "name": f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email} for u in managers),
            key=lambda row: row["name"].lower(),
        ),
        "project_manager_basis": "Project manager is the project's design leader (ProTrack has no separate project-manager field).",
        "teams": [{"id": str(t.id), "name": t.name} for t in teams],
        "business_units": units,
        "business_unit_supported": bool(units),
    }
