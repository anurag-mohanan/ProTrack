"""Tool contract: every tool declares its schema, its permission rule and returns sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.services.assistant.context import AssistantContext


@dataclass
class Source:
    """A record the answer rests on. ``route`` is an in-app link the UI may open."""

    kind: str  # project | milestone | finding | quote | invoice | person | skill | report | forecast
    ref: str
    label: str
    detail: str | None = None
    route: str | None = None

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.ref}"

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "kind": self.kind, "ref": self.ref, "label": self.label,
                "detail": self.detail, "route": self.route}


@dataclass
class Table:
    title: str
    columns: list[str]
    rows: list[list[Any]]

    def as_dict(self) -> dict[str, Any]:
        return {"title": self.title, "columns": self.columns, "rows": self.rows}


@dataclass
class ToolResult:
    """``data`` goes to the provider; ``tables`` and ``sources`` go to the UI as well."""

    data: dict[str, Any]
    record_count: int
    sources: list[Source] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    summary: str | None = None


class ToolDenied(Exception):
    """The caller may not use this tool or see the requested record."""


class ToolInputError(Exception):
    """Arguments were valid JSON but do not identify anything usable."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    module: str  # projects | resources | finance | management | recommendations
    description: str
    parameters: dict[str, Any]
    allowed: Callable[[AssistantContext], bool]
    handler: Callable[[AssistantContext, dict[str, Any]], ToolResult]
    denied_message: str
    writes_recommendation: bool = False

    def openai_schema(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                                                 "parameters": self.parameters}}
