from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.crud.base import CRUDBase
from app.models.enums import MilestoneStatus
from app.models.models import Milestone
from app.schemas.project import MilestoneCreate, MilestoneUpdate
from app.services.project_calculation_service import recalculate_project_progress


class CRUDMilestone(CRUDBase[Milestone, MilestoneCreate, MilestoneUpdate]):
    def create(self, db, *, obj_in: MilestoneCreate) -> Milestone:
        db_obj = super().create(db, obj_in=obj_in)
        recalculate_project_progress(db, db_obj.project_id)
        return db_obj

    def update(
        self,
        db,
        *,
        db_obj: Milestone,
        obj_in: MilestoneUpdate | dict[str, Any],
    ) -> Milestone:
        if isinstance(obj_in, dict):
            update_data = dict(obj_in)
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        if "status" in update_data:
            if update_data["status"] == MilestoneStatus.completed:
                update_data["completed_at"] = datetime.now(timezone.utc)
            else:
                update_data["completed_at"] = None

        updated = super().update(db, db_obj=db_obj, obj_in=update_data)
        recalculate_project_progress(db, updated.project_id)
        return updated

    def delete(self, db, *, record_id: UUID) -> Milestone | None:
        db_obj = self.get(db, record_id)
        if db_obj is None:
            return None
        project_id = db_obj.project_id
        deleted = super().delete(db, record_id=record_id)
        if deleted is not None:
            recalculate_project_progress(db, project_id)
        return deleted


milestone = CRUDMilestone(Milestone)
