"""Shared helpers for assistant tools: scoped project lookup, safe text, number formatting."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.models.models import Customer, Project, User
from app.schemas.engineering_metrics import MetricValue
from app.services.assistant.context import AssistantContext
from app.services.assistant.types import Source, ToolInputError

MAX_TEXT = 160


def clip(value: object | None, limit: int = MAX_TEXT) -> str | None:
    """Record text is data, not instructions; keep it short and on one line."""
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def num(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def metric(value: MetricValue) -> dict:
    """Keep the metrics service's own status and reason; never turn unavailable into zero."""
    return {"value": num(value.value), "status": value.status, "reason": value.reason}


def person_name(user: User | None) -> str | None:
    if user is None:
        return None
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or None


def project_label(project: Project) -> str:
    ref = project.code or project.tool_number
    return f"{ref} — {clip(project.part_description, 60)}" if project.part_description else ref


def project_source(project: Project, detail: str | None = None) -> Source:
    return Source(kind="project", ref=str(project.id), label=project_label(project), detail=detail,
                  route=f"/projects/{project.id}")


def visible_projects_stmt(ctx: AssistantContext, *, include_archived: bool = True):
    stmt = select(Project).where(Project.is_deleted.is_(False)).options(
        selectinload(Project.customer), selectinload(Project.design_leader),
        selectinload(Project.designer), selectinload(Project.surfacer),
    )
    if not include_archived:
        stmt = stmt.where(Project.is_archived.is_(False))
    if ctx.visibility_clause is not None:
        stmt = stmt.where(ctx.visibility_clause)
    return stmt


def resolve_project(ctx: AssistantContext, ref: str) -> Project:
    """Find a project by code, tool number or id inside the caller's visibility only.

    A project outside the caller's scope gets the same answer as one that does not
    exist, so the assistant cannot be used to probe for project numbers.
    """
    ref = (ref or "").strip()
    if not ref:
        raise ToolInputError("Give a project code or tool number.")
    conditions = [func.lower(Project.code) == ref.lower(), func.lower(Project.tool_number) == ref.lower()]
    try:
        conditions.append(Project.id == UUID(ref))
    except ValueError:
        pass
    matches = ctx.db.scalars(visible_projects_stmt(ctx).where(or_(*conditions))).all()
    if not matches:
        raise ToolInputError(f"No project '{clip(ref, 40)}' was found among the projects you can access.")
    if len(matches) > 1:
        raise ToolInputError(f"'{clip(ref, 40)}' matches more than one project; use the project code.")
    ctx.seen_project_ids.add(matches[0].id)
    return matches[0]


def search_condition(text: str):
    pattern = f"%{text.strip()}%"
    return or_(
        Project.code.ilike(pattern),
        Project.tool_number.ilike(pattern),
        Project.part_description.ilike(pattern),
        Project.customer_id.in_(select(Customer.id).where(Customer.name.ilike(pattern))),
    )
