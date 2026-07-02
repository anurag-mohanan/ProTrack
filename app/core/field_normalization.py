"""Normalize optional form and import values before persistence."""

from __future__ import annotations

import math
from typing import Any, get_args, get_origin

INVALID_TEXT_VALUES = frozenset(
    {
        "#value",
        "#n/a",
        "#ref!",
        "#name?",
        "#div/0!",
        "#null!",
        "#num!",
        "undefined",
        "null",
        "nan",
        "[object object]",
    }
)


def normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, bool):
        return str(value)
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in INVALID_TEXT_VALUES:
        return None
    return text


def annotation_allows_none(annotation: Any) -> bool:
    if annotation is type(None):
        return True
    origin = get_origin(annotation)
    if origin is not None:
        return any(annotation_allows_none(arg) for arg in get_args(annotation))
    return False


def normalize_optional_uuid(value: Any) -> Any:
    if value is None or value == "":
        return None
    return value
