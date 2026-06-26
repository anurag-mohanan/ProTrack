from typing import Any

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.crud.base import CRUDBase
from app.models.models import User
from app.schemas.identity import UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        data = obj_in.model_dump(exclude={"password"})
        db_obj = User(
            **data,
            password_hash=hash_password(obj_in.password),
        )
        db.add(db_obj)
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
        return super().update(db, db_obj=db_obj, obj_in=update_data)


user = CRUDUser(User)
