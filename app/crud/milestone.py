from datetime import datetime, timezone

from app.crud.base import CRUDBase
from app.models.enums import MilestoneStatus
from app.models.models import Milestone
from app.schemas.project import MilestoneCreate, MilestoneUpdate


class CRUDMilestone(CRUDBase[Milestone, MilestoneCreate, MilestoneUpdate]):
    def update(
        self,
        db,
        *,
        db_obj: Milestone,
        obj_in: MilestoneUpdate | dict,
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

        return super().update(db, db_obj=db_obj, obj_in=update_data)


milestone = CRUDMilestone(Milestone)
