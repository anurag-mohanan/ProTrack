"""In-memory report schedule store (future-ready for email delivery)."""

from __future__ import annotations

from app.schemas.reporting import ReportScheduleEntry, ReportScheduleRequest

_schedules: dict[str, ReportScheduleEntry] = {}


def list_schedules() -> list[ReportScheduleEntry]:
    return list(_schedules.values())


def upsert_schedule(payload: ReportScheduleRequest) -> ReportScheduleEntry:
    entry = ReportScheduleEntry(
        report_id=payload.report_id,
        period_type=payload.period_type,
        frequency=payload.frequency,
        enabled=payload.enabled,
    )
    _schedules[payload.report_id] = entry
    return entry
