from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import (
    can_delete_timesheet,
    can_edit_timesheet,
    can_read_timesheet,
    can_write_timesheet_entry,
    get_role_name,
    FULL_ACCESS_ROLES,
)
from app.crud.base import CRUDBase
from app.models.enums import TimesheetStatus
from app.models.models import Timesheet, User
from app.schemas.timesheet import TimesheetCreate, TimesheetUpdate
from app.services.timesheet_workflow_service import filter_visible_timesheets


class CRUDTimesheet(CRUDBase[Timesheet, TimesheetCreate, TimesheetUpdate]):
    def get_multi_for_user(
        self,
        db: Session,
        *,
        actor: User,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
    ) -> list[Timesheet]:
        rows = self.get_multi(db, skip=skip, limit=limit, filters=filters)
        visible = filter_visible_timesheets(db, actor, rows)
        return visible

    def get_for_user(self, db: Session, *, actor: User, record_id: UUID) -> Timesheet | None:
        row = self.get(db, record_id)
        if row is None:
            return None
        if not can_read_timesheet(db, actor, row):
            return None
        return row

    def create_for_user(
        self,
        db: Session,
        *,
        actor: User,
        obj_in: TimesheetCreate,
    ) -> Timesheet:
        if not can_write_timesheet_entry(db, actor):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        if obj_in.user_id != actor.id and get_role_name(db, actor) not in FULL_ACCESS_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create timesheets for yourself",
            )
        payload = obj_in.model_dump()
        payload["status"] = TimesheetStatus.draft
        payload["submitted_at"] = None
        payload["approved_by"] = None
        payload["approved_at"] = None
        payload["approval_comments"] = None
        return super().create(db, obj_in=TimesheetCreate(**payload))

    def update_for_user(
        self,
        db: Session,
        *,
        actor: User,
        db_obj: Timesheet,
        obj_in: TimesheetUpdate | dict[str, Any],
    ) -> Timesheet:
        if not can_edit_timesheet(db, actor, db_obj):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Timesheet is locked or you lack permission to edit it",
            )
        if isinstance(obj_in, dict):
            update_data = dict(obj_in)
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        forbidden = {"status", "submitted_at", "approved_by", "approved_at", "approval_comments"}
        if forbidden.intersection(update_data):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Use workflow endpoints to change timesheet status",
            )
        return super().update(db, db_obj=db_obj, obj_in=update_data)

    def delete_for_user(
        self,
        db: Session,
        *,
        actor: User,
        record_id: UUID,
    ) -> Timesheet | None:
        db_obj = self.get(db, record_id)
        if db_obj is None:
            return None
        if not can_delete_timesheet(db, actor, db_obj):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only draft timesheets can be deleted",
            )
        return super().delete(db, record_id=record_id)


timesheet = CRUDTimesheet(Timesheet)
