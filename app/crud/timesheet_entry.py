from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.core.permissions import (
    can_edit_timesheet_entry,
    can_write_timesheet_entry,
)
from app.crud.base import CRUDBase
from app.crud.timesheet_entry_metrics import build_timesheet_entry_read, build_timesheet_entry_reads
from app.services.project_calculation_service import recalculate_project
from app.models.models import Timesheet, TimesheetEntry
from app.schemas.timesheet import TimesheetEntryCreate, TimesheetEntryRead, TimesheetEntryUpdate
from app.services.timesheet_entry_service import normalize_entry_payload


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

    @staticmethod
    def _recalculate_projects(db: Session, *project_ids: UUID | None) -> None:
        seen: set[UUID] = set()
        for project_id in project_ids:
            if project_id is None or project_id in seen:
                continue
            seen.add(project_id)
            recalculate_project(db, project_id)

    def _handle_validation(self, exc: ProTrackValidationError) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.detail,
        )

    def get_read(self, db: Session, record_id: UUID) -> TimesheetEntryRead | None:
        entry = self.get(db, record_id)
        if entry is None:
            return None
        return build_timesheet_entry_read(db, entry)

    def get_multi_read(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, object] | None = None,
    ) -> list[TimesheetEntryRead]:
        entries = self.get_multi(db, skip=skip, limit=limit, filters=filters)
        return build_timesheet_entry_reads(db, entries)

    def create(self, db: Session, *, obj_in: TimesheetEntryCreate, actor=None) -> TimesheetEntry:
        if actor is not None:
            self._ensure_editable(db, actor=actor, timesheet_id=obj_in.timesheet_id)
        try:
            data = normalize_entry_payload(db, obj_in, actor=actor)
        except ProTrackValidationError as exc:
            raise self._handle_validation(exc) from exc
        db_obj = self.model(**data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        self._recalculate_projects(db, db_obj.project_id)
        return db_obj

    def create_read(
        self, db: Session, *, obj_in: TimesheetEntryCreate, actor=None
    ) -> TimesheetEntryRead:
        entry = self.create(db, obj_in=obj_in, actor=actor)
        return build_timesheet_entry_read(db, entry)

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
        if isinstance(obj_in, TimesheetEntryUpdate):
            try:
                data = normalize_entry_payload(
                    db, obj_in, actor=actor, existing=db_obj
                )
            except ProTrackValidationError as exc:
                raise self._handle_validation(exc) from exc
            updated = super().update(db, db_obj=db_obj, obj_in=data)
        else:
            updated = super().update(db, db_obj=db_obj, obj_in=obj_in)
        if actor is not None:
            target_timesheet_id = updated.timesheet_id
            if isinstance(obj_in, TimesheetEntryUpdate) and obj_in.timesheet_id is not None:
                self._ensure_editable(db, actor=actor, timesheet_id=target_timesheet_id)
        self._recalculate_projects(db, updated.project_id, previous_project_id)
        return updated

    def update_read(
        self,
        db: Session,
        *,
        db_obj: TimesheetEntry,
        obj_in: TimesheetEntryUpdate,
        actor=None,
    ) -> TimesheetEntryRead:
        entry = self.update(db, db_obj=db_obj, obj_in=obj_in, actor=actor)
        return build_timesheet_entry_read(db, entry)

    def delete(self, db: Session, *, record_id: UUID, actor=None) -> TimesheetEntry | None:
        db_obj = self.get(db, record_id)
        if db_obj is None:
            return None
        if actor is not None:
            self._ensure_editable(db, actor=actor, timesheet_id=db_obj.timesheet_id)
        project_id = db_obj.project_id
        db.delete(db_obj)
        db.commit()
        self._recalculate_projects(db, project_id)
        return db_obj


timesheet_entry = CRUDTimesheetEntry(TimesheetEntry)
