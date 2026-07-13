from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import get_db, get_object_or_404
from app.core.exceptions import ProTrackValidationError
from app.crud.team import team
from app.models.models import Team, User
from app.schemas.delete_check import DeleteCheckResponse
from app.schemas.team import (
    TeamCreate,
    TeamMemberCreate,
    TeamMemberRead,
    TeamMemberTransfer,
    TeamMemberUpdate,
    TeamRead,
    TeamUpdate,
)

from app.services.master_data_delete_service import (
    ensure_can_delete,
    log_record_deleted,
    run_delete_check,
)

router = APIRouter(
    prefix="/teams",
    tags=["teams"],
    dependencies=[Depends(get_current_user)],
)

write_access = Depends(require_roles("Admin"))
admin_access = Depends(require_roles("Admin"))
read_access = Depends(
    require_roles(
        "Admin",
        "Engineering Manager",
        "Design Leader",
        "Read Only",
        "Planning Board",
    )
)


def _handle_validation(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail=exc.detail,
    )


@router.get("", response_model=list[TeamRead])
def list_teams(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    _user: User = read_access,
):
    return team.list_read(db, skip=skip, limit=limit, is_active=is_active)


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate,
    db: Session = Depends(get_db),
    _user: User = write_access,
):
    try:
        created = team.create(db, obj_in=payload)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    return team.get_read(db, created.id)


@router.get("/{record_id}", response_model=TeamRead)
def get_team(
    record_id: UUID,
    db: Session = Depends(get_db),
    _user: User = read_access,
):
    result = team.get_read(db, record_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return result


@router.patch("/{record_id}", response_model=TeamRead)
def update_team(
    record_id: UUID,
    payload: TeamUpdate,
    db: Session = Depends(get_db),
    _user: User = write_access,
):
    db_obj = get_object_or_404(db, Team, record_id)
    try:
        team.update(db, db_obj=db_obj, obj_in=payload)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    result = team.get_read(db, record_id)
    assert result is not None
    return result


@router.get(
    "/{record_id}/delete-check",
    response_model=DeleteCheckResponse,
    dependencies=[admin_access],
)
def delete_check(
    record_id: UUID,
    db: Session = Depends(get_db),
    _user: User = admin_access,
):
    try:
        return run_delete_check(db, "team", record_id)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _user: User = admin_access,
):
    db_obj = get_object_or_404(db, Team, record_id)
    try:
        ensure_can_delete(db, "team", record_id)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
    team.delete(db, record_id=db_obj.id)
    log_record_deleted(
        db,
        user=current_user,
        entity_key="team",
        record_id=record_id,
        record_name=db_obj.name,
    )


@router.get("/{record_id}/members", response_model=list[TeamMemberRead])
def list_team_members(
    record_id: UUID,
    db: Session = Depends(get_db),
    _user: User = read_access,
):
    get_object_or_404(db, Team, record_id)
    return team.list_members(db, record_id)


@router.post("/{record_id}/members", response_model=TeamMemberRead, status_code=status.HTTP_201_CREATED)
def add_team_member(
    record_id: UUID,
    payload: TeamMemberCreate,
    db: Session = Depends(get_db),
    _user: User = write_access,
):
    try:
        return team.add_member(db, team_id=record_id, obj_in=payload)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.patch("/{record_id}/members/{member_id}", response_model=TeamMemberRead)
def update_team_member(
    record_id: UUID,
    member_id: UUID,
    payload: TeamMemberUpdate,
    db: Session = Depends(get_db),
    _user: User = write_access,
):
    try:
        return team.update_member(
            db, team_id=record_id, member_id=member_id, obj_in=payload
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.delete("/{record_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_team_member(
    record_id: UUID,
    member_id: UUID,
    db: Session = Depends(get_db),
    _user: User = write_access,
):
    try:
        team.remove_member(db, team_id=record_id, member_id=member_id)
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc


@router.post("/{record_id}/members/{member_id}/transfer", response_model=TeamMemberRead)
def transfer_team_member(
    record_id: UUID,
    member_id: UUID,
    payload: TeamMemberTransfer,
    db: Session = Depends(get_db),
    _user: User = write_access,
):
    try:
        return team.transfer_member(
            db,
            team_id=record_id,
            member_id=member_id,
            target_team_id=payload.target_team_id,
        )
    except ProTrackValidationError as exc:
        raise _handle_validation(exc) from exc
