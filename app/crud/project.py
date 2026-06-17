from app.crud.base import CRUDBase
from app.models.enums import MilestoneStatus
from app.models.models import Milestone, Project
from app.schemas.project import ProjectCreate, ProjectUpdate

DEFAULT_PROJECT_MILESTONES = (
    "Feasibility",
    "Blockout",
    "Roughing",
    "Intermediate Review",
    "Final Review",
    "File Release",
    "BOM Release",
)


class CRUDProject(CRUDBase[Project, ProjectCreate, ProjectUpdate]):
    def create(self, db, *, obj_in: ProjectCreate) -> Project:
        db_obj = Project(**obj_in.model_dump())
        db.add(db_obj)
        db.flush()

        for sort_order, name in enumerate(DEFAULT_PROJECT_MILESTONES, start=1):
            db.add(
                Milestone(
                    project_id=db_obj.id,
                    name=name,
                    status=MilestoneStatus.not_started,
                    sort_order=sort_order,
                )
            )

        db.commit()
        db.refresh(db_obj)
        return db_obj


project = CRUDProject(Project)
