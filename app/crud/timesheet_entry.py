from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import (
    can_edit_timesheet_entry,
    can_write_timesheet_entry,
)
from app.crud.base import CRUDBase
from app.services.project_calculation_service import recalculate_project
from app.models.models import Timesheet, TimesheetEntry
from app.schemas.timesheet import TimesheetEntryCreate, TimesheetEntryUpdate


class CRUDTimesheetEntry(
    CRUDBase[TimesheetEntry, TimesheetEntryCreate, TimesheetEntryUpdate]
):
    def _get_timesheet(self, db: Session, timesheet_id: UUID) -> Timesheet | None:
        return db.get(Timesheet, timesheet_id)

    def _ensure_editable(
        self,
        db: Session,
        *,
        actor,
        timesheet_id: UUID,
    ) -> Timesheet:
        if not can_write_timesheet_entry(db, actor):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        timesheet = self._get_timesheet(db, timesheet_id)
        if timesheet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Timesheet not found",
            )
        if not can_edit_timesheet_entry(db, actor, timesheet):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Timesheet entries can only be edited while in draft status",
            )
        return timesheet

    def create(self, db: Session, *, obj_in: TimesheetEntryCreate, actor=None) -> TimesheetEntry:
        if actor is None:
            return super().create(db, obj_in=obj_in)
        self._ensure_editable(db, actor=actor, timesheet_id=obj_in.timesheet_id)
        db_obj = self.model(**obj_in.model_dump())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        recalculate_project(db, db_obj.project_id)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: TimesheetEntry,
        obj_in: TimesheetEntryUpdate | dict[str, Any],
        actor=None,
    ) -> TimesheetEntry:
        if actor is not None:
            self._ensure_editable(db, actor=actor, timesheet_id=db_obj.timesheet_id)
        previous_project_id = db_obj.project_id
        updated = super().update(db, db_obj=db_obj, obj_in=obj_in)
        if actor is not None:
            target_timesheet_id = updated.timesheet_id
            if "timesheet_id" in (
                obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
            ):
                self._ensure_editable(db, actor=actor, timesheet_id=target_timesheet_id)
        recalculate_project(db, updated.project_id)
        if updated.project_id != previous_project_id:
            recalculate_project(db, previous_project_id)
        return updated

    def delete(self, db: Session, *, record_id: UUID, actor=None) -> TimesheetEntry | None:
        db_obj = self.get(db, record_id)
        if db_obj is None:
            return None
        if actor is not None:
            self._ensure_editable(db, actor=actor, timesheet_id=db_obj.timesheet_id)
        project_id = db_obj.project_id
        db.delete(db_obj)
        db.commit()
        recalculate_project(db, project_id)
        return db_obj


timesheet_entry = CRUDTimesheetEntry(TimesheetEntry)
