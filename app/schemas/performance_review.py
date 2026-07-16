from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PerformanceReviewRatingScaleItem(BaseModel):
    value: int
    label: str
    short_label: str
    guidance: str
    tone: str


class PerformanceReviewTemplateItem(BaseModel):
    prompt: str
    guidance: str | None = None


class PerformanceReviewTemplateSection(BaseModel):
    title: str
    description: str | None = None
    employee_notes_label: str | None = None
    items: list[PerformanceReviewTemplateItem] = Field(default_factory=list)


class PerformanceReviewTemplateRead(BaseModel):
    form_code: str = "PP-HRD-FO-20"
    form_title: str = "Employee Performance Review"
    form_revision: str = "Rev 3 · 01/19/2023"
    review_cycle_month: int = 7
    review_cycle_note: str = (
        "Annual performance reviews are conducted every July for the preceding "
        "financial year (July–June)."
    )
    rating_scale: list[PerformanceReviewRatingScaleItem] = Field(default_factory=list)
    sections: list[PerformanceReviewTemplateSection] = Field(default_factory=list)


class PerformanceReviewProjectUpdate(BaseModel):
    id: UUID | None = None
    project_id: UUID | None = None
    tool_number: str = ""
    part_description: str | None = None
    customer_name: str | None = None
    assignment_role: str | None = None
    hours_logged: Decimal | None = None
    execution_status: str | None = None
    project_stage: str | None = None
    completed_at: date | None = None
    contribution_summary: str | None = None
    achievement_notes: str | None = None
    ownership_type: str = "owned"
    tasks_summary: str | None = None
    complexity: str | None = None
    is_auto_imported: bool = False
    sort_order: int = 0


class PerformanceReviewProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID | None = None
    tool_number: str
    part_description: str | None = None
    customer_name: str | None = None
    assignment_role: str | None = None
    hours_logged: Decimal | None = None
    execution_status: str | None = None
    project_stage: str | None = None
    completed_at: date | None = None
    contribution_summary: str | None = None
    achievement_notes: str | None = None
    ownership_type: str = "owned"
    tasks_summary: str | None = None
    complexity: str | None = None
    is_auto_imported: bool = False
    sort_order: int


class PerformanceReviewProjectSuggestionRead(BaseModel):
    project_id: UUID | None = None
    tool_number: str
    part_description: str | None = None
    customer_name: str | None = None
    assignment_role: str | None = None
    hours_logged: Decimal | None = None
    execution_status: str | None = None
    project_stage: str | None = None
    completed_at: date | None = None
    contribution_summary: str | None = None
    achievement_notes: str | None = None
    ownership_type: str = "owned"
    tasks_summary: str | None = None
    complexity: str | None = None
    is_auto_imported: bool = True
    sort_order: int = 0


class PerformanceReviewItemUpdate(BaseModel):
    id: UUID | None = None
    prompt: str
    guidance: str | None = None
    rating: Decimal | None = Field(default=None, ge=0, le=5)
    employee_comment: str | None = None
    manager_comment: str | None = None
    sort_order: int = 0


class PerformanceReviewSectionUpdate(BaseModel):
    id: UUID | None = None
    title: str
    description: str | None = None
    employee_notes: str | None = None
    reviewer_notes: str | None = None
    sort_order: int = 0
    items: list[PerformanceReviewItemUpdate] = Field(default_factory=list)


class PerformanceReviewCycleCreate(BaseModel):
    title: str
    review_year: int
    start_date: date | None = None
    end_date: date | None = None
    due_date: date | None = None
    status: str = "draft"


class PerformanceReviewCycleRead(PerformanceReviewCycleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_by_id: UUID | None = None
    is_active: bool = True


class PerformanceReviewCreate(BaseModel):
    employee_id: UUID
    reviewer_id: UUID | None = None
    team_id: UUID
    cycle_id: UUID | None = None
    period_label: str = ""
    review_date: date | None = None
    due_date: date | None = None
    review_year: int | None = None
    employee_joining_date: date | None = None
    employee_first_job_date: date | None = None
    total_experience: str | None = None
    industry_experience: str | None = None
    overall_score: Decimal | None = Field(default=None, ge=0, le=5)
    employee_summary: str | None = None
    manager_summary: str | None = None
    strengths_summary: str | None = None
    improvement_summary: str | None = None
    career_goals: str | None = None
    status: str = "draft"
    sections: list[PerformanceReviewSectionUpdate] = Field(default_factory=list)
    projects: list[PerformanceReviewProjectUpdate] = Field(default_factory=list)


class PerformanceReviewUpdate(BaseModel):
    reviewer_id: UUID | None = None
    team_id: UUID | None = None
    period_label: str | None = None
    review_date: date | None = None
    due_date: date | None = None
    employee_joining_date: date | None = None
    employee_first_job_date: date | None = None
    total_experience: str | None = None
    industry_experience: str | None = None
    overall_score: Decimal | None = Field(default=None, ge=0, le=5)
    employee_summary: str | None = None
    manager_summary: str | None = None
    strengths_summary: str | None = None
    improvement_summary: str | None = None
    career_goals: str | None = None
    status: str | None = None
    acknowledged: bool | None = None
    sections: list[PerformanceReviewSectionUpdate] | None = None
    projects: list[PerformanceReviewProjectUpdate] | None = None
    import_suggested_projects: bool | None = None


class PerformanceReviewItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prompt: str
    guidance: str | None = None
    rating: Decimal | None = None
    rating_label: str | None = None
    employee_comment: str | None = None
    manager_comment: str | None = None
    sort_order: int


class PerformanceReviewSectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None = None
    employee_notes: str | None = None
    reviewer_notes: str | None = None
    employee_notes_label: str | None = None
    average_score: Decimal | None = None
    rated_count: int = 0
    total_count: int = 0
    sort_order: int
    items: list[PerformanceReviewItemRead] = Field(default_factory=list)


class PerformanceReviewRead(BaseModel):
    id: UUID
    cycle_id: UUID | None = None
    cycle_title: str | None = None
    employee_id: UUID
    employee_name: str
    employee_department: str | None = None
    employee_designation: str | None = None
    employee_role: str | None = None
    employee_joining_date: date | None = None
    employee_first_job_date: date | None = None
    company_experience: str | None = None
    reviewer_id: UUID
    reviewer_name: str
    team_id: UUID | None = None
    team_name: str | None = None
    period_label: str
    status: str
    review_date: date | None = None
    due_date: date | None = None
    review_period_start: date | None = None
    review_period_end: date | None = None
    total_experience: str | None = None
    industry_experience: str | None = None
    overall_score: Decimal | None = None
    overall_score_label: str | None = None
    completion_percent: int = 0
    employee_summary: str | None = None
    manager_summary: str | None = None
    strengths_summary: str | None = None
    improvement_summary: str | None = None
    career_goals: str | None = None
    submitted_at: datetime | None = None
    acknowledged_at: datetime | None = None
    sections: list[PerformanceReviewSectionRead] = Field(default_factory=list)
    projects: list[PerformanceReviewProjectRead] = Field(default_factory=list)
    is_editable: bool = False
    can_acknowledge: bool = False


class PerformanceReviewTeamMemberRead(BaseModel):
    user_id: UUID
    name: str
    email: str
    team_id: UUID
    team_name: str
    review_count: int = 0
