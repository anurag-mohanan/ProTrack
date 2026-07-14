from decimal import Decimal
from types import SimpleNamespace

from app.models.enums import ExecutionStatus
from app.services.resource_planning_service import (
    _ACTIVE_TOOL_CARRY_HOURS,
    _active_planning_remaining,
)


def test_active_planning_remaining_overburn_with_open_milestones():
    project = SimpleNamespace(
        current_planned_hours=Decimal("0"),
        quoted_hours=Decimal("210"),
        execution_status=ExecutionStatus.currently_being_worked_on,
    )
    # Actual already > quote, but 3 milestones still open → quote share stays > 0.
    remaining = _active_planning_remaining(
        project,
        actual_hours=Decimal("342"),
        open_planned=Decimal("0"),
        open_count=3,
        milestone_total=7,
    )
    assert remaining > 0
    assert remaining == Decimal("90.00")  # (210/7)*3


def test_active_planning_remaining_carry_when_no_open_ms():
    project = SimpleNamespace(
        current_planned_hours=Decimal("0"),
        quoted_hours=Decimal("210"),
        execution_status=ExecutionStatus.currently_being_worked_on,
    )
    remaining = _active_planning_remaining(
        project,
        actual_hours=Decimal("342"),
        open_planned=Decimal("0"),
        open_count=0,
        milestone_total=7,
    )
    assert remaining == _ACTIVE_TOOL_CARRY_HOURS
