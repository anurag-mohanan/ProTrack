from uuid import UUID

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase, select
from app.models.models import NonProductiveCode
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


non_productive_code = CRUDNonProductiveCode(NonProductiveCode)
