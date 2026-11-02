"""The authoritative definition of actual engineering hours.

Official actual hours are non-deleted timesheet entries on an **approved**
timesheet. Submitted hours are provisional: reported separately and never added
to the official figure. Draft and rejected hours are not actual hours. Billable
and non-billable entries both count toward total effort; billable effort is the
subset with ``is_billable``. See docs/PROTRACK_TIMESHEET_HOUR_DEFINITION.md.

Every project, milestone, stage and person actual-hours query uses
``official_entry_clause`` so no module applies its own status filter.
"""

from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.sql.elements import ColumnElement

from app.models.enums import TimesheetStatus
from app.models.models import Timesheet, TimesheetEntry

OFFICIAL_STATUSES = frozenset({TimesheetStatus.approved})
PROVISIONAL_STATUSES = frozenset({TimesheetStatus.submitted})
EXCLUDED_STATUSES = frozenset({TimesheetStatus.draft, TimesheetStatus.rejected})


def entries_on(statuses: frozenset[TimesheetStatus]) -> ColumnElement[bool]:
    """A non-deleted entry on a timesheet in one of ``statuses``. Each entry is matched at most once."""
    return and_(
        TimesheetEntry.is_deleted.is_(False),
        TimesheetEntry.timesheet_id.in_(select(Timesheet.id).where(Timesheet.status.in_(statuses))),
    )


def official_entry_clause() -> ColumnElement[bool]:
    """A non-deleted entry on an approved timesheet."""
    return entries_on(OFFICIAL_STATUSES)


def provisional_entry_clause() -> ColumnElement[bool]:
    """A non-deleted entry on a submitted (awaiting approval) timesheet."""
    return entries_on(PROVISIONAL_STATUSES)


__all__ = [
    "EXCLUDED_STATUSES",
    "OFFICIAL_STATUSES",
    "PROVISIONAL_STATUSES",
    "entries_on",
    "official_entry_clause",
    "provisional_entry_clause",
]
