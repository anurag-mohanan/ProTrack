"""Application events → automation rules. Called after the triggering change has committed."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.models import Milestone, User
from app.models.workflow import ProjectTemplateReconciliation
from app.services.automation.engine import Candidate, emit
from app.services.automation.rules import EVENT_MILESTONE_COMPLETED, EVENT_TEMPLATE_RECONCILED


def template_reconciled(db: Session, recon: ProjectTemplateReconciliation, *, actor: User | None) -> None:
    context = {"reconciliation_id": str(recon.id), "actor_id": str(actor.id) if actor else None}

    def candidate(rule_key: str) -> Candidate:
        return Candidate(
            dedupe_key=f"{rule_key}:{recon.id}",
            target_type="project",
            target_id=recon.project_id,
            project_id=recon.project_id,
            context=context,
        )

    emit(
        db,
        EVENT_TEMPLATE_RECONCILED,
        {
            "milestones.template_reconciled_notice": [candidate("milestones.template_reconciled_notice")],
            "milestones.added_needs_owner": [candidate("milestones.added_needs_owner")],
        },
        actor=actor,
    )


def milestone_completed(db: Session, milestone: Milestone, *, actor: User | None) -> None:
    stamp = (milestone.completed_date or milestone.completed_at or milestone.updated_at)
    key = f"milestones.dependency_ready:{milestone.id}:{stamp.isoformat() if stamp else 'na'}"
    emit(
        db,
        EVENT_MILESTONE_COMPLETED,
        {
            "milestones.dependency_ready": [
                Candidate(
                    dedupe_key=key,
                    target_type="milestone",
                    target_id=milestone.id,
                    project_id=milestone.project_id,
                    context={"milestone_id": str(milestone.id)},
                )
            ]
        },
        actor=actor,
    )
