"""Milestone record lifecycle (phase 110).

``Milestone.status`` is the engineering workflow state and is never rewritten by
reconciliation. ``Milestone.lifecycle_state`` says whether the record still takes
part in the project's current plan:

* ``active`` — counts in progress, schedules, overdue checks and reports.
* ``merged`` — a confirmed duplicate; ``merged_into_id`` points at the surviving
  milestone. Its own status, dates, hours and history are kept for traceability.
* ``superseded`` — no longer part of the selected template; kept as history.
* ``archived`` — deactivated by an explicit decision; kept as history.

Only active records count, so a merged duplicate is never double-counted and a
superseded milestone never shows as overdue. Timesheet entries stay linked to the
record they were booked on (timesheets are not rewritten); project totals are
unaffected because they are summed by project.
"""

from __future__ import annotations

from app.models.models import Milestone
from app.models.workflow import (
    LIFECYCLE_ACTIVE,
    LIFECYCLE_ARCHIVED,
    LIFECYCLE_MERGED,
    LIFECYCLE_SUPERSEDED,
)

LIFECYCLE_LABELS = {
    LIFECYCLE_ACTIVE: "Active",
    LIFECYCLE_MERGED: "Merged",
    LIFECYCLE_SUPERSEDED: "Superseded",
    LIFECYCLE_ARCHIVED: "Archived",
}


def active_milestone_clause():
    """SQL filter for milestones that take part in the current plan."""
    return Milestone.lifecycle_state == LIFECYCLE_ACTIVE


def is_active(milestone: Milestone) -> bool:
    return (milestone.lifecycle_state or LIFECYCLE_ACTIVE) == LIFECYCLE_ACTIVE
