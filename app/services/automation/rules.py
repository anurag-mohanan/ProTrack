"""Rule catalog. Every executable rule notifies or recommends; none changes records.

``external`` entries describe automations that already exist elsewhere in ProTrack
and keep running where they are (their own settings and dedupe). They are listed
so the Automation page shows the whole picture; this engine does not run them.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select

from app.models.control_tower import OPEN_FINDING_STATUSES, ProjectRiskFinding
from app.models.enums import EntityType, ExecutionStatus, MilestoneStatus
from app.models.models import Milestone, Project, ProjectTemplate
from app.models.workflow import (
    EXEC_PENDING_REVIEW,
    EXEC_SKIPPED,
    EXEC_SUCCEEDED,
    LIFECYCLE_ACTIVE,
    ProjectTemplateReconciliation,
)
from app.services.automation.engine import (
    KIND_EVENT,
    KIND_EXTERNAL,
    KIND_SWEEP,
    ActionResult,
    Candidate,
    RuleDefinition,
    notify,
    register,
)
from app.services.scheduling_service import parse_id_list

EVENT_TEMPLATE_RECONCILED = "project.template_reconciled"
EVENT_MILESTONE_COMPLETED = "milestone.completed"

_CLOSED = {MilestoneStatus.completed, MilestoneStatus.not_applicable, MilestoneStatus.cancelled}
_LIVE_PROJECT = (ExecutionStatus.planning, ExecutionStatus.currently_being_worked_on)


def _project_label(project: Project) -> str:
    return project.code or project.tool_number or str(project.id)[:8]


def _live_projects():
    return select(Project).where(
        Project.is_deleted.is_(False),
        Project.is_archived.is_(False),
        Project.execution_status.in_(_LIVE_PROJECT),
    )


# --------------------------------------------------------------------------- milestones


def _template_reconciled(db, ctx: dict) -> ActionResult:
    recon = db.get(ProjectTemplateReconciliation, UUID(ctx["reconciliation_id"]))
    project = db.get(Project, recon.project_id) if recon else None
    if recon is None or project is None:
        return ActionResult(EXEC_SKIPPED, "Reconciliation or project no longer exists.")
    actor_id = ctx.get("actor_id")
    recipients = [
        u for u in (project.design_leader_id, project.designer_id, project.surfacer_id)
        if u and str(u) != actor_id
    ]
    if not recipients:
        return ActionResult(EXEC_SKIPPED, "No project owners other than the person who made the change.")
    message = (
        f"Template changed from {recon.previous_template_name or 'none'} to {recon.new_template_name} "
        f"v{recon.new_template_version}: {recon.added_count} added, {recon.matched_count} matched, "
        f"{recon.merged_count} merged, {recon.superseded_count} superseded, {recon.archived_count} archived. "
        "Completed work was kept."
    )
    sent = notify(db, recipients, title=f"Template changed on {_project_label(project)}", message=message,
                  entity_type=EntityType.project, entity_id=project.id)
    return ActionResult(EXEC_SUCCEEDED if sent else EXEC_SKIPPED, f"Notified {len(sent)} project owner(s).",
                        {"notified_user_ids": sent})


def _added_needs_owner(db, ctx: dict) -> ActionResult:
    recon_id = UUID(ctx["reconciliation_id"])
    recon = db.get(ProjectTemplateReconciliation, recon_id)
    project = db.get(Project, recon.project_id) if recon else None
    if project is None:
        return ActionResult(EXEC_SKIPPED, "Project no longer exists.")
    unowned = list(db.scalars(
        select(Milestone).where(
            Milestone.reconciliation_id == recon_id,
            Milestone.lifecycle_state == LIFECYCLE_ACTIVE,
            Milestone.assigned_user_id.is_(None),
        )
    ).all())
    if not unowned:
        return ActionResult(EXEC_SKIPPED, "Every added milestone has an owner.")
    if project.design_leader_id is None:
        return ActionResult(EXEC_SKIPPED, f"{len(unowned)} added milestone(s) have no owner and the project has no design leader to tell.",
                            {"milestone_ids": [str(m.id) for m in unowned]})
    names = ", ".join(m.name for m in unowned[:8]) + (" …" if len(unowned) > 8 else "")
    sent = notify(db, [project.design_leader_id], title=f"Milestones need an owner on {_project_label(project)}",
                  message=f"Added by the template change and not assigned: {names}. Assign them from the project page.",
                  entity_type=EntityType.project, entity_id=project.id)
    return ActionResult(EXEC_SUCCEEDED if sent else EXEC_SKIPPED, f"Asked the design leader to assign {len(unowned)} milestone(s).",
                        {"notified_user_ids": sent, "milestone_ids": [str(m.id) for m in unowned]})


def _dependency_ready(db, ctx: dict) -> ActionResult:
    completed = db.get(Milestone, UUID(ctx["milestone_id"]))
    if completed is None or completed.status != MilestoneStatus.completed:
        return ActionResult(EXEC_SKIPPED, "The milestone is no longer completed.")
    project = db.get(Project, completed.project_id)
    rows = list(db.scalars(
        select(Milestone).where(Milestone.project_id == completed.project_id, Milestone.lifecycle_state == LIFECYCLE_ACTIVE)
    ).all())
    by_id = {str(m.id): m for m in rows}
    ready = []
    for m in rows:
        deps = parse_id_list(m.depends_on_ids)
        if str(completed.id) not in deps or m.status != MilestoneStatus.not_started:
            continue
        if all(by_id[d].status in _CLOSED for d in deps if d in by_id):
            ready.append(m)
    if not ready:
        return ActionResult(EXEC_SKIPPED, "No waiting milestone became ready.")
    sent: list[str] = []
    for m in ready:
        sent += notify(db, [m.assigned_user_id or (project.design_leader_id if project else None)],
                       title=f"Ready to start: {m.name}",
                       message=f"'{completed.name}' is completed, so '{m.name}' has no open predecessors. Its status was not changed.",
                       entity_type=EntityType.milestone, entity_id=m.id)
    return ActionResult(EXEC_SUCCEEDED if sent else EXEC_SKIPPED,
                        f"{len(ready)} milestone(s) ready to start; {len(sent)} notification(s).",
                        {"ready_milestone_ids": [str(m.id) for m in ready], "notified_user_ids": sent})


def _overdue_candidates(db, today: date):
    rows = db.execute(
        select(Milestone, Project)
        .join(Project, Project.id == Milestone.project_id)
        .where(
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
            Project.execution_status.in_(_LIVE_PROJECT),
            Milestone.lifecycle_state == LIFECYCLE_ACTIVE,
            Milestone.status.not_in(_CLOSED),
            Milestone.due_date.is_not(None),
            Milestone.due_date < today,
        )
    ).all()
    for milestone, project in rows:
        yield Candidate(
            dedupe_key=f"milestones.overdue_alert:{milestone.id}:{milestone.due_date.isoformat()}",
            target_type="milestone",
            target_id=milestone.id,
            project_id=project.id,
            context={"milestone_id": str(milestone.id), "due_date": milestone.due_date.isoformat(),
                     "evaluated_on": today.isoformat()},
        )


def _overdue_alert(db, ctx: dict) -> ActionResult:
    milestone = db.get(Milestone, UUID(ctx["milestone_id"]))
    if milestone is None or milestone.status in _CLOSED or milestone.lifecycle_state != LIFECYCLE_ACTIVE:
        return ActionResult(EXEC_SKIPPED, "The milestone is closed or no longer active.")
    if milestone.due_date is None or milestone.due_date.isoformat() != ctx.get("due_date"):
        return ActionResult(EXEC_SKIPPED, "The due date changed; the new date is evaluated separately.")
    project = db.get(Project, milestone.project_id)
    finding = db.scalar(
        select(ProjectRiskFinding).where(
            ProjectRiskFinding.milestone_id == milestone.id,
            ProjectRiskFinding.status.in_(OPEN_FINDING_STATUSES),
        )
    )
    recipient = milestone.assigned_user_id or project.design_leader_id
    evaluated_on = date.fromisoformat(ctx["evaluated_on"]) if ctx.get("evaluated_on") else date.today()
    days = (evaluated_on - milestone.due_date).days
    message = f"'{milestone.name}' was due {milestone.due_date.isoformat()} ({days} day(s) ago) and is not closed."
    if finding is not None:
        message += " The Control Tower has an open finding with the evidence and recommended action."
    sent = notify(db, [recipient], title=f"Overdue milestone on {_project_label(project)}", message=message,
                  entity_type=EntityType.milestone, entity_id=milestone.id)
    return ActionResult(EXEC_SUCCEEDED if sent else EXEC_SKIPPED,
                        f"Overdue by {days} day(s); notified {len(sent)}.",
                        {"notified_user_ids": sent, "control_tower_finding_id": str(finding.id) if finding else None,
                         "recipient_basis": "milestone assignee" if milestone.assigned_user_id else "design leader"})


# --------------------------------------------------------------------------- projects


def _update_candidates(db, today: date):
    projects = db.scalars(
        select(Project).where(
            Project.is_deleted.is_(False),
            Project.is_archived.is_(False),
            Project.execution_status.not_in((ExecutionStatus.completed, ExecutionStatus.cancelled)),
            Project.project_template_id.is_not(None),
        )
    ).all()
    for project in projects:
        current = db.get(ProjectTemplate, project.project_template_id)
        if current is None or current.is_active:
            continue
        family = current.template_family_id or current.id
        active = db.scalar(
            select(ProjectTemplate).where(
                ProjectTemplate.template_family_id == family,
                ProjectTemplate.is_active.is_(True),
                ProjectTemplate.id != current.id,
            )
        )
        if active is None or active.version <= current.version:
            continue
        yield Candidate(
            dedupe_key=f"projects.template_update_available:{project.id}:{active.id}",
            target_type="project",
            target_id=project.id,
            project_id=project.id,
            context={"project_id": str(project.id), "current_template_id": str(current.id),
                     "available_template_id": str(active.id)},
        )


def _template_update_available(db, ctx: dict) -> ActionResult:
    project = db.get(Project, UUID(ctx["project_id"]))
    current = db.get(ProjectTemplate, UUID(ctx["current_template_id"]))
    available = db.get(ProjectTemplate, UUID(ctx["available_template_id"]))
    if project is None or available is None or project.project_template_id != current.id:
        return ActionResult(EXEC_SKIPPED, "The project already moved to another template.")
    sent = notify(db, [project.design_leader_id],
                  title=f"Template update available for {_project_label(project)}",
                  message=f"{available.name} v{available.version} is now active (project uses v{current.version}). "
                          "Open Change Template on the project to preview the reconciliation; nothing changes automatically.",
                  entity_type=EntityType.project, entity_id=project.id)
    return ActionResult(EXEC_PENDING_REVIEW,
                        f"Recommend previewing {available.name} v{available.version} (currently v{current.version}).",
                        {"notified_user_ids": sent, "current_version": current.version,
                         "available_version": available.version, "available_template_id": str(available.id)})


# --------------------------------------------------------------------------- resource planning


def _no_designer_candidates(db, today: date):
    year, week, _ = today.isocalendar()
    for project in db.scalars(_live_projects().where(Project.designer_id.is_(None))).all():
        yield Candidate(
            dedupe_key=f"resource.project_without_designer:{project.id}:{year}-W{week:02d}",
            target_type="project",
            target_id=project.id,
            project_id=project.id,
            context={"project_id": str(project.id)},
        )


def _no_designer(db, ctx: dict) -> ActionResult:
    project = db.get(Project, UUID(ctx["project_id"]))
    if project is None or project.designer_id is not None:
        return ActionResult(EXEC_SKIPPED, "A designer has been assigned.")
    if project.design_leader_id is None:
        return ActionResult(EXEC_PENDING_REVIEW, "Live project with no designer and no design leader; needs a planner.")
    sent = notify(db, [project.design_leader_id], title=f"No designer on {_project_label(project)}",
                  message="This live project has no designer. Assign one from Resource Planning; nobody was assigned automatically.",
                  entity_type=EntityType.project, entity_id=project.id)
    return ActionResult(EXEC_SUCCEEDED if sent else EXEC_SKIPPED, "Asked the design leader to assign a designer.",
                        {"notified_user_ids": sent})


# --------------------------------------------------------------------------- registry

register(RuleDefinition(
    key="milestones.template_reconciled_notice",
    name="Template change notice",
    module="Projects",
    kind=KIND_EVENT,
    trigger=EVENT_TEMPLATE_RECONCILED,
    description="Tells the project's design leader, designer and surfacer what a confirmed template change did.",
    conditions="A template reconciliation was applied. The person who applied it is not notified.",
    action="In-app notification",
    recipients="Project design leader, designer, surfacer",
    authorization="Notification only. The change itself was confirmed by an authorised user in the preview.",
    perform=_template_reconciled,
))
register(RuleDefinition(
    key="milestones.added_needs_owner",
    name="New milestones without an owner",
    module="Projects",
    kind=KIND_EVENT,
    trigger=EVENT_TEMPLATE_RECONCILED,
    description="When a template change adds milestones the assignment rules could not staff, asks the design leader to assign them.",
    conditions="Milestones added by the reconciliation are still unassigned.",
    action="In-app notification",
    recipients="Project design leader",
    authorization="Never assigns anyone.",
    perform=_added_needs_owner,
))
register(RuleDefinition(
    key="milestones.dependency_ready",
    name="Milestone ready to start",
    module="Projects",
    kind=KIND_EVENT,
    trigger=EVENT_MILESTONE_COMPLETED,
    description="When a milestone is completed, tells the owner of each waiting milestone whose predecessors are now all closed.",
    conditions="Dependent milestone is active, not started, and every predecessor is completed, cancelled or not applicable.",
    action="In-app notification",
    recipients="Dependent milestone owner (design leader when unassigned)",
    authorization="Never starts or completes dependent work; statuses are unchanged.",
    perform=_dependency_ready,
))
register(RuleDefinition(
    key="milestones.overdue_alert",
    name="Overdue milestone alert",
    module="Projects",
    kind=KIND_SWEEP,
    trigger="Daily sweep",
    description="One alert per milestone and due date when an active milestone on a live project passes its due date.",
    conditions="Active milestone, not closed, due date before today, project planning or in progress. Moving the due date re-arms the alert once.",
    action="In-app notification linked to the open Control Tower finding when one exists",
    recipients="Milestone owner (design leader when unassigned)",
    authorization="Notification only. The Control Tower finding remains the record of the risk.",
    perform=_overdue_alert,
    candidates=_overdue_candidates,
))
register(RuleDefinition(
    key="projects.template_update_available",
    name="Template update available",
    module="Projects",
    kind=KIND_SWEEP,
    trigger="Daily sweep",
    description="Recommends reviewing a newer active version of the project's template.",
    conditions="Project is open and its template version is no longer the active version of the family.",
    action="Recommendation for review plus in-app notification",
    recipients="Project design leader",
    authorization="Never changes the template; a person must preview and confirm the reconciliation.",
    consequential=True,
    perform=_template_update_available,
    candidates=_update_candidates,
))
register(RuleDefinition(
    key="resource.project_without_designer",
    name="Live project without a designer",
    module="Resource Planning",
    kind=KIND_SWEEP,
    trigger="Weekly (deduplicated per ISO week)",
    description="Flags live projects that have no designer so work does not stall unnoticed.",
    conditions="Project planning or in progress, not archived or deleted, no designer.",
    action="In-app notification, or a review item when the project has no design leader",
    recipients="Project design leader",
    authorization="Never assigns resources.",
    perform=_no_designer,
    candidates=_no_designer_candidates,
))

_EXTERNAL = [
    ("timesheets.workflow_notifications", "Timesheet submitted / approved / rejected", "Timesheets",
     "Timesheet submission and approval actions",
     "Notifies approvers and submitters as timesheets move through approval.",
     "Admin → Notification settings (pending approvals)", "Never approves timesheets."),
    ("finance.quote_not_invoiced", "Quote not invoiced reminder", "Finance",
     "Startup and the Finance invoicing page",
     "Reminds finance users about accepted quotes with nothing invoiced; deduplicated by the last reminder date.",
     "Finance module", "Never creates invoices."),
    ("finance.payment_follow_up", "Payment follow-up reminder", "Finance",
     "Startup and the Finance payments page",
     "Reminds finance users about overdue unpaid quote balances.",
     "Finance module", "Never records payments or changes balances."),
    ("it.renewal_reminders", "Licence and contract renewals", "IT",
     "Startup and the IT renewals page",
     "Reminds IT about upcoming renewals; deduplicated per renewal date.",
     "IT module", "Never renews or purchases."),
    ("it.ticket_sla_sweep", "Ticket SLA sweep", "IT",
     "Startup and the ticket SLA endpoint",
     "Marks SLA breaches and notifies ticket owners.",
     "IT module", "Never closes or reassigns tickets."),
    ("hr.new_hire_onboarding", "New hire onboarding", "IT / Onboarding",
     "HR onboarding flow",
     "Notifies the team leader of a new hire and prepares provisioning requests for IT approval.",
     "HR onboarding", "Provisioning requests still need IT approval."),
    ("controltower.evaluation", "Control Tower evaluation", "Projects",
     "Background job (runner --control-tower) and the Control Tower page",
     "Opens, updates and resolves project risk findings.",
     "Control Tower", "Findings are advisory; nothing is changed on projects."),
]
for key, name, module, where, description, managed_by, authorization in _EXTERNAL:
    register(RuleDefinition(
        key=key, name=name, module=module, kind=KIND_EXTERNAL, trigger=where, description=description,
        conditions="Defined by the owning module.", action="Existing module behaviour", recipients="Defined by the owning module",
        authorization=authorization, runs_where=managed_by,
    ))


def describe(definition: RuleDefinition) -> dict:
    return {
        "key": definition.key,
        "name": definition.name,
        "module": definition.module,
        "kind": definition.kind,
        "trigger": definition.trigger,
        "description": definition.description,
        "conditions": definition.conditions,
        "action": definition.action,
        "recipients": definition.recipients,
        "authorization": definition.authorization,
        "consequential": definition.consequential,
        "executable": definition.executable,
        "managed_by": definition.runs_where,
    }
