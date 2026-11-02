"""Engineering Control Tower API payloads."""

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "info"]
Category = Literal["schedule", "effort", "delivery", "data_quality", "capability", "resource"]
FindingStatus = Literal["active", "not_assessable", "resolved"]
ControlTowerView = Literal["risks", "predictive", "data_quality", "resolved"]
ControlTowerState = Literal["never_evaluated", "running", "last_run_failed", "stale", "ok"]
FindingSource = Literal["operational", "predictive"]
TriageStatus = Literal["investigating", "dismissed"]
TriageFilter = Literal["untriaged", "investigating", "dismissed"]


class RuleDefinitionRead(BaseModel):
    rule_id: str
    title: str
    category: Category
    kind: Literal["risk", "data_quality", "predictive"]
    severity_rule: str
    condition: str
    recommended_action: str


class DeferredRuleRead(BaseModel):
    rule_id: str
    title: str
    reason: str


class EvidenceLine(BaseModel):
    label: str
    value: str


class FindingProjectRef(BaseModel):
    id: UUID
    code: str | None = None
    tool_number: str | None = None
    part_description: str | None = None
    execution_status: str


class FindingMilestoneRef(BaseModel):
    id: UUID
    name: str


class FindingOwner(BaseModel):
    id: UUID | None = None
    name: str | None = None
    basis: Literal["milestone_assignee", "design_leader"] | None = None
    basis_label: str | None = None


class FindingRead(BaseModel):
    id: UUID
    finding_key: str
    rule_id: str
    rule_title: str
    category: Category
    category_label: str
    severity: Severity
    status: FindingStatus
    title: str
    explanation: str
    recommended_action: str
    evidence: list[EvidenceLine] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    not_assessable_reason: str | None = None
    project: FindingProjectRef
    milestone: FindingMilestoneRef | None = None
    owner: FindingOwner
    first_detected_at: datetime
    last_evaluated_at: datetime
    last_changed_at: datetime
    evaluation_date: date
    resolved_at: datetime | None = None
    resolution_note: str | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by_name: str | None = None
    acknowledgement_note: str | None = None
    is_recurrence: bool = False
    source: FindingSource = "operational"
    source_label: str = "Operational"
    prediction_id: UUID | None = None
    triage_status: TriageStatus | None = None
    triage_note: str | None = None
    triaged_at: datetime | None = None
    triaged_by_name: str | None = None
    recommendation_id: UUID | None = None


class FindingEventRead(BaseModel):
    event: str
    occurred_at: datetime
    user_name: str | None = None
    detail: str | None = None


class FindingDetail(FindingRead):
    events: list[FindingEventRead] = Field(default_factory=list)


class EvaluationRunRead(BaseModel):
    id: UUID
    status: Literal["running", "succeeded", "failed"]
    trigger: str
    evaluation_date: date
    rules_version: str
    started_at: datetime
    finished_at: datetime | None = None
    projects_evaluated: int = 0
    findings_opened: int = 0
    findings_updated: int = 0
    findings_resolved: int = 0
    findings_open: int = 0
    error: str | None = None


class SeverityCount(BaseModel):
    severity: Severity
    label: str
    count: int


class CategoryCount(BaseModel):
    category: Category
    label: str
    count: int


class ControlTowerSummary(BaseModel):
    """Counts of open findings in the caller's project scope (filters not applied).

    ``open_risks`` and ``by_severity`` cover operational risks only; forecasts are in ``open_predictive``.
    Dismissed findings are excluded from every count except ``dismissed``.
    """

    open_risks: int = 0
    open_data_quality: int = 0
    open_predictive: int = 0
    dismissed: int = 0
    not_assessable: int = 0
    projects_with_risks: int = 0
    projects_with_data_quality: int = 0
    resolved_last_30_days: int = 0
    by_severity: list[SeverityCount] = Field(default_factory=list)
    by_category: list[CategoryCount] = Field(default_factory=list)


class FilterOption(BaseModel):
    value: str
    label: str


class ControlTowerFilters(BaseModel):
    view: ControlTowerView
    severity: Severity | None = None
    category: Category | None = None
    status: FindingStatus | None = None
    project_id: UUID | None = None
    owner_id: str | None = None
    search: str | None = None
    triage: TriageFilter | None = None


class ControlTowerResponse(BaseModel):
    state: ControlTowerState
    state_message: str
    evaluation_date: date | None = None
    latest_run: EvaluationRunRead | None = None
    last_successful_run: EvaluationRunRead | None = None
    can_evaluate: bool = False
    can_acknowledge: bool = False
    summary: ControlTowerSummary
    filters: ControlTowerFilters
    findings: list[FindingRead] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 25
    owner_options: list[FilterOption] = Field(default_factory=list)
    project_options: list[FilterOption] = Field(default_factory=list)
    rules: list[RuleDefinitionRead] = Field(default_factory=list)
    deferred_rules: list[DeferredRuleRead] = Field(default_factory=list)
    empty_message: str | None = None


class AcknowledgeRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class TriageRequest(BaseModel):
    action: Literal["investigate", "dismiss", "reopen"]
    note: str | None = Field(default=None, max_length=500)


class ConvertRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class ConvertResult(BaseModel):
    recommendation_id: UUID
    status: str
    title: str
