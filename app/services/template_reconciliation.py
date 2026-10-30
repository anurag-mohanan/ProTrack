"""Smart project template change: reconcile existing milestones with a new template.

Nothing is replaced. A template change is a *plan* computed from the project's
current milestones and the selected template version, shown as a preview, and
applied only after explicit confirmation in one transaction.

Matching a template milestone to an existing project milestone
(``classify_match``):

* **confirmed** — created from that template milestone; the same template
  milestone in another version (lineage); the same template family and name; or
  the same normalised name with no stage conflict. Applied by default.
* **likely** — same normalised name but the stages differ.
* **possible** — names share at least half of their significant words and the
  stages do not conflict. Similar wording often means a different deliverable,
  so likely and possible matches are never applied unless the user picks them.
* **different** — anything else.

Duplicates among existing milestones (``classify_duplicate``):

* **confirmed** — same template identity, same name, compatible stage and the
  same completion state. Merge is the default decision.
* **likely** — same identity but one is completed and the other is not; or same
  name and stage without a shared template identity. Merge needs the user.
* **possible** — similar names, compatible stage. Merge needs the user.

Rules that always hold:

* Workflow status, completion dates, actual hours, comments and timesheets are
  never rewritten. Merged, superseded and archived milestones keep everything and
  only change ``lifecycle_state`` (see ``milestone_lifecycle``).
* A completed milestone is never merged into an incomplete one, and a pending
  record never overwrites completion evidence.
* Milestones missing from the new template are kept unless the user chooses to
  supersede, archive or merge them.
* New milestones get dates only from the template's configured offset from the
  project start date, never in the past, and owners only from the template's
  existing assignment rule. Template hours are applied only on request, because
  they change the planned (approved) hours.
* Dependencies are re-pointed on merge, bridged on supersede/archive, and never
  allowed to form a loop.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.enums import (
    ActivityAction,
    EntityType,
    ExecutionStatus,
    MilestoneStatus,
    PLANNED_STAGES,
)
from app.models.models import (
    Milestone,
    Project,
    ProjectStageEstimate,
    ProjectTemplate,
    ProjectTemplateMilestone,
    TimesheetEntry,
    User,
)
from app.models.workflow import (
    LIFECYCLE_ACTIVE,
    LIFECYCLE_ARCHIVED,
    LIFECYCLE_MERGED,
    LIFECYCLE_SUPERSEDED,
    RECON_APPLIED,
    RECON_FAILED,
    ProjectTemplateReconciliation,
)
from app.services.activity_service import log_activity
from app.services.scheduling_service import dump_id_list, parse_id_list

RECONCILIATION_VERSION = "template-reconcile-1"

CONFIRMED = "confirmed"
LIKELY = "likely"
POSSIBLE = "possible"
DIFFERENT = "different"
CLASS_LABELS = {
    CONFIRMED: "Confirmed",
    LIKELY: "Likely — needs your confirmation",
    POSSIBLE: "Possible — needs your confirmation",
    DIFFERENT: "Different",
}

ACTION_MATCH = "match"
ACTION_ADD = "add"
ACTION_RETAIN = "retain"
ACTION_SUPERSEDE = "supersede"
ACTION_ARCHIVE = "archive"
ACTION_MERGE = "merge"
EXISTING_ACTIONS = (ACTION_RETAIN, ACTION_SUPERSEDE, ACTION_ARCHIVE, ACTION_MERGE)

_STOPWORDS = frozenset({"the", "a", "an", "and", "of", "for", "to", "with"})
_SIMILARITY_THRESHOLD = 0.5
_DONE = MilestoneStatus.completed


class ReconciliationConflict(ProTrackValidationError):
    """The project changed after the preview, or the plan cannot be applied."""

    def __init__(self, detail: str):
        super().__init__(detail, status_code=409)


# --------------------------------------------------------------------------- naming


def normalize_name(name: str | None) -> str:
    text = (name or "").lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def name_tokens(name: str | None) -> frozenset[str]:
    return frozenset(token for token in normalize_name(name).split() if token not in _STOPWORDS)


def token_similarity(a: str | None, b: str | None) -> float:
    left, right = name_tokens(a), name_tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _stage(value: Any) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _stages_compatible(a: str | None, b: str | None) -> bool:
    return a is None or b is None or a == b


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- snapshot


@dataclass(frozen=True)
class TemplateRef:
    id: UUID
    lineage: UUID
    family_id: UUID
    template_id: UUID
    name: str
    norm: str
    stage: str | None
    depends_on: tuple[str, ...]
    is_required: bool
    sort_order: int
    offset_days: int | None
    estimated_hours: Decimal | None
    assigned_role: str | None
    default_assigned_user_id: UUID | None
    description: str | None


def _template_refs(db: Session, rows: list[ProjectTemplateMilestone]) -> dict[UUID, TemplateRef]:
    template_ids = {row.project_template_id for row in rows}
    families = {
        tid: (fam or tid)
        for tid, fam in db.execute(
            select(ProjectTemplate.id, ProjectTemplate.template_family_id).where(
                ProjectTemplate.id.in_(template_ids)
            )
        ).all()
    } if template_ids else {}
    return {
        row.id: TemplateRef(
            id=row.id,
            lineage=row.lineage_id or row.id,
            family_id=families.get(row.project_template_id, row.project_template_id),
            template_id=row.project_template_id,
            name=row.milestone_name,
            norm=normalize_name(row.milestone_name),
            stage=_stage(row.project_stage),
            depends_on=tuple(parse_id_list(row.depends_on_ids)),
            is_required=bool(row.is_required),
            sort_order=int(row.sort_order or 0),
            offset_days=row.default_due_offset_days,
            estimated_hours=Decimal(str(row.estimated_hours)) if row.estimated_hours is not None else None,
            assigned_role=row.assigned_role,
            default_assigned_user_id=row.default_assigned_user_id,
            description=row.description,
        )
        for row in rows
    }


@dataclass
class Snapshot:
    project: Project
    template: ProjectTemplate
    previous_template: ProjectTemplate | None
    milestones: list[Milestone]
    active: list[Milestone]
    template_items: list[TemplateRef]
    source_refs: dict[UUID, TemplateRef]
    hours: dict[UUID, Decimal]
    users: dict[UUID, str]
    has_stage_estimates: bool
    stage_total: Decimal
    fingerprint: str


def _milestone_hours(db: Session, milestone_ids: list[UUID]) -> dict[UUID, Decimal]:
    if not milestone_ids:
        return {}
    rows = db.execute(
        select(TimesheetEntry.milestone_id, func.coalesce(func.sum(TimesheetEntry.hours), 0))
        .where(TimesheetEntry.milestone_id.in_(milestone_ids), TimesheetEntry.is_deleted.is_(False))
        .group_by(TimesheetEntry.milestone_id)
    ).all()
    return {mid: Decimal(str(total or 0)) for mid, total in rows if mid is not None}


def _fingerprint(project: Project, template: ProjectTemplate, milestones: list[Milestone],
                 template_rows: list[ProjectTemplateMilestone], stage_total: Decimal) -> str:
    payload = {
        "v": RECONCILIATION_VERSION,
        "project": [
            str(project.id),
            str(project.project_template_id),
            int(project.milestone_plan_version or 0),
            _stage(project.execution_status),
            project.start_date.isoformat() if project.start_date else None,
            str(project.designer_id),
            str(project.surfacer_id),
            str(project.design_leader_id),
            str(stage_total),
        ],
        "template": str(template.id),
        "milestones": sorted(
            [
                str(m.id), m.name, _stage(m.status), m.lifecycle_state, str(m.merged_into_id),
                m.depends_on_ids, int(m.sort_order or 0), str(m.template_milestone_id),
                _stage(m.project_stage), str(m.planned_hours), str(m.assigned_user_id),
                m.completed_date.isoformat() if m.completed_date else None,
                m.updated_at.isoformat() if m.updated_at else None,
            ]
            for m in milestones
        ),
        "template_milestones": sorted(
            [
                str(r.id), r.milestone_name, r.depends_on_ids, int(r.sort_order or 0),
                _stage(r.project_stage), r.default_due_offset_days, bool(r.is_required),
                str(r.estimated_hours), r.assigned_role, str(r.default_assigned_user_id),
                bool(r.is_visible), r.updated_at.isoformat() if r.updated_at else None,
            ]
            for r in template_rows
        ),
    }
    return hashlib.sha256(json.dumps(payload, default=str).encode()).hexdigest()


def load_snapshot(db: Session, project: Project, template: ProjectTemplate) -> Snapshot:
    milestones = list(
        db.scalars(
            select(Milestone)
            .where(Milestone.project_id == project.id)
            .order_by(Milestone.sort_order, Milestone.name, Milestone.id)
        ).all()
    )
    active = [m for m in milestones if (m.lifecycle_state or LIFECYCLE_ACTIVE) == LIFECYCLE_ACTIVE]
    template_rows = list(
        db.scalars(
            select(ProjectTemplateMilestone)
            .where(ProjectTemplateMilestone.project_template_id == template.id)
            .order_by(ProjectTemplateMilestone.sort_order, ProjectTemplateMilestone.milestone_name)
        ).all()
    )
    visible = [r for r in template_rows if r.is_visible is not False]
    target_refs = _template_refs(db, visible)
    source_ids = {m.template_milestone_id for m in milestones if m.template_milestone_id}
    source_rows = list(
        db.scalars(select(ProjectTemplateMilestone).where(ProjectTemplateMilestone.id.in_(source_ids))).all()
    ) if source_ids else []
    source_refs = _template_refs(db, source_rows)
    stage_total_raw = db.scalar(
        select(func.sum(ProjectStageEstimate.current_hours)).where(ProjectStageEstimate.project_id == project.id)
    )
    user_ids = {m.assigned_user_id for m in milestones if m.assigned_user_id}
    user_ids |= {r.default_assigned_user_id for r in visible if r.default_assigned_user_id}
    user_ids |= {u for u in (project.designer_id, project.surfacer_id, project.design_leader_id) if u}
    users = {
        u.id: (f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email)
        for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()
    } if user_ids else {}
    previous = db.get(ProjectTemplate, project.project_template_id) if project.project_template_id else None
    stage_total = Decimal(str(stage_total_raw or 0))
    return Snapshot(
        project=project,
        template=template,
        previous_template=previous,
        milestones=milestones,
        active=active,
        template_items=[target_refs[r.id] for r in visible],
        source_refs=source_refs,
        hours=_milestone_hours(db, [m.id for m in milestones]),
        users=users,
        has_stage_estimates=stage_total_raw is not None,
        stage_total=stage_total,
        fingerprint=_fingerprint(project, template, milestones, template_rows, stage_total),
    )


# --------------------------------------------------------------------------- classification


def classify_match(milestone: Milestone, source: TemplateRef | None, item: TemplateRef) -> tuple[str, list[str]]:
    same_name = normalize_name(milestone.name) == item.norm
    m_stage = _stage(milestone.project_stage)
    stage_ok = _stages_compatible(m_stage, item.stage)
    if milestone.template_milestone_id == item.id:
        return CONFIRMED, ["Created from this template milestone."]
    if source is not None and source.lineage == item.lineage:
        return CONFIRMED, ["The same template milestone in another version of the template."]
    if source is not None and source.family_id == item.family_id and same_name:
        return CONFIRMED, ["Same template family and milestone name."]
    if same_name and stage_ok:
        detail = " and stage" if m_stage and item.stage else ""
        return CONFIRMED, [f"Same milestone name{detail}."]
    if same_name:
        return LIKELY, [f"Same name, but the stage differs ({m_stage} in the project, {item.stage} in the template)."]
    similarity = token_similarity(milestone.name, item.name)
    if similarity >= _SIMILARITY_THRESHOLD and stage_ok:
        shared = ", ".join(sorted(name_tokens(milestone.name) & name_tokens(item.name)))
        return POSSIBLE, [
            f"Similar name (shared words: {shared}). Similar wording can mean a different deliverable; "
            "match only if it is the same work."
        ]
    return DIFFERENT, []


def classify_duplicate(a: Milestone, a_src: TemplateRef | None, b: Milestone, b_src: TemplateRef | None) -> tuple[str, list[str]]:
    same_name = normalize_name(a.name) == normalize_name(b.name)
    stage_ok = _stages_compatible(_stage(a.project_stage), _stage(b.project_stage))
    same_identity = bool(
        (a.template_milestone_id and a.template_milestone_id == b.template_milestone_id)
        or (a_src is not None and b_src is not None and a_src.lineage == b_src.lineage)
        or (a_src is not None and b_src is not None and a_src.family_id == b_src.family_id and same_name)
    )
    conflict = (a.status == _DONE) != (b.status == _DONE)
    conflict_text = "One is completed and the other is not; merge only if they are the same work."
    if same_identity and same_name and stage_ok:
        if conflict:
            return LIKELY, ["Created from the same template milestone.", conflict_text]
        return CONFIRMED, ["Created from the same template milestone, with the same name, stage and completion state."]
    if same_name and stage_ok:
        reasons = ["Same name and stage, but not created from the same template milestone."]
        return LIKELY, reasons + ([conflict_text] if conflict else [])
    if same_identity:
        return LIKELY, ["Created from the same template milestone but renamed."] + ([conflict_text] if conflict else [])
    if token_similarity(a.name, b.name) >= _SIMILARITY_THRESHOLD and stage_ok:
        return POSSIBLE, ["Similar names; check whether they are the same deliverable."]
    return DIFFERENT, []


_STATUS_RANK = {
    MilestoneStatus.completed: 0,
    MilestoneStatus.in_progress: 1,
    MilestoneStatus.waiting: 2,
    MilestoneStatus.on_hold: 3,
    MilestoneStatus.not_started: 4,
    MilestoneStatus.not_applicable: 5,
    MilestoneStatus.cancelled: 6,
}


def _canonical_key(milestone: Milestone, *, target_template_milestone_id: UUID | None = None):
    completed = milestone.status == _DONE
    return (
        0 if completed else 1,
        (milestone.completed_date or date.max) if completed else date.max,
        0 if target_template_milestone_id and milestone.template_milestone_id == target_template_milestone_id else 1,
        _STATUS_RANK.get(milestone.status, 9),
        milestone.created_at or datetime.max,
        str(milestone.id),
    )


def choose_canonical(milestones: list[Milestone], *, target_template_milestone_id: UUID | None = None) -> Milestone:
    """Completed first (earliest completion), then the template's own record, then progress, then oldest."""
    return min(milestones, key=lambda m: _canonical_key(m, target_template_milestone_id=target_template_milestone_id))


# --------------------------------------------------------------------------- plan


@dataclass
class Plan:
    template_matches: dict[UUID, UUID]  # template milestone id -> existing milestone id
    template_adds: list[TemplateRef]
    match_candidates: dict[UUID, list[dict]]  # template milestone id -> candidates
    duplicate_pairs: list[dict]
    existing_actions: dict[UUID, tuple[str, UUID | None]]  # milestone id -> (action, merge target)
    new_rows: list[dict] = field(default_factory=list)
    dependency_changes: list[dict] = field(default_factory=list)
    order: list[str] = field(default_factory=list)  # final active order: "m:<id>" / "t:<id>"
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    planned_hours_before: Decimal = Decimal("0")
    planned_hours_after: Decimal = Decimal("0")
    deps: dict[str, list[str]] = field(default_factory=dict)
    original_deps: dict[str, list[str]] = field(default_factory=dict)


def _candidates(snap: Snapshot) -> tuple[dict[UUID, list[tuple[Milestone, str, list[str]]]], dict[UUID, UUID]]:
    by_item: dict[UUID, list[tuple[Milestone, str, list[str]]]] = {}
    for item in snap.template_items:
        rows = []
        for m in snap.active:
            cls, reasons = classify_match(m, snap.source_refs.get(m.template_milestone_id), item)
            if cls != DIFFERENT:
                rows.append((m, cls, reasons))
        by_item[item.id] = rows
    matches: dict[UUID, UUID] = {}
    taken: set[UUID] = set()
    for item in snap.template_items:
        confirmed = [m for m, cls, _ in by_item[item.id] if cls == CONFIRMED and m.id not in taken]
        if confirmed:
            chosen = choose_canonical(confirmed, target_template_milestone_id=item.id)
            matches[item.id] = chosen.id
            taken.add(chosen.id)
    return by_item, matches


def _duplicates(snap: Snapshot, matched_ids: set[UUID]) -> list[dict]:
    pairs: list[dict] = []
    active = snap.active
    parent: dict[UUID, UUID] = {m.id: m.id for m in active}

    def find(x: UUID) -> UUID:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    raw: list[tuple[Milestone, Milestone, str, list[str]]] = []
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            cls, reasons = classify_duplicate(
                a, snap.source_refs.get(a.template_milestone_id), b, snap.source_refs.get(b.template_milestone_id)
            )
            if cls == DIFFERENT:
                continue
            raw.append((a, b, cls, reasons))
            if cls == CONFIRMED:
                parent[find(a.id)] = find(b.id)
    by_id = {m.id: m for m in active}
    clusters: dict[UUID, list[Milestone]] = {}
    for m in active:
        clusters.setdefault(find(m.id), []).append(m)
    canonical_of: dict[UUID, UUID] = {}
    for members in clusters.values():
        if len(members) < 2:
            continue
        preferred = [m for m in members if m.id in matched_ids]
        chosen = preferred[0] if preferred else choose_canonical(members)
        for m in members:
            canonical_of[m.id] = chosen.id
    for a, b, cls, reasons in raw:
        if cls == CONFIRMED:
            canonical_id = canonical_of[a.id]
            for member in (a, b):
                if member.id == canonical_id:
                    continue
                if any(p["milestone_id"] == member.id for p in pairs):
                    continue
                pairs.append(
                    {
                        "milestone_id": member.id,
                        "canonical_id": canonical_id,
                        "classification": cls,
                        "reasons": reasons,
                        "default_action": ACTION_MERGE,
                    }
                )
        else:
            preferred = [m for m in (a, b) if m.id in matched_ids]
            canonical = preferred[0] if len(preferred) == 1 else choose_canonical([a, b])
            other = b if canonical.id == a.id else a
            pairs.append(
                {
                    "milestone_id": other.id,
                    "canonical_id": canonical.id,
                    "classification": cls,
                    "reasons": reasons,
                    "default_action": ACTION_RETAIN,
                }
            )
    for p in pairs:
        p["canonical_completed"] = by_id[p["canonical_id"]].status == _DONE
        p["duplicate_completed"] = by_id[p["milestone_id"]].status == _DONE
    return pairs


def _reachable(deps: dict[str, list[str]], start: str, goal: str) -> bool:
    stack, seen = [start], set()
    while stack:
        node = stack.pop()
        if node == goal:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(deps.get(node, []))
    return False


def _add_edge(deps: dict[str, list[str]], frm: str, to: str) -> bool:
    """``frm`` depends on ``to``. Refuses self-links, repeats and loops."""
    if frm == to or to in deps.setdefault(frm, []):
        return False
    if _reachable(deps, to, frm):
        return False
    deps[frm].append(to)
    return True


def build_plan(
    db: Session,
    snap: Snapshot,
    *,
    template_decisions: dict[UUID, tuple[str, UUID | None]] | None = None,
    existing_decisions: dict[UUID, tuple[str, UUID | None]] | None = None,
    apply_template_hours: bool = False,
    schedule_new: bool = True,
    today: date | None = None,
) -> Plan:
    today = today or date.today()
    project = snap.project
    by_item, auto_matches = _candidates(snap)
    by_id = {m.id: m for m in snap.milestones}
    active_ids = {m.id for m in snap.active}
    blockers: list[str] = []
    warnings: list[str] = []

    if project.is_deleted or project.is_archived:
        blockers.append("Archived or deleted projects cannot change template.")
    if project.execution_status == ExecutionStatus.cancelled:
        blockers.append("Cancelled projects are not re-planned.")
    if snap.template.project_type_id != project.project_type_id:
        blockers.append("The selected template does not match the project type.")
    if not snap.template_items:
        blockers.append(f"Template '{snap.template.name}' has no visible milestones.")

    # Template decisions: default to the confirmed match, else add.
    matches: dict[UUID, UUID] = {}
    adds: list[TemplateRef] = []
    used: set[UUID] = set()
    template_decisions = template_decisions or {}
    for item in snap.template_items:
        action, target = template_decisions.get(item.id, (None, None))
        auto = auto_matches.get(item.id)
        if action is None:
            action, target = (ACTION_MATCH, auto) if auto else (ACTION_ADD, None)
        if action == ACTION_ADD:
            if auto is not None:
                raise ProTrackValidationError(
                    f"'{item.name}' already exists in the project as a confirmed match; it cannot be added again."
                )
            adds.append(item)
            continue
        if action != ACTION_MATCH or target is None:
            raise ProTrackValidationError(f"Choose match or add for template milestone '{item.name}'.")
        candidate_ids = {m.id for m, _cls, _r in by_item[item.id]}
        if target not in candidate_ids:
            raise ProTrackValidationError(f"The selected milestone is not a candidate match for '{item.name}'.")
        if target in used:
            raise ProTrackValidationError("An existing milestone can match only one template milestone.")
        used.add(target)
        matches[item.id] = target

    matched_ids = set(matches.values())
    duplicate_pairs = _duplicates(snap, matched_ids)

    # Existing decisions: confirmed duplicates merge by default; everything else is kept.
    defaults: dict[UUID, tuple[str, UUID | None]] = {mid: (ACTION_RETAIN, None) for mid in active_ids}
    for pair in duplicate_pairs:
        if pair["default_action"] == ACTION_MERGE and pair["milestone_id"] not in matched_ids:
            defaults[pair["milestone_id"]] = (ACTION_MERGE, pair["canonical_id"])
    decisions = dict(defaults)
    for mid, value in (existing_decisions or {}).items():
        if mid not in active_ids:
            raise ProTrackValidationError("Decisions can only be made for active milestones of this project.")
        if value[0] not in EXISTING_ACTIONS:
            raise ProTrackValidationError(f"Unknown action '{value[0]}'.")
        decisions[mid] = value

    for mid, (action, target) in decisions.items():
        m = by_id[mid]
        if action == ACTION_RETAIN:
            continue
        if mid in matched_ids:
            raise ProTrackValidationError(
                f"'{m.name}' matches the new template, so it must be kept. Unmatch it before "
                f"{'merging' if action == ACTION_MERGE else action + '-ing'} it."
            )
        if action == ACTION_MERGE:
            if target is None or target not in active_ids or target == mid:
                raise ProTrackValidationError(f"Choose an active milestone to merge '{m.name}' into.")
            if decisions.get(target, (ACTION_RETAIN, None))[0] != ACTION_RETAIN:
                raise ProTrackValidationError(
                    f"'{by_id[target].name}' is itself being merged, superseded or archived; it cannot receive a merge."
                )
            if m.status == _DONE and by_id[target].status != _DONE:
                raise ProTrackValidationError(
                    f"'{m.name}' is completed and '{by_id[target].name}' is not. Keep the completed milestone as the "
                    "surviving record so its completion evidence is not lost."
                )

    if project.execution_status == ExecutionStatus.completed and any(item.is_required for item in adds):
        blockers.append(
            "The project is marked completed. Adding required milestones would contradict that completion; "
            "reopen the project through the normal workflow first."
        )

    # Dependencies over the final active set.
    removed = {mid for mid, (action, _t) in decisions.items() if action != ACTION_RETAIN}
    keep_active = [m for m in snap.active if m.id not in removed]
    deps: dict[str, list[str]] = {
        f"m:{m.id}": [f"m:{d}" for d in parse_id_list(m.depends_on_ids)] for m in snap.milestones
    }
    original_deps = {key: list(value) for key, value in deps.items()}
    dependency_changes: list[dict] = []

    def note(kind: str, frm: str, to: str | None, detail: str) -> None:
        dependency_changes.append({"kind": kind, "milestone": frm, "depends_on": to, "detail": detail})

    keep_keys = {f"m:{m.id}" for m in keep_active}
    for mid, (action, target) in decisions.items():
        if action == ACTION_RETAIN:
            continue
        src = f"m:{mid}"
        replacement: list[str]
        if action == ACTION_MERGE:
            replacement = [f"m:{target}"]
            for pred in list(deps.get(src, [])):
                if pred != f"m:{target}" and _add_edge(deps, f"m:{target}", pred):
                    note("added", f"m:{target}", pred, "Carried over from the merged milestone.")
        else:
            replacement = [p for p in deps.get(src, []) if p != src]
        deps[src] = []
        # Every node still pointing at ``src`` is re-pointed, including records removed
        # later in this loop, so chains of superseded milestones bridge correctly.
        for key in list(deps):
            if key == src or src not in deps[key]:
                continue
            deps[key] = [d for d in deps[key] if d != src]
            if key in keep_keys:
                note("removed", key, src, f"Pointed at a milestone being {action}d.")
            for rep in replacement:
                if _add_edge(deps, key, rep):
                    if key in keep_keys:
                        note("added", key, rep, "Re-pointed to keep the original order.")
                elif rep != key and key in keep_keys:
                    warnings.append(
                        f"A dependency of '{_label(key, by_id, snap)}' could not be re-pointed without creating a loop."
                    )

    item_key: dict[UUID, str] = {}
    for item in snap.template_items:
        item_key[item.id] = f"m:{matches[item.id]}" if item.id in matches else f"t:{item.id}"
        deps.setdefault(item_key[item.id], [])
    known_items = {item.id for item in snap.template_items}
    for item in snap.template_items:
        frm = item_key[item.id]
        for dep in item.depends_on:
            try:
                dep_id = UUID(dep)
            except ValueError:
                continue
            if dep_id not in known_items:
                warnings.append(f"Template milestone '{item.name}' depends on a milestone that is not in the template.")
                continue
            to = item_key[dep_id]
            if to in deps[frm]:
                continue
            if frm.startswith("m:") and to.startswith("t:") and by_id[UUID(frm[2:])].status == _DONE:
                warnings.append(
                    f"'{by_id[UUID(frm[2:])].name}' is already completed, so it was not made to wait for new "
                    f"milestone '{_label(to, by_id, snap)}'."
                )
                continue
            if _add_edge(deps, frm, to):
                note("added", frm, to, "From the template's dependency rules.")
            else:
                warnings.append(
                    f"'{item.name}' should follow '{_label(to, by_id, snap)}', but that link would create a loop; "
                    "it was not added."
                )

    # Final order: keep existing order, slot new milestones next to their template neighbours.
    order = [f"m:{m.id}" for m in sorted(keep_active, key=lambda m: (m.sort_order or 0, m.name, str(m.id)))]
    template_keys = [item_key[item.id] for item in snap.template_items]
    for index, item in enumerate(snap.template_items):
        if item.id in matches:
            continue
        key = item_key[item.id]
        before = next((k for k in reversed(template_keys[:index]) if k in order), None)
        after = next((k for k in template_keys[index + 1:] if k in order), None)
        if before is not None:
            order.insert(order.index(before) + 1, key)
        elif after is not None:
            order.insert(order.index(after), key)
        else:
            order.append(key)

    # New milestone rows.
    from app.services.project_template_service import resolve_template_assigned_user
    from app.services.milestone_assignment_service import resolve_auto_assigned_user_id

    new_rows = []
    for item in adds:
        due, due_note = None, None
        if not schedule_new:
            due_note = "Left unscheduled at your request."
        elif item.offset_days is None:
            due_note = "The template has no date offset for this milestone; left unscheduled."
        elif project.start_date is None:
            due_note = "The project has no start date; left unscheduled."
        else:
            candidate = project.start_date + timedelta(days=item.offset_days)
            if candidate < today:
                due_note = (
                    f"The template offset gives {candidate.isoformat()}, which is in the past; left unscheduled."
                )
            else:
                due = candidate
                due_note = f"Project start date + {item.offset_days} days (template rule)."
        owner = resolve_template_assigned_user(
            project, assigned_role=item.assigned_role, default_assigned_user_id=item.default_assigned_user_id
        )
        if owner is None and item.assigned_role:
            owner = resolve_auto_assigned_user_id(project, item.name)
        hours = item.estimated_hours if (apply_template_hours and item.estimated_hours is not None) else Decimal("0")
        new_rows.append(
            {
                "template_milestone_id": item.id,
                "name": item.name,
                "description": item.description,
                "stage": item.stage,
                "is_required": item.is_required,
                "due_date": due,
                "due_date_rule": due_note,
                "assigned_user_id": owner,
                "assigned_user_name": snap.users.get(owner) if owner else None,
                "assignment_rule": (
                    "Template default user" if item.default_assigned_user_id
                    else f"Template role '{item.assigned_role}' → project team" if owner
                    else "No owner from existing rules; needs assignment"
                ),
                "assignment_manual": item.default_assigned_user_id is not None,
                "planned_hours": hours,
                "template_estimated_hours": item.estimated_hours,
                "depends_on": [k for k in deps.get(item_key[item.id], [])],
            }
        )
        if owner is None:
            warnings.append(f"New milestone '{item.name}' has no owner; assign one after applying.")

    closed = {MilestoneStatus.completed, MilestoneStatus.not_applicable, MilestoneStatus.cancelled}
    flagged = [m for m in keep_active if m.is_required] + [r for r in new_rows if r["is_required"]]
    required_after = flagged or (list(keep_active) + new_rows)
    if (
        project.execution_status != ExecutionStatus.completed
        and required_after
        and all(not isinstance(r, dict) and r.status in closed for r in required_after)
    ):
        warnings.append(
            "After this change every required milestone is closed, so the existing stage rule will mark "
            "the project completed."
        )

    # Planned hours before and after (same rule as recalculate_project_planned_hours).
    def total(rows: list[tuple[Decimal, str | None]]) -> Decimal:
        if snap.has_stage_estimates:
            unstaged = sum(
                (h for h, stage in rows if stage is None or stage not in {s.value for s in PLANNED_STAGES}),
                Decimal("0"),
            )
            return snap.stage_total + unstaged
        return sum((h for h, _s in rows), Decimal("0"))

    before_rows = [(Decimal(str(m.planned_hours or 0)), _stage(m.project_stage)) for m in snap.active]
    after_rows = [(Decimal(str(m.planned_hours or 0)), _stage(m.project_stage)) for m in keep_active]
    after_rows += [(row["planned_hours"], row["stage"]) for row in new_rows]

    plan = Plan(
        template_matches=matches,
        template_adds=adds,
        match_candidates={
            item.id: [
                {"milestone_id": m.id, "classification": cls, "reasons": reasons}
                for m, cls, reasons in by_item[item.id]
            ]
            for item in snap.template_items
        },
        duplicate_pairs=duplicate_pairs,
        existing_actions=decisions,
        new_rows=new_rows,
        dependency_changes=[c for c in dependency_changes if c["depends_on"] != c["milestone"]],
        order=order,
        warnings=warnings,
        blockers=blockers,
        planned_hours_before=total(before_rows),
        planned_hours_after=total(after_rows),
        deps=deps,
        original_deps=original_deps,
    )
    return plan


def _label(key: str, by_id: dict[UUID, Milestone], snap: Snapshot) -> str:
    kind, raw = key.split(":", 1)
    if kind == "m":
        m = by_id.get(UUID(raw))
        return m.name if m else raw
    item = next((i for i in snap.template_items if str(i.id) == raw), None)
    return item.name if item else raw


# --------------------------------------------------------------------------- preview


def _milestone_view(m: Milestone, snap: Snapshot) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "status": _stage(m.status),
        "lifecycle_state": m.lifecycle_state,
        "project_stage": _stage(m.project_stage),
        "completed_date": m.completed_date,
        "due_date": m.due_date,
        "assigned_user_id": m.assigned_user_id,
        "assigned_user_name": snap.users.get(m.assigned_user_id) if m.assigned_user_id else None,
        "is_required": bool(m.is_required),
        "planned_hours": Decimal(str(m.planned_hours or 0)),
        "actual_hours": snap.hours.get(m.id, Decimal("0")),
        "template_milestone_id": m.template_milestone_id,
        "created_at": m.created_at,
    }


def preview_payload(snap: Snapshot, plan: Plan, *, apply_template_hours: bool, schedule_new: bool) -> dict:
    by_id = {m.id: m for m in snap.milestones}
    items = {item.id: item for item in snap.template_items}

    def label(key: str) -> str:
        return _label(key, by_id, snap)

    matched = []
    for item in snap.template_items:
        candidates = plan.match_candidates[item.id]
        chosen = plan.template_matches.get(item.id)
        chosen_row = next((c for c in candidates if c["milestone_id"] == chosen), None)
        m = by_id.get(chosen) if chosen else None
        differences = []
        if m is not None:
            if m.name != item.name:
                differences.append(f"Name kept as '{m.name}' (template: '{item.name}').")
            if _stage(m.project_stage) != item.stage:
                differences.append(
                    f"Stage kept as {_stage(m.project_stage) or 'none'} (template: {item.stage or 'none'})."
                )
            if bool(m.is_required) != item.is_required:
                differences.append(f"Required flag kept as {'yes' if m.is_required else 'no'}.")
            if m.template_milestone_id != item.id:
                differences.append("Linked to the new template milestone.")
        matched.append(
            {
                "template_milestone_id": item.id,
                "template_name": item.name,
                "template_stage": item.stage,
                "decision": ACTION_MATCH if chosen else ACTION_ADD,
                "milestone": _milestone_view(m, snap) if m else None,
                "classification": chosen_row["classification"] if chosen_row else None,
                "reasons": chosen_row["reasons"] if chosen_row else [],
                "completion_retained": bool(m and m.status == _DONE),
                "attribute_changes": differences,
                "candidates": [
                    {
                        **c,
                        "classification_label": CLASS_LABELS[c["classification"]],
                        "milestone_name": by_id[c["milestone_id"]].name,
                        "milestone_status": _stage(by_id[c["milestone_id"]].status),
                        "requires_confirmation": c["classification"] != CONFIRMED,
                    }
                    for c in candidates
                ],
                "needs_review": not chosen and bool(candidates),
            }
        )

    existing = []
    for m in snap.active:
        action, target = plan.existing_actions.get(m.id, (ACTION_RETAIN, None))
        in_template = m.id in set(plan.template_matches.values())
        existing.append(
            {
                **_milestone_view(m, snap),
                "in_new_template": in_template,
                "decision": action,
                "merge_into_id": target,
                "merge_into_name": by_id[target].name if target else None,
                "allowed_actions": [ACTION_RETAIN] if in_template else list(EXISTING_ACTIONS),
            }
        )

    duplicates = []
    for pair in plan.duplicate_pairs:
        dup, canon = by_id[pair["milestone_id"]], by_id[pair["canonical_id"]]
        preserved = [
            "Both records, their statuses and completion dates.",
            "Timesheet hours stay on the record they were booked on.",
            "History and comments on both records.",
            "Dependencies are re-pointed to the surviving milestone.",
        ]
        if dup.assigned_user_id and not canon.assigned_user_id:
            preserved.append("The surviving milestone takes over the owner, which it does not have.")
        duplicates.append(
            {
                "milestone": _milestone_view(dup, snap),
                "canonical": _milestone_view(canon, snap),
                "classification": pair["classification"],
                "classification_label": CLASS_LABELS[pair["classification"]],
                "reasons": pair["reasons"],
                "default_action": pair["default_action"],
                "merge_allowed": not (dup.status == _DONE and canon.status != _DONE),
                "requires_confirmation": pair["classification"] != CONFIRMED,
                "preserved": preserved,
            }
        )

    new = []
    for row in plan.new_rows:
        item = items[row["template_milestone_id"]]
        new.append(
            {
                **row,
                "depends_on_names": [label(k) for k in row["depends_on"]],
                "sort_position": plan.order.index(f"t:{item.id}") + 1,
            }
        )

    not_in_template = [e for e in existing if not e["in_new_template"]]
    counts = {
        "add": len(plan.new_rows),
        "match": len(plan.template_matches),
        "retain": sum(1 for e in existing if e["decision"] == ACTION_RETAIN),
        "merge": sum(1 for e in existing if e["decision"] == ACTION_MERGE),
        "supersede": sum(1 for e in existing if e["decision"] == ACTION_SUPERSEDE),
        "archive": sum(1 for e in existing if e["decision"] == ACTION_ARCHIVE),
        "needs_review": sum(1 for m in matched if m["needs_review"])
        + sum(1 for d in duplicates if d["requires_confirmation"]),
        "inactive_untouched": len(snap.milestones) - len(snap.active),
    }
    consequential = counts["merge"] + counts["supersede"] + counts["archive"] > 0
    estimate_changes = plan.planned_hours_before != plan.planned_hours_after
    previous = snap.previous_template
    return {
        "method_version": RECONCILIATION_VERSION,
        "project_id": snap.project.id,
        "fingerprint": snap.fingerprint,
        "plan_version": int(snap.project.milestone_plan_version or 0),
        "previous_template": (
            {"id": previous.id, "name": previous.name, "version": previous.version} if previous else None
        ),
        "new_template": {"id": snap.template.id, "name": snap.template.name, "version": snap.template.version},
        "same_template": previous is not None and previous.id == snap.template.id,
        "options": {"apply_template_hours": apply_template_hours, "schedule_new": schedule_new},
        "existing": existing,
        "matches": matched,
        "new_milestones": new,
        "duplicates": duplicates,
        "not_in_template": not_in_template,
        "inactive_milestones": [
            {
                **_milestone_view(m, snap),
                "merged_into_id": m.merged_into_id,
                "lifecycle_reason": m.lifecycle_reason,
            }
            for m in snap.milestones
            if m not in snap.active
        ],
        "dependency_changes": [
            {**c, "milestone_name": label(c["milestone"]), "depends_on_name": label(c["depends_on"]) if c["depends_on"] else None}
            for c in plan.dependency_changes
        ],
        "planned_hours": {
            "before": plan.planned_hours_before,
            "after": plan.planned_hours_after,
            "changes": estimate_changes,
            "uses_stage_estimates": snap.has_stage_estimates,
        },
        "counts": counts,
        "requires_confirmation": True,
        "consequential": consequential,
        "requires_estimate_acknowledgement": estimate_changes,
        "warnings": plan.warnings,
        "blockers": plan.blockers,
        "rules": [
            "Completed milestones stay completed; status, completion dates, hours and history are never rewritten.",
            "Milestones missing from the new template are kept unless you choose to supersede, archive or merge them.",
            "Only confirmed matches are applied automatically; likely and possible matches need your choice.",
            "A completed milestone is never merged into an incomplete one.",
            "New milestones get dates only from the template offset and owners only from existing assignment rules.",
            "Merged, superseded and archived milestones no longer count in progress or reports.",
            "Nothing changes until you confirm. The whole change is applied in one transaction.",
        ],
    }


def resolve_target_template(db: Session, project: Project, template_id: UUID) -> ProjectTemplate:
    from app.services.project_template_service import active_version_of

    template = active_version_of(db, db.get(ProjectTemplate, template_id))
    if template is None:
        raise ProTrackValidationError("Select an active project template.")
    if project.project_type_id is None:
        raise ProTrackValidationError("Set the project type before changing the template.")
    if template.project_type_id != project.project_type_id:
        raise ProTrackValidationError("Selected template does not match the project type.")
    return template


def preview(
    db: Session,
    project: Project,
    template_id: UUID,
    *,
    template_decisions: dict | None = None,
    existing_decisions: dict | None = None,
    apply_template_hours: bool = False,
    schedule_new: bool = True,
) -> dict:
    template = resolve_target_template(db, project, template_id)
    snap = load_snapshot(db, project, template)
    plan = build_plan(
        db,
        snap,
        template_decisions=template_decisions,
        existing_decisions=existing_decisions,
        apply_template_hours=apply_template_hours,
        schedule_new=schedule_new,
    )
    return preview_payload(snap, plan, apply_template_hours=apply_template_hours, schedule_new=schedule_new)


# --------------------------------------------------------------------------- apply


@dataclass
class ApplyRequest:
    template_id: UUID
    fingerprint: str
    plan_version: int
    request_key: str
    confirm: bool
    acknowledge_estimate_change: bool = False
    template_decisions: dict[UUID, tuple[str, UUID | None]] = field(default_factory=dict)
    existing_decisions: dict[UUID, tuple[str, UUID | None]] = field(default_factory=dict)
    apply_template_hours: bool = False
    schedule_new: bool = True
    reason: str | None = None


def reconciliation_read(row: ProjectTemplateReconciliation, users: dict[UUID, str] | None = None) -> dict:
    users = users or {}
    try:
        decisions = json.loads(row.decisions_json or "{}")
    except ValueError:
        decisions = {}
    return {
        "id": row.id,
        "project_id": row.project_id,
        "status": row.status,
        "previous_template": {
            "id": row.previous_template_id,
            "name": row.previous_template_name,
            "version": row.previous_template_version,
        } if row.previous_template_id else None,
        "new_template": {"id": row.new_template_id, "name": row.new_template_name, "version": row.new_template_version},
        "counts": {
            "add": row.added_count,
            "match": row.matched_count,
            "retain": row.retained_count,
            "merge": row.merged_count,
            "supersede": row.superseded_count,
            "archive": row.archived_count,
        },
        "decisions": decisions,
        "reason": row.reason,
        "error_message": row.error_message,
        "confirmed_by_id": row.confirmed_by_id,
        "confirmed_by_name": users.get(row.confirmed_by_id) if row.confirmed_by_id else None,
        "confirmed_at": row.confirmed_at,
    }


def _record_failure(db: Session, project_id: UUID, actor: User, req: ApplyRequest, error: str) -> None:
    project = db.get(Project, project_id)
    template = db.get(ProjectTemplate, req.template_id)
    if project is None or template is None:
        return
    previous = db.get(ProjectTemplate, project.project_template_id) if project and project.project_template_id else None
    db.add(
        ProjectTemplateReconciliation(
            project_id=project_id,
            request_key=f"failed-{uuid4().hex}",
            status=RECON_FAILED,
            previous_template_id=previous.id if previous else None,
            previous_template_name=previous.name if previous else None,
            previous_template_version=previous.version if previous else None,
            new_template_id=template.id,
            new_template_name=template.name,
            new_template_version=template.version,
            plan_version_before=int(project.milestone_plan_version or 0),
            preview_fingerprint=req.fingerprint[:64],
            decisions_json=json.dumps({"request_key": req.request_key}),
            reason=req.reason,
            error_message=error[:2000],
            confirmed_by_id=actor.id,
            confirmed_at=_now(),
        )
    )
    db.commit()


def apply(db: Session, project_id: UUID, actor: User, req: ApplyRequest) -> tuple[dict, bool]:
    """Apply a confirmed plan. Returns (reconciliation, replayed)."""
    existing = db.scalar(
        select(ProjectTemplateReconciliation).where(
            ProjectTemplateReconciliation.project_id == project_id,
            ProjectTemplateReconciliation.request_key == req.request_key,
        )
    )
    if existing is not None:
        return reconciliation_read(existing), True
    if not req.confirm:
        raise ProTrackValidationError("Confirm the reconciliation to apply it.")
    try:
        result = _apply(db, project_id, actor, req)
        db.commit()
    except ReconciliationConflict:
        db.rollback()
        raise
    except ProTrackValidationError as exc:
        db.rollback()
        _record_failure(db, project_id, actor, req, str(exc.detail))
        raise
    except Exception as exc:
        db.rollback()
        _record_failure(db, project_id, actor, req, f"{type(exc).__name__}: {exc}")
        raise
    _after_commit(db, project_id, actor, result)
    db.refresh(result)
    return reconciliation_read(result), False


def _apply(db: Session, project_id: UUID, actor: User, req: ApplyRequest) -> ProjectTemplateReconciliation:
    project = db.get(Project, project_id)
    if project is None:
        raise ProTrackValidationError("Project not found.")
    # Compare-and-set on the plan version: the first write of the transaction, so a
    # concurrent reconciliation of the same project fails here instead of interleaving.
    claimed = db.execute(
        update(Project)
        .where(Project.id == project_id, Project.milestone_plan_version == req.plan_version)
        .values(milestone_plan_version=req.plan_version + 1)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        raise ReconciliationConflict(
            "Another template change was applied to this project after your preview. Preview again."
        )
    db.refresh(project)
    template = resolve_target_template(db, project, req.template_id)
    snap = load_snapshot(db, project, template)
    # The fingerprint was taken at plan version N; compare with the same version.
    expected = _fingerprint_at_version(snap, template, req.plan_version)
    if expected != req.fingerprint:
        raise ReconciliationConflict("The project's milestones or the template changed after your preview. Preview again.")
    plan = build_plan(
        db,
        snap,
        template_decisions=req.template_decisions,
        existing_decisions=req.existing_decisions,
        apply_template_hours=req.apply_template_hours,
        schedule_new=req.schedule_new,
    )
    if plan.blockers:
        raise ReconciliationConflict(" ".join(plan.blockers))
    if plan.planned_hours_before != plan.planned_hours_after and not req.acknowledge_estimate_change:
        raise ProTrackValidationError(
            f"This change moves planned hours from {plan.planned_hours_before} h to {plan.planned_hours_after} h. "
            "Acknowledge the estimate change to continue."
        )

    now = _now()
    recon_id = uuid4()
    by_id = {m.id: m for m in snap.milestones}
    previous = snap.previous_template

    created: dict[UUID, Milestone] = {}
    for row in plan.new_rows:
        milestone = Milestone(
            project_id=project.id,
            name=row["name"],
            description=row["description"],
            status=MilestoneStatus.not_started,
            due_date=row["due_date"],
            planned_hours=row["planned_hours"],
            original_planned_hours=row["planned_hours"] if row["planned_hours"] else None,
            estimate_basis="template" if row["planned_hours"] else None,
            assigned_user_id=row["assigned_user_id"],
            assignment_manual=row["assignment_manual"],
            is_required=row["is_required"],
            project_stage=_project_stage(row["stage"]),
            template_milestone_id=row["template_milestone_id"],
            lifecycle_state=LIFECYCLE_ACTIVE,
            reconciliation_id=recon_id,
            sort_order=0,
        )
        db.add(milestone)
        created[row["template_milestone_id"]] = milestone
    db.flush()

    def resolve(key: str) -> UUID:
        kind, raw = key.split(":", 1)
        return UUID(raw) if kind == "m" else created[UUID(raw)].id

    # Link matched milestones to the new template identity.
    relinked = []
    for item_id, mid in plan.template_matches.items():
        m = by_id[mid]
        if m.template_milestone_id != item_id:
            relinked.append({"milestone_id": str(mid), "from": str(m.template_milestone_id) if m.template_milestone_id else None, "to": str(item_id)})
            m.template_milestone_id = item_id

    lifecycle_changes = []
    merges = []
    for mid, (action, target) in plan.existing_actions.items():
        if action == ACTION_RETAIN:
            continue
        m = by_id[mid]
        state = {ACTION_MERGE: LIFECYCLE_MERGED, ACTION_SUPERSEDE: LIFECYCLE_SUPERSEDED, ACTION_ARCHIVE: LIFECYCLE_ARCHIVED}[action]
        m.lifecycle_state = state
        m.lifecycle_changed_at = now
        m.lifecycle_changed_by_id = actor.id
        m.reconciliation_id = recon_id
        if action == ACTION_MERGE:
            canonical = by_id[target]
            m.merged_into_id = canonical.id
            m.lifecycle_reason = f"Merged into '{canonical.name}' during template change to '{template.name}'."
            owner_moved = False
            if canonical.assigned_user_id is None and m.assigned_user_id is not None:
                canonical.assigned_user_id = m.assigned_user_id
                canonical.assignment_manual = m.assignment_manual
                owner_moved = True
            merges.append(
                {
                    "merged_id": str(m.id),
                    "merged_name": m.name,
                    "canonical_id": str(canonical.id),
                    "canonical_name": canonical.name,
                    "merged_status": _stage(m.status),
                    "merged_completed_date": m.completed_date.isoformat() if m.completed_date else None,
                    "canonical_status": _stage(canonical.status),
                    "canonical_completed_date": canonical.completed_date.isoformat() if canonical.completed_date else None,
                    "merged_actual_hours": str(snap.hours.get(m.id, Decimal("0"))),
                    "owner_moved_to_canonical": owner_moved,
                }
            )
        else:
            m.lifecycle_reason = (
                f"{'Superseded' if action == ACTION_SUPERSEDE else 'Archived'} during template change to '{template.name}'."
            )
        lifecycle_changes.append({"milestone_id": str(mid), "name": m.name, "state": state, "status_kept": _stage(m.status)})

    # Dependencies and order on the final active set. Untouched dependency lists are
    # left exactly as stored.
    for key in plan.order:
        if key.startswith("m:") and plan.deps.get(key, []) == plan.original_deps.get(key, []):
            continue
        target_id = resolve(key)
        milestone = created[UUID(key[2:])] if key.startswith("t:") else by_id[target_id]
        new_deps = [resolve(d) for d in plan.deps.get(key, [])]
        milestone.depends_on_ids = dump_id_list([str(d) for d in dict.fromkeys(new_deps) if d != target_id])
    order_changes = 0
    for index, key in enumerate(plan.order, start=1):
        milestone = created.get(UUID(key[2:])) if key.startswith("t:") else by_id[UUID(key[2:])]
        if milestone.sort_order != index * 10:
            if key.startswith("m:"):
                order_changes += 1
            milestone.sort_order = index * 10

    project.project_template_id = template.id
    if project.team_id is None and template.default_team_id is not None:
        project.team_id = template.default_team_id
    db.flush()
    _validate_no_cycle(db, project.id)

    from app.services.milestone_workspace_service import recalculate_project_planned_hours
    from app.services.project_stage_sync_service import sync_project_stage_from_milestones

    recalculate_project_planned_hours(db, project.id, commit=False)
    stage_effect = sync_project_stage_from_milestones(
        db, project, actor=actor, reason=f"Template changed to '{template.name}' v{template.version}"
    )

    decisions = {
        "request_key": req.request_key,
        "method_version": RECONCILIATION_VERSION,
        "existing_milestone_ids": [str(m.id) for m in snap.milestones],
        "added": [
            {"milestone_id": str(created[r["template_milestone_id"]].id), "name": r["name"],
             "template_milestone_id": str(r["template_milestone_id"]), "due_date": r["due_date"].isoformat() if r["due_date"] else None,
             "due_date_rule": r["due_date_rule"], "assigned_user_id": str(r["assigned_user_id"]) if r["assigned_user_id"] else None,
             "planned_hours": str(r["planned_hours"])}
            for r in plan.new_rows
        ],
        "matched": [
            {"template_milestone_id": str(tid), "milestone_id": str(mid), "name": by_id[mid].name,
             "status_kept": _stage(by_id[mid].status)}
            for tid, mid in plan.template_matches.items()
        ],
        "retained": [str(mid) for mid, (a, _t) in plan.existing_actions.items() if a == ACTION_RETAIN],
        "merged": merges,
        "canonical_ids": sorted({m["canonical_id"] for m in merges}),
        "superseded": [c for c in lifecycle_changes if c["state"] == LIFECYCLE_SUPERSEDED],
        "archived": [c for c in lifecycle_changes if c["state"] == LIFECYCLE_ARCHIVED],
        "relinked_to_template": relinked,
        "dependency_changes": plan.dependency_changes,
        "sort_order_changes": order_changes,
        "planned_hours": {"before": str(plan.planned_hours_before), "after": str(plan.planned_hours_after),
                          "acknowledged": bool(req.acknowledge_estimate_change)},
        "options": {"apply_template_hours": req.apply_template_hours, "schedule_new": req.schedule_new},
        "project_stage": {k: stage_effect.get(k) for k in ("stage_before", "stage_after", "status_before", "status_after")},
        "warnings": plan.warnings,
        "confirmation": "Confirmed by the user in the reconciliation preview.",
    }
    recon = ProjectTemplateReconciliation(
        id=recon_id,
        project_id=project.id,
        request_key=req.request_key,
        status=RECON_APPLIED,
        previous_template_id=previous.id if previous else None,
        previous_template_name=previous.name if previous else None,
        previous_template_version=previous.version if previous else None,
        new_template_id=template.id,
        new_template_name=template.name,
        new_template_version=template.version,
        plan_version_before=req.plan_version,
        preview_fingerprint=req.fingerprint,
        added_count=len(plan.new_rows),
        matched_count=len(plan.template_matches),
        retained_count=len(decisions["retained"]),
        merged_count=len(merges),
        superseded_count=len(decisions["superseded"]),
        archived_count=len(decisions["archived"]),
        decisions_json=json.dumps(decisions, default=str),
        reason=(req.reason or "").strip() or None,
        confirmed_by_id=actor.id,
        confirmed_at=now,
    )
    db.add(recon)
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.project,
        entity_id=project.id,
        action=ActivityAction.project_template_reconciled,
        old_value=f"{previous.name} v{previous.version}" if previous else None,
        new_value=(
            f"{template.name} v{template.version}: {len(plan.new_rows)} added, {len(plan.template_matches)} matched, "
            f"{len(merges)} merged, {len(decisions['superseded'])} superseded, {len(decisions['archived'])} archived"
        ),
        commit=False,
    )
    for change in lifecycle_changes:
        log_activity(
            db,
            user=actor,
            entity_type=EntityType.milestone,
            entity_id=UUID(change["milestone_id"]),
            action=ActivityAction.milestone_lifecycle_changed,
            old_value=LIFECYCLE_ACTIVE,
            new_value=f"{change['state']} (status kept: {change['status_kept']})",
            commit=False,
        )
    for milestone in created.values():
        log_activity(
            db,
            user=actor,
            entity_type=EntityType.milestone,
            entity_id=milestone.id,
            action=ActivityAction.milestone_created,
            new_value=f"{milestone.name} (from template '{template.name}' v{template.version})",
            commit=False,
        )
    db.flush()
    return recon


def _fingerprint_at_version(snap: Snapshot, template: ProjectTemplate, version: int) -> str:
    project = snap.project
    current = project.milestone_plan_version
    project.milestone_plan_version = version
    try:
        rows = list(template.milestones)
        return _fingerprint(project, template, snap.milestones, rows, snap.stage_total)
    finally:
        project.milestone_plan_version = current


def _project_stage(value: str | None):
    if value is None:
        return None
    from app.models.enums import ProjectStage

    return ProjectStage(value)


def _validate_no_cycle(db: Session, project_id: UUID) -> None:
    from app.services.scheduling_service import find_dependency_cycle

    rows = db.scalars(
        select(Milestone).where(Milestone.project_id == project_id, Milestone.lifecycle_state == LIFECYCLE_ACTIVE)
    ).all()
    graph = {str(m.id): parse_id_list(m.depends_on_ids) for m in rows}
    if find_dependency_cycle(graph):
        raise ProTrackValidationError("The resulting milestone dependencies would form a loop; nothing was changed.")


def _after_commit(db: Session, project_id: UUID, actor: User, recon: ProjectTemplateReconciliation) -> None:
    """Derived values only: health and forecast are recomputed from the committed milestones."""
    from app.services.project_calculation_service import recalculate_project

    try:
        recalculate_project(db, project_id)
    except Exception:  # noqa: BLE001 - derived values; the next edit recomputes them
        db.rollback()
    try:
        from app.services.automation import events

        events.template_reconciled(db, recon, actor=actor)
    except Exception:  # noqa: BLE001 - automation failures are recorded by the engine itself
        db.rollback()


def history(db: Session, project_id: UUID) -> list[dict]:
    rows = list(
        db.scalars(
            select(ProjectTemplateReconciliation)
            .where(ProjectTemplateReconciliation.project_id == project_id)
            .order_by(ProjectTemplateReconciliation.confirmed_at.desc())
        ).all()
    )
    ids = {r.confirmed_by_id for r in rows if r.confirmed_by_id}
    users = {
        u.id: (f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email)
        for u in db.scalars(select(User).where(User.id.in_(ids))).all()
    } if ids else {}
    return [reconciliation_read(r, users) for r in rows]
