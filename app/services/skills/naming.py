"""Skill name normalisation used for duplicate detection (no database access)."""

from __future__ import annotations

import json
import re

_SEPARATORS = re.compile(r"[\s\-_/.,()]+")


def normalize_skill_name(value: str | None) -> str:
    """Case, spacing and punctuation-insensitive key: 'Core & Cavity-Design' == 'core and cavity design'."""
    text = (value or "").strip().lower().replace("&", " and ").replace("+", " and ")
    return " ".join(part for part in _SEPARATORS.split(text) if part)


def parse_aliases(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        values = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(values, list):
        return []
    return [str(v).strip() for v in values if str(v).strip()]


def dump_aliases(values: list[str]) -> str | None:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        key = normalize_skill_name(text)
        if text and key and key not in seen:
            seen.add(key)
            cleaned.append(text)
    return json.dumps(cleaned) if cleaned else None


def skill_name_keys(name: str | None, aliases_raw: str | None) -> set[str]:
    keys = {normalize_skill_name(name)}
    keys.update(normalize_skill_name(alias) for alias in parse_aliases(aliases_raw))
    keys.discard("")
    return keys
