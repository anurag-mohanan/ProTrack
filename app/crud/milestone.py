from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.crud.base import CRUDBase
from app.models.enums import ActivityAction, EntityType, MilestoneStatus
from app.models.models import Milestone
from app.schemas.project import MilestoneCreate, MilestoneUpdate
from app.services.activity_service import log_activity
from app.services.milestone_workspace_service import (
    apply_progress_rules,
    log_milestone_field_changes,
    recalculate_project_planned_hours,
)
from app.services.project_calculation_service import recalculate_project


class CRUDMilestone(CRUDBase[Milestone, MilestoneCreate, MilestoneUpdate]):
    def create(self, db, *, obj_in: MilestoneCreate, actor=None) -> Milestone:
        db_obj = super().create(db, obj_in=obj_in)
        from app.services.milestone_assignment_service import sync_milestone_assignments

        sync_milestone_assignments(db, db_obj.project_id)
        db.refresh(db_obj)
        recalculate_project_planned_hours(db, db_obj.project_id)
        recalculate_project(db, db_obj.project_id)
        if actor is not None:
            log_activity(
                db,
                user=actor,
                entity_type=EntityType.milestone,
                entity_id=db_obj.id,
                action=ActivityAction.milestone_created,
                new_value=db_obj.name,
            )
        return db_obj

    def update(
        self,
        db,
        *,
        db_obj: Milestone,
        obj_in: MilestoneUpdate | dict[str, Any],
        actor=None,
    ) -> Milestone:
        if isinstance(obj_in, dict):
            update_data = dict(obj_in)
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        previous = {
            "name": db_obj.name,
            "planned_hours": db_obj.planned_hours,
            "due_date": db_obj.due_date,
            "assigned_user_id": db_obj.assigned_user_id,
            "status": db_obj.status,
            "progress_percent": db_obj.progress_percent,
        }
        previous_status = db_obj.status
        update_data = apply_progress_rules(update_data)
        if "assigned_user_id" in update_data:
            update_data["assignment_manual"] = True

        updated = super().update(db, db_obj=db_obj, obj_in=update_data)
        recalculate_project_planned_hours(db, updated.project_id)
        recalculate_project(db, updated.project_id)

        if actor is not None:
            log_milestone_field_changes(
                db,
                actor=actor,
                milestone=db_obj,
                previous=previous,
                updated=updated,
            )
            if "status" in update_data and update_data["status"] != previous_status:
                if update_data["status"] == MilestoneStatus.completed:
                    log_activity(
                        db,
                        user=actor,
                        entity_type=EntityType.milestone,
                        entity_id=updated.id,
                        action=ActivityAction.milestone_completed,
                        old_value=previous_status,
                        new_value=updated.status,
                    )
                elif (
                    previous_status == MilestoneStatus.completed
                    and update_data["status"] != MilestoneStatus.completed
                ):
                    log_activity(
                        db,
                        user=actor,
                        entity_type=EntityType.milestone,
                        entity_id=updated.id,
                        action=ActivityAction.milestone_reopened,
                        old_value=previous_status,
                        new_value=updated.status,
                    )
        return updated

    def delete(self, db, *, record_id: UUID, actor=None) -> Milestone | None:
        db_obj = self.get(db, record_id)
        if db_obj is None:
            return None
        project_id = db_obj.project_id
        name = db_obj.name
        deleted = super().delete(db, record_id=record_id)
        if deleted is not None:
            recalculate_project_planned_hours(db, project_id)
            recalculate_project(db, project_id)
            if actor is not None:
                log_activity(
                    db,
                    user=actor,
                    entity_type=EntityType.milestone,
                    entity_id=record_id,
                    action=ActivityAction.milestone_deleted,
                    old_value=name,
                )
        return deleted


milestone = CRUDMilestone(Milestone)
