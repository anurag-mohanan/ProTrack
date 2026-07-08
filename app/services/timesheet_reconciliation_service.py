"""Central timesheet calculation & reconciliation service.

This is the single source of truth for timesheet hour aggregation on the
backend. Dashboard, reports and the admin repair tool all categorize entries
using the same rules defined here and in
``app/core/non_productive_categories.py``. Totals are always derived directly
from the Timesheet Entries table — never stored or duplicated.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.non_productive_categories import is_leave_entry
from app.models.enums import WorkCategory
from app.models.models import (
    NonProductiveCode,
    Project,
    TaskType,
    Timesheet,
    TimesheetEntry,
    User,
)
from app.services.project_calculation_service import (
    batch_calculate_hours,
    calculate_project_health,
)


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _round_hours(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class EntryBreakdown:
    worked_hours: Decimal = Decimal("0")
    productive_hours: Decimal = Decimal("0")
    non_productive_hours: Decimal = Decimal("0")
    billable_hours: Decimal = Decimal("0")
    non_billable_hours: Decimal = Decimal("0")
    leave_days: Decimal = Decimal("0")
    leave_entries: int = 0
    entry_count: int = 0

    def as_dict(self) -> dict:
        return {
            "worked_hours": float(_round_hours(self.worked_hours)),
            "productive_hours": float(_round_hours(self.productive_hours)),
            "non_productive_hours": float(_round_hours(self.non_productive_hours)),
            "billable_hours": float(_round_hours(self.billable_hours)),
            "non_billable_hours": float(_round_hours(self.non_billable_hours)),
            "leave_days": float(self.leave_days),
            "leave_entries": self.leave_entries,
            "entry_count": self.entry_count,
        }


def categorize_entries(entries: list[TimesheetEntry]) -> EntryBreakdown:
    """Categorize entries into canonical hour buckets. Approval-agnostic."""
    breakdown = EntryBreakdown()
    for entry in entries:
        if entry.is_deleted:
            continue
        breakdown.entry_count += 1
        hours = _decimal(entry.hours)

        if is_leave_entry(entry):
            breakdown.leave_entries += 1
            breakdown.leave_days += _decimal(entry.leave_count) or Decimal("1")
            continue

        if entry.work_category == WorkCategory.non_productive:
            breakdown.non_productive_hours += hours
        else:
            breakdown.productive_hours += hours

        if entry.is_billable:
            breakdown.billable_hours += hours
        else:
            breakdown.non_billable_hours += hours

    breakdown.worked_hours = breakdown.productive_hours + breakdown.non_productive_hours
    return breakdown


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def compute_month_summary(
    db: Session,
    *,
    user_id: UUID,
    year: int,
    month: int,
    expected_hours: Decimal | float | int,
) -> dict:
    """Canonical month summary for a single user, derived from entries."""
    start, end = month_bounds(year, month)
    entries = list(
        db.scalars(
            select(TimesheetEntry)
            .join(Timesheet, Timesheet.id == TimesheetEntry.timesheet_id)
            .where(
                Timesheet.user_id == user_id,
                TimesheetEntry.entry_date >= start,
                TimesheetEntry.entry_date <= end,
                TimesheetEntry.is_deleted.is_(False),
            )
        ).all()
    )
    breakdown = categorize_entries(entries)
    expected = _round_hours(_decimal(expected_hours))
    worked = _round_hours(breakdown.worked_hours)
    remaining = _round_hours(expected - worked)
    result = breakdown.as_dict()
    result.update(
        {
            "year": year,
            "month": month,
            "expected_hours": float(expected),
            "remaining_hours": float(remaining),
            "monthly_percent": (
                round(float(worked / expected * 100)) if expected > 0 else None
            ),
            "efficiency_percent": (
                round(float(breakdown.billable_hours / worked * 100))
                if worked > 0
                else None
            ),
        }
    )
    return result


# ---------------------------------------------------------------------------
# Reconciliation / repair (admin tool + post-import)
# ---------------------------------------------------------------------------


@dataclass
class ReconciliationReport:
    users_checked: int = 0
    months_recalculated: int = 0
    entries_scanned: int = 0
    projects_recalculated: int = 0
    errors_fixed: int = 0
    warnings: list[str] = field(default_factory=list)
    execution_ms: int = 0

    def as_dict(self) -> dict:
        return {
            "users_checked": self.users_checked,
            "months_recalculated": self.months_recalculated,
            "entries_scanned": self.entries_scanned,
            "projects_recalculated": self.projects_recalculated,
            "errors_fixed": self.errors_fixed,
            "warnings": self.warnings,
            "execution_ms": self.execution_ms,
        }


def recalculate_all_timesheets(db: Session) -> ReconciliationReport:
    """Rebuild derived timesheet statistics and validate data integrity.

    - Recomputes every project's ``actual_hours`` and ``health`` from entries.
    - Validates orphaned entries and dangling project/task/NP references.
    - Reports inconsistencies. Returns a structured report.
    """
    started = time.perf_counter()
    report = ReconciliationReport()

    # Distinct users + months that actually have entries.
    entries = list(
        db.scalars(select(TimesheetEntry).where(TimesheetEntry.is_deleted.is_(False))).all()
    )
    report.entries_scanned = len(entries)

    timesheet_ids = {e.timesheet_id for e in entries}
    timesheets = {
        ts.id: ts
        for ts in db.scalars(
            select(Timesheet).where(Timesheet.id.in_(timesheet_ids))
        ).all()
    }

    user_months: set[tuple[UUID, int, int]] = set()
    users: set[UUID] = set()
    valid_project_ids = {
        pid for (pid,) in db.execute(select(Project.id)).all()
    }
    valid_task_ids = {tid for (tid,) in db.execute(select(TaskType.id)).all()}
    valid_np_ids = {nid for (nid,) in db.execute(select(NonProductiveCode.id)).all()}

    orphan_entries = 0
    bad_project_refs = 0
    bad_task_refs = 0
    bad_np_refs = 0

    for entry in entries:
        ts = timesheets.get(entry.timesheet_id)
        if ts is None:
            orphan_entries += 1
            continue
        users.add(ts.user_id)
        user_months.add((ts.user_id, entry.entry_date.year, entry.entry_date.month))

        if entry.project_id is not None and entry.project_id not in valid_project_ids:
            bad_project_refs += 1
        if entry.task_type_id is not None and entry.task_type_id not in valid_task_ids:
            bad_task_refs += 1
        if (
            entry.non_productive_code_id is not None
            and entry.non_productive_code_id not in valid_np_ids
        ):
            bad_np_refs += 1

    report.users_checked = len(users)
    report.months_recalculated = len(user_months)

    if orphan_entries:
        report.warnings.append(
            f"{orphan_entries} entr{'y' if orphan_entries == 1 else 'ies'} "
            "reference a missing timesheet."
        )
    if bad_project_refs:
        report.warnings.append(
            f"{bad_project_refs} entr{'y' if bad_project_refs == 1 else 'ies'} "
            "reference a missing project."
        )
    if bad_task_refs:
        report.warnings.append(
            f"{bad_task_refs} entr{'y' if bad_task_refs == 1 else 'ies'} "
            "reference a missing task type."
        )
    if bad_np_refs:
        report.warnings.append(
            f"{bad_np_refs} entr{'y' if bad_np_refs == 1 else 'ies'} "
            "reference a missing non-productive code."
        )

    # Rebuild project actual_hours + health from entries; count corrections.
    projects = list(db.scalars(select(Project)).all())
    hours_by_project = batch_calculate_hours(db, projects)
    for project in projects:
        recalculated = hours_by_project.get(project.id)
        if recalculated is None:
            continue
        report.projects_recalculated += 1
        changed = False
        if _round_hours(_decimal(project.actual_hours)) != recalculated.actual:
            project.actual_hours = recalculated.actual
            changed = True
        new_health = calculate_project_health(project, db=db)
        if project.health != new_health:
            project.health = new_health
            changed = True
        if changed:
            report.errors_fixed += 1
            db.add(project)

    db.commit()
    report.execution_ms = int((time.perf_counter() - started) * 1000)
    return report
