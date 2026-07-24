"""Optional QA acknowledgement gate before milestone complete (R4)."""

from __future__ import annotations

from app.core.exceptions import ProTrackValidationError
from app.models.enums import MilestoneStatus
from app.models.models import Milestone, Project
from sqlalchemy.orm import Session


def assert_milestone_qa_gate(
    db: Session,
    milestone: Milestone,
    *,
    next_status: MilestoneStatus | str | None,
    qa_acknowledged: bool | None = None,
) -> None:
    status_raw = next_status
    if hasattr(status_raw, "value"):
        status_raw = status_raw.value  # type: ignore[union-attr]
    if status_raw != MilestoneStatus.completed.value:
        return

    project = db.get(Project, milestone.project_id)
    if project is None or not bool(getattr(project, "qa_gate_enabled", False)):
        return

    acknowledged = qa_acknowledged
    if acknowledged is None:
        acknowledged = bool(getattr(milestone, "qa_acknowledged", False))
    if acknowledged:
        return

    raise ProTrackValidationError(
        "QA gate is enabled for this project. Acknowledge the QA checklist "
        "(qa_acknowledged=true) before marking the milestone complete."
    )
