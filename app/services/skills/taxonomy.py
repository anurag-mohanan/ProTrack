"""Configurable engineering skills taxonomy on the existing ``skills`` master.

* Duplicates are detected on a normalised key over names and aliases, across
  active and inactive skills. Renaming keeps the old name as an alias so the
  startup seed and later imports cannot re-create it.
* Skills are deactivated, never deleted: employee records and history keep
  pointing at them.
* The standard pack only adds missing skills; it never renames, reclassifies,
  reactivates or deletes anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ActivityAction, EntityType
from app.models.foundation import EngineeringDiscipline, Skill
from app.models.models import Customer, User
from app.models.skills import SkillProficiencyLevel, SkillRelationship
from app.services.activity_service import log_activity
from app.services.skills.errors import (
    SkillConflictError,
    SkillNotFoundError,
    SkillValidationError,
)
from app.services.skills.naming import (
    dump_aliases,
    normalize_skill_name,
    parse_aliases,
    skill_name_keys,
)

LEVELS = (1, 2, 3, 4, 5)
DEFAULT_SPECIALIST_LEVEL = 4
DEFAULT_LEVELS: dict[int, tuple[str, str]] = {
    1: ("Awareness", "Understands basic concepts and can assist under supervision."),
    2: ("Basic", "Can complete simple tasks with guidance."),
    3: ("Intermediate", "Can independently complete standard tasks."),
    4: ("Advanced", "Can handle complex work and guide other designers."),
    5: ("Expert", "Recognised specialist who can establish standards and mentor others."),
}

SKILL_KINDS: dict[str, str] = {
    "software": "CAD / engineering software",
    "discipline": "Engineering discipline",
    "specialization": "Specialisation within a discipline",
    "documentation": "Engineering documentation",
    "customer_standard": "Customer standard or workflow",
    "other": "Other",
}

RELATION_TYPES: dict[str, str] = {
    "used_with": "Software used for this discipline or specialisation",
    "specialization_of": "Is a specialisation of",
    "related": "Related skill",
    "prerequisite": "Prerequisite for",
}

CAD_CATEGORY = "CAD software"
STANDARD_TAXONOMY: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    # (category, kind, name, aliases)
    (CAD_CATEGORY, "software", "Siemens NX", ("NX", "Unigraphics", "UG NX", "NX CAD")),
    (CAD_CATEGORY, "software", "Cimatron", ("Cimatron E",)),
    ("Mold design engineering", "discipline", "Injection mold design", ("Plastic injection mold design",)),
    ("Mold design engineering", "specialization", "Mold layout", ()),
    ("Mold design engineering", "specialization", "Core and cavity design", ("Core cavity design",)),
    ("Mold design engineering", "specialization", "Parting line and shut-off design", ("Parting line design",)),
    ("Mold design engineering", "specialization", "Slider and lifter design", ()),
    ("Mold design engineering", "specialization", "Cooling system design", ()),
    ("Mold design engineering", "specialization", "Ejection system design", ()),
    ("Mold design engineering", "specialization", "Hot runner integration", ()),
    ("Mold design engineering", "specialization", "Moldbase and standard component selection", ()),
    ("Mold design engineering", "specialization", "Mold design detailing", ()),
    ("Surfacing", "specialization", "Part surfacing", ()),
    ("Surfacing", "specialization", "Mold surface preparation", ()),
    ("Surfacing", "specialization", "Core and cavity surface development", ()),
    ("Surfacing", "specialization", "Surface extension and repair", ()),
    ("Surfacing", "specialization", "Complex automotive plastic surfacing", ()),
    ("Fixture and tooling engineering", "discipline", "Fixture design", ()),
    ("Fixture and tooling engineering", "specialization", "Assembly fixture design", ()),
    ("Fixture and tooling engineering", "specialization", "Inspection fixture design", ("Checking fixture design",)),
    ("Fixture and tooling engineering", "specialization", "Tooling support", ()),
    ("Fixture and tooling engineering", "specialization", "Electrode design", ()),
    ("Engineering documentation", "documentation", "2D detailing", ("2D drawing detailing",)),
    ("Engineering documentation", "documentation", "Engineering drawings", ()),
    ("Engineering documentation", "documentation", "BOM preparation", ("Bill of materials preparation",)),
    ("Engineering documentation", "documentation", "Design standards and documentation", ()),
)


# --- Proficiency framework -------------------------------------------------


def proficiency_framework(db: Session) -> list[dict]:
    stored = {row.level: row for row in db.scalars(select(SkillProficiencyLevel)).all()}
    out = []
    for level in LEVELS:
        default_name, default_description = DEFAULT_LEVELS[level]
        row = stored.get(level)
        out.append(
            {
                "level": level,
                "name": row.name if row else default_name,
                "description": (row.description if row else default_description) or "",
                "is_default": row is None,
            }
        )
    return out


def level_names(db: Session) -> dict[int, str]:
    return {row["level"]: row["name"] for row in proficiency_framework(db)}


def validate_level(value: int | None, *, field_name: str = "level", required: bool = True) -> int | None:
    if value is None:
        if required:
            raise SkillValidationError(f"{field_name} is required.")
        return None
    if int(value) not in LEVELS:
        raise SkillValidationError(f"{field_name} must be between 1 and 5.")
    return int(value)


def update_proficiency_level(db: Session, *, level: int, name: str, description: str | None, actor: User) -> None:
    validate_level(level)
    name = (name or "").strip()
    if not name:
        raise SkillValidationError("Level name is required.")
    row = db.scalar(select(SkillProficiencyLevel).where(SkillProficiencyLevel.level == level))
    old = {"name": row.name, "description": row.description} if row else {"name": DEFAULT_LEVELS[level][0]}
    if row is None:
        row = SkillProficiencyLevel(level=level, name=name, description=description)
        db.add(row)
    else:
        row.name = name
        row.description = description
    db.flush()
    _log_taxonomy(db, actor, row.id, {"proficiency_level": level, **old}, {"proficiency_level": level, "name": name, "description": description})


# --- Skills ----------------------------------------------------------------


@dataclass
class SkillInput:
    name: str
    category: str | None = None
    kind: str | None = None
    description: str | None = None
    aliases: list[str] = field(default_factory=list)
    discipline_id: UUID | None = None
    customer_id: UUID | None = None
    is_critical: bool = False
    min_verified_coverage: int | None = None
    specialist_level: int | None = None
    reassessment_months: int | None = None
    sort_order: int = 0
    is_active: bool = True


def _log_taxonomy(db: Session, actor: User, entity_id: UUID, old: object, new: object) -> None:
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.settings,
        entity_id=entity_id,
        action=ActivityAction.skill_taxonomy_changed,
        old_value=old,
        new_value=new,
        module="skills",
        commit=False,
    )


def _snapshot(skill: Skill) -> dict:
    return {
        "name": skill.name,
        "category": skill.category,
        "kind": skill.kind,
        "aliases": parse_aliases(skill.aliases),
        "discipline_id": str(skill.discipline_id) if skill.discipline_id else None,
        "customer_id": str(skill.customer_id) if skill.customer_id else None,
        "is_critical": bool(skill.is_critical),
        "min_verified_coverage": skill.min_verified_coverage,
        "specialist_level": skill.specialist_level,
        "reassessment_months": skill.reassessment_months,
        "is_active": bool(skill.is_active),
    }


def find_conflicts(db: Session, keys: set[str], *, exclude_id: UUID | None = None) -> list[Skill]:
    conflicts = []
    for skill in db.scalars(select(Skill)).all():
        if exclude_id is not None and skill.id == exclude_id:
            continue
        if skill_name_keys(skill.name, skill.aliases) & keys:
            conflicts.append(skill)
    return conflicts


def _clean_category(db: Session, category: str | None) -> str | None:
    """Reuse an existing category's spelling when only case or spacing differs."""
    text = " ".join((category or "").split())
    if not text:
        return None
    key = normalize_skill_name(text)
    for existing in db.scalars(select(Skill.category).where(Skill.category.is_not(None)).distinct()).all():
        if existing and normalize_skill_name(existing) == key:
            return existing
    return text


def _validate(db: Session, data: SkillInput) -> None:
    if not data.name or not data.name.strip():
        raise SkillValidationError("Skill name is required.")
    if len(data.name.strip()) > 100:
        raise SkillValidationError("Skill name must be 100 characters or fewer.")
    if data.kind is not None and data.kind not in SKILL_KINDS:
        raise SkillValidationError(f"Unknown skill type '{data.kind}'.")
    if data.discipline_id is not None and db.get(EngineeringDiscipline, data.discipline_id) is None:
        raise SkillValidationError("Engineering discipline not found.")
    if data.customer_id is not None and db.get(Customer, data.customer_id) is None:
        raise SkillValidationError("Customer not found.")
    validate_level(data.specialist_level, field_name="specialist_level", required=False)
    for name, value in (("min_verified_coverage", data.min_verified_coverage), ("reassessment_months", data.reassessment_months)):
        if value is not None and int(value) < 1:
            raise SkillValidationError(f"{name} must be at least 1.")


def _raise_conflict(conflicts: list[Skill]) -> None:
    first = conflicts[0]
    raise SkillConflictError(
        f"'{first.name}' already exists"
        + ("" if first.is_active else " (inactive — reactivate it instead)")
        + " with the same or an equivalent name.",
        detail={"conflicting_skill_ids": [str(s.id) for s in conflicts]},
    )


def create_skill(db: Session, data: SkillInput, *, actor: User) -> Skill:
    _validate(db, data)
    name = " ".join(data.name.split())
    aliases_raw = dump_aliases([a for a in data.aliases if normalize_skill_name(a) != normalize_skill_name(name)])
    conflicts = find_conflicts(db, skill_name_keys(name, aliases_raw))
    if conflicts:
        _raise_conflict(conflicts)
    skill = Skill(
        name=name,
        category=_clean_category(db, data.category),
        kind=data.kind,
        description=(data.description or "").strip() or None,
        aliases=aliases_raw,
        discipline_id=data.discipline_id,
        customer_id=data.customer_id,
        is_critical=bool(data.is_critical),
        min_verified_coverage=data.min_verified_coverage,
        specialist_level=data.specialist_level,
        reassessment_months=data.reassessment_months,
        sort_order=data.sort_order or 0,
        is_active=bool(data.is_active),
    )
    db.add(skill)
    db.flush()
    _log_taxonomy(db, actor, skill.id, None, _snapshot(skill))
    return skill


def update_skill(db: Session, skill: Skill, data: SkillInput, *, actor: User) -> Skill:
    _validate(db, data)
    before = _snapshot(skill)
    name = " ".join(data.name.split())
    aliases = list(data.aliases)
    if normalize_skill_name(name) != normalize_skill_name(skill.name):
        aliases.append(skill.name)
    aliases_raw = dump_aliases([a for a in aliases if normalize_skill_name(a) != normalize_skill_name(name)])
    conflicts = find_conflicts(db, skill_name_keys(name, aliases_raw), exclude_id=skill.id)
    if conflicts:
        _raise_conflict(conflicts)
    skill.name = name
    skill.category = _clean_category(db, data.category)
    skill.kind = data.kind
    skill.description = (data.description or "").strip() or None
    skill.aliases = aliases_raw
    skill.discipline_id = data.discipline_id
    skill.customer_id = data.customer_id
    skill.is_critical = bool(data.is_critical)
    skill.min_verified_coverage = data.min_verified_coverage
    skill.specialist_level = data.specialist_level
    skill.reassessment_months = data.reassessment_months
    skill.sort_order = data.sort_order or 0
    skill.is_active = bool(data.is_active)
    db.flush()
    after = _snapshot(skill)
    if after != before:
        _log_taxonomy(db, actor, skill.id, before, after)
    return skill


def rename_category(db: Session, *, old: str, new: str, actor: User) -> int:
    new_text = " ".join((new or "").split())
    if not new_text:
        raise SkillValidationError("New category name is required.")
    key = normalize_skill_name(old)
    rows = [s for s in db.scalars(select(Skill).where(Skill.category.is_not(None))).all() if normalize_skill_name(s.category) == key]
    if not rows:
        raise SkillNotFoundError(f"No skills are in category '{old}'.")
    target = new_text
    for existing in db.scalars(select(Skill.category).where(Skill.category.is_not(None)).distinct()).all():
        if existing and normalize_skill_name(existing) == normalize_skill_name(new_text) and normalize_skill_name(existing) != key:
            target = existing
    for skill in rows:
        skill.category = target
    db.flush()
    _log_taxonomy(db, actor, rows[0].id, {"category": old, "skills": len(rows)}, {"category": target, "skills": len(rows)})
    return len(rows)


def get_skill(db: Session, skill_id: UUID) -> Skill:
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise SkillNotFoundError("Skill not found.")
    return skill


# --- Relationships ---------------------------------------------------------


def _parents(db: Session, skill_id: UUID) -> set[UUID]:
    seen: set[UUID] = set()
    frontier = {skill_id}
    while frontier:
        rows = db.scalars(
            select(SkillRelationship.to_skill_id).where(
                SkillRelationship.from_skill_id.in_(frontier),
                SkillRelationship.relation_type == "specialization_of",
            )
        ).all()
        frontier = {r for r in rows if r not in seen}
        seen |= frontier
    return seen


def add_relationship(
    db: Session, *, from_skill_id: UUID, to_skill_id: UUID, relation_type: str, note: str | None, actor: User
) -> SkillRelationship:
    if relation_type not in RELATION_TYPES:
        raise SkillValidationError(f"Unknown relationship type '{relation_type}'.")
    if from_skill_id == to_skill_id:
        raise SkillValidationError("A skill cannot be related to itself.")
    get_skill(db, from_skill_id)
    get_skill(db, to_skill_id)
    existing = db.scalar(
        select(SkillRelationship).where(
            SkillRelationship.from_skill_id == from_skill_id,
            SkillRelationship.to_skill_id == to_skill_id,
            SkillRelationship.relation_type == relation_type,
        )
    )
    if existing is not None:
        raise SkillConflictError("This relationship already exists.")
    if relation_type == "specialization_of" and from_skill_id in _parents(db, to_skill_id) | {to_skill_id}:
        raise SkillValidationError("This would make a skill a specialisation of itself.")
    row = SkillRelationship(
        from_skill_id=from_skill_id,
        to_skill_id=to_skill_id,
        relation_type=relation_type,
        note=(note or "").strip() or None,
        created_by_id=actor.id,
    )
    db.add(row)
    db.flush()
    _log_taxonomy(db, actor, row.id, None, {"from": str(from_skill_id), "to": str(to_skill_id), "type": relation_type})
    return row


def remove_relationship(db: Session, relationship_id: UUID, *, actor: User) -> None:
    row = db.get(SkillRelationship, relationship_id)
    if row is None:
        raise SkillNotFoundError("Relationship not found.")
    _log_taxonomy(db, actor, row.id, {"from": str(row.from_skill_id), "to": str(row.to_skill_id), "type": row.relation_type}, None)
    db.delete(row)
    db.flush()


# --- Standard pack ---------------------------------------------------------


def load_standard_taxonomy(db: Session, *, actor: User, dry_run: bool) -> dict:
    skills = list(db.scalars(select(Skill)).all())
    key_to_skill: dict[str, Skill] = {}
    for skill in skills:
        for key in skill_name_keys(skill.name, skill.aliases):
            key_to_skill.setdefault(key, skill)
    # When a pack skill already exists, new pack skills in the same pack category
    # take that skill's category label so related skills stay grouped.
    category_label: dict[str, str] = {}
    for category, _kind, name, aliases in STANDARD_TAXONOMY:
        match = next((key_to_skill[k] for k in skill_name_keys(name, dump_aliases(list(aliases))) if k in key_to_skill), None)
        if match is not None and match.category and category not in category_label:
            category_label[category] = match.category
    created: list[dict] = []
    existing: list[dict] = []
    for category, kind, name, aliases in STANDARD_TAXONOMY:
        aliases_raw = dump_aliases(list(aliases))
        match = next((key_to_skill[k] for k in skill_name_keys(name, aliases_raw) if k in key_to_skill), None)
        if match is not None:
            existing.append(
                {
                    "name": name,
                    "existing_skill_id": str(match.id),
                    "existing_name": match.name,
                    "existing_is_active": bool(match.is_active),
                    "existing_kind": match.kind,
                }
            )
            continue
        label = category_label.get(category, category)
        created.append({"name": name, "category": label, "kind": kind})
        if not dry_run:
            skill = create_skill(db, SkillInput(name=name, category=label, kind=kind, aliases=list(aliases)), actor=actor)
            for key in skill_name_keys(skill.name, skill.aliases):
                key_to_skill.setdefault(key, skill)
    return {"dry_run": dry_run, "created": created, "already_present": existing}


def holder_counts(db: Session) -> dict[UUID, int]:
    from app.models.foundation import UserSkill
    from app.models.skills import STATUS_ARCHIVED

    return {
        skill_id: int(count)
        for skill_id, count in db.execute(
            select(UserSkill.skill_id, func.count(UserSkill.id))
            .where(UserSkill.status != STATUS_ARCHIVED)
            .group_by(UserSkill.skill_id)
        ).all()
    }
