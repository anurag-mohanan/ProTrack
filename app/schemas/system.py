from datetime import datetime

from pydantic import BaseModel, Field


class SystemHealthRead(BaseModel):
    backend_status: str = "ok"
    database_status: str = "ok"
    api_status: str = "ok"
    application_version: str
    release_candidate: str
    database_version: str | None = None
    active_users: int = 0
    storage_usage_bytes: int = 0
    storage_usage_label: str = "0 B"
    last_backup: datetime | None = None
    import_queue: int = 0
    failed_jobs: int = 0
    failed_emails: int = 0
    recent_errors: list[str] = Field(default_factory=list)
    internal_release: bool = True
