"""Strategic initiatives: lightweight plans linked to an objective and to existing projects.

Initiatives reference projects; they never copy project data. Progress is the owner's reported
progress and is labelled so; project figures stay on the project.
"""

from __future__ import annotations

import json
from datetime import date
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.management import ManagementAction, StrategicInitiative, StrategicObjective
from app.models.models import Project, User
from app.schemas.management import InitiativeCreate, InitiativeUpdate
from app.services.management.access import ManagementAccess, ManagementForbidden
from app.services.management.events import list_events, record_event, user_name

OWNER_FIELDS = {"status", "status_reason", "progress_percent", "milestones", "notes", "risks", "dependencies"}


def _check(db: Session, *, objective_id=None, owner_id=None, project_ids=None) -> None:
    if objective_id is not None and db.get(StrategicObjective, objective_id) is None:
        raise ValueError("Unknown objective")
    if owner_id is not None and db.get(User, owner_id) is None:
        raise ValueError("Unknown owner")
    if project_ids:
        found = set(db.scalars(select(Project.id).where(Project.id.in_(project_ids), Project.is_deleted.is_(False))).all())
        if len(found) != len(set(project_ids)):
            raise ValueError("Unknown project in related projects")


def get_initiative(db: Session, initiative_id: UUID) -> StrategicInitiative:
    row = db.get(StrategicInitiative, initiative_id)
    if row is None:
        raise LookupError("Initiative not found")
    return row


def _projects(db: Session, access: ManagementAccess, ids: list[str]) -> tuple[list[dict], int]:
    if not ids:
        return [], 0
    uuids = [UUID(i) for i in ids]
    stmt = select(Project).where(Project.id.in_(uuids), Project.is_deleted.is_(False))
    if access.visibility_clause is not None:
        stmt = stmt.where(and_(access.visibility_clause))
    rows = db.scalars(stmt).all()
    visible = [{"id": str(p.id), "code": p.code, "tool_number": p.tool_number, "part_description": p.part_description,
                "status": p.execution_status.value if p.execution_status else None,
                "due_date": p.due_date.isoformat() if p.due_date else None} for p in rows]
    return visible, len(uuids) - len(visible)


def serialize(db: Session, access: ManagementAccess, row: StrategicInitiative, today: date | None = None,
              *, detail: bool = False) -> dict:
    today = today or date.today()
    owner = db.get(User, row.owner_id) if row.owner_id else None
    objective = db.get(StrategicObjective, row.objective_id) if row.objective_id else None
    milestones = json.loads(row.milestones_json or "[]")
    projects, hidden = _projects(db, access, json.loads(row.related_project_ids_json or "[]"))
    out = {
        "id": str(row.id), "name": row.name, "description": row.description,
        "objective_id": str(row.objective_id) if row.objective_id else None,
        "objective": objective.title if objective else None,
        "owner_id": str(row.owner_id) if row.owner_id else None, "owner": user_name(owner),
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "target_date": row.target_date.isoformat() if row.target_date else None,
        "status": row.status, "priority": row.priority,
        "progress_percent": row.progress_percent, "progress_kind": "reported",
        "overdue": bool(row.target_date and row.target_date < today and row.status not in {"completed", "cancelled"}),
        "milestones": milestones,
        "milestones_done": sum(1 for m in milestones if m.get("done")),
        "dependencies": row.dependencies, "risks": row.risks, "notes": row.notes,
        "projects": projects, "projects_hidden": hidden,
        "can_edit": access.manage or row.owner_id == access.user.id,
    }
    if detail:
        out["events"] = list_events(db, "initiative", row.id)
        out["actions"] = [{"id": str(a.id), "title": a.title, "status": a.status,
                           "due_date": a.due_date.isoformat() if a.due_date else None}
                          for a in db.scalars(select(ManagementAction).where(ManagementAction.initiative_id == row.id)).all()]
    return out


def list_initiatives(db: Session, access: ManagementAccess, *, objective_id: UUID | None = None,
                     status: str | None = None) -> list[dict]:
    stmt = select(StrategicInitiative)
    if objective_id is not None:
        stmt = stmt.where(StrategicInitiative.objective_id == objective_id)
    if status:
        stmt = stmt.where(StrategicInitiative.status == status)
    rows = db.scalars(stmt.order_by(StrategicInitiative.target_date.is_(None), StrategicInitiative.target_date,
                                    StrategicInitiative.name)).all()
    return [serialize(db, access, r) for r in rows]


def create_initiative(db: Session, access: ManagementAccess, body: InitiativeCreate) -> StrategicInitiative:
    if not access.manage:
        raise ManagementForbidden("Creating initiatives needs the Manage strategy permission.")
    _check(db, objective_id=body.objective_id, owner_id=body.owner_id, project_ids=body.related_project_ids)
    row = StrategicInitiative(
        name=body.name, description=body.description, objective_id=body.objective_id, owner_id=body.owner_id,
        start_date=body.start_date, target_date=body.target_date, status=body.status,
        progress_percent=body.progress_percent, priority=body.priority,
        milestones_json=json.dumps([m.model_dump(mode="json") for m in body.milestones]) if body.milestones else None,
        dependencies=body.dependencies, risks=body.risks, notes=body.notes,
        related_project_ids_json=json.dumps([str(p) for p in body.related_project_ids]) if body.related_project_ids else None,
        created_by_id=access.user.id,
    )
    db.add(row)
    db.flush()
    record_event(db, entity_type="initiative", entity_id=row.id, event_type="created", summary="Initiative created",
                 actor=access.user, new={"name": row.name, "status": row.status})
    return row


def update_initiative(db: Session, access: ManagementAccess, row: StrategicInitiative, body: InitiativeUpdate) -> None:
    owner = row.owner_id == access.user.id
    if not (access.manage or owner):
        raise ManagementForbidden("Only the owner or a strategy manager can change this initiative.")
    data = body.model_dump(exclude_unset=True)
    if not access.manage and set(data) - OWNER_FIELDS:
        raise ManagementForbidden("The owner can update status, progress, milestones, risks and notes only.")
    _check(db, objective_id=data.get("objective_id"), owner_id=data.get("owner_id"),
           project_ids=data.get("related_project_ids"))
    old, new = {}, {}
    for name in ("name", "description", "objective_id", "owner_id", "start_date", "target_date", "priority",
                 "progress_percent", "dependencies", "risks", "notes"):
        if name in data and getattr(row, name) != data[name]:
            old[name], new[name] = getattr(row, name), data[name]
            setattr(row, name, data[name])
    if "milestones" in data and data["milestones"] is not None:
        row.milestones_json = json.dumps([dict(m, due_date=m["due_date"].isoformat() if m.get("due_date") else None)
                                          for m in data["milestones"]])
        new["milestones"] = len(data["milestones"])
    if "related_project_ids" in data and data["related_project_ids"] is not None:
        row.related_project_ids_json = json.dumps([str(p) for p in data["related_project_ids"]])
        new["related_project_ids"] = [str(p) for p in data["related_project_ids"]]
    if row.start_date and row.target_date and row.target_date < row.start_date:
        raise ValueError("Target date is before the start date")
    if old or new:
        record_event(db, entity_type="initiative", entity_id=row.id, event_type="updated",
                     summary="Initiative updated", actor=access.user, old=old, new=new)
    status = data.get("status")
    if status and status != row.status:
        reason = data.get("status_reason")
        if status in {"on_hold", "at_risk", "cancelled"} and not reason:
            raise ValueError("Give a reason for this status")
        record_event(db, entity_type="initiative", entity_id=row.id, event_type="status_changed",
                     summary=f"Status {row.status} -> {status}", actor=access.user, old=row.status, new=status,
                     reason=reason)
        row.status = status
