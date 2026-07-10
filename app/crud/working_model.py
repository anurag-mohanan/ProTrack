import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.enums import WorkingModelCode
from app.models.models import Customer, Project, User, WorkingModel
from app.schemas.organization import (
    WorkingModelCreate,
    WorkingModelUpdate,
)


def _slugify_code(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return slug.strip("_")[:50] or "working_model"


class CRUDWorkingModel(
    CRUDBase[WorkingModel, WorkingModelCreate, WorkingModelUpdate]
):
    def get_by_code(self, db: Session, code: str) -> WorkingModel | None:
        return db.scalar(select(WorkingModel).where(WorkingModel.code == code))

    def create(self, db: Session, *, obj_in: WorkingModelCreate) -> WorkingModel:
        data = obj_in.model_dump()
        if not data.get("code"):
            data["code"] = _slugify_code(data["name"])
        if self.get_by_code(db, data["code"]) is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Working model code already exists",
            )
        if data.get("sort_order", 0) == 0:
            max_order = db.scalar(select(func.max(WorkingModel.sort_order))) or 0
            data["sort_order"] = int(max_order) + 1
        return super().create(db, obj_in=WorkingModelCreate(**data))

    def update(
        self,
        db: Session,
        *,
        db_obj: WorkingModel,
        obj_in: WorkingModelUpdate,
    ) -> WorkingModel:
        data = obj_in.model_dump(exclude_unset=True)
        if "code" in data and data["code"]:
            existing = self.get_by_code(db, data["code"])
            if existing is not None and existing.id != db_obj.id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Working model code already exists",
                )
        return super().update(db, db_obj=db_obj, obj_in=obj_in)

    def reorder(self, db: Session, ordered_ids: list[UUID]) -> list[WorkingModel]:
        rows = db.scalars(select(WorkingModel).where(WorkingModel.id.in_(ordered_ids))).all()
        by_id = {row.id: row for row in rows}
        if len(by_id) != len(ordered_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="One or more working model ids are invalid",
            )
        for index, model_id in enumerate(ordered_ids):
            by_id[model_id].sort_order = index
            db.add(by_id[model_id])
        db.commit()
        return self.get_multi(db, skip=0, limit=1000)

    def archive(self, db: Session, record_id: UUID) -> WorkingModel:
        row = self.get(db, record_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
        row.is_archived = True
        row.is_active = False
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def list_active_strategies(self) -> list[WorkingModelCode]:
        return list(WorkingModelCode)


working_model = CRUDWorkingModel(WorkingModel)
