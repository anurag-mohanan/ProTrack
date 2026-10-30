"""Engineering Control Tower: deterministic project risk and data-quality findings.

Every rule is evaluated from the shared engineering metrics
(``engineering_metrics_service``) and delivery definitions
(``delivery_variance_service``); this module adds no metric of its own. Rules
apply only where the project's working model allows the matching
``ProjectRiskType`` (the same filter as the project command center).

Evaluation writes only Control Tower tables. It never changes estimates,
dates, assignments, statuses or Finance records.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models.control_tower import (
    FINDING_ACTIVE,
    FINDING_NOT_ASSESSABLE,
    FINDING_RESOLVED,
    OPEN_FINDING_STATUSES,
    RUN_FAILED,
    RUN_RUNNING,
    RUN_SUCCEEDED,
    ProjectRiskEvaluationRun,
    ProjectRiskFinding,
    ProjectRiskFindingEvent,
)
from app.models.enums import MilestoneStatus, ProjectRiskType
from app.models.models import Milestone, Project, User
from app.schemas.control_tower import (
    CategoryCount,
    ControlTowerSummary,
    DeferredRuleRead,
    EvaluationRunRead,
    EvidenceLine,
    FilterOption,
    FindingEventRead,
    FindingMilestoneRef,
    FindingOwner,
    FindingProjectRef,
    FindingRead,
    RuleDefinitionRead,
    SeverityCount,
)
from app.schemas.engineering_metrics import ProjectEngineeringMetrics
from app.services.delivery_variance_service import is_milestone_skipped
from app.services.engineering_metrics_service import (
    compute_project_metrics,
    load_metric_inputs,
)
from app.services.reporting.quote_to_delivery import (
    APPROVED_ESTIMATE_SOURCES,
    OPEN_STATUSES,
)
from app.services.working_model.registry import build_default_registry
from app.services.working_model.resolver import resolve_working_models_for_projects

logger = logging.getLogger("protrack.control_tower")

RULES_VERSION = "2"
RUN_ABANDON_AFTER = timedelta(minutes=15)

SEVERITIES = ("critical", "high", "medium", "info")
SEVERITY_LABELS = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "info": "Informational",
}
CATEGORY_LABELS = {
    "schedule": "Milestone schedule",
    "effort": "Effort vs estimate",
    "delivery": "Project delivery",
    "data_quality": "Data quality",
    "capability": "Skills capability",
}
OWNER_BASIS_LABELS = {
    "milestone_assignee": "Milestone assignee",
    "design_leader": "Design leader",
}
TARGET_SOURCE_LABELS = {
    "due_date": "Due date",
    "baseline_finish_date": "Baseline finish (no due date)",
    "baseline_completion_date": "Baseline completion (no due date)",
}


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    title: str
    category: str
    kind: str
    severity_rule: str
    condition: str
    recommended_action: str
    risk_type: ProjectRiskType | None = None


RULES: dict[str, RuleDefinition] = {
    rule.rule_id: rule
    for rule in (
        RuleDefinition(
            rule_id="milestone_overdue",
            title="Overdue milestone",
            category="schedule",
            kind="risk",
            severity_rule="High for required milestones, Medium for optional ones (matches the project command center).",
            condition=(
                "The milestone is not completed, cancelled or not applicable, and the evaluation date is after "
                "its current target (due date, or baseline finish when no due date is set)."
            ),
            recommended_action=(
                "Confirm the milestone's real status with its owner. Complete it, or agree and record a "
                "revised date through the normal planning workflow."
            ),
            risk_type=ProjectRiskType.milestone_delay,
        ),
        RuleDefinition(
            rule_id="project_past_target",
            title="Project past its current target",
            category="delivery",
            kind="risk",
            severity_rule="Critical (matches the project command center 'Project overdue' risk).",
            condition=(
                "The project is open (planning, in progress or on hold) and the evaluation date is after its "
                "current target (due date, or baseline completion when no due date is set)."
            ),
            recommended_action=(
                "Review the remaining work with the design leader and the customer. Agree a recovery plan "
                "or a revised commitment through the baseline approval workflow."
            ),
            risk_type=ProjectRiskType.overdue,
        ),
        RuleDefinition(
            rule_id="estimate_overrun_realized",
            title="Actual hours exceed the approved estimate",
            category="effort",
            kind="risk",
            severity_rule="High (matches the project command center 'Hours exceeding quote' risk).",
            condition=(
                "The project has an approved estimate (stage estimates or milestone planned hours) above zero, "
                "its actual hours are recorded, and actual hours are strictly greater than the estimate. "
                "Quoted hours alone are not an approved estimate."
            ),
            recommended_action=(
                "Review where the extra hours were spent. If the scope changed, submit an estimate revision "
                "for approval; estimates are never raised automatically."
            ),
            risk_type=ProjectRiskType.hours_over_quote,
        ),
        RuleDefinition(
            rule_id="dq_approved_estimate_missing",
            title="Approved estimate missing",
            category="data_quality",
            kind="data_quality",
            severity_rule="Informational.",
            condition=(
                "Effort overrun applies to the project's working model, but there are no stage estimates "
                "or milestone planned hours (or they total zero), so overrun cannot be assessed."
            ),
            recommended_action="Enter stage estimates on the project's planning page.",
            risk_type=ProjectRiskType.hours_over_quote,
        ),
        RuleDefinition(
            rule_id="dq_actual_hours_incomplete",
            title="Actual hours incomplete",
            category="data_quality",
            kind="data_quality",
            severity_rule="Informational.",
            condition=(
                "Actual hours are missing (a cached total exists without timesheet entries) or some entries "
                "have no timesheet record."
            ),
            recommended_action="Check the project's timesheet history and import or correct the missing entries.",
        ),
        RuleDefinition(
            rule_id="dq_stage_attribution_incomplete",
            title="Stage attribution incomplete",
            category="data_quality",
            kind="data_quality",
            severity_rule="Informational.",
            condition=(
                "The project is estimated by stage and has recorded hours, but some hours are not linked "
                "to a staged milestone."
            ),
            recommended_action="Ask designers to book time against the project's staged milestones.",
        ),
        RuleDefinition(
            rule_id="dq_quote_link_unresolved",
            title="Quote link unresolved",
            category="data_quality",
            kind="data_quality",
            severity_rule="Informational.",
            condition=(
                "More than one active Finance quote is linked to the project, or the linked quote's current "
                "revision cannot be found."
            ),
            recommended_action="Ask Finance to keep exactly one active quote per project with a valid current revision.",
        ),
        RuleDefinition(
            rule_id="dq_milestone_target_missing",
            title="Milestone target dates missing",
            category="data_quality",
            kind="data_quality",
            severity_rule="Informational.",
            condition="One or more open milestones have neither a due date nor a baseline finish date.",
            recommended_action="Set due dates on the open milestones so schedule risk can be assessed.",
            risk_type=ProjectRiskType.milestone_delay,
        ),
        RuleDefinition(
            rule_id="dq_project_target_missing",
            title="Project target date missing",
            category="data_quality",
            kind="data_quality",
            severity_rule="Informational.",
            condition="The open project has neither a due date nor a baseline completion date.",
            recommended_action="Set the project's due date or approve a baseline.",
            risk_type=ProjectRiskType.overdue,
        ),
        RuleDefinition(
            rule_id="dq_original_baseline_unavailable",
            title="Original baseline unavailable",
            category="data_quality",
            kind="data_quality",
            severity_rule="Informational.",
            condition=(
                "The project has a current target but no verified original baseline (no baseline, or a "
                "baseline whose revision history is incomplete), so slippage from the original commitment "
                "cannot be measured."
            ),
            recommended_action="Approve a baseline so future changes are recorded as revisions.",
            risk_type=ProjectRiskType.overdue,
        ),
        RuleDefinition(
            rule_id="skill_requirement_uncovered",
            title="Required skill has no verified holder",
            category="capability",
            kind="risk",
            severity_rule="Medium. Capability findings never mark a project as delayed.",
            condition=(
                "A mandatory skill requirement recorded on the open project has no active employee with a "
                "current verified level at or above the required minimum. Self-declared or unverified skills "
                "do not count. A missing skill record is not proof that nobody has the skill."
            ),
            recommended_action=(
                "Ask managers to assess the people likely to hold the skill, or plan training or external "
                "support. Review the requirement if it is no longer needed."
            ),
        ),
        RuleDefinition(
            rule_id="skill_no_confirmed_candidate",
            title="No single verified candidate for all mandatory skills",
            category="capability",
            kind="risk",
            severity_rule="Medium.",
            condition=(
                "Each mandatory requirement on the open project has at least one verified holder, but no "
                "single active employee is verified at the required level for all of them."
            ),
            recommended_action=(
                "Plan the work as a team across the verified holders, or assess further people. "
                "Use the candidate finder to check availability."
            ),
        ),
        RuleDefinition(
            rule_id="skill_requirement_single_specialist",
            title="Required skill depends on one verified holder",
            category="capability",
            kind="risk",
            severity_rule="Informational.",
            condition=(
                "A mandatory skill requirement on the open project has exactly one active employee verified "
                "at or above the required level."
            ),
            recommended_action="Consider knowledge transfer or a development plan for a second holder.",
        ),
    )
}

DEFERRED_RULES: tuple[DeferredRuleRead, ...] = (
    DeferredRuleRead(
        rule_id="estimate_overrun_forecast",
        title="Forecast estimate overrun",
        reason=(
            "There is no reliable remaining-effort forecast. Remaining hours are estimate minus actual, and the "
            "stage-plan forecast is provisional, so a forecast overrun would be invented."
        ),
    ),
    DeferredRuleRead(
        rule_id="delivery_forecast_risk",
        title="Forecast delivery risk",
        reason=(
            "The stage-plan completion forecast assumes one person per stage and ignores capacity, so it is "
            "not a validated completion forecast."
        ),
    ),
    DeferredRuleRead(
        rule_id="stage_overrun",
        title="Stage-specific overrun",
        reason=(
            "Stage actual hours depend on entries linked to staged milestones; the weekly timesheet grid and "
            "imports do not set that link, so stage actuals are incomplete for most projects."
        ),
    ),
    DeferredRuleRead(
        rule_id="resource_bottleneck",
        title="Resource bottleneck",
        reason=(
            "There is no leave model, no allocation model and no validated demand. Workload uses heuristic "
            "16 h / 40 h floors and fixed role shares, and verified skills only cover projects with recorded "
            "requirements, so capacity cannot be judged reliably."
        ),
    ),
)


def rule_catalog() -> list[RuleDefinitionRead]:
    return [
        RuleDefinitionRead(
            rule_id=rule.rule_id,
            title=rule.title,
            category=rule.category,  # type: ignore[arg-type]
            kind=rule.kind,  # type: ignore[arg-type]
            severity_rule=rule.severity_rule,
            condition=rule.condition,
            recommended_action=rule.recommended_action,
        )
        for rule in RULES.values()
    ]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hours(value: Decimal | None) -> str:
    return "Not recorded" if value is None else f"{value} h"


def _day(value: date | None) -> str:
    return value.isoformat() if value else "Not recorded"


def _json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


@dataclass
class Detection:
    """What one rule concluded for one subject in this evaluation."""

    rule_id: str
    project_id: UUID
    severity: str
    title: str
    explanation: str
    milestone_id: UUID | None = None
    metrics: dict = field(default_factory=dict)
    evidence: list[tuple[str, str]] = field(default_factory=list)
    owner_user_id: UUID | None = None
    owner_basis: str | None = None
    # Set when the rule's inputs are missing: an open finding is kept as
    # not_assessable instead of being resolved; no new finding is opened.
    not_assessable_reason: str | None = None

    @property
    def key(self) -> str:
        return f"{self.rule_id}:{self.project_id}:{self.milestone_id or '-'}"

    @property
    def rule(self) -> RuleDefinition:
        return RULES[self.rule_id]


def applicable_risk_types(db: Session, projects: list[Project]) -> dict[UUID, set[ProjectRiskType]]:
    """Working-model applicability for many projects; matches ``WorkingModelEngine.applicable_risk_types``."""
    registry = build_default_registry()
    models = resolve_working_models_for_projects(db, projects)
    result: dict[UUID, set[ProjectRiskType]] = {}
    for project in projects:
        model = models.get(project.id)
        result[project.id] = (
            set(ProjectRiskType) if model is None else registry.get(model.strategy_key).applicable_risk_types()
        )
    return result


def _project_owner(project: Project) -> tuple[UUID | None, str | None]:
    return (project.design_leader_id, "design_leader") if project.design_leader_id else (None, None)


def _milestone_owner(milestone: Milestone, project: Project) -> tuple[UUID | None, str | None]:
    if milestone.assigned_user_id:
        return milestone.assigned_user_id, "milestone_assignee"
    return _project_owner(project)


def _is_open_milestone(milestone: Milestone) -> bool:
    return not is_milestone_skipped(milestone) and milestone.status != MilestoneStatus.completed


def evaluate_project(
    project: Project,
    metrics: ProjectEngineeringMetrics,
    milestones: list[Milestone],
    allowed: set[ProjectRiskType],
) -> list[Detection]:
    """Pure function of the shared metrics; no database access."""
    detections: list[Detection] = []
    owner_id, owner_basis = _project_owner(project)
    issue_codes = {issue.code: issue for issue in metrics.issues}
    delivery = metrics.delivery.project
    by_milestone = {row.milestone_id: row for row in metrics.delivery.milestones}

    if ProjectRiskType.milestone_delay in allowed:
        undated: list[Milestone] = []
        for milestone in milestones:
            row = by_milestone.get(milestone.id)
            if row is None or not _is_open_milestone(milestone):
                continue
            m_owner, m_basis = _milestone_owner(milestone, project)
            if row.status == "overdue":
                source = "due_date" if milestone.due_date else "baseline_finish_date"
                severity = "high" if milestone.is_required else "medium"
                detections.append(
                    Detection(
                        rule_id="milestone_overdue",
                        project_id=project.id,
                        milestone_id=milestone.id,
                        severity=severity,
                        title=f"Milestone '{milestone.name}' is {row.days_overdue} day(s) past its target",
                        explanation=(
                            f"'{milestone.name}' is {milestone.status.value.replace('_', ' ')} and its current "
                            f"target ({TARGET_SOURCE_LABELS[source].lower()}) was {_day(row.current_target_date)}."
                        ),
                        metrics={
                            "milestone_status": milestone.status.value,
                            "is_required": bool(milestone.is_required),
                            "current_target_date": row.current_target_date,
                            "target_source": source,
                            "original_baseline_finish_date": row.original_baseline_finish_date,
                            "days_overdue": row.days_overdue,
                        },
                        evidence=[
                            ("Milestone", milestone.name),
                            ("Stage", row.stage_label or "None"),
                            ("Milestone status", milestone.status.value.replace("_", " ").capitalize()),
                            ("Required", "Yes" if milestone.is_required else "No"),
                            ("Current target", f"{_day(row.current_target_date)} ({TARGET_SOURCE_LABELS[source]})"),
                            ("Original baseline finish", _day(row.original_baseline_finish_date)),
                            ("Days past target", str(row.days_overdue)),
                        ],
                        owner_user_id=m_owner,
                        owner_basis=m_basis,
                    )
                )
            elif row.status == "no_target":
                undated.append(milestone)
                detections.append(
                    Detection(
                        rule_id="milestone_overdue",
                        project_id=project.id,
                        milestone_id=milestone.id,
                        severity="high" if milestone.is_required else "medium",
                        title=f"Milestone '{milestone.name}' cannot be assessed",
                        explanation="The milestone no longer has a target date.",
                        owner_user_id=m_owner,
                        owner_basis=m_basis,
                        not_assessable_reason="The milestone has no due date or baseline finish date.",
                    )
                )
        if undated:
            names = [m.name for m in undated]
            detections.append(
                Detection(
                    rule_id="dq_milestone_target_missing",
                    project_id=project.id,
                    severity="info",
                    title=f"{len(undated)} open milestone(s) have no target date",
                    explanation=(
                        "Schedule risk cannot be assessed for these milestones until they have a due date."
                    ),
                    metrics={
                        "open_milestones_without_target": len(undated),
                        "milestone_ids": [str(m.id) for m in undated],
                    },
                    evidence=[
                        ("Open milestones without a target", str(len(undated))),
                        ("Milestones", ", ".join(names[:10]) + (f" and {len(names) - 10} more" if len(names) > 10 else "")),
                    ],
                    owner_user_id=owner_id,
                    owner_basis=owner_basis,
                )
            )

    if ProjectRiskType.overdue in allowed:
        target_source = "due_date" if project.due_date else "baseline_completion_date"
        original = delivery.original_baseline_completion_date if delivery.reference_source == "original_baseline" else None
        if delivery.status == "overdue":
            detections.append(
                Detection(
                    rule_id="project_past_target",
                    project_id=project.id,
                    severity="critical",
                    title=f"Project is {delivery.days_overdue} day(s) past its current target",
                    explanation=(
                        f"The project is still {project.execution_status.value.replace('_', ' ')} and its current "
                        f"target ({TARGET_SOURCE_LABELS[target_source].lower()}) was {_day(delivery.current_target_date)}."
                    ),
                    metrics={
                        "execution_status": project.execution_status.value,
                        "current_target_date": delivery.current_target_date,
                        "target_source": target_source,
                        "current_due_date": delivery.current_due_date,
                        "current_baseline_completion_date": delivery.current_baseline_completion_date,
                        "original_baseline_completion_date": original,
                        "reference_source": delivery.reference_source,
                        "target_moved_days": delivery.target_moved_days if original else None,
                        "days_overdue": delivery.days_overdue,
                        "open_required_milestones": metrics.milestones.open_required,
                    },
                    evidence=[
                        ("Project status", project.execution_status.value.replace("_", " ").capitalize()),
                        ("Current target", f"{_day(delivery.current_target_date)} ({TARGET_SOURCE_LABELS[target_source]})"),
                        (
                            "Original baseline",
                            _day(original) if original else f"Not available ({delivery.reference_label})",
                        ),
                        (
                            "Target moved since original",
                            f"{delivery.target_moved_days} day(s)" if original and delivery.target_moved_days is not None else "Not measurable",
                        ),
                        ("Days past target", str(delivery.days_overdue)),
                        ("Open required milestones", str(metrics.milestones.open_required)),
                    ],
                    owner_user_id=owner_id,
                    owner_basis=owner_basis,
                )
            )
        elif delivery.status == "no_target":
            detections.append(
                Detection(
                    rule_id="project_past_target",
                    project_id=project.id,
                    severity="critical",
                    title="Project delivery cannot be assessed",
                    explanation="The project no longer has a target date.",
                    owner_user_id=owner_id,
                    owner_basis=owner_basis,
                    not_assessable_reason="The project has no due date or baseline completion date.",
                )
            )
            detections.append(
                Detection(
                    rule_id="dq_project_target_missing",
                    project_id=project.id,
                    severity="info",
                    title="Project has no target date",
                    explanation="Delivery risk cannot be assessed until the project has a due date or baseline.",
                    evidence=[("Due date", "Not recorded"), ("Baseline completion", "Not recorded")],
                    owner_user_id=owner_id,
                    owner_basis=owner_basis,
                )
            )
        if delivery.current_target_date is not None and delivery.reference_source != "original_baseline":
            detections.append(
                Detection(
                    rule_id="dq_original_baseline_unavailable",
                    project_id=project.id,
                    severity="info",
                    title="Original delivery baseline unavailable",
                    explanation=(
                        "Only the current target is known, so slippage from the original commitment cannot be measured."
                    ),
                    metrics={"reference_source": delivery.reference_source},
                    evidence=[
                        ("Reference available", delivery.reference_label),
                        ("Current target", _day(delivery.current_target_date)),
                        ("Baseline revisions", str(delivery.baseline_revision_count)),
                    ],
                    owner_user_id=owner_id,
                    owner_basis=owner_basis,
                )
            )

    estimate = metrics.estimate
    actual = metrics.actual
    approved = (
        estimate.estimate_source in APPROVED_ESTIMATE_SOURCES
        and estimate.current_estimate_hours is not None
        and estimate.current_estimate_hours > 0
    )
    if ProjectRiskType.hours_over_quote in allowed:
        if not approved:
            reason = "No approved estimate (stage estimates or milestone planned hours) above zero."
            detections.append(
                Detection(
                    rule_id="estimate_overrun_realized",
                    project_id=project.id,
                    severity="high",
                    title="Effort overrun cannot be assessed",
                    explanation=reason,
                    owner_user_id=owner_id,
                    owner_basis=owner_basis,
                    not_assessable_reason=reason,
                )
            )
            detections.append(
                Detection(
                    rule_id="dq_approved_estimate_missing",
                    project_id=project.id,
                    severity="info",
                    title="No approved estimate to compare actual hours against",
                    explanation=(
                        f"The project is measured against {estimate.estimate_source_label.lower()}. Quoted hours "
                        "alone are not an approved estimate, so effort overrun is not assessed."
                    ),
                    metrics={
                        "estimate_source": estimate.estimate_source,
                        "quoted_hours": estimate.quoted_hours,
                        "current_estimate_hours": estimate.current_estimate_hours,
                    },
                    evidence=[
                        ("Estimate basis", estimate.estimate_source_label),
                        ("Quoted hours", _hours(estimate.quoted_hours)),
                        ("Actual hours", _hours(actual.total_hours)),
                    ],
                    owner_user_id=owner_id,
                    owner_basis=owner_basis,
                )
            )
        elif actual.status == "missing":
            reason = "Actual hours are missing for this project."
            detections.append(
                Detection(
                    rule_id="estimate_overrun_realized",
                    project_id=project.id,
                    severity="high",
                    title="Effort overrun cannot be assessed",
                    explanation=reason,
                    owner_user_id=owner_id,
                    owner_basis=owner_basis,
                    not_assessable_reason=reason,
                )
            )
        elif actual.total_hours is not None and actual.total_hours > estimate.current_estimate_hours:
            over = actual.total_hours - estimate.current_estimate_hours
            pending = actual.draft_hours + actual.submitted_hours
            detections.append(
                Detection(
                    rule_id="estimate_overrun_realized",
                    project_id=project.id,
                    severity="high",
                    title=f"Actual hours exceed the approved estimate by {over} h",
                    explanation=(
                        f"{actual.total_hours} h are recorded against an approved estimate of "
                        f"{estimate.current_estimate_hours} h ({estimate.estimate_source_label.lower()}). "
                        "This is a realized overrun from recorded hours, not a forecast. Draft, submitted and "
                        "rejected hours count under the current project rule."
                    ),
                    metrics={
                        "basis": "realized",
                        "estimate_source": estimate.estimate_source,
                        "current_estimate_hours": estimate.current_estimate_hours,
                        "original_estimate_hours": estimate.original_estimate_hours,
                        "quoted_hours": estimate.quoted_hours,
                        "actual_hours": actual.total_hours,
                        "variance_hours": metrics.variance_hours.value,
                        "utilization_percent": metrics.utilization_percent.value,
                        "approved_hours": actual.approved_hours,
                        "submitted_hours": actual.submitted_hours,
                        "draft_hours": actual.draft_hours,
                        "rejected_hours": actual.rejected_hours,
                        "estimate_revisions": estimate.revision_count,
                    },
                    evidence=[
                        ("Approved estimate", f"{_hours(estimate.current_estimate_hours)} ({estimate.estimate_source_label})"),
                        ("Original estimate", _hours(estimate.original_estimate_hours)),
                        ("Actual hours", _hours(actual.total_hours)),
                        ("Over estimate by", f"{over} h"),
                        (
                            "Estimate used",
                            f"{metrics.utilization_percent.value}%" if metrics.utilization_percent.value is not None else "Not available",
                        ),
                        ("Approved timesheet hours", _hours(actual.approved_hours)),
                        ("Not yet approved (draft or submitted)", _hours(pending)),
                        ("On rejected timesheets", _hours(actual.rejected_hours)),
                        ("Estimate revisions", str(estimate.revision_count)),
                    ],
                    owner_user_id=owner_id,
                    owner_basis=owner_basis,
                )
            )

    actual_problems = [issue_codes[code] for code in ("actual_hours_missing", "entries_without_timesheet") if code in issue_codes]
    if actual_problems:
        detections.append(
            Detection(
                rule_id="dq_actual_hours_incomplete",
                project_id=project.id,
                severity="info",
                title="Actual hours are incomplete",
                explanation=" ".join(issue.message for issue in actual_problems),
                metrics={"issue_codes": [issue.code for issue in actual_problems], "actual_status": actual.status},
                evidence=[("Actual hours status", actual.status.replace("_", " ").capitalize())]
                + [("Issue", issue.message) for issue in actual_problems],
                owner_user_id=owner_id,
                owner_basis=owner_basis,
            )
        )

    attribution = metrics.stage_attribution
    if (
        estimate.estimate_source == "stage_estimates"
        and actual.status == "recorded"
        and attribution.status in {"partial", "unavailable"}
    ):
        detections.append(
            Detection(
                rule_id="dq_stage_attribution_incomplete",
                project_id=project.id,
                severity="info",
                title=f"{attribution.unattributed_hours} h are not linked to a project stage",
                explanation=(
                    "Stage-wise actual hours are incomplete, so stage performance cannot be judged. Total actual "
                    "hours are unaffected."
                ),
                metrics={
                    "attribution_status": attribution.status,
                    "attributed_hours": attribution.attributed_hours,
                    "unattributed_hours": attribution.unattributed_hours,
                    "coverage_percent": attribution.coverage_percent,
                },
                evidence=[
                    ("Hours linked to a stage", _hours(attribution.attributed_hours)),
                    ("Hours not linked to a stage", _hours(attribution.unattributed_hours)),
                    (
                        "Coverage",
                        f"{attribution.coverage_percent}%" if attribution.coverage_percent is not None else "Not available",
                    ),
                ],
                owner_user_id=owner_id,
                owner_basis=owner_basis,
            )
        )

    quote_problems = [issue_codes[code] for code in ("quote_link_ambiguous", "quote_revision_unresolved") if code in issue_codes]
    if quote_problems:
        detections.append(
            Detection(
                rule_id="dq_quote_link_unresolved",
                project_id=project.id,
                severity="info",
                title="Finance quote link is unresolved",
                explanation=" ".join(issue.message for issue in quote_problems),
                metrics={
                    "issue_codes": [issue.code for issue in quote_problems],
                    "active_quote_count": metrics.quote_linkage.active_quote_count,
                },
                evidence=[("Active linked quotes", str(metrics.quote_linkage.active_quote_count))]
                + [("Issue", issue.message) for issue in quote_problems],
                owner_user_id=owner_id,
                owner_basis=owner_basis,
            )
        )
    return detections


class EvaluationInProgress(Exception):
    pass


def _record_event(
    db: Session,
    finding: ProjectRiskFinding,
    event: str,
    at: datetime,
    *,
    run_id: UUID | None = None,
    user_id: UUID | None = None,
    detail: str | None = None,
) -> None:
    db.add(
        ProjectRiskFindingEvent(
            finding_id=finding.id,
            event=event,
            occurred_at=at,
            run_id=run_id,
            user_id=user_id,
            detail=detail,
        )
    )


def _apply_detection(finding: ProjectRiskFinding, detection: Detection) -> bool:
    """Copy the detection onto the finding; True when anything a reader sees changed."""
    metrics_json = json.dumps({k: _json_value(v) for k, v in detection.metrics.items()}, sort_keys=True)
    evidence_json = json.dumps([{"label": label, "value": value} for label, value in detection.evidence])
    values = {
        "severity": detection.severity,
        "title": detection.title,
        "explanation": detection.explanation,
        "recommended_action": detection.rule.recommended_action,
        "metrics_json": metrics_json,
        "evidence_json": evidence_json,
        "owner_user_id": detection.owner_user_id,
        "owner_basis": detection.owner_basis,
    }
    changed = False
    for name, value in values.items():
        if getattr(finding, name) != value:
            setattr(finding, name, value)
            changed = True
    return changed


def _evaluated_projects(db: Session) -> list[Project]:
    return list(
        db.scalars(
            select(Project).where(
                Project.execution_status.in_(OPEN_STATUSES),
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
            )
        )
    )


def detect_all(db: Session, today: date) -> tuple[list[Project], list[Detection]]:
    """Read-only: every rule for every open project, using a fixed number of queries."""
    projects = _evaluated_projects(db)
    inputs = load_metric_inputs(db, projects)
    allowed = applicable_risk_types(db, projects)
    detections: list[Detection] = []
    for project in projects:
        project_inputs = inputs[project.id]
        metrics = compute_project_metrics(project, project_inputs, finance_details_visible=False, today=today)
        detections.extend(evaluate_project(project, metrics, project_inputs.milestone_rows, allowed[project.id]))
    detections.extend(capability_detections(db, projects, today))
    return projects, detections


_CAPABILITY_CAVEAT = (
    "Only verified skill records count; a missing record does not prove that nobody has the skill. "
    "This finding does not mean the project is delayed."
)


def capability_detections(db: Session, projects: list[Project], today: date) -> list[Detection]:
    """Org-wide verified coverage of each open project's recorded skill requirements (counts only, no names)."""
    from app.services.skills.gaps import requirement_coverage

    coverage = requirement_coverage(db, projects, today)
    detections: list[Detection] = []
    for project in projects:
        mandatory = [r for r in coverage.get(project.id, []) if r["is_mandatory"]]
        if not mandatory:
            continue
        owner_id, owner_basis = _project_owner(project)

        def lines(rows: list[dict]) -> list[tuple[str, str]]:
            return [
                (f"{r['skill_name']} (level {r['min_level']}+)", f"{r['verified_holders']} verified, {r['claimed_unverified']} unverified claim(s)")
                for r in rows
            ]

        uncovered = [r for r in mandatory if r["verified_holders"] == 0]
        if uncovered:
            names = ", ".join(r["skill_name"] for r in uncovered)
            detections.append(
                Detection(
                    rule_id="skill_requirement_uncovered",
                    project_id=project.id,
                    severity="medium",
                    title=f"{len(uncovered)} required skill(s) have no verified holder",
                    explanation=f"No active employee is verified at the required level for: {names}. {_CAPABILITY_CAVEAT}",
                    metrics={"uncovered_skill_ids": sorted(str(r["skill_id"]) for r in uncovered), "mandatory_requirements": len(mandatory)},
                    evidence=lines(uncovered),
                    owner_user_id=owner_id,
                    owner_basis=owner_basis,
                )
            )
            continue
        common = set.intersection(*(set(r["verified_holder_ids"]) for r in mandatory))
        if len(mandatory) > 1 and not common:
            detections.append(
                Detection(
                    rule_id="skill_no_confirmed_candidate",
                    project_id=project.id,
                    severity="medium",
                    title="No single verified candidate covers all mandatory skills",
                    explanation=(
                        f"Each of the {len(mandatory)} mandatory skills has a verified holder, but nobody is verified "
                        f"for all of them. {_CAPABILITY_CAVEAT}"
                    ),
                    metrics={"mandatory_requirements": len(mandatory)},
                    evidence=lines(mandatory),
                    owner_user_id=owner_id,
                    owner_basis=owner_basis,
                )
            )
        single = [r for r in mandatory if r["verified_holders"] == 1]
        if single:
            names = ", ".join(r["skill_name"] for r in single)
            detections.append(
                Detection(
                    rule_id="skill_requirement_single_specialist",
                    project_id=project.id,
                    severity="info",
                    title=f"{len(single)} required skill(s) depend on one verified holder",
                    explanation=f"Only one active employee is verified at the required level for: {names}. {_CAPABILITY_CAVEAT}",
                    metrics={"single_holder_skill_ids": sorted(str(r["skill_id"]) for r in single)},
                    evidence=lines(single),
                    owner_user_id=owner_id,
                    owner_basis=owner_basis,
                )
            )
    return detections


def _start_run(db: Session, *, trigger: str, user_id: UUID | None, today: date) -> ProjectRiskEvaluationRun:
    now = _now()
    running = db.scalars(
        select(ProjectRiskEvaluationRun).where(ProjectRiskEvaluationRun.status == RUN_RUNNING)
    ).all()
    for run in running:
        if now - run.started_at < RUN_ABANDON_AFTER:
            raise EvaluationInProgress("A Control Tower evaluation is already running.")
        run.status = RUN_FAILED
        run.finished_at = now
        run.error = "Abandoned: the run did not finish within 15 minutes."
    run = ProjectRiskEvaluationRun(
        status=RUN_RUNNING,
        trigger=trigger,
        triggered_by_id=user_id,
        evaluation_date=today,
        rules_version=RULES_VERSION,
        started_at=now,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def run_evaluation(
    db: Session,
    *,
    trigger: str = "manual",
    user_id: UUID | None = None,
    today: date | None = None,
) -> ProjectRiskEvaluationRun:
    """Evaluate all open projects and reconcile the open findings.

    On failure nothing from this run is kept except the run record marked
    ``failed``; previously open findings are left untouched.
    """
    today = today or date.today()
    run = _start_run(db, trigger=trigger, user_id=user_id, today=today)
    run_id = run.id
    try:
        projects, detections = detect_all(db, today)
        now = _now()
        evaluated_ids = {project.id for project in projects}
        open_findings = {
            finding.finding_key: finding
            for finding in db.scalars(
                select(ProjectRiskFinding).where(ProjectRiskFinding.status.in_(OPEN_FINDING_STATUSES))
            )
        }
        new_keys = [d.key for d in detections if d.not_assessable_reason is None and d.key not in open_findings]
        previous_episode: dict[str, UUID] = {}
        if new_keys:
            for key, finding_id, _resolved in db.execute(
                select(ProjectRiskFinding.finding_key, ProjectRiskFinding.id, ProjectRiskFinding.resolved_at)
                .where(
                    ProjectRiskFinding.status == FINDING_RESOLVED,
                    ProjectRiskFinding.finding_key.in_(new_keys),
                )
                .order_by(ProjectRiskFinding.resolved_at.asc())
            ):
                previous_episode[key] = finding_id
        opened = updated = resolved = 0
        for detection in detections:
            finding = open_findings.pop(detection.key, None)
            if detection.not_assessable_reason is not None:
                if finding is None:
                    continue
                finding.last_evaluated_at = now
                finding.last_run_id = run_id
                finding.evaluation_date = today
                if finding.status != FINDING_NOT_ASSESSABLE or finding.not_assessable_reason != detection.not_assessable_reason:
                    finding.status = FINDING_NOT_ASSESSABLE
                    finding.not_assessable_reason = detection.not_assessable_reason
                    finding.last_changed_at = now
                    _record_event(db, finding, "not_assessable", now, run_id=run_id, detail=detection.not_assessable_reason)
                    updated += 1
                continue
            if finding is None:
                previous_id = previous_episode.get(detection.key)
                finding = ProjectRiskFinding(
                    finding_key=detection.key,
                    rule_id=detection.rule_id,
                    category=detection.rule.category,
                    project_id=detection.project_id,
                    milestone_id=detection.milestone_id,
                    status=FINDING_ACTIVE,
                    first_detected_at=now,
                    last_evaluated_at=now,
                    last_changed_at=now,
                    evaluation_date=today,
                    previous_episode_id=previous_id,
                    detected_run_id=run_id,
                    last_run_id=run_id,
                )
                _apply_detection(finding, detection)
                db.add(finding)
                db.flush()
                _record_event(
                    db,
                    finding,
                    "reopened" if previous_id else "opened",
                    now,
                    run_id=run_id,
                    detail=f"Severity {SEVERITY_LABELS[finding.severity]}: {finding.title}",
                )
                opened += 1
                continue
            old_severity = finding.severity
            was_not_assessable = finding.status == FINDING_NOT_ASSESSABLE
            changed = _apply_detection(finding, detection)
            finding.last_evaluated_at = now
            finding.last_run_id = run_id
            finding.evaluation_date = today
            if was_not_assessable:
                finding.status = FINDING_ACTIVE
                finding.not_assessable_reason = None
                _record_event(db, finding, "reassessed", now, run_id=run_id, detail="Inputs available again; condition still met.")
                changed = True
            if old_severity != finding.severity:
                _record_event(
                    db,
                    finding,
                    "severity_changed",
                    now,
                    run_id=run_id,
                    detail=f"{SEVERITY_LABELS[old_severity]} → {SEVERITY_LABELS[finding.severity]}",
                )
            if changed:
                finding.last_changed_at = now
                updated += 1
        for finding in open_findings.values():
            note = (
                "Condition no longer met."
                if finding.project_id in evaluated_ids
                else "Project is no longer open (completed, cancelled, archived or deleted)."
            )
            finding.status = FINDING_RESOLVED
            finding.resolved_at = now
            finding.resolution_note = note
            finding.last_evaluated_at = now
            finding.last_changed_at = now
            finding.last_run_id = run_id
            finding.evaluation_date = today
            _record_event(db, finding, "resolved", now, run_id=run_id, detail=note)
            resolved += 1
        db.flush()
        run = db.get(ProjectRiskEvaluationRun, run_id)
        run.status = RUN_SUCCEEDED
        run.finished_at = _now()
        run.projects_evaluated = len(projects)
        run.findings_opened = opened
        run.findings_updated = updated
        run.findings_resolved = resolved
        run.findings_open = int(
            db.scalar(
                select(func.count(ProjectRiskFinding.id)).where(
                    ProjectRiskFinding.status.in_(OPEN_FINDING_STATUSES)
                )
            )
            or 0
        )
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:
        db.rollback()
        logger.exception("Control Tower evaluation %s failed", run_id)
        failed = db.get(ProjectRiskEvaluationRun, run_id)
        if failed is not None:
            failed.status = RUN_FAILED
            failed.finished_at = _now()
            failed.error = f"{type(exc).__name__}: {exc}"[:2000]
            db.commit()
        raise


def acknowledge_finding(
    db: Session, finding: ProjectRiskFinding, *, user_id: UUID, note: str | None
) -> ProjectRiskFinding:
    now = _now()
    finding.acknowledged_at = now
    finding.acknowledged_by_id = user_id
    finding.acknowledgement_note = (note or "").strip() or None
    _record_event(db, finding, "acknowledged", now, user_id=user_id, detail=finding.acknowledgement_note)
    db.commit()
    db.refresh(finding)
    return finding


# --- Read model ---------------------------------------------------------------


@dataclass
class FindingQuery:
    view: str = "risks"
    severity: str | None = None
    category: str | None = None
    status: str | None = None
    project_id: UUID | None = None
    owner_id: str | None = None
    search: str | None = None


@dataclass(frozen=True)
class FindingScope:
    """The caller's project scope: same clauses as the other project reports."""

    visibility_clause: object | None = None
    team_ids: frozenset[UUID] | None = None

    def apply(self, stmt):
        stmt = (
            stmt.select_from(ProjectRiskFinding)
            .join(Project, Project.id == ProjectRiskFinding.project_id)
            .where(Project.is_deleted.is_(False))
        )
        if self.visibility_clause is not None:
            stmt = stmt.where(self.visibility_clause)
        if self.team_ids is not None:
            stmt = stmt.where(Project.team_id.in_(self.team_ids) if self.team_ids else Project.id.is_(None))
        return stmt


def _apply_view(stmt, view: str):
    if view == "resolved":
        return stmt.where(ProjectRiskFinding.status == FINDING_RESOLVED)
    stmt = stmt.where(ProjectRiskFinding.status.in_(OPEN_FINDING_STATUSES))
    if view == "data_quality":
        return stmt.where(ProjectRiskFinding.category == "data_quality")
    return stmt.where(ProjectRiskFinding.category != "data_quality")


def filtered_findings(base, query: FindingQuery):
    stmt = _apply_view(base, query.view)
    if query.severity:
        stmt = stmt.where(ProjectRiskFinding.severity == query.severity)
    if query.category:
        stmt = stmt.where(ProjectRiskFinding.category == query.category)
    if query.status:
        stmt = stmt.where(ProjectRiskFinding.status == query.status)
    if query.project_id:
        stmt = stmt.where(ProjectRiskFinding.project_id == query.project_id)
    if query.owner_id == "unassigned":
        stmt = stmt.where(ProjectRiskFinding.owner_user_id.is_(None))
    elif query.owner_id:
        stmt = stmt.where(ProjectRiskFinding.owner_user_id == UUID(query.owner_id))
    if query.search:
        pattern = f"%{query.search.strip()}%"
        stmt = stmt.where(
            or_(
                Project.code.ilike(pattern),
                Project.tool_number.ilike(pattern),
                Project.part_description.ilike(pattern),
                ProjectRiskFinding.title.ilike(pattern),
            )
        )
    return stmt


_SEVERITY_RANK = case(
    {severity: rank for rank, severity in enumerate(SEVERITIES)},
    value=ProjectRiskFinding.severity,
    else_=len(SEVERITIES),
)


def ordered(stmt, view: str):
    if view == "resolved":
        return stmt.order_by(ProjectRiskFinding.resolved_at.desc(), ProjectRiskFinding.id)
    return stmt.order_by(_SEVERITY_RANK, ProjectRiskFinding.first_detected_at.asc(), ProjectRiskFinding.id)


def list_findings(
    db: Session, scope: FindingScope, query: FindingQuery, *, page: int, page_size: int
) -> tuple[list[FindingRead], int]:
    total = int(
        db.scalar(filtered_findings(scope.apply(select(func.count(ProjectRiskFinding.id))), query)) or 0
    )
    stmt = ordered(filtered_findings(scope.apply(select(ProjectRiskFinding, Project)), query), query.view)
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return to_reads(db, [(row[0], row[1]) for row in rows]), total


def build_summary(db: Session, scope: FindingScope, today: date) -> ControlTowerSummary:
    sub = scope.apply(
        select(
            ProjectRiskFinding.status,
            ProjectRiskFinding.category,
            ProjectRiskFinding.severity,
            ProjectRiskFinding.project_id,
            ProjectRiskFinding.resolved_at,
        )
    ).subquery()
    finding = sub.c
    open_clause = finding.status.in_(OPEN_FINDING_STATUSES)
    risk_clause = finding.category != "data_quality"
    by_severity = dict(
        db.execute(
            select(finding.severity, func.count())
            .where(open_clause, risk_clause)
            .group_by(finding.severity)
        ).all()
    )
    by_category = dict(
        db.execute(select(finding.category, func.count()).where(open_clause).group_by(finding.category)).all()
    )
    not_assessable = db.scalar(
        select(func.count()).select_from(sub).where(finding.status == FINDING_NOT_ASSESSABLE)
    )
    projects_with_risks = db.scalar(
        select(func.count(func.distinct(finding.project_id))).where(open_clause, risk_clause)
    )
    projects_with_dq = db.scalar(
        select(func.count(func.distinct(finding.project_id))).where(open_clause, finding.category == "data_quality")
    )
    cutoff = datetime.combine(today - timedelta(days=30), datetime.min.time())
    resolved_recent = db.scalar(
        select(func.count()).select_from(sub).where(
            finding.status == FINDING_RESOLVED, finding.resolved_at >= cutoff
        )
    )
    return ControlTowerSummary(
        open_risks=sum(by_severity.values()),
        open_data_quality=int(by_category.get("data_quality", 0)),
        not_assessable=int(not_assessable or 0),
        projects_with_risks=int(projects_with_risks or 0),
        projects_with_data_quality=int(projects_with_dq or 0),
        resolved_last_30_days=int(resolved_recent or 0),
        by_severity=[
            SeverityCount(severity=s, label=SEVERITY_LABELS[s], count=int(by_severity.get(s, 0)))  # type: ignore[arg-type]
            for s in SEVERITIES
            if s != "info"
        ],
        by_category=[
            CategoryCount(category=c, label=label, count=int(by_category.get(c, 0)))  # type: ignore[arg-type]
            for c, label in CATEGORY_LABELS.items()
        ],
    )


def _user_label(user: User) -> str:
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return name or user.email


def users_by_id(db: Session, ids: set[UUID]) -> dict[UUID, User]:
    ids = {uid for uid in ids if uid}
    if not ids:
        return {}
    return {user.id: user for user in db.scalars(select(User).where(User.id.in_(ids)))}


def filter_options(db: Session, scope: FindingScope) -> tuple[list[FilterOption], list[FilterOption]]:
    sub = (
        scope.apply(select(ProjectRiskFinding.owner_user_id, ProjectRiskFinding.project_id))
        .where(ProjectRiskFinding.status.in_(OPEN_FINDING_STATUSES))
        .subquery()
    )
    owner_ids = {row[0] for row in db.execute(select(sub.c.owner_user_id).distinct())}
    users = users_by_id(db, {uid for uid in owner_ids if uid})
    owners = sorted(
        (FilterOption(value=str(uid), label=_user_label(user)) for uid, user in users.items()),
        key=lambda option: option.label.lower(),
    )
    if None in owner_ids:
        owners.append(FilterOption(value="unassigned", label="Unassigned"))
    project_rows = db.execute(
        select(Project.id, Project.code, Project.tool_number)
        .where(Project.id.in_(select(sub.c.project_id).distinct()))
        .order_by(Project.code, Project.tool_number)
    ).all()
    projects = [
        FilterOption(value=str(pid), label=" · ".join(part for part in (code, tool) if part) or str(pid))
        for pid, code, tool in project_rows
    ]
    return owners, projects


def to_reads(db: Session, rows: list[tuple[ProjectRiskFinding, Project]]) -> list[FindingRead]:
    findings = [row[0] for row in rows]
    users = users_by_id(
        db,
        {f.owner_user_id for f in findings if f.owner_user_id}
        | {f.acknowledged_by_id for f in findings if f.acknowledged_by_id},
    )
    milestone_ids = {f.milestone_id for f in findings if f.milestone_id}
    milestones = (
        dict(db.execute(select(Milestone.id, Milestone.name).where(Milestone.id.in_(milestone_ids))).all())
        if milestone_ids
        else {}
    )
    result: list[FindingRead] = []
    for finding, project in rows:
        rule = RULES.get(finding.rule_id)
        owner = users.get(finding.owner_user_id) if finding.owner_user_id else None
        acknowledged_by = users.get(finding.acknowledged_by_id) if finding.acknowledged_by_id else None
        result.append(
            FindingRead(
                id=finding.id,
                finding_key=finding.finding_key,
                rule_id=finding.rule_id,
                rule_title=rule.title if rule else finding.rule_id,
                category=finding.category,  # type: ignore[arg-type]
                category_label=CATEGORY_LABELS.get(finding.category, finding.category),
                severity=finding.severity,  # type: ignore[arg-type]
                status=finding.status,  # type: ignore[arg-type]
                title=finding.title,
                explanation=finding.explanation,
                recommended_action=finding.recommended_action,
                evidence=[EvidenceLine(**line) for line in json.loads(finding.evidence_json or "[]")],
                metrics=json.loads(finding.metrics_json or "{}"),
                not_assessable_reason=finding.not_assessable_reason,
                project=FindingProjectRef(
                    id=project.id,
                    code=project.code,
                    tool_number=project.tool_number,
                    part_description=project.part_description,
                    execution_status=project.execution_status.value if project.execution_status else "unknown",
                ),
                milestone=FindingMilestoneRef(id=finding.milestone_id, name=milestones[finding.milestone_id])
                if finding.milestone_id in milestones
                else None,
                owner=FindingOwner(
                    id=finding.owner_user_id,
                    name=_user_label(owner) if owner else None,
                    basis=finding.owner_basis,  # type: ignore[arg-type]
                    basis_label=OWNER_BASIS_LABELS.get(finding.owner_basis or ""),
                ),
                first_detected_at=finding.first_detected_at,
                last_evaluated_at=finding.last_evaluated_at,
                last_changed_at=finding.last_changed_at,
                evaluation_date=finding.evaluation_date,
                resolved_at=finding.resolved_at,
                resolution_note=finding.resolution_note,
                acknowledged_at=finding.acknowledged_at,
                acknowledged_by_name=_user_label(acknowledged_by) if acknowledged_by else None,
                acknowledgement_note=finding.acknowledgement_note,
                is_recurrence=finding.previous_episode_id is not None,
            )
        )
    return result


def finding_events(db: Session, finding_id: UUID) -> list[FindingEventRead]:
    events = db.scalars(
        select(ProjectRiskFindingEvent)
        .where(ProjectRiskFindingEvent.finding_id == finding_id)
        .order_by(ProjectRiskFindingEvent.occurred_at, ProjectRiskFindingEvent.created_at)
    ).all()
    users = users_by_id(db, {e.user_id for e in events if e.user_id})
    return [
        FindingEventRead(
            event=e.event,
            occurred_at=e.occurred_at,
            user_name=_user_label(users[e.user_id]) if e.user_id in users else None,
            detail=e.detail,
        )
        for e in events
    ]


def run_read(run: ProjectRiskEvaluationRun | None, *, include_error: bool) -> EvaluationRunRead | None:
    if run is None:
        return None
    return EvaluationRunRead(
        id=run.id,
        status=run.status,  # type: ignore[arg-type]
        trigger=run.trigger,
        evaluation_date=run.evaluation_date,
        rules_version=run.rules_version,
        started_at=run.started_at,
        finished_at=run.finished_at,
        projects_evaluated=run.projects_evaluated,
        findings_opened=run.findings_opened,
        findings_updated=run.findings_updated,
        findings_resolved=run.findings_resolved,
        findings_open=run.findings_open,
        error=(run.error if include_error else ("The evaluation failed." if run.error else None)),
    )


def latest_runs(db: Session) -> tuple[ProjectRiskEvaluationRun | None, ProjectRiskEvaluationRun | None]:
    latest = db.scalar(
        select(ProjectRiskEvaluationRun).order_by(ProjectRiskEvaluationRun.started_at.desc()).limit(1)
    )
    succeeded = (
        latest
        if latest is not None and latest.status == RUN_SUCCEEDED
        else db.scalar(
            select(ProjectRiskEvaluationRun)
            .where(ProjectRiskEvaluationRun.status == RUN_SUCCEEDED)
            .order_by(ProjectRiskEvaluationRun.started_at.desc())
            .limit(1)
        )
    )
    return latest, succeeded


def control_tower_state(
    latest: ProjectRiskEvaluationRun | None,
    succeeded: ProjectRiskEvaluationRun | None,
    today: date,
) -> tuple[str, str]:
    if latest is None:
        return "never_evaluated", (
            "The Control Tower has not been evaluated yet. No findings are shown because no evaluation has run, "
            "not because there are no risks."
        )
    if latest.status == RUN_RUNNING:
        return "running", "An evaluation is running. Findings shown are from the previous successful evaluation."
    if latest.status == RUN_FAILED:
        if succeeded is None:
            return "last_run_failed", (
                "The evaluation failed and no evaluation has ever succeeded, so risks are unknown."
            )
        return "last_run_failed", (
            f"The latest evaluation failed. Findings shown are from the last successful evaluation on "
            f"{succeeded.evaluation_date.isoformat()} and may be out of date."
        )
    if succeeded is not None and succeeded.evaluation_date < today:
        return "stale", (
            f"Findings were last evaluated on {succeeded.evaluation_date.isoformat()}. Overdue days and newly "
            "overdue items are not up to date until the Control Tower is evaluated again."
        )
    return "ok", "Findings are up to date for today."
