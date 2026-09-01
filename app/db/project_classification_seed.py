"""Seed configurable small-task types for project classification."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import ProjectSmallTaskType

DEFAULT_PROJECT_SMALL_TASK_TYPES: list[tuple[str, str, int]] = [
    ("blockout_only", "Blockout Only", 10),
    ("feasibility", "Feasibility", 20),
    ("engineering_change", "Engineering Change", 30),
    ("design_change", "Design Change", 40),
    ("modification", "Modification", 50),
    ("requirements_review", "Requirements Review", 60),
    ("design_review", "Design Review", 70),
    ("cad_update", "CAD Update", 80),
    ("drawing_update", "Drawing Update", 90),
    ("rework", "Rework", 100),
    ("analysis", "Analysis", 110),
    ("other", "Other", 120),
]


def ensure_project_small_task_types(db: Session) -> int:
    existing = {
        item.code.strip().lower(): item
        for item in db.scalars(select(ProjectSmallTaskType)).all()
    }
    created = 0
    for code, name, sort_order in DEFAULT_PROJECT_SMALL_TASK_TYPES:
        key = code.strip().lower()
        if key in existing:
            row = existing[key]
            if not row.is_active:
                row.is_active = True
            if not row.name:
                row.name = name
            continue
        db.add(
            ProjectSmallTaskType(
                code=code,
                name=name,
                sort_order=sort_order,
                is_active=True,
            )
        )
        created += 1
    if created:
        db.flush()
    return created
