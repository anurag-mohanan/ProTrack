"""Resource Planning — shift masters, assignments, and calendar."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.access_control import (
    MODULE_RESOURCE_PLANNING,
    SPECIAL_ASSIGN_RESOURCE_SHIFTS,
    SPECIAL_MANAGE_RESOURCE_SHIFTS,
    SPECIAL_VIEW_RESOURCE_PLANNING,
    normalize_role_name,
    user_has_module,
    user_has_special,
)
from app.core.permissions import get_role_name
from app.models.models import User
from app.models.resource_shifts import ResourceShiftAssignment
from app.schemas.resource_shifts import (
    ShiftAssignmentBulkCreate,
    ShiftAssignmentBulkResult,
    ShiftAssignmentCreate,
    ShiftAssignmentEnd,
    ShiftAssignmentRead,
    ShiftBoard,
    ShiftBulkReassignRequest,
    ShiftCalendar,
    ShiftCreate,
    ShiftForUser,
    ShiftOverview,
    ShiftRead,
    ShiftReassignRequest,
    ShiftUpdate,
)
from app.services import resource_shift_service
from app.services.resource_shift_service import (
    ShiftConflictError,
    ShiftValidationError,
)

router = APIRouter(
    prefix="/resource-planning",
    tags=["resource-planning-shifts"],
    dependencies=[Depends(get_current_user)],
)


def _role_name(db: Session, user: User) -> str:
    return normalize_role_name(get_role_name(db, user))


def _require_view(db: Session, user: User) -> None:
    role = _role_name(db, user)
    if user_has_module(user, role, MODULE_RESOURCE_PLANNING) or user_has_special(
        user, role, SPECIAL_VIEW_RESOURCE_PLANNING
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Requires the Resource Planning module or view_resource_planning permission.",
    )


def _require_manage(db: Session, user: User) -> None:
    role = _role_name(db, user)
    if user_has_special(user, role, SPECIAL_MANAGE_RESOURCE_SHIFTS):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Requires the 'manage_resource_shifts' permission.",
    )


def _require_assign(db: Session, user: User) -> None:
    role = _role_name(db, user)
    if user_has_special(user, role, SPECIAL_ASSIGN_RESOURCE_SHIFTS) or user_has_special(
        user, role, SPECIAL_MANAGE_RESOURCE_SHIFTS
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Requires the 'assign_resource_shifts' permission.",
    )


def _assignment_payload(db: Session, assignment: ResourceShiftAssignment) -> dict:
    shift = resource_shift_service.get_shift(db, assignment.shift_id)
    user = db.get(User, assignment.user_id)
    config = resource_shift_service._rotation_config(assignment)
    sequence_raw = config.get("sequence") or []
    sequence: list = []
    for item in sequence_raw:
        try:
            sequence.append(UUID(str(item)))
        except (ValueError, TypeError):
            continue
    segments = resource_shift_service._sequence_segments(config)
    slot_days = config.get("slot_days")
    return {
        "id": assignment.id,
        "user_id": assignment.user_id,
        "shift_id": assignment.shift_id,
        "assignment_type": assignment.assignment_type,
        "rotation_pattern": assignment.rotation_pattern,
        "rotation_weekdays": resource_shift_service.assignment_weekdays(assignment),
        "rotation_sequence": sequence,
        "rotation_segments": segments,
        "slot_days": int(slot_days) if slot_days is not None else None,
        "effective_from": assignment.effective_from,
        "effective_to": assignment.effective_to,
        "is_active": assignment.is_active,
        "notes": assignment.notes,
        "user_name": resource_shift_service.display_name(user) if user else None,
        "shift_code": shift.code if shift else None,
        "shift_name": shift.name if shift else None,
        "shift_display": (
            resource_shift_service.format_shift_label(shift) if shift else None
        ),
    }


# --------------------------------------------------------------------------
# Shift masters
# --------------------------------------------------------------------------


@router.get("/shifts", response_model=list[ShiftRead])
def list_shifts(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    return resource_shift_service.list_shifts(db, active_only=active_only)


@router.post("/shifts", response_model=ShiftRead, status_code=status.HTTP_201_CREATED)
def create_shift(
    payload: ShiftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manage(db, current_user)
    try:
        return resource_shift_service.create_shift(db, payload.model_dump())
    except ShiftConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ShiftValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/shifts/{shift_id}", response_model=ShiftRead)
def update_shift(
    shift_id: UUID,
    payload: ShiftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manage(db, current_user)
    shift = resource_shift_service.get_shift(db, shift_id)
    if shift is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    try:
        return resource_shift_service.update_shift(
            db, shift, payload.model_dump(exclude_unset=True)
        )
    except ShiftConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ShiftValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# --------------------------------------------------------------------------
# Assignments
# --------------------------------------------------------------------------


@router.get("/shifts/assignments", response_model=list[ShiftAssignmentRead])
def list_assignments(
    user_id: UUID | None = None,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    assignments = resource_shift_service.list_assignments(
        db,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        include_inactive=include_inactive,
    )
    return [_assignment_payload(db, assignment) for assignment in assignments]


@router.post(
    "/shifts/assignments",
    response_model=ShiftAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    payload: ShiftAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_assign(db, current_user)
    data = payload.model_dump()
    data["assignment_type"] = payload.assignment_type.value
    data["rotation_pattern"] = (
        payload.rotation_pattern.value if payload.rotation_pattern else None
    )
    try:
        assignment = resource_shift_service.assign_shift(db, data)
    except ShiftConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ShiftValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _assignment_payload(db, assignment)


@router.post("/shifts/assignments/bulk", response_model=ShiftAssignmentBulkResult)
def bulk_create_assignments(
    payload: ShiftAssignmentBulkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_assign(db, current_user)
    data = payload.model_dump()
    data["assignment_type"] = payload.assignment_type.value
    data["rotation_pattern"] = (
        payload.rotation_pattern.value if payload.rotation_pattern else None
    )
    created, conflicts = resource_shift_service.bulk_assign(db, data)
    return ShiftAssignmentBulkResult(
        created=[_assignment_payload(db, assignment) for assignment in created],
        conflicts=conflicts,
    )


@router.post("/shifts/assignments/reassign", response_model=ShiftAssignmentRead)
def reassign_assignment(
    payload: ShiftReassignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move one employee to another shift (end-dates prior permanent coverage)."""
    _require_assign(db, current_user)
    try:
        assignment = resource_shift_service.reassign_employee_shift(
            db,
            user_id=payload.user_id,
            new_shift_id=payload.shift_id,
            effective_from=payload.effective_from,
            assignment_type=payload.assignment_type.value,
            notes=payload.notes,
        )
    except ShiftConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ShiftValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _assignment_payload(db, assignment)


@router.post("/shifts/assignments/bulk-reassign", response_model=ShiftAssignmentBulkResult)
def bulk_reassign_assignments(
    payload: ShiftBulkReassignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_assign(db, current_user)
    created, conflicts = resource_shift_service.bulk_reassign_employee_shifts(
        db,
        user_ids=payload.user_ids,
        new_shift_id=payload.shift_id,
        effective_from=payload.effective_from,
        assignment_type=payload.assignment_type.value,
        notes=payload.notes,
    )
    return ShiftAssignmentBulkResult(
        created=[_assignment_payload(db, assignment) for assignment in created],
        conflicts=conflicts,
    )


@router.patch("/shifts/assignments/{assignment_id}/end", response_model=ShiftAssignmentRead)
def end_assignment(
    assignment_id: UUID,
    payload: ShiftAssignmentEnd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_assign(db, current_user)
    assignment = db.get(ResourceShiftAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    try:
        resource_shift_service.end_assignment(db, assignment, payload.effective_to)
    except ShiftValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _assignment_payload(db, assignment)


# --------------------------------------------------------------------------
# Resolution + calendar
# --------------------------------------------------------------------------


@router.get("/shifts/for-user/{user_id}", response_model=ShiftForUser)
def shift_for_user(
    user_id: UUID,
    on_date: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    target = on_date or date.today()
    shift = resource_shift_service.get_employee_shift(db, user_id, target)
    nxt = resource_shift_service.next_employee_shift(db, user_id, after_date=target)
    next_shift = nxt.get("next_shift") if nxt else None
    return ShiftForUser(
        user_id=user_id,
        on_date=target,
        shift=ShiftRead.model_validate(shift) if shift else None,
        shift_hours=(
            resource_shift_service.shift_duration_hours(shift) if shift else None
        ),
        next_change_date=nxt.get("next_change_date") if nxt else None,
        next_shift=ShiftRead.model_validate(next_shift) if next_shift else None,
    )


@router.get("/shifts/roster")
def shift_roster(
    on_date: date | None = Query(default=None, alias="date"),
    status_filter: str = Query(default="active", alias="status"),
    shift: str | None = None,
    department_id: UUID | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Every employee from the User master with their shift on ``date``."""
    from app.core.exceptions import ProTrackValidationError
    from app.services import employee_directory_service as directory

    _require_view(db, current_user)
    try:
        return directory.employee_roster(
            db, on_date=on_date, status=status_filter, shift=shift, department_id=department_id, q=q
        )
    except ProTrackValidationError as exc:
        raise HTTPException(status_code=exc.status_code or 422, detail=exc.detail) from exc


@router.get("/shifts/capacity")
def shift_capacity(
    on_date: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Employees, computers and concurrent license rights per shift (allocation engine)."""
    from app.services import it_availability_service

    _require_view(db, current_user)
    return it_availability_service.shift_capacity(db, on_date=on_date)


@router.get("/shifts/overview", response_model=ShiftOverview)
def shifts_overview(
    on_date: date | None = Query(default=None, alias="date"),
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    return resource_shift_service.shift_overview(db, on_date=on_date, team_id=team_id)


@router.get("/shifts/board", response_model=ShiftBoard)
def shifts_board(
    on_date: date | None = Query(default=None, alias="date"),
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    return resource_shift_service.shift_board(db, on_date=on_date, team_id=team_id)


@router.get("/shifts/calendar", response_model=ShiftCalendar)
def shift_calendar(
    date_from: date = Query(alias="from"),
    date_to: date = Query(alias="to"),
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(db, current_user)
    try:
        return resource_shift_service.shift_calendar(
            db, start=date_from, end=date_to, team_id=team_id
        )
    except ShiftValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc