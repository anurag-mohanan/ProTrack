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
