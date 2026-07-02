from pydantic import BaseModel, Field


class DeleteCheckResponse(BaseModel):
    can_delete: bool
    blockers: list[str] = Field(default_factory=list)
    record_name: str | None = None
    record_type: str | None = None
    related_records: list[str] = Field(default_factory=list)
