"""Dated user lifecycle changes — promotions, billing (working-model), transfers.

All changes are recorded with an effective date and applied forward:

* if ``effective_date <= today`` the change is applied to the live ``User`` /
  ``employee_cost_profiles`` row immediately;
* otherwise a pending ``UserJobEvent`` is written and activated later by
  :func:`apply_due_lifecycle` (run on startup and on demand).

Team transfers reuse :mod:`app.services.team_transfer_service` (which already
maintains dated ``TeamMembershipPeriod`` rows for finance proration); this
module only adds the audit event alongside.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.models import (
    CompensationChangeRequest,
    Role,
    TeamMember,
    UserJobEvent,
    UserWorkingModelPeriod,
    User,
    WorkingModel,
)

EVENT_TRANSFER = "transfer"
EVENT_PROMOTION = "promotion"
EVENT_BILLING_CHANGE = "billing_change"
EVENT_HIKE = "hike"


def _now() -> datetime:
    return datetime.utcnow()


def _dumps(value: dict) -> str:
    return json.dumps(value, default=str, sort_keys=True)


# ---------------------------------------------------------------------------
# Salary application (mirrors app/api/v1/finance.upsert_employee_cost)
# ---------------------------------------------------------------------------
def apply_salary_change(
    db: Session,
    *,
    user: User,
    new_monthly_salary: Decimal,
    currency_code: str,
    effective_date: date,
) -> None:
    """Overwrite the current employee cost profile with a new monthly salary."""
    from app.models.finance import EmployeeCostProfile
    from app.services.finance.fx_service import to_base_amount

    base_salary, fx_rate, _ = to_base_amount(
        db,
        amount=new_monthly_salary,
        currency_code=currency_code,
        on_date=effective_date,
    )

    row = db.scalar(
        select(EmployeeCostProfile).where(EmployeeCostProfile.user_id == user.id)
    )
    if row is None:
        row = EmployeeCostProfile(
            user_id=user.id,
            currency_code=currency_code,
            monthly_salary=new_monthly_salary,
            hourly_cost=Decimal("0"),
            base_monthly_salary_inr=base_salary,
            base_hourly_cost_inr=Decimal("0"),
            fx_rate=fx_rate,
            effective_from=effective_date,
            is_active=True,
        )
        db.add(row)
    else:
        row.currency_code = currency_code
        row.monthly_salary = new_monthly_salary
        row.base_monthly_salary_inr = base_salary
        row.fx_rate = fx_rate
        row.effective_from = effective_date
    db.flush()


# ---------------------------------------------------------------------------
# Promotion (role / designation)
# ---------------------------------------------------------------------------
def record_promotion(
    db: Session,
    *,
    user: User,
    new_role_id: Optional[UUID] = None,
    new_designation: Optional[str] = None,
    effective_date: date,
    created_by: Optional[User] = None,
    source_request_id: Optional[UUID] = None,
    notes: Optional[str] = None,
) -> UserJobEvent:
    if new_role_id is None and not new_designation:
        raise ProTrackValidationError("A promotion needs a new role or designation")
    if new_role_id is not None and db.get(Role, new_role_id) is None:
        raise ProTrackValidationError("Target role not found")

    from_value = {"role_id": user.role_id, "designation": user.designation}
    to_value = {
        "role_id": new_role_id if new_role_id is not None else user.role_id,
        "designation": new_designation or user.designation,
    }
    event = UserJobEvent(
        user_id=user.id,
        event_type=EVENT_PROMOTION,
        effective_date=effective_date,
        from_value=_dumps(from_value),
        to_value=_dumps(to_value),
        source_request_id=source_request_id,
        created_by_id=created_by.id if created_by else None,
        notes=notes,
    )
    db.add(event)

    if effective_date <= date.today():
        _apply_promotion_event(db, user=user, event=event)
    db.flush()
    return event


def _apply_promotion_event(db: Session, *, user: User, event: UserJobEvent) -> None:
    payload = json.loads(event.to_value or "{}")
    role_id = payload.get("role_id")
    designation = payload.get("designation")
    if role_id:
        user.role_id = UUID(str(role_id)) if not isinstance(role_id, UUID) else role_id
    if designation is not None:
        user.designation = designation
    event.applied_at = _now()
    db.add(user)


# ---------------------------------------------------------------------------
# Billing / working-model change
# ---------------------------------------------------------------------------
def record_billing_change(
    db: Session,
    *,
    user: User,
    new_working_model_id: Optional[UUID],
    effective_date: date,
    created_by: Optional[User] = None,
    source_request_id: Optional[UUID] = None,
    notes: Optional[str] = None,
) -> UserJobEvent:
    if (
        new_working_model_id is not None
        and db.get(WorkingModel, new_working_model_id) is None
    ):
        raise ProTrackValidationError("Target working model not found")

    last_day_before = effective_date - timedelta(days=1)
    open_rows = db.scalars(
        select(UserWorkingModelPeriod).where(
            UserWorkingModelPeriod.user_id == user.id,
            UserWorkingModelPeriod.effective_to.is_(None),
        )
    ).all()
    for row in open_rows:
        row.effective_to = (
            row.effective_from if row.effective_from > last_day_before else last_day_before
        )

    db.add(
        UserWorkingModelPeriod(
            user_id=user.id,
            working_model_id=new_working_model_id,
            effective_from=effective_date,
            effective_to=None,
            source_request_id=source_request_id,
            notes=notes,
        )
    )

    event = UserJobEvent(
        user_id=user.id,
        event_type=EVENT_BILLING_CHANGE,
        effective_date=effective_date,
        from_value=_dumps({"working_model_id": user.default_working_model_id}),
        to_value=_dumps({"working_model_id": new_working_model_id}),
        source_request_id=source_request_id,
        created_by_id=created_by.id if created_by else None,
        notes=notes,
    )
    db.add(event)

    if effective_date <= date.today():
        _apply_billing_event(db, user=user, event=event)
    db.flush()
    return event


def _apply_billing_event(db: Session, *, user: User, event: UserJobEvent) -> None:
    payload = json.loads(event.to_value or "{}")
    wm_id = payload.get("working_model_id")
    user.default_working_model_id = (
        UUID(str(wm_id)) if wm_id and not isinstance(wm_id, UUID) else wm_id
    )
    event.applied_at = _now()
    db.add(user)


# ---------------------------------------------------------------------------
# Transfer (reuse team_transfer_service, add audit event)
# ---------------------------------------------------------------------------
def record_transfer(
    db: Session,
    *,
    user: User,
    target_team_id: UUID,
    effective_date: date,
    created_by: Optional[User] = None,
    update_reporting_manager: bool = True,
) -> UserJobEvent:
    from app.services.team_transfer_service import (
        assign_primary_membership,
        transfer_primary_membership,
    )

    primary_member = db.scalar(
        select(TeamMember).where(
            TeamMember.user_id == user.id,
            TeamMember.is_primary.is_(True),
        )
    )
    source_team_id = primary_member.team_id if primary_member else None

    if primary_member is None:
        assign_primary_membership(
            db,
            user=user,
            target_team_id=target_team_id,
            effective_from=effective_date,
            update_reporting_manager=update_reporting_manager,
        )
    else:
        transfer_primary_membership(
            db,
            user=user,
            source_team_id=primary_member.team_id,
            target_team_id=target_team_id,
            effective_from=effective_date,
            member=primary_member,
            update_reporting_manager=update_reporting_manager,
        )

    event = UserJobEvent(
        user_id=user.id,
        event_type=EVENT_TRANSFER,
        effective_date=effective_date,
        from_value=_dumps({"team_id": source_team_id}),
        to_value=_dumps({"team_id": target_team_id}),
        source_request_id=None,
        created_by_id=created_by.id if created_by else None,
        applied_at=_now() if effective_date <= date.today() else None,
    )
    db.add(event)
    db.flush()
    return event


# ---------------------------------------------------------------------------
# Apply-forward sweep
# ---------------------------------------------------------------------------
def apply_due_lifecycle(db: Session, *, as_of: Optional[date] = None) -> int:
    """Activate any pending lifecycle events whose effective date has arrived."""
    ref = as_of or date.today()
    pending = db.scalars(
        select(UserJobEvent).where(
            UserJobEvent.applied_at.is_(None),
            UserJobEvent.effective_date <= ref,
        )
    ).all()
    applied = 0
    for event in pending:
        user = db.get(User, event.user_id)
        if user is None:
            event.applied_at = _now()
            continue
        if event.event_type == EVENT_PROMOTION:
            _apply_promotion_event(db, user=user, event=event)
            applied += 1
        elif event.event_type == EVENT_BILLING_CHANGE:
            _apply_billing_event(db, user=user, event=event)
            applied += 1
        elif event.event_type == EVENT_HIKE:
            event.applied_at = _now()
            applied += 1
        else:
            event.applied_at = _now()
    if applied:
        db.flush()
    return applied


def apply_due_compensation(db: Session, *, as_of: Optional[date] = None) -> int:
    """Apply approved compensation requests whose effective date has arrived."""
    from app.services.compensation_change_service import (
        STAGE_L2_APPROVED,
        apply_compensation_request,
    )

    ref = as_of or date.today()
    pending = db.scalars(
        select(CompensationChangeRequest).where(
            CompensationChangeRequest.stage == STAGE_L2_APPROVED,
            CompensationChangeRequest.effective_date <= ref,
        )
    ).all()
    applied = 0
    for request in pending:
        apply_compensation_request(db, request=request, as_of=ref)
        applied += 1
    if applied:
        db.flush()
    return applied
