"""Filesystem path sandboxing helpers.

Server-side code that accepts a caller-supplied path (email attachments, folder
imports) must confine that path to an allowlisted set of base directories to
prevent path traversal and arbitrary-file access.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def is_within(path: Path, roots: Iterable[Path]) -> bool:
    """True if ``path`` resolves inside one of ``roots``."""
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError):
        return False
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def resolve_within(base: Path, relative: str) -> Path | None:
    """Join ``relative`` onto ``base`` and confirm it stays inside ``base``.

    Returns the resolved path, or ``None`` if the input escapes ``base`` (e.g.
    via ``..`` or an absolute path). ``base`` itself is returned as safe.
    """
    cleaned = relative.replace("\\", "/").lstrip("/")
    candidate = (base / cleaned)
    try:
        resolved = candidate.resolve()
        base_resolved = base.resolve()
    except (OSError, RuntimeError):
        return None
    if resolved == base_resolved:
        return resolved
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        return None
    return resolved
