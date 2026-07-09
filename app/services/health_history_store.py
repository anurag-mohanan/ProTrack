"""Persist health snapshot history for trend charts."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import BASE_DIR
from app.schemas.operations import HealthLevel, HealthSnapshotPoint

HISTORY_FILE = BASE_DIR / "data" / "health_history.json"
MAX_POINTS = 2880  # ~24 hours at 30-second intervals


def _ensure_file() -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text("[]", encoding="utf-8")


def record_snapshot(
    *,
    overall_status: HealthLevel,
    response_time_ms: int,
    error_count: int,
    cpu_percent: float | None = None,
    memory_mb: float | None = None,
    disk_percent: float | None = None,
) -> None:
    _ensure_file()
    points = _load_raw()
    points.append(
        {
            "recorded_at": datetime.now(UTC).isoformat(),
            "overall_status": overall_status,
            "response_time_ms": response_time_ms,
            "error_count": error_count,
            "cpu_percent": cpu_percent,
            "memory_mb": memory_mb,
            "disk_percent": disk_percent,
        }
    )
    if len(points) > MAX_POINTS:
        points = points[-MAX_POINTS:]
    HISTORY_FILE.write_text(json.dumps(points, indent=0), encoding="utf-8")


def get_history(period: str = "24h") -> list[HealthSnapshotPoint]:
    _ensure_file()
    points = _load_raw()
    now = datetime.now(UTC)
    if period == "7d":
        cutoff = now - timedelta(days=7)
    elif period == "30d":
        cutoff = now - timedelta(days=30)
    else:
        cutoff = now - timedelta(hours=24)

    result: list[HealthSnapshotPoint] = []
    for item in points:
        try:
            recorded = datetime.fromisoformat(item["recorded_at"])
            if recorded.tzinfo is None:
                recorded = recorded.replace(tzinfo=UTC)
        except (KeyError, ValueError):
            continue
        if recorded < cutoff:
            continue
        result.append(HealthSnapshotPoint(**item))
    return result


def _load_raw() -> list[dict]:
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
