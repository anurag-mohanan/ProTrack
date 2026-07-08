"""Engineering knowledge base."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.crud.project_metrics import build_project_read
from app.models.enums import ExecutionStatus
from app.models.intelligence import EngineeringChange, ProjectKnowledgeRecord
from app.models.models import Milestone, Project
from app.schemas.ai import KnowledgeRecord
from app.services.ai.base import AiContext, AiModule, round_hours


class KnowledgeBaseModule(AiModule):
    name = "knowledge_base"

    def index_completed_project(self, ctx: AiContext, project: Project) -> ProjectKnowledgeRecord:
        existing = ctx.db.scalar(
            select(ProjectKnowledgeRecord).where(ProjectKnowledgeRecord.project_id == project.id)
        )
        read = build_project_read(ctx.db, project)
        milestone_count = int(
            ctx.db.scalar(
                select(func.count()).select_from(Milestone).where(Milestone.project_id == project.id)
            )
            or 0
        )
        ec_count = int(
            ctx.db.scalar(
                select(func.count())
                .select_from(EngineeringChange)
                .where(EngineeringChange.project_id == project.id)
            )
            or 0
        )
        keywords = [
            project.tool_number,
            read.customer_name or "",
            read.project_type_name or "",
            read.designer_name or "",
        ]
        keyword_str = ",".join(k for k in keywords if k)

        if existing:
            existing.quoted_hours = project.quoted_hours
            existing.actual_hours = project.actual_hours
            existing.milestone_count = milestone_count
            existing.engineering_change_count = ec_count
            existing.keywords = keyword_str
            ctx.db.commit()
            ctx.db.refresh(existing)
            return existing

        record = ProjectKnowledgeRecord(
            project_id=project.id,
            tool_number=project.tool_number,
            customer_name=read.customer_name,
            project_type_name=read.project_type_name,
            designer_name=read.designer_name,
            surfacer_name=read.surfacer_name,
            quoted_hours=project.quoted_hours,
            actual_hours=project.actual_hours,
            milestone_count=milestone_count,
            engineering_change_count=ec_count,
            keywords=keyword_str,
            completed_at=project.completed_at,
        )
        ctx.db.add(record)
        ctx.db.commit()
        ctx.db.refresh(record)
        return record

    def run(self, ctx: AiContext, **kwargs: Any) -> list[KnowledgeRecord]:
        query = kwargs.get("query", "").strip().lower()
        customer_id = kwargs.get("customer_id")
        project_type = kwargs.get("project_type")

        completed = ctx.db.scalars(
            select(Project).where(
                Project.is_deleted.is_(False),
                Project.execution_status == ExecutionStatus.completed,
            )
        ).all()
        indexed_ids = {
            r.project_id for r in ctx.db.scalars(select(ProjectKnowledgeRecord)).all()
        }
        for project in completed:
            if project.id not in indexed_ids:
                self.index_completed_project(ctx, project)

        records = list(ctx.db.scalars(select(ProjectKnowledgeRecord)).all())

        if customer_id:
            records = [
                r
                for r in records
                if (project := ctx.db.get(Project, r.project_id))
                and str(project.customer_id) == str(customer_id)
            ]

        if query:
            records = [
                r
                for r in records
                if query in (r.tool_number or "").lower()
                or query in (r.customer_name or "").lower()
                or query in (r.keywords or "").lower()
                or query in (r.project_type_name or "").lower()
            ]
        if project_type:
            records = [
                r for r in records if (r.project_type_name or "").lower() == project_type.lower()
            ]

        return [
            KnowledgeRecord(
                id=r.id,
                project_id=r.project_id,
                tool_number=r.tool_number,
                customer_name=r.customer_name,
                project_type_name=r.project_type_name,
                designer_name=r.designer_name,
                surfacer_name=r.surfacer_name,
                quoted_hours=round_hours(r.quoted_hours),
                actual_hours=round_hours(r.actual_hours),
                milestone_count=r.milestone_count,
                engineering_change_count=r.engineering_change_count,
                mechanism=r.mechanism,
                keywords=(r.keywords or "").split(",") if r.keywords else [],
                completed_at=r.completed_at,
            )
            for r in records[: int(kwargs.get("limit", 50))]
        ]
