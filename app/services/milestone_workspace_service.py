"""Milestone workspace helpers — summaries, enrichment, reorder, audit."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ActivityAction, EntityType, MilestoneStatus
from app.models.models import Milestone, Project, TimesheetEntry, User
from app.schemas.project import MilestoneRead, ProjectMilestoneSummary
from app.services.activity_service import log_activity


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def batch_milestone_actual_hours(
    db: Session,
    milestone_ids: list[UUID],
) -> dict[UUID, Decimal]:
    if not milestone_ids:
        return {}
    rows = db.execute(
        select(TimesheetEntry.milestone_id, func.coalesce(func.sum(TimesheetEntry.hours), 0))
        .where(
            TimesheetEntry.milestone_id.in_(milestone_ids),
            TimesheetEntry.is_deleted.is_(False),
        )
        .group_by(TimesheetEntry.milestone_id)
    ).all()
    return {row[0]: _decimal(row[1]) for row in rows if row[0] is not None}


def enrich_milestone_read(
    db: Session,
    milestone: Milestone,
    *,
    actual_hours: Decimal | None = None,
) -> MilestoneRead:
    if actual_hours is None:
        actual_hours = _decimal(
            db.scalar(
                select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
                    TimesheetEntry.milestone_id == milestone.id,
                    TimesheetEntry.is_deleted.is_(False),
                )
            )
        )
    assigned_name = None
    if milestone.assigned_user_id is not None:
        user = db.get(User, milestone.assigned_user_id)
        if user is not None:
            assigned_name = f"{user.first_name} {user.last_name}".strip() or user.email
    return MilestoneRead(
        id=milestone.id,
        created_at=milestone.created_at,
        updated_at=milestone.updated_at,
        project_id=milestone.project_id,
        name=milestone.name,
        description=milestone.description,
        status=milestone.status,
        due_date=milestone.due_date,
        completed_at=milestone.completed_at,
        completed_date=milestone.completed_date,
        planned_hours=_decimal(milestone.planned_hours),
        progress_percent=int(milestone.progress_percent or 0),
        assigned_user_id=milestone.assigned_user_id,
        sort_order=milestone.sort_order,
        actual_hours=actual_hours,
        assigned_user_name=assigned_name,
    )


def get_project_milestone_summary(db: Session, project_id: UUID) -> ProjectMilestoneSummary:
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError("Project not found")

    milestones = list(
        db.scalars(
            select(Milestone)
            .where(Milestone.project_id == project_id)
            .order_by(Milestone.sort_order, Milestone.name)
        ).all()
    )
    milestone_ids = [row.id for row in milestones]
    actual_by_milestone = batch_milestone_actual_hours(db, milestone_ids)

    total_planned = sum((_decimal(row.planned_hours) for row in milestones), Decimal("0"))
    total_actual = sum(actual_by_milestone.values(), Decimal("0"))
    completed_count = sum(
        1 for row in milestones if row.status == MilestoneStatus.completed
    )
    quoted = _decimal(project.quoted_hours)
    current_planned = _decimal(project.current_planned_hours or total_planned)

    return ProjectMilestoneSummary(
        total_planned_hours=total_planned,
        total_actual_hours=total_actual,
        milestone_count=len(milestones),
        completed_count=completed_count,
        remaining_hours=max(total_planned - total_actual, Decimal("0")),
        quoted_hours=quoted,
        current_planned_hours=current_planned,
        planned_variance_hours=current_planned - quoted,
    )


def recalculate_project_planned_hours(db: Session, project_id: UUID) -> Decimal:
    total = _decimal(
        db.scalar(
            select(func.coalesce(func.sum(Milestone.planned_hours), 0)).where(
                Milestone.project_id == project_id
            )
        )
    )
    project = db.get(Project, project_id)
    if project is not None:
        project.current_planned_hours = total
        db.add(project)
        db.commit()
    return total


def apply_progress_rules(update_data: dict) -> dict:
    progress = update_data.get("progress_percent")
    if progress is not None:
        progress = max(0, min(100, int(progress)))
        update_data["progress_percent"] = progress
        if progress == 100:
            update_data["status"] = MilestoneStatus.completed
        elif progress > 0 and update_data.get("status") in (
            None,
            MilestoneStatus.not_started,
        ):
            update_data.setdefault("status", MilestoneStatus.in_progress)
    if update_data.get("status") == MilestoneStatus.completed:
        update_data["progress_percent"] = 100
        if update_data.get("completed_at") is None:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            update_data["completed_at"] = now
            update_data["completed_date"] = now.date()
    elif "status" in update_data and update_data["status"] != MilestoneStatus.completed:
        update_data["completed_at"] = None
        update_data["completed_date"] = None
    return update_data


def log_milestone_field_changes(
    db: Session,
    *,
    actor: User,
    milestone: Milestone,
    previous: dict,
    updated: Milestone,
) -> None:
    field_labels = {
        "name": "Name",
        "planned_hours": "Planned Hours",
        "due_date": "Target Date",
        "assigned_user_id": "Assigned To",
        "status": "Status",
        "progress_percent": "Progress",
    }
    changes: list[str] = []
    for field, label in field_labels.items():
        old = previous.get(field)
        new = getattr(updated, field)
        if old != new:
            changes.append(f"{label}: {old} → {new}")
    if not changes:
        return
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.milestone,
        entity_id=updated.id,
        action=ActivityAction.milestone_updated,
        old_value=previous.get("name"),
        new_value="; ".join(changes),
    )


def reorder_milestones(
    db: Session,
    *,
    project_id: UUID,
    items: list[tuple[UUID, int]],
    actor: User | None = None,
) -> list[Milestone]:
    milestones = {
        row.id: row
        for row in db.scalars(
            select(Milestone).where(Milestone.project_id == project_id)
        ).all()
    }
    for milestone_id, sort_order in items:
        row = milestones.get(milestone_id)
        if row is None:
            continue
        row.sort_order = sort_order
        db.add(row)
    db.commit()
    if actor is not None:
        log_activity(
            db,
            user=actor,
            entity_type=EntityType.milestone,
            entity_id=project_id,
            action=ActivityAction.milestone_reordered,
            new_value=f"{len(items)} milestones reordered",
        )
    return list(
        db.scalars(
            select(Milestone)
            .where(Milestone.project_id == project_id)
            .order_by(Milestone.sort_order, Milestone.name)
        ).all()
    )
