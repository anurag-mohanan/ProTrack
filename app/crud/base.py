from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.pagination import PaginatedResponse
from app.db.base import Base

__all__ = ["CRUDBase", "Session", "select"]

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: type[ModelType]):
        self.model = model

    def get(self, db: Session, record_id: UUID) -> ModelType | None:
        return db.get(self.model, record_id)

    def _apply_filters(
        self,
        stmt: Select[tuple[ModelType]],
        filters: dict[str, Any] | None = None,
    ) -> Select[tuple[ModelType]]:
        if filters:
            for field, value in filters.items():
                if value is not None:
                    stmt = stmt.where(getattr(self.model, field) == value)
        return stmt

    def count_multi(
        self,
        db: Session,
        *,
        filters: dict[str, Any] | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(self.model)
        if filters:
            for field, value in filters.items():
                if value is not None:
                    stmt = stmt.where(getattr(self.model, field) == value)
        return int(db.scalar(stmt) or 0)

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
        sort: str | None = None,
    ) -> list[ModelType]:
        from app.core.pagination import apply_sort

        stmt: Select[tuple[ModelType]] = select(self.model)
        stmt = self._apply_filters(stmt, filters)
        stmt = apply_sort(stmt, self.model, sort)
        stmt = stmt.offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def get_multi_paginated(
        self,
        db: Session,
        *,
        page: int = 1,
        page_size: int = 25,
        skip: int | None = None,
        limit: int | None = None,
        filters: dict[str, Any] | None = None,
        sort: str | None = None,
    ) -> PaginatedResponse[Any]:
        resolved_skip = skip if skip is not None else (page - 1) * page_size
        resolved_limit = limit if limit is not None else page_size
        resolved_page = (resolved_skip // resolved_limit) + 1 if resolved_limit else page
        total = self.count_multi(db, filters=filters)
        items = self.get_multi(
            db,
            skip=resolved_skip,
            limit=resolved_limit,
            filters=filters,
            sort=sort,
        )
        return PaginatedResponse.build(
            items=items,
            total=total,
            page=resolved_page,
            page_size=resolved_limit,
        )

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        db_obj = self.model(**obj_in.model_dump())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: UpdateSchemaType | dict[str, Any],
    ) -> ModelType:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, *, record_id: UUID) -> ModelType | None:
        db_obj = self.get(db, record_id)
        if db_obj is None:
            return None
        db.delete(db_obj)
        db.commit()
        return db_obj
