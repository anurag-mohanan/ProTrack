from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.models import NonProductiveCode, TimesheetEntry
from app.schemas.organization import (
    NonProductiveCodeCreate,
    NonProductiveCodeUpdate,
)


class CRUDNonProductiveCode(
    CRUDBase[NonProductiveCode, NonProductiveCodeCreate, NonProductiveCodeUpdate]
):
    def get_by_code(self, db: Session, code: str) -> NonProductiveCode | None:
        return db.scalar(
            select(NonProductiveCode).where(NonProductiveCode.code == code)
        )

    def delete_with_validation(self, db: Session, record_id: UUID) -> None:
        row = self.get(db, record_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
        usage = db.scalar(
            select(func.count())
            .select_from(TimesheetEntry)
            .where(TimesheetEntry.non_productive_code_id == record_id)
        )
        if int(usage or 0) > 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="NP code is referenced by timesheet entries and cannot be deleted",
            )
        db.delete(row)
        db.commit()


non_productive_code = CRUDNonProductiveCode(NonProductiveCode)
