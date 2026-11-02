"""The only operations the model can request. Anything not registered here is refused."""

from __future__ import annotations

from typing import Any

from app.services.assistant.context import AssistantContext
from app.services.assistant.types import ToolInputError, ToolSpec


def _all_specs() -> list[ToolSpec]:
    from app.services.assistant.tools import finance, insights, projects, recommend, resources

    return [*projects.SPECS, *resources.SPECS, *finance.SPECS, *insights.SPECS, *recommend.SPECS]


def tool_specs() -> dict[str, ToolSpec]:
    return {spec.name: spec for spec in _all_specs()}


def available_specs(ctx: AssistantContext) -> list[ToolSpec]:
    return [spec for spec in _all_specs() if spec.allowed(ctx)]


def available_modules(ctx: AssistantContext) -> set[str]:
    return {spec.module for spec in available_specs(ctx)}


def validate_arguments(spec: ToolSpec, raw: dict[str, Any]) -> dict[str, Any]:
    """Strict check against the declared schema: unknown keys, wrong types and out-of-range values fail."""
    if not isinstance(raw, dict):
        raise ToolInputError("Arguments must be an object.")
    props: dict[str, dict] = spec.parameters.get("properties", {})
    unknown = set(raw) - set(props)
    if unknown:
        raise ToolInputError(f"Unknown argument(s): {', '.join(sorted(unknown))}.")
    for name in spec.parameters.get("required", []):
        if raw.get(name) in (None, ""):
            raise ToolInputError(f"Missing required argument: {name}.")
    clean: dict[str, Any] = {}
    for name, value in raw.items():
        if value is None:
            continue
        clean[name] = _check(name, value, props[name])
    return clean


def _check(name: str, value: Any, schema: dict) -> Any:
    kind = schema.get("type")
    if kind == "string":
        if not isinstance(value, str):
            raise ToolInputError(f"{name} must be text.")
        value = value.strip()
        if len(value) > schema.get("maxLength", 200):
            raise ToolInputError(f"{name} is too long.")
    elif kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ToolInputError(f"{name} must be a whole number.")
        if "minimum" in schema and value < schema["minimum"] or "maximum" in schema and value > schema["maximum"]:
            raise ToolInputError(f"{name} is out of range.")
    elif kind == "boolean":
        if not isinstance(value, bool):
            raise ToolInputError(f"{name} must be true or false.")
    elif kind == "array":
        if not isinstance(value, list) or len(value) > schema.get("maxItems", 10):
            raise ToolInputError(f"{name} must be a short list.")
        return [_check(name, item, schema.get("items", {})) for item in value]
    else:
        raise ToolInputError(f"{name} has an unsupported type.")
    if "enum" in schema and value not in schema["enum"]:
        raise ToolInputError(f"{name} must be one of: {', '.join(map(str, schema['enum']))}.")
    return value
