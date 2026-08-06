from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import TimestampSchema


class UserPreferencesRead(TimestampSchema):
    id: UUID
    user_id: UUID
    theme_mode: str = "company_default"
    sidebar_expanded: bool = True
    sidebar_auto_collapse: bool = False
    dashboard_layout: str = "default"
    table_density: str = "comfortable"
    font_size: str = "medium"
    animations_enabled: bool = True
    reduced_motion: bool = False
    default_landing_page: str = "dashboard"
    projects_portfolio_scope: str = "my_streams"
    projects_cc_layout: str = "list"
    projects_cc_default_view_id: UUID | None = None
    projects_cc_show_workstreams: bool = True
    projects_cc_show_teams: bool = True
    projects_cc_show_status: bool = True
    email_notifications_enabled: bool = True
    email_assignment_enabled: bool = True
    email_reminder_enabled: bool = True
    email_ai_insights_enabled: bool = True
    email_daily_summary_enabled: bool = True
    email_weekly_summary_enabled: bool = True
    email_monthly_report_enabled: bool = True


class UserPreferencesUpdate(BaseModel):
    theme_mode: str | None = Field(default=None, max_length=32)
    sidebar_expanded: bool | None = None
    sidebar_auto_collapse: bool | None = None
    dashboard_layout: str | None = Field(default=None, max_length=20)
    table_density: str | None = Field(default=None, max_length=20)
    font_size: str | None = Field(default=None, max_length=20)
    animations_enabled: bool | None = None
    reduced_motion: bool | None = None
    default_landing_page: str | None = Field(default=None, max_length=32)
    projects_portfolio_scope: str | None = Field(default=None, max_length=32)
    projects_cc_layout: str | None = Field(default=None, max_length=20)
    projects_cc_default_view_id: UUID | None = None
    projects_cc_show_workstreams: bool | None = None
    projects_cc_show_teams: bool | None = None
    projects_cc_show_status: bool | None = None
    email_notifications_enabled: bool | None = None
    email_assignment_enabled: bool | None = None
    email_reminder_enabled: bool | None = None
    email_ai_insights_enabled: bool | None = None
    email_daily_summary_enabled: bool | None = None
    email_weekly_summary_enabled: bool | None = None
    email_monthly_report_enabled: bool | None = None
