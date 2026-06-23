from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.crud.project_metrics import recalculate_project_actual_hours
from app.models.models import TimesheetEntry
from app.schemas.timesheet import TimesheetEntryCreate, TimesheetEntryUpdate


class CRUDTimesheetEntry(
    CRUDBase[TimesheetEntry, TimesheetEntryCreate, TimesheetEntryUpdate]
):
    def create(self, db: Session, *, obj_in: TimesheetEntryCreate) -> TimesheetEntry:
        db_obj = self.model(**obj_in.model_dump())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        recalculate_project_actual_hours(db, db_obj.project_id)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: TimesheetEntry,
        obj_in: TimesheetEntryUpdate | dict[str, Any],
    ) -> TimesheetEntry:
        previous_project_id = db_obj.project_id
        updated = super().update(db, db_obj=db_obj, obj_in=obj_in)
        recalculate_project_actual_hours(db, updated.project_id)
        if updated.project_id != previous_project_id:
            recalculate_project_actual_hours(db, previous_project_id)
        return updated

    def delete(self, db: Session, *, record_id: UUID) -> TimesheetEntry | None:
        db_obj = self.get(db, record_id)
        if db_obj is None:
            return None
        project_id = db_obj.project_id
        db.delete(db_obj)
        db.commit()
        recalculate_project_actual_hours(db, project_id)
        return db_obj


timesheet_entry = CRUDTimesheetEntry(TimesheetEntry)
