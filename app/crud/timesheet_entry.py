from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.core.permissions import (
    can_edit_timesheet_entry,
    can_write_timesheet_entry,
    is_admin,
)
from app.core.timesheet_locking import (
    TIMESHEET_CALENDAR_LOCKED_MESSAGE,
    is_timesheet_month_calendar_locked,
)
from app.crud.base import CRUDBase
from app.crud.timesheet_entry_metrics import build_timesheet_entry_read, build_timesheet_entry_reads
from app.services.project_calculation_service import recalculate_project
from app.models.models import Timesheet, TimesheetEntry, TimesheetEntryDeletionLog, User
from app.models.enums import TimesheetStatus
from app.schemas.timesheet import (
    TimesheetEntryBulkRequest,
    TimesheetEntryBulkResponse,
    TimesheetEntryCreate,
    TimesheetEntryDeletionLogRead,
    TimesheetEntryRead,
    TimesheetEntryUpdate,
)
from app.services.timesheet_entry_service import normalize_entry_payload

TIMESHEET_LOCKED_MESSAGE = (
    "This month's timesheet has already been submitted and can no longer be modified."
)
TIMESHEET_UNAUTHORIZED_MESSAGE = "You are not authorized to modify this timesheet entry."


class CRUDTimesheetEntry(
    CRUDBase[TimesheetEntry, TimesheetEntryCreate, TimesheetEntryUpdate]
):
    def _active_entry_filter(self, stmt):
        return stmt.where(TimesheetEntry.is_deleted.is_(False))

    def get(self, db: Session, record_id: UUID) -> TimesheetEntry | None:
        entry = db.get(self.model, record_id)
        if entry is None or entry.is_deleted:
            return None
        return entry

    def get_including_deleted(self, db: Session, record_id: UUID) -> TimesheetEntry | None:
        return db.get(self.model, record_id)

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, object] | None = None,
    ) -> list[TimesheetEntry]:
        stmt = select(self.model)
        if filters:
            for field, value in filters.items():
                if value is not None:
                    stmt = stmt.where(getattr(self.model, field) == value)
        stmt = self._active_entry_filter(stmt).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def _get_timesheet(self, db: Session, timesheet_id: UUID) -> Timesheet | None:
        return db.get(Timesheet, timesheet_id)

    def _ensure_editable(
        self,
        db: Session,
        *,
        actor,
        timesheet_id: UUID,
        entry_date: date | None = None,
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
        lock_date = entry_date or timesheet.week_start
        if is_timesheet_month_calendar_locked(
            lock_date,
            admin_override=is_admin(db, actor),
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=TIMESHEET_CALENDAR_LOCKED_MESSAGE,
            )
        if timesheet.status != TimesheetStatus.draft:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=TIMESHEET_LOCKED_MESSAGE,
            )
        if not can_edit_timesheet_entry(db, actor, timesheet):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=TIMESHEET_UNAUTHORIZED_MESSAGE,
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

    @staticmethod
    def _deletion_snapshot(db: Session, entry: TimesheetEntry) -> dict[str, Any]:
        read = build_timesheet_entry_read(db, entry)
        tool_number = read.project_tool_number or read.non_productive_code
        task_name = read.task_type_name or read.non_productive_description
        return {
            "tool_number": tool_number,
            "task_name": task_name,
            "designer_name": read.user_name or "",
        }

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

    def get_multi_read_for_range(
        self,
        db: Session,
        *,
        entry_date_from: date | None = None,
        entry_date_to: date | None = None,
        user_id: UUID | None = None,
        skip: int = 0,
        limit: int = 500,
    ) -> list[TimesheetEntryRead]:
        query = select(TimesheetEntry).join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        query = query.where(TimesheetEntry.is_deleted.is_(False))
        if entry_date_from is not None:
            query = query.where(TimesheetEntry.entry_date >= entry_date_from)
        if entry_date_to is not None:
            query = query.where(TimesheetEntry.entry_date <= entry_date_to)
        if user_id is not None:
            query = query.where(Timesheet.user_id == user_id)
        query = query.order_by(TimesheetEntry.entry_date, TimesheetEntry.created_at).offset(skip).limit(limit)
        entries = db.scalars(query).all()
        return build_timesheet_entry_reads(db, entries)

    def bulk_save(
        self,
        db: Session,
        *,
        actor,
        request: TimesheetEntryBulkRequest,
    ) -> TimesheetEntryBulkResponse:
        deleted: list[UUID] = []
        for record_id in request.deletes:
            removed = self.delete(db, record_id=record_id, actor=actor)
            if removed is not None:
                deleted.append(record_id)

        upserted: list[TimesheetEntryRead] = []
        for item in request.upserts:
            payload = TimesheetEntryCreate(**item.model_dump(exclude={"id"}))
            if item.id is not None:
                db_obj = self.get(db, item.id)
                if db_obj is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Timesheet entry {item.id} not found",
                    )
                update_payload = TimesheetEntryUpdate(**item.model_dump(exclude={"id"}))
                upserted.append(
                    self.update_read(db, db_obj=db_obj, obj_in=update_payload, actor=actor)
                )
            else:
                upserted.append(self.create_read(db, obj_in=payload, actor=actor))

        return TimesheetEntryBulkResponse(upserted=upserted, deleted=deleted)

    def create(self, db: Session, *, obj_in: TimesheetEntryCreate, actor=None) -> TimesheetEntry:
        if actor is not None:
            self._ensure_editable(
                db,
                actor=actor,
                timesheet_id=obj_in.timesheet_id,
                entry_date=obj_in.entry_date,
            )
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
        if db_obj.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Record not found",
            )
        if actor is not None:
            self._ensure_editable(
                db,
                actor=actor,
                timesheet_id=db_obj.timesheet_id,
                entry_date=db_obj.entry_date,
            )
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
                self._ensure_editable(
                    db,
                    actor=actor,
                    timesheet_id=target_timesheet_id,
                    entry_date=updated.entry_date,
                )
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

    def delete(
        self,
        db: Session,
        *,
        record_id: UUID,
        actor=None,
        reason: str = "User Deleted",
    ) -> TimesheetEntry | None:
        db_obj = self.get_including_deleted(db, record_id)
        if db_obj is None or db_obj.is_deleted:
            return None
        if actor is not None:
            timesheet = self._ensure_editable(
                db,
                actor=actor,
                timesheet_id=db_obj.timesheet_id,
                entry_date=db_obj.entry_date,
            )
        else:
            timesheet = self._get_timesheet(db, db_obj.timesheet_id)
            if timesheet is None:
                return None

        snapshot = self._deletion_snapshot(db, db_obj)
        deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        project_id = db_obj.project_id

        log = TimesheetEntryDeletionLog(
            entry_id=db_obj.id,
            designer_user_id=timesheet.user_id,
            designer_name=snapshot["designer_name"],
            entry_date=db_obj.entry_date,
            tool_number=snapshot["tool_number"],
            task_name=snapshot["task_name"],
            hours=db_obj.hours,
            is_billable=db_obj.is_billable,
            notes=db_obj.description,
            deleted_by_id=actor.id if actor is not None else timesheet.user_id,
            deleted_at=deleted_at,
            reason=reason,
        )
        db_obj.is_deleted = True
        db_obj.deleted_at = deleted_at
        db_obj.deleted_by_id = actor.id if actor is not None else None
        db_obj.delete_reason = reason
        db.add(log)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        self._recalculate_projects(db, project_id)
        return db_obj

    def list_deletion_logs(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        include_restored: bool = False,
    ) -> list[TimesheetEntryDeletionLogRead]:
        query = select(TimesheetEntryDeletionLog).order_by(
            TimesheetEntryDeletionLog.deleted_at.desc()
        )
        if not include_restored:
            query = query.where(TimesheetEntryDeletionLog.restored_at.is_(None))
        logs = db.scalars(query.offset(skip).limit(limit)).all()
        results: list[TimesheetEntryDeletionLogRead] = []
        for log in logs:
            deleted_by = db.get(User, log.deleted_by_id)
            deleted_by_name = None
            if deleted_by is not None:
                deleted_by_name = f"{deleted_by.first_name} {deleted_by.last_name}".strip()
            results.append(
                TimesheetEntryDeletionLogRead(
                    id=log.id,
                    entry_id=log.entry_id,
                    designer_user_id=log.designer_user_id,
                    designer_name=log.designer_name,
                    entry_date=log.entry_date,
                    tool_number=log.tool_number,
                    task_name=log.task_name,
                    hours=log.hours,
                    is_billable=log.is_billable,
                    notes=log.notes,
                    deleted_by_id=log.deleted_by_id,
                    deleted_by_name=deleted_by_name,
                    deleted_at=log.deleted_at,
                    reason=log.reason,
                    restored_at=log.restored_at,
                    restored_by_id=log.restored_by_id,
                    created_at=log.created_at,
                    updated_at=log.updated_at,
                )
            )
        return results

    def restore(self, db: Session, *, record_id: UUID, actor) -> TimesheetEntryRead:
        if not is_admin(db, actor):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only system administrators can restore deleted entries",
            )
        entry = self.get_including_deleted(db, record_id)
        if entry is None or not entry.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deleted entry not found",
            )
        timesheet = self._get_timesheet(db, entry.timesheet_id)
        if timesheet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Timesheet not found",
            )
        if timesheet.status != TimesheetStatus.draft:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Entries can only be restored while the timesheet month is still in draft",
            )

        entry.is_deleted = False
        entry.deleted_at = None
        entry.deleted_by_id = None
        entry.delete_reason = None
        db.add(entry)

        log = db.scalar(
            select(TimesheetEntryDeletionLog)
            .where(
                TimesheetEntryDeletionLog.entry_id == entry.id,
                TimesheetEntryDeletionLog.restored_at.is_(None),
            )
            .order_by(TimesheetEntryDeletionLog.deleted_at.desc())
            .limit(1)
        )
        if log is not None:
            log.restored_at = datetime.now(timezone.utc).replace(tzinfo=None)
            log.restored_by_id = actor.id
            db.add(log)

        db.commit()
        db.refresh(entry)
        self._recalculate_projects(db, entry.project_id)
        return build_timesheet_entry_read(db, entry)


timesheet_entry = CRUDTimesheetEntry(TimesheetEntry)
