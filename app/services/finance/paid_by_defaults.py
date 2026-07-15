"""Resolve default paid_by from team commercial who-pays flags + cost centre."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ExpensePaidBy
from app.models.finance import CostCentre, TeamCommercialTerms

SOFTWARE_CODES = frozenset({"SW_LICENSES", "SW_RENEWALS"})
HARDWARE_CODES = frozenset({"HARDWARE", "SERVERS", "CLOUD"})


def _active_terms_for_team(db: Session, team_id: UUID, *, today: date | None = None) -> TeamCommercialTerms | None:
    today = today or date.today()
    rows = db.scalars(
        select(TeamCommercialTerms)
        .where(
            TeamCommercialTerms.team_id == team_id,
            TeamCommercialTerms.is_active.is_(True),
        )
        .order_by(TeamCommercialTerms.effective_from.desc())
    ).all()
    for row in rows:
        if row.effective_from and row.effective_from > today:
            continue
        if row.effective_to and row.effective_to < today:
            continue
        return row
    return None


def cost_centre_group(code: str) -> str | None:
    upper = (code or "").upper()
    if upper in SOFTWARE_CODES or upper.startswith("SW_"):
        return "software"
    if upper in HARDWARE_CODES:
        return "hardware"
    return None


def default_paid_by(
    db: Session,
    *,
    team_id: UUID,
    cost_centre_id: UUID,
    today: date | None = None,
) -> ExpensePaidBy:
    centre = db.get(CostCentre, cost_centre_id)
    if centre is None:
        return ExpensePaidBy.prosohm
    group = cost_centre_group(centre.code)
    if group is None:
        return ExpensePaidBy.prosohm
    terms = _active_terms_for_team(db, team_id, today=today)
    if terms is None:
        return ExpensePaidBy.prosohm
    if group == "software" and terms.customer_pays_software:
        return ExpensePaidBy.customer
    if group == "hardware" and terms.customer_pays_hardware:
        return ExpensePaidBy.customer
    return ExpensePaidBy.prosohm
