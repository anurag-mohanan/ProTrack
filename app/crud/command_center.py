"""CRUD for Project Command Center entities."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import EngineeringChangeStatus, ExecutionStatus
from app.models.intelligence import EngineeringChange, ProjectDecision
from app.models.models import Milestone, Project, ProjectType
from app.schemas.command_center import (
    EngineeringChangeCreate,
    EngineeringChangeUpdate,
    ProjectDecisionCreate,
    ProjectDecisionUpdate,
    ProjectFolderPathsUpdate,
)
from app.schemas.project import ProjectCreate
from app.services.command_center_service import _decision_to_read
from app.services.project_calculation_service import recalculate_project
from app.services.project_template_service import create_milestones_from_template, resolve_template


class CRUDProjectDecision:
    def list_for_project(self, db: Session, project_id: UUID) -> list:
        rows = db.scalars(
            select(ProjectDecision)
            .where(ProjectDecision.project_id == project_id)
            .order_by(ProjectDecision.created_at.desc())
        ).all()
        return [_decision_to_read(db, row) for row in rows]

    def create(
        self,
        db: Session,
        *,
        project_id: UUID,
        user_id: UUID,
        obj_in: ProjectDecisionCreate,
    ):
        if obj_in.milestone_id is not None:
            milestone = db.get(Milestone, obj_in.milestone_id)
            if milestone is None or milestone.project_id != project_id:
                raise ProTrackValidationError(
                    "milestone_id must belong to the selected project"
                )
        row = ProjectDecision(
            project_id=project_id,
            user_id=user_id,
            category=obj_in.category,
            comment=obj_in.comment,
            milestone_id=obj_in.milestone_id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _decision_to_read(db, row)

    def update(
        self,
        db: Session,
        *,
        decision_id: UUID,
        project_id: UUID,
        obj_in: ProjectDecisionUpdate,
    ):
        row = db.get(ProjectDecision, decision_id)
        if row is None or row.project_id != project_id:
            return None
        data = obj_in.model_dump(exclude_unset=True)
        if "milestone_id" in data and data["milestone_id"] is not None:
            milestone = db.get(Milestone, data["milestone_id"])
            if milestone is None or milestone.project_id != project_id:
                raise ProTrackValidationError(
                    "milestone_id must belong to the selected project"
                )
        for key, value in data.items():
            setattr(row, key, value)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _decision_to_read(db, row)

    def delete(self, db: Session, *, decision_id: UUID, project_id: UUID) -> bool:
        row = db.get(ProjectDecision, decision_id)
        if row is None or row.project_id != project_id:
            return False
        db.delete(row)
        db.commit()
        return True


class CRUDEngineeringChange:
    def create(
        self, db: Session, *, project_id: UUID, obj_in: EngineeringChangeCreate
    ) -> EngineeringChange:
        row = EngineeringChange(
            project_id=project_id,
            ec_number=obj_in.ec_number.strip(),
            title=obj_in.title.strip(),
            hours=obj_in.hours,
            status=EngineeringChangeStatus.open,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def update(
        self,
        db: Session,
        *,
        ec_id: UUID,
        project_id: UUID,
        obj_in: EngineeringChangeUpdate,
    ) -> EngineeringChange | None:
        row = db.get(EngineeringChange, ec_id)
        if row is None or row.project_id != project_id:
            return None
        data = obj_in.model_dump(exclude_unset=True)
        if data.get("status") == EngineeringChangeStatus.closed and row.closed_at is None:
            row.closed_at = datetime.now(timezone.utc)
        if data.get("status") == EngineeringChangeStatus.open:
            row.closed_at = None
        for key, value in data.items():
            setattr(row, key, value)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row


def update_project_folders(
    db: Session, project: Project, payload: ProjectFolderPathsUpdate
) -> Project:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def clone_project(db: Session, source: Project) -> Project:
    project_type_id = source.project_type_id
    if project_type_id is None:
        project_type_id = db.scalar(
            select(ProjectType.id).where(ProjectType.name == "Mold Design").limit(1)
        )
    if project_type_id is None:
        raise ProTrackValidationError(
            "Cannot clone a project without a configured project type"
        )

    suffix = "-COPY"
    new_tool = f"{source.tool_number}{suffix}"[:50]
    new_code = f"{source.code}{suffix}"[:50]

    existing = db.scalar(select(Project.id).where(Project.code == new_code).limit(1))
    counter = 1
    while existing is not None:
        new_code = f"{source.code}{suffix}{counter}"[:50]
        new_tool = f"{source.tool_number}{suffix}{counter}"[:50]
        existing = db.scalar(select(Project.id).where(Project.code == new_code).limit(1))
        counter += 1

    clone = Project(
        tool_number=new_tool,
        part_description=f"{source.part_description} (Copy)",
        customer_id=source.customer_id,
        customer_contact_id=source.customer_contact_id,
        design_leader_id=source.design_leader_id,
        designer_id=source.designer_id,
        surfacer_id=source.surfacer_id,
        stream_id=source.stream_id,
        team_id=source.team_id,
        project_type_id=project_type_id,
        project_template_id=source.project_template_id,
        code=new_code,
        quoted_hours=source.quoted_hours,
        due_date=source.due_date,
        project_stage=source.project_stage,
        execution_status=ExecutionStatus.currently_being_worked_on,
        priority=source.priority,
        notes=source.notes,
        project_folder_path=source.project_folder_path,
        cad_folder_path=source.cad_folder_path,
        released_folder_path=source.released_folder_path,
    )
    db.add(clone)
    db.flush()

    template = resolve_template(
        db,
        project_type_id=project_type_id,
        customer_id=source.customer_id,
        template_id=source.project_template_id,
    )
    clone.project_template_id = template.id
    create_milestones_from_template(db, project=clone, template=template)
    db.commit()
    db.refresh(clone)
    recalculate_project(db, clone.id)
    return clone


project_decision = CRUDProjectDecision()
engineering_change = CRUDEngineeringChange()
