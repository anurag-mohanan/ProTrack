"""Seed starter workstream catalog (admin-editable; not hardcoded in UX)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import ProjectType
from app.models.workstream import Workstream

# Optional starter catalog — inactive-safe; admins can rename/deactivate/reorder.
# Tuple: name, code, description, display_order, color, icon
STARTER_WORKSTREAMS: list[tuple[str, str | None, str, int, str | None, str | None]] = [
    ("Mold Design", "MOLD", "Mold design delivery workstream", 10, "#0d9488", "precision"),
    ("Fixture Design", "FIXTURE", "Fixture and tooling fixture design", 20, "#0369a1", "build"),
    ("CAD Development", "CAD", "CAD / product design engineering", 30, "#7c3aed", "architecture"),
    ("Engineering Changes", "ECO", "Engineering change and ECO work", 40, "#c2410c", "change"),
    ("Product Development", "PD", "New product development", 50, "#b45309", "science"),
    ("Concept", "CONCEPT", "Early concept and ideation", 60, "#64748b", "lightbulb"),
    ("Validation", "VALID", "Validation, trials, and sign-off", 70, "#15803d", "verified"),
]

# Project type name (lower) → workstream code. Admin can override via default_workstream_id.
# Kept in seed config only — UI never hardcodes discipline names.
_TYPE_TO_WORKSTREAM_CODE: dict[str, str] = {
    "mold design": "MOLD",
    "cad development": "CAD",
    "fixture": "FIXTURE",
    "fixture design": "FIXTURE",
    "engineering change": "ECO",
    "engineering changes": "ECO",
    "product development": "PD",
    "concept": "CONCEPT",
    "validation": "VALID",
    "dfm": "MOLD",
    "surfacing": "MOLD",
    "electrode": "MOLD",
}


def ensure_workstream_catalog(session: Session) -> int:
    """Insert missing starter workstreams by name. Returns rows created."""
    existing_rows = list(session.scalars(select(Workstream)).all())
    existing = {row.name.lower() for row in existing_rows}
    created = 0
    for name, code, description, order, color, icon in STARTER_WORKSTREAMS:
        if name.lower() in existing:
            continue
        session.add(
            Workstream(
                name=name,
                code=code,
                description=description,
                display_order=order,
                color=color,
                icon=icon,
                is_active=True,
            )
        )
        created += 1
    # Backfill color/icon on existing rows that lack them (non-destructive).
    color_by_name = {row[0].lower(): (row[4], row[5]) for row in STARTER_WORKSTREAMS}
    for row in existing_rows:
        preset = color_by_name.get(row.name.lower())
        if not preset:
            continue
        color, icon = preset
        if row.color is None and color:
            row.color = color
        if row.icon is None and icon:
            row.icon = icon
    if created:
        session.flush()
    return created


def ensure_project_type_workstream_defaults(session: Session) -> int:
    """Link project types to default workstreams when unset (seed mapping only)."""
    workstreams = list(session.scalars(select(Workstream)).all())
    by_code = {(ws.code or "").upper(): ws for ws in workstreams if ws.code}
    by_name = {ws.name.lower(): ws for ws in workstreams}
    updated = 0
    for project_type in session.scalars(select(ProjectType)).all():
        if getattr(project_type, "default_workstream_id", None) is not None:
            continue
        key = (project_type.name or "").strip().lower()
        code = _TYPE_TO_WORKSTREAM_CODE.get(key)
        target = None
        if code:
            target = by_code.get(code.upper())
        if target is None:
            target = by_name.get(key)
        if target is None:
            # Soft contain match: type name inside workstream name or vice versa
            for ws in workstreams:
                wn = ws.name.lower()
                if key and (key in wn or wn in key):
                    target = ws
                    break
        if target is None:
            continue
        project_type.default_workstream_id = target.id
        updated += 1
    if updated:
        session.flush()
    return updated
