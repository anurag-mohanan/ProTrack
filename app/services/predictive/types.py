"""What a predictor returns. Mirrors the ``predictions`` columns; persisted by the engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.models.prediction import INSUFFICIENT, PREDICTED

CALCULATION = "calculation"
CONTEXT = "context"


def factor(name: str, value, *, role: str = CONTEXT, detail: str | None = None) -> dict:
    """``calculation`` factors change the number; ``context`` factors explain it without changing it."""
    return {"name": name, "value": value if value is None or isinstance(value, (int, float, str, bool)) else str(value),
            "role": role, "detail": detail}


@dataclass
class Outcome:
    prediction_type: str
    subject_type: str
    subject_key: str
    subject_label: str
    status: str = INSUFFICIENT
    reason: str | None = None
    unit: str | None = None
    predicted_value: Decimal | None = None
    predicted_date: date | None = None
    lower_value: Decimal | None = None
    upper_value: Decimal | None = None
    lower_date: date | None = None
    upper_date: date | None = None
    range_basis: str | None = None
    observed_frequency: Decimal | None = None
    baseline_label: str | None = None
    baseline_value: Decimal | None = None
    baseline_date: date | None = None
    variance_value: Decimal | None = None
    sample_size: int = 0
    comparison_group: str | None = None
    factors: list[dict] = field(default_factory=list)
    data_used: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    project_id: UUID | None = None
    milestone_id: UUID | None = None
    team_id: UUID | None = None
    customer_id: UUID | None = None
    currency: str | None = None
    horizon_start: date | None = None
    horizon_end: date | None = None

    @property
    def predicted(self) -> bool:
        return self.status == PREDICTED

    def insufficient(self, reason: str) -> Outcome:
        self.status = INSUFFICIENT
        self.reason = reason
        self.predicted_value = self.predicted_date = None
        self.lower_value = self.upper_value = self.lower_date = self.upper_date = None
        self.observed_frequency = self.variance_value = None
        return self


def hours(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))
