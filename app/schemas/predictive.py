"""Predictive intelligence API request bodies. Responses are the read-model dicts of ``app.services.predictive``."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ScenarioAssumptionsIn(BaseModel):
    scope_change_percent: Decimal = Field(default=Decimal(0), ge=-50, le=200)
    extra_delay_days: int = Field(default=0, ge=0, le=365)
    target_shift_days: int = Field(default=0, ge=-365, le=365)
    milestone_delays: dict[UUID, int] = Field(default_factory=dict, max_length=50)
    designer_id: UUID | None = None
    added_hours_per_week: Decimal = Field(default=Decimal(0), ge=0, le=80)
    start_date: date | None = None

    @field_validator("milestone_delays")
    @classmethod
    def _delays(cls, value: dict[UUID, int]) -> dict[UUID, int]:
        if any(days < 0 or days > 365 for days in value.values()):
            raise ValueError("Milestone delays must be between 0 and 365 days.")
        return value


class ScenarioSaveIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    assumptions: ScenarioAssumptionsIn


class SettingUpdateIn(BaseModel):
    enabled: bool
    reason: str | None = Field(default=None, max_length=500)


class ActivateVersionIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)
