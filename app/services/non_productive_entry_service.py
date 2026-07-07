"""Build normalized non-productive timesheet entry payloads."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.non_productive_categories import apply_category_rules
from app.models.enums import WorkCategory
from app.models.models import NonProductiveCode, TimesheetEntry


def build_np_timesheet_entry(
    *,
    np_code: NonProductiveCode,
    timesheet_id: UUID,
    entry_date: date,
    hours: Decimal | float | int,
    description: str | None = None,
    customer_id: UUID | None = None,
    allow_billable_override: bool = False,
    is_billable: bool | None = None,
) -> TimesheetEntry:
    data: dict[str, Any] = {
        "timesheet_id": timesheet_id,
        "work_category": WorkCategory.non_productive,
        "non_productive_code_id": np_code.id,
        "project_id": None,
        "milestone_id": None,
        "task_type_id": None,
        "customer_id": customer_id,
        "entry_date": entry_date,
        "hours": Decimal(str(hours)),
        "description": description,
        "is_billable": is_billable if is_billable is not None else False,
    }
    apply_category_rules(
        data,
        np_code,
        allow_billable_override=allow_billable_override,
    )
    return TimesheetEntry(**data)
