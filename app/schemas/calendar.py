from datetime import date
from uuid import UUID

from pydantic import BaseModel


class CalendarEvent(BaseModel):
    id: str
    title: str
    date: date
    category: str
    project_id: UUID | None = None
    milestone_id: UUID | None = None
    user_id: UUID | None = None


class ProjectTimelineBar(BaseModel):
    project_id: UUID
    tool_number: str
    customer_name: str | None = None
    team_id: UUID | None = None
    team_name: str | None = None
    health: str
    execution_status: str
    designer_name: str | None = None
    surfacer_name: str | None = None
    start_date: date
    end_date: date
    progress_percent: float = 0
    due_date_missing: bool = False
