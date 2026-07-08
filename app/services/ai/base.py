"""Core primitives for the AI & Analytics framework."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Generic, TypeVar

from sqlalchemy.orm import Session

T = TypeVar("T")


@dataclass
class AiContext:
    """Shared operational context gathered once per request."""

    db: Session
    today: date = field(default_factory=date.today)
    week_start: date | None = None
    week_end: date | None = None
    actor_id: Any | None = None
    actor_name: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.week_start is None:
            self.week_start = self.today - timedelta(days=self.today.weekday())
        if self.week_end is None:
            self.week_end = self.week_start + timedelta(days=6)


class AiModule(ABC):
    """Base class for pluggable AI feature modules."""

    name: str = "base"

    @abstractmethod
    def run(self, ctx: AiContext, **kwargs: Any) -> Any:
        """Execute module logic and return typed result."""


class AiProvider(ABC):
    """Reusable analytics primitive used by multiple modules."""

    name: str = "provider"


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def round_hours(value: Decimal | float) -> float:
    return float(_decimal(value).quantize(Decimal("0.1")))


def round_percent(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def confidence_from_sample_size(sample_size: int, *, base: float = 55, per_sample: float = 8) -> float:
    """Higher confidence when more historical data supports a recommendation."""
    return round_percent(base + min(sample_size, 5) * per_sample)


class AiResult(Generic[T]):
    def __init__(self, *, module: str, value: T, cached: bool = False) -> None:
        self.module = module
        self.value = value
        self.cached = cached
        self.generated_at = datetime.utcnow()
