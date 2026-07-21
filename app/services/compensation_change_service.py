"""Compensation change requests — Team Leader suggestion with 2-level approval.

Flow (mirrors the review-engine stage machine):

``suggested`` --approve-l1--> ``l1_approved`` --approve-l2--> ``l2_approved``
--> ``applied`` (on/after the effective date). Any pending stage can move to
``rejected``.

Level 1 = Engineering Manager over the employee's team. Level 2 = Director. On
final approval the change is applied forward: the current salary row is
overwritten and dated ``UserJobEvent`` / lifecycle records are written.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access_control import (
    DIRECTOR_ROLES as ORG_DIRECTOR_ROLES,
    MANAGING_DIRECTOR,
)
from app.core.exceptions import ProTrackValidationError
from app.core.permissions import (
    ADMIN,
    ENGINEERING_MANAGER,
    get_role_name,
    has_role,
    is_admin,
    normalize_role_name,
)
from app.models.enums import TeamRelationshipType
from app.models.models import (
    CompensationChangeRequest,
    OrgDepartment,
    Role,
    TeamMember,
    UserJobEvent,
    User,
    WorkingModel,
)

STAGE_SUGGESTED = "suggested"
STAGE_L1_APPROVED = "l1_approved"
STAGE_L2_APPROVED = "l2_approved"
STAGE_APPLIED = "applied"
STAGE_REJECTED = "rejected"

VALID_STAGES = (
    STAGE_SUGGESTED,
    STAGE_L1_APPROVED,
    STAGE_L2_APPROVED,
    STAGE_APPLIED,
    STAGE_REJECTED,
)

REQUEST_HIKE = "hike"
REQUEST_PROMOTION = "promotion"

# Level-2 approvers: the Managing Director (top authority) and every Director.
# Draws from the standardized org roles so a new Director department is covered
# automatically. The legacy generic "Director" is retained via ORG_DIRECTOR_ROLES.
DIRECTOR_ROLES = frozenset({MANAGING_DIRECTOR}) | ORG_DIRECTOR_ROLES


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _dumps(value: dict) -> str:
    return json.dumps(value, default=str, sort_keys=True)


def _employee_primary_team_id(db: Session, user: User) -> Optional[UUID]:
    member = db.scalar(
        select(TeamMember).where(
            TeamMember.user_id == user.id,
            TeamMember.is_primary.is_(True),
        )
    )
    if member is not None:
        return member.team_id
    return user.team_id


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------
def can_approve_l1(db: Session, actor: User, employee: User) -> bool:
    """Level 1 — Engineering Manager over the employee's team (or Admin)."""
    if is_admin(db, actor):
        return True
    if normalize_role_name(get_role_name(db, actor)) == ENGINEERING_MANAGER:
        return True
    team_id = _employee_primary_team_id(db, employee)
    if team_id is None:
        return False
    rel = db.scalar(
        select(TeamMember.id).where(
            TeamMember.user_id == actor.id,
            TeamMember.team_id == team_id,
            TeamMember.relationship_type == TeamRelationshipType.engineering_manager,
        )
    )
    return rel is not None


def can_approve_l2(db: Session, actor: User, employee: User) -> bool:
    """Level 2 — Director (or Admin, or the employee's org department head)."""
    if is_admin(db, actor):
        return True
    if get_role_name(db, actor) in DIRECTOR_ROLES:
        return True
    dept_id = employee.org_department_id
    if dept_id is not None:
        dept = db.get(OrgDepartment, dept_id)
        if dept is not None and dept.head_user_id == actor.id:
            return True
    return False


def can_suggest(db: Session, actor: User, employee: User) -> bool:
    """Team Leaders (and above) may suggest a hike / promotion."""
    if is_admin(db, actor):
        return True
    if has_role(db, actor, ENGINEERING_MANAGER):
        return True
    if get_role_name(db, actor) in DIRECTOR_ROLES:
        return True
    team_id = _employee_primary_team_id(db, employee)
    if team_id is None:
        return False
    from app.models.models import Team

    team = db.get(Team, team_id)
    if team is not None and team.team_lead_id == actor.id:
        return True
    rel = db.scalar(
        select(TeamMember.id).where(
            TeamMember.user_id == actor.id,
            TeamMember.team_id == team_id,
            TeamMember.relationship_type.in_(
                (
                    TeamRelationshipType.team_leader,
                    TeamRelationshipType.engineering_manager,
                )
            ),
        )
    )
    return rel is not None


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def _current_monthly_salary(db: Session, user: User) -> tuple[Optional[Decimal], str]:
    from app.models.finance import EmployeeCostProfile

    row = db.scalar(
        select(EmployeeCostProfile).where(EmployeeCostProfile.user_id == user.id)
    )
    if row is None:
        return None, "INR"
    return row.monthly_salary, row.currency_code


def create_request(
    db: Session,
    *,
    employee: User,
    actor: User,
    request_type: str = REQUEST_HIKE,
    hike_pct: Optional[Decimal] = None,
    effective_date: date,
    justification: Optional[str] = None,
    new_role_id: Optional[UUID] = None,
    new_designation: Optional[str] = None,
    new_working_model_id: Optional[UUID] = None,
) -> CompensationChangeRequest:
    if request_type not in (REQUEST_HIKE, REQUEST_PROMOTION):
        raise ProTrackValidationError("Invalid request type")
    if not can_suggest(db, actor, employee):
        raise ProTrackValidationError("You are not allowed to suggest changes for this employee")
    if actor.id == employee.id:
        raise ProTrackValidationError("You cannot raise a compensation request for yourself")

    if request_type == REQUEST_PROMOTION and new_role_id is None and not new_designation:
        raise ProTrackValidationError("A promotion needs a target role or designation")
    if new_role_id is not None and db.get(Role, new_role_id) is None:
        raise ProTrackValidationError("Target role not found")
    if (
        new_working_model_id is not None
        and db.get(WorkingModel, new_working_model_id) is None
    ):
        raise ProTrackValidationError("Target working model not found")

    current_salary, currency = _current_monthly_salary(db, employee)
    proposed_salary: Optional[Decimal] = None
    if hike_pct is not None:
        if hike_pct <= 0:
            raise ProTrackValidationError("Hike % must be greater than zero")
        if current_salary is not None:
            proposed_salary = (
                current_salary * (Decimal("1") + hike_pct / Decimal("100"))
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    request = CompensationChangeRequest(
        user_id=employee.id,
        request_type=request_type,
        stage=STAGE_SUGGESTED,
        status="pending",
        suggested_by_id=actor.id,
        hike_pct=hike_pct,
        currency_code=currency,
        current_monthly_salary=current_salary,
        proposed_monthly_salary=proposed_salary,
        new_role_id=new_role_id,
        new_designation=new_designation,
        new_working_model_id=new_working_model_id,
        effective_date=effective_date,
        justification=justification,
    )
    db.add(request)
    db.flush()
    return request


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------
def advance_request(
    db: Session,
    *,
    request: CompensationChangeRequest,
    action: str,
    actor: User,
    rejection_reason: Optional[str] = None,
    as_of: Optional[date] = None,
) -> CompensationChangeRequest:
    employee = db.get(User, request.user_id)
    if employee is None:
        raise ProTrackValidationError("Employee not found")

    if action == "approve-l1":
        if request.stage != STAGE_SUGGESTED:
            raise ProTrackValidationError("Request is not awaiting level 1 approval")
        if actor.id == request.suggested_by_id:
            raise ProTrackValidationError("The suggester cannot approve their own request")
        if not can_approve_l1(db, actor, employee):
            raise ProTrackValidationError("You are not authorized for level 1 approval")
        request.stage = STAGE_L1_APPROVED
        request.l1_approver_id = actor.id
        request.l1_at = _now()

    elif action == "approve-l2":
        if request.stage != STAGE_L1_APPROVED:
            raise ProTrackValidationError("Request is not awaiting level 2 approval")
        if actor.id in {request.suggested_by_id, request.l1_approver_id}:
            raise ProTrackValidationError("A different approver is required for level 2")
        if not can_approve_l2(db, actor, employee):
            raise ProTrackValidationError("You are not authorized for level 2 approval")
        request.stage = STAGE_L2_APPROVED
        request.l2_approver_id = actor.id
        request.l2_at = _now()
        apply_compensation_request(db, request=request, as_of=as_of)

    elif action == "reject":
        if request.stage not in (STAGE_SUGGESTED, STAGE_L1_APPROVED):
            raise ProTrackValidationError("Only pending requests can be rejected")
        if not (
            can_approve_l1(db, actor, employee) or can_approve_l2(db, actor, employee)
        ):
            raise ProTrackValidationError("You are not authorized to reject this request")
        request.stage = STAGE_REJECTED
        request.status = "rejected"
        request.rejection_reason = rejection_reason

    elif action == "withdraw":
        if request.stage in (STAGE_APPLIED, STAGE_REJECTED):
            raise ProTrackValidationError("Request can no longer be withdrawn")
        if actor.id != request.suggested_by_id and not is_admin(db, actor):
            raise ProTrackValidationError("Only the suggester or an admin can withdraw")
        request.stage = STAGE_REJECTED
        request.status = "withdrawn"
        request.rejection_reason = rejection_reason or "Withdrawn by suggester"

    else:
        raise ProTrackValidationError(f"Unknown action: {action}")

    db.flush()
    return request


# ---------------------------------------------------------------------------
# Apply-forward
# ---------------------------------------------------------------------------
def apply_compensation_request(
    db: Session,
    *,
    request: CompensationChangeRequest,
    as_of: Optional[date] = None,
) -> bool:
    """Apply an L2-approved request if its effective date has arrived.

    Returns True when the change was applied, False when it remains pending.
    """
    if request.stage != STAGE_L2_APPROVED:
        return False
    ref = as_of or date.today()
    if request.effective_date > ref:
        request.status = "approved"
        return False

    from app.services.user_change_service import (
        EVENT_HIKE,
        apply_salary_change,
        record_billing_change,
        record_promotion,
    )

    employee = db.get(User, request.user_id)
    if employee is None:
        raise ProTrackValidationError("Employee not found")

    if request.proposed_monthly_salary is not None:
        apply_salary_change(
            db,
            user=employee,
            new_monthly_salary=request.proposed_monthly_salary,
            currency_code=request.currency_code,
            effective_date=request.effective_date,
        )
        db.add(
            UserJobEvent(
                user_id=employee.id,
                event_type=EVENT_HIKE,
                effective_date=request.effective_date,
                from_value=_dumps(
                    {"monthly_salary": request.current_monthly_salary}
                ),
                to_value=_dumps(
                    {
                        "monthly_salary": request.proposed_monthly_salary,
                        "hike_pct": request.hike_pct,
                    }
                ),
                source_request_id=request.id,
                created_by_id=request.l2_approver_id,
                applied_at=_now(),
            )
        )

    if request.request_type == REQUEST_PROMOTION and (
        request.new_role_id is not None or request.new_designation
    ):
        record_promotion(
            db,
            user=employee,
            new_role_id=request.new_role_id,
            new_designation=request.new_designation,
            effective_date=request.effective_date,
            created_by=None,
            source_request_id=request.id,
            notes="Promotion applied via compensation approval",
        )

    if request.new_working_model_id is not None:
        record_billing_change(
            db,
            user=employee,
            new_working_model_id=request.new_working_model_id,
            effective_date=request.effective_date,
            created_by=None,
            source_request_id=request.id,
            notes="Billing change applied via compensation approval",
        )

    request.stage = STAGE_APPLIED
    request.status = "applied"
    request.applied_at = _now()
    db.flush()
    return True
