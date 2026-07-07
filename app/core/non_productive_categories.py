"""Category-driven rules for non-productive and leave timesheet entries."""

from __future__ import annotations

from sqlalchemy import ColumnElement, and_, or_
from sqlalchemy.sql import false

from app.models.enums import NonProductiveCodeCategory, WorkCategory
from app.models.models import NonProductiveCode, TimesheetEntry

LEAVE_CATEGORY = NonProductiveCodeCategory.leave
DEFAULT_LEAVE_COUNT = 1


def is_leave_code(np_code: NonProductiveCode | None) -> bool:
    if np_code is None:
        return False
    return np_code.category == LEAVE_CATEGORY


def is_standard_np_code(np_code: NonProductiveCode | None) -> bool:
    if np_code is None:
        return False
    return np_code.category == NonProductiveCodeCategory.non_productive


def category_display_label(np_code: NonProductiveCode) -> str:
    if is_leave_code(np_code):
        return "Leave"
    return np_code.description


def apply_category_rules(
    data: dict,
    np_code: NonProductiveCode,
    *,
    allow_billable_override: bool = False,
) -> dict:
    """Normalize billable/leave fields from the selected NP code category."""
    if is_leave_code(np_code):
        data["is_billable"] = False
        data["leave_count"] = DEFAULT_LEAVE_COUNT
        return data

    data["leave_count"] = None
    if not allow_billable_override:
        data["is_billable"] = False
    return data


def is_leave_entry(entry: TimesheetEntry) -> bool:
    return bool(entry.leave_count and entry.leave_count > 0)


def leave_entry_clause() -> ColumnElement[bool]:
    return and_(
        TimesheetEntry.work_category == WorkCategory.non_productive,
        TimesheetEntry.leave_count.is_not(None),
        TimesheetEntry.leave_count > 0,
    )


def standard_np_hours_clause() -> ColumnElement[bool]:
    """Approved NP hours that count toward non-productive totals (excludes leave)."""
    return and_(
        TimesheetEntry.work_category == WorkCategory.non_productive,
        or_(
            TimesheetEntry.leave_count.is_(None),
            TimesheetEntry.leave_count <= 0,
        ),
    )


def leave_np_code_clause(np_code_model=NonProductiveCode) -> ColumnElement[bool]:
    return np_code_model.category == LEAVE_CATEGORY


def standard_np_code_clause(np_code_model=NonProductiveCode) -> ColumnElement[bool]:
    return np_code_model.category != LEAVE_CATEGORY


def empty_clause() -> ColumnElement[bool]:
    return false()
