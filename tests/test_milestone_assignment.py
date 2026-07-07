"""Tests for milestone auto-assignment rules."""

from uuid import uuid4

from app.models.models import Project
from app.services.milestone_assignment_service import (
    is_feasibility_milestone,
    resolve_auto_assigned_user_id,
)


def test_is_feasibility_milestone():
    assert is_feasibility_milestone("Feasibility")
    assert is_feasibility_milestone("Design Feasibility Review")
    assert not is_feasibility_milestone("Blockout")


def test_resolve_auto_assigned_user_id():
    designer_id = uuid4()
    surfacer_id = uuid4()
    project = Project(
        tool_number="T-1",
        part_description="Part",
        customer_id=uuid4(),
        designer_id=designer_id,
        surfacer_id=surfacer_id,
    )
    assert resolve_auto_assigned_user_id(project, "Feasibility") == surfacer_id
    assert resolve_auto_assigned_user_id(project, "Roughing") == designer_id
