from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.crud.base import CRUDBase
from app.crud.team import sync_user_team_membership
from app.models.models import Team, User
from app.schemas.identity import UserCreate, UserRead, UserUpdate


def build_user_read(db: Session, user: User) -> UserRead:
    team_name = None
    if user.team_id is not None:
        team = db.get(Team, user.team_id)
        team_name = team.name if team else None
    return UserRead(
        id=user.id,
        role_id=user.role_id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        team_id=user.team_id,
        team_name=team_name,
        is_archived=user.is_archived,
        archived_at=user.archived_at,
        is_deleted=user.is_deleted,
        deleted_at=user.deleted_at,
        deleted_by_id=user.deleted_by_id,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        data = obj_in.model_dump(exclude={"password"})
        team_id = data.pop("team_id", None)
        db_obj = User(
            **data,
            team_id=team_id,
            password_hash=hash_password(obj_in.password),
        )
        db.add(db_obj)
        db.flush()
        sync_user_team_membership(db, db_obj.id, team_id)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: User,
        obj_in: UserUpdate | dict[str, Any],
    ) -> User:
        if isinstance(obj_in, dict):
            update_data = dict(obj_in)
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        password = update_data.pop("password", None)
        if password is not None:
            update_data["password_hash"] = hash_password(password)
            update_data["must_change_password"] = True
        team_id_provided = "team_id" in update_data
        team_id = update_data.pop("team_id", None) if team_id_provided else None
        updated = super().update(db, db_obj=db_obj, obj_in=update_data)
        if team_id_provided:
            sync_user_team_membership(db, updated.id, team_id)
            db.commit()
            db.refresh(updated)
        return updated

    def get_read(self, db: Session, record_id: UUID) -> UserRead | None:
        user = self.get(db, record_id)
        if user is None:
            return None
        return build_user_read(db, user)


user = CRUDUser(User)
