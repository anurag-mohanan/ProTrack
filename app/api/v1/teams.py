from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user, require_roles
from app.api.deps import get_db, get_object_or_404
from app.core.exceptions import ProTrackValidationError
from app.crud.team import team
from app.models.models import Team, User
from app.schemas.team import (
    TeamCreate,
    TeamMemberCreate,
    TeamMemberRead,
    TeamMemberTransfer,
    TeamMemberUpdate,
    TeamRead,
    TeamUpdate,
)

router = APIRouter(
    prefix="/teams",
    tags=["teams"],
    dependencies=[Depends(get_current_user), Depends(require_roles("Admin", "Engineering Manager"))],
)

write_access = Depends(require_roles("Admin", "Engineering Manager"))


def _handle_validation(exc: ProTrackValidationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.detail,
    )


@router.get("", response_model=list[TeamRead])
def list_teams(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    is_active: bool | None = None,
    db: Session = Depends(get_db),
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
def get_team(record_id: UUID, db: Session = Depends(get_db)):
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


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    record_id: UUID,
    db: Session = Depends(get_db),
    _user: User = write_access,
):
    db_obj = get_object_or_404(db, Team, record_id)
    team.delete(db, record_id=db_obj.id)


@router.get("/{record_id}/members", response_model=list[TeamMemberRead])
def list_team_members(record_id: UUID, db: Session = Depends(get_db)):
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
