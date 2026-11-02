"""Milestone finish-date prediction (milestone-1). Never changes milestone dates.

Only recorded dependencies (``depends_on_ids``) hold a milestone back: an earlier incomplete
milestone without a recorded dependency is not assumed to delay a later one, and milestone
sequences are not assumed to be the same across projects.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import MilestoneStatus
from app.models.models import Milestone, Project, ProjectTemplateMilestone
from app.models.prediction import PREDICTED
from app.services.delivery_variance_service import (
    is_milestone_skipped,
    milestone_completion_date,
    milestone_current_target,
)
from app.services.milestone_lifecycle import active_milestone_clause
from app.services.predictive.inputs import project_label
from app.services.predictive.stats import MIN_RANGE_SAMPLE, MIN_SAMPLE, central, quantile, share
from app.services.predictive.types import CALCULATION, Outcome, factor
from app.services.scheduling_service import parse_id_list

TYPE = "milestone_delay"
VERSION = "milestone-1"


@dataclass(frozen=True)
class MilestoneFacts:
    milestone_id: UUID
    project_id: UUID
    project_label: str
    name: str
    stage: str | None
    group_key: str | None
    group_label: str | None
    team_id: UUID | None
    customer_id: UUID | None
    assigned_user_id: UUID | None
    completed: bool
    completed_on: date | None
    actual_start: date | None
    planned_start: date | None
    target: date | None
    baseline_finish: date | None
    depends_on: tuple[UUID, ...]

    @property
    def planned_days(self) -> int | None:
        if self.planned_start is None or self.target is None:
            return None
        days = (self.target - self.planned_start).days
        return days if days > 0 else None

    def with_changes(self, **changes) -> MilestoneFacts:
        from dataclasses import replace

        return replace(self, **changes)


@dataclass(frozen=True)
class MilestoneSample:
    group_key: str
    ratio: float


def _facts(m: Milestone, project: Project, lineage: dict[UUID, UUID]) -> MilestoneFacts:
    stage = m.project_stage.value if m.project_stage else None
    if m.template_milestone_id:
        key = f"lineage:{lineage.get(m.template_milestone_id, m.template_milestone_id)}"
        group = "the same template milestone"
    elif stage:
        key = f"stage:{project.project_type_id or 'none'}:{stage}"
        group = f"the {stage.replace('_', ' ')} stage in projects of the same type"
    else:
        key, group = None, None
    return MilestoneFacts(
        milestone_id=m.id,
        project_id=project.id,
        project_label=project_label(project),
        name=m.name,
        stage=stage,
        group_key=key,
        group_label=group,
        team_id=project.team_id,
        customer_id=project.customer_id,
        assigned_user_id=m.assigned_user_id,
        completed=m.status == MilestoneStatus.completed,
        completed_on=milestone_completion_date(m),
        actual_start=m.actual_start_date,
        planned_start=m.override_start_date or m.baseline_start_date,
        target=milestone_current_target(m),
        baseline_finish=m.baseline_finish_date,
        depends_on=_ids(m.depends_on_ids),
    )


def _ids(raw: str | None) -> tuple[UUID, ...]:
    out = []
    for value in parse_id_list(raw):
        try:
            out.append(UUID(value))
        except ValueError:
            continue
    return tuple(out)


def load_milestones(db: Session, projects: list[Project]) -> dict[UUID, list[MilestoneFacts]]:
    """Active, applicable milestones per project."""
    if not projects:
        return {}
    by_id = {p.id: p for p in projects}
    rows = list(db.scalars(select(Milestone).where(Milestone.project_id.in_(by_id), active_milestone_clause())))
    template_ids = {m.template_milestone_id for m in rows if m.template_milestone_id}
    lineage = {
        tid: lid or tid
        for tid, lid in db.execute(
            select(ProjectTemplateMilestone.id, ProjectTemplateMilestone.lineage_id).where(ProjectTemplateMilestone.id.in_(template_ids))
        ).all()
    } if template_ids else {}
    out: dict[UUID, list[MilestoneFacts]] = defaultdict(list)
    for m in rows:
        if is_milestone_skipped(m):
            continue
        out[m.project_id].append(_facts(m, by_id[m.project_id], lineage))
    return dict(out)


def milestone_samples(history: dict[UUID, list[MilestoneFacts]], as_of: date) -> dict[str, list[MilestoneSample]]:
    """Completed milestones with an actual start, a completion and a planned duration."""
    out: dict[str, list[MilestoneSample]] = defaultdict(list)
    for rows in history.values():
        for f in rows:
            if not f.completed or f.group_key is None or f.completed_on is None or f.completed_on > as_of:
                continue
            if f.actual_start is None or f.planned_days is None or f.completed_on < f.actual_start:
                continue
            out[f.group_key].append(MilestoneSample(f.group_key, (f.completed_on - f.actual_start).days / f.planned_days))
    return dict(out)


def _order(rows: list[MilestoneFacts]) -> tuple[list[MilestoneFacts], set[UUID]]:
    """Dependency order within one project, and the ids caught in a dependency cycle."""
    by_id = {m.milestone_id: m for m in rows}
    state: dict[UUID, int] = {}
    ordered: list[MilestoneFacts] = []
    cyclic: set[UUID] = set()

    def visit(mid: UUID, path: list[UUID]) -> None:
        if state.get(mid) == 2:
            return
        if state.get(mid) == 1:
            cyclic.update(path[path.index(mid):])
            return
        state[mid] = 1
        for dep in by_id[mid].depends_on:
            if dep in by_id:
                visit(dep, [*path, dep])
        state[mid] = 2
        ordered.append(by_id[mid])

    for m in rows:
        visit(m.milestone_id, [m.milestone_id])
    return ordered, cyclic


def predict_project_milestones(rows: list[MilestoneFacts], samples: dict[str, list[MilestoneSample]], as_of: date, *,
                               extra_delay: dict[UUID, int] | None = None) -> list[Outcome]:
    extra_delay = extra_delay or {}
    ordered, cyclic = _order(rows)
    finish: dict[UUID, date | None] = {m.milestone_id: m.completed_on for m in rows if m.completed}
    done = {m.milestone_id for m in rows if m.completed}
    names = {m.milestone_id: m.name for m in rows}
    outcomes = []
    for m in ordered:
        if m.completed:
            continue
        out = Outcome(
            prediction_type=TYPE,
            subject_type="milestone",
            subject_key=f"milestone:{m.milestone_id}",
            subject_label=f"{m.project_label} · {m.name}",
            unit="days",
            project_id=m.project_id,
            milestone_id=m.milestone_id,
            team_id=m.team_id,
            customer_id=m.customer_id,
            baseline_label="Current milestone target",
            baseline_date=m.target,
            horizon_start=as_of,
            horizon_end=m.target,
            data_used={
                "planned_start": m.planned_start.isoformat() if m.planned_start else None,
                "actual_start": m.actual_start.isoformat() if m.actual_start else None,
                "target": m.target.isoformat() if m.target else None,
                "recorded_dependencies": [names.get(d, str(d)) for d in m.depends_on],
                "stage": m.stage,
            },
        )
        outcomes.append(out)
        finish[m.milestone_id] = None
        if m.milestone_id in cyclic:
            out.insufficient("The recorded dependencies of this milestone form a cycle.")
            continue
        if m.target is None:
            out.insufficient("No target date (due date or baseline finish) is recorded.")
            continue
        if m.planned_days is None:
            out.insufficient("No planned duration: a planned start (baseline or override) before the target is needed.")
            continue
        group = samples.get(m.group_key or "", [])
        if len(group) < MIN_SAMPLE:
            what = m.group_label or "a comparable milestone (no template link or stage)"
            out.insufficient(f"Only {len(group)} completed milestone(s) of {what} have actual start and finish dates; "
                             f"at least {MIN_SAMPLE} are needed.")
            continue
        preds = [d for d in m.depends_on if d in names]
        unknown = [names[d] for d in preds if d not in done and finish.get(d) is None]
        if unknown and m.actual_start is None:
            out.insufficient(f"Recorded predecessor(s) without a prediction: {', '.join(unknown)}.")
            continue
        durations = [m.planned_days * s.ratio for s in group]
        out.sample_size = len(group)
        out.comparison_group = f"{len(group)} completed milestones of {m.group_label}"
        out.factors = [
            factor("Comparable milestones", out.comparison_group, role=CALCULATION),
            factor("Median actual ÷ planned duration", round(central([s.ratio for s in group]), 3), role=CALCULATION),
            factor("Planned duration (days)", m.planned_days, role=CALCULATION),
        ]
        delay = extra_delay.get(m.milestone_id, 0)
        if m.actual_start is not None:
            start = m.actual_start
            elapsed = max(0, (as_of - start).days)
            pool = [d for d in durations if d > elapsed]
            out.factors.append(factor("Days since actual start", elapsed, role=CALCULATION))
            if len(pool) < MIN_SAMPLE:
                out.insufficient(f"Already running {elapsed} days, longer than most comparable milestones; history "
                                 "cannot say how much longer it will take.")
                continue
        else:
            pool = durations
            start = max(m.planned_start, as_of)
            if start > m.planned_start:
                out.factors.append(factor("Planned start has passed without an actual start", m.planned_start.isoformat(),
                                          role=CALCULATION, detail="The start is taken as today."))
            latest = max((finish[d] for d in preds if finish.get(d) is not None), default=None)
            if latest is not None and latest > start:
                start = latest
                out.factors.append(factor("Waiting for recorded predecessor", latest.isoformat(), role=CALCULATION))
        if delay:
            out.factors.append(factor("Added delay (scenario)", f"{delay} days", role=CALCULATION))

        def to_date(days: float) -> date:
            return start + timedelta(days=math.ceil(days) + delay)

        out.status = PREDICTED
        out.predicted_date = to_date(central(pool))
        if len(pool) >= MIN_RANGE_SAMPLE:
            out.lower_date = to_date(quantile(pool, 0.1))
            out.upper_date = to_date(quantile(pool, 0.9))
            out.range_basis = f"10th–90th percentile of {len(pool)} comparable durations"
        out.variance_value = Decimal((out.predicted_date - m.target).days)
        out.observed_frequency = Decimal(str(round(share(pool, lambda d: to_date(d) > m.target), 4)))
        finish[m.milestone_id] = out.predicted_date
    return outcomes
