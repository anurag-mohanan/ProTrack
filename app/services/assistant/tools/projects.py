"""Project tools. Hours and dates come from the engineering metrics service; risks from the Control Tower."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import func, or_, select

from app.models.enums import ExecutionStatus
from app.models.models import Project, User
from app.schemas.engineering_metrics import ProjectEngineeringMetrics
from app.services import control_tower_service as ct
from app.services.assistant.context import AssistantContext
from app.services.assistant.tools.common import (
    clip,
    metric,
    num,
    person_name,
    project_label,
    project_source,
    resolve_project,
    search_condition,
    visible_projects_stmt,
)
from app.services.assistant.types import Source, Table, ToolResult, ToolSpec
from app.services.engineering_metrics_service import build_engineering_metrics_batch

OPEN_STATUSES = (ExecutionStatus.planning, ExecutionStatus.currently_being_worked_on, ExecutionStatus.on_hold)
MAX_SCAN = 400
CLOSED_MILESTONE = {"completed", "cancelled", "not_applicable"}

HOURS_NOTE = (
    "Actual hours are all recorded timesheet hours (approved, submitted, draft and rejected are listed separately). "
    "Approved estimate is the current approved estimate; quoted hours are the original quote."
)


def _metrics(ctx: AssistantContext, projects: list[Project]) -> dict:
    if not projects:
        return {}
    return build_engineering_metrics_batch(ctx.db, projects, finance_details_visible=ctx.finance_visible, today=ctx.today)


def _project_facts(project: Project, m: ProjectEngineeringMetrics) -> dict[str, Any]:
    d = m.delivery.project
    return {
        "project": project.code or project.tool_number,
        "tool_number": project.tool_number,
        "description": clip(project.part_description),
        "customer": clip(project.customer.name if project.customer else None, 80),
        "status": m.execution_status,
        "design_leader": person_name(project.design_leader),
        "designer": person_name(project.designer),
        "surfacer": person_name(project.surfacer),
        "dates": {
            "current_due_date": d.current_due_date,
            "original_baseline_completion_date": d.original_baseline_completion_date,
            "current_baseline_completion_date": d.current_baseline_completion_date,
            "actual_completion_date": d.actual_completion_date,
            "delivery_status": d.status,
            "delivery_reference": d.reference_label,
            "schedule_variance_days": d.schedule_variance_days,
            "days_overdue": d.days_overdue,
            "target_moved_days": d.target_moved_days,
        },
        "hours": {
            "quoted_estimate": num(m.estimate.quoted_hours),
            "original_approved_estimate": num(m.estimate.original_estimate_hours),
            "current_approved_estimate": num(m.estimate.current_estimate_hours),
            "estimate_source": m.estimate.estimate_source_label,
            "actual_status": m.actual.status,
            "actual_recorded": num(m.actual.total_hours),
            "actual_approved": num(m.actual.approved_hours),
            "actual_submitted": num(m.actual.submitted_hours),
            "actual_draft": num(m.actual.draft_hours),
            "actual_rejected": num(m.actual.rejected_hours),
            "remaining": metric(m.remaining_hours),
            "variance_vs_current_estimate": metric(m.variance_hours),
            "variance_vs_original_estimate": metric(m.original_variance_hours),
        },
        "milestones": {
            "total": m.milestones.total,
            "completed": m.milestones.completed,
            "open": m.milestones.open,
            "open_overdue": m.milestones.open_overdue,
            "open_without_target_date": m.milestones.open_without_target_date,
        },
        "data_quality": m.data_quality_status,
        "data_quality_issues": [i.message for i in m.issues][:5],
    }


def _limitations(metrics: list[ProjectEngineeringMetrics]) -> list[str]:
    notes = [HOURS_NOTE]
    quoted_only = sum(1 for m in metrics if m.estimate.estimate_source == "quoted_hours")
    no_estimate = sum(1 for m in metrics if m.estimate.estimate_source == "none")
    missing = sum(1 for m in metrics if m.actual.status == "missing")
    if quoted_only:
        notes.append(f"{quoted_only} project(s) have no approved estimate and are measured against quoted hours.")
    if no_estimate:
        notes.append(f"{no_estimate} project(s) have no estimate at all; remaining and variance are unavailable for them.")
    if missing:
        notes.append(f"{missing} project(s) show progress but no timesheet hours; their actual hours are treated as missing, not zero.")
    return notes


# ---------------------------------------------------------------- find_projects


def _find_projects(ctx: AssistantContext, args: dict) -> ToolResult:
    status = args.get("status", "open")
    stmt = visible_projects_stmt(ctx, include_archived=status in ("completed", "cancelled", "any"))
    if status == "open":
        stmt = stmt.where(Project.execution_status.in_(OPEN_STATUSES))
    elif status != "any":
        stmt = stmt.where(Project.execution_status == ExecutionStatus(status))
    if args.get("search"):
        stmt = stmt.where(search_condition(args["search"]))
    if args.get("person"):
        pattern = f"%{args['person'].lower()}%"
        user_ids = select(User.id).where(func.lower(User.first_name + " " + User.last_name).like(pattern))
        stmt = stmt.where(or_(Project.design_leader_id.in_(user_ids), Project.designer_id.in_(user_ids),
                              Project.surfacer_id.in_(user_ids)))
    projects = list(ctx.db.scalars(stmt.order_by(Project.tool_number).limit(MAX_SCAN + 1)).all())
    truncated = len(projects) > MAX_SCAN
    projects = projects[:MAX_SCAN]
    metrics = _metrics(ctx, projects)

    horizon = args.get("due_within_days")
    rows: list[tuple[Project, ProjectEngineeringMetrics]] = []
    for project in projects:
        m = metrics[project.id]
        d = m.delivery.project
        if horizon is not None and not (d.current_due_date and ctx.today <= d.current_due_date <= ctx.today + timedelta(days=horizon)):
            continue
        if args.get("overdue_only") and not (d.days_overdue and d.days_overdue > 0):
            continue
        if args.get("over_estimate_only") and not (
            m.variance_hours.status == "available" and m.variance_hours.value is not None and m.variance_hours.value > 0
        ):
            continue
        rows.append((project, m))

    sort_by = args.get("sort_by", "due_date")
    if sort_by == "days_overdue":
        rows.sort(key=lambda r: -(r[1].delivery.project.days_overdue or 0))
    elif sort_by == "hours_over_estimate":
        rows.sort(key=lambda r: -(r[1].variance_hours.value or 0) if r[1].variance_hours.status == "available" else 0)
    elif sort_by == "due_date":
        rows.sort(key=lambda r: (r[1].delivery.project.current_due_date is None, r[1].delivery.project.current_due_date or ctx.today))
    matched = len(rows)
    rows = rows[: args.get("limit", 15)]

    table = Table(
        title="Projects",
        columns=["Project", "Description", "Customer", "Status", "Design leader", "Current due", "Days overdue",
                 "Approved estimate (h)", "Actual recorded (h)", "Remaining (h)"],
        rows=[[
            p.code or p.tool_number, clip(p.part_description, 60), clip(p.customer.name if p.customer else None, 40),
            m.execution_status, person_name(p.design_leader), m.delivery.project.current_due_date,
            m.delivery.project.days_overdue, num(m.estimate.current_estimate_hours), num(m.actual.total_hours),
            num(m.remaining_hours.value),
        ] for p, m in rows],
    )
    limitations = _limitations([m for _, m in rows])
    if truncated:
        limitations.append(f"Only the first {MAX_SCAN} matching projects were examined; narrow the search for a complete answer.")
    if matched > len(rows):
        limitations.append(f"{matched} projects matched; the first {len(rows)} are shown.")
    for p, _ in rows:
        ctx.seen_project_ids.add(p.id)
    return ToolResult(
        data={"filters": args, "as_of": ctx.today, "matched": matched, "shown": len(rows),
              "projects": [_project_facts(p, m) for p, m in rows]},
        record_count=matched,
        sources=[project_source(p, f"Due {m.delivery.project.current_due_date or 'not set'}") for p, m in rows],
        tables=[table] if rows else [],
        limitations=limitations,
        summary=f"{matched} project(s) matched.",
    )


# ---------------------------------------------------------------- project summary


def _findings_for(ctx: AssistantContext, project: Project) -> tuple[list, str, str]:
    scope = ct.FindingScope(visibility_clause=ctx.visibility_clause, team_ids=ctx.report_team_ids)
    findings = []
    for view in ("risks", "data_quality"):
        rows, _ = ct.list_findings(ctx.db, scope, ct.FindingQuery(view=view, project_id=project.id), page=1, page_size=25)
        findings.extend(rows)
    latest, succeeded = ct.latest_runs(ctx.db)
    state, message = ct.control_tower_state(latest, succeeded, ctx.today)
    return findings, state, message


def _finding_dict(f) -> dict[str, Any]:
    return {
        "finding": f.title, "severity": f.severity, "category": f.category_label, "status": f.status,
        "explanation": clip(f.explanation, 400), "recommended_action": clip(f.recommended_action, 300),
        "evidence": [{"label": e.label, "value": clip(e.value, 120)} for e in f.evidence][:8],
        "milestone": f.milestone.name if f.milestone else None,
        "owner": f.owner.name, "first_detected": f.first_detected_at.date() if f.first_detected_at else None,
        "evaluation_date": f.evaluation_date,
    }


def _finding_source(f) -> Source:
    ref = f.project.code or f.project.tool_number
    return Source(kind="finding", ref=str(f.id), label=f"{ref}: {clip(f.title, 80)}",
                  detail=f"{f.severity} · {f.category_label}", route="/reports")


def _project_summary(ctx: AssistantContext, args: dict) -> ToolResult:
    project = resolve_project(ctx, args["project"])
    m = _metrics(ctx, [project])[project.id]
    facts = _project_facts(project, m)
    milestones = m.delivery.milestones
    open_ms = [x for x in milestones if x.milestone_status not in CLOSED_MILESTONE]
    current = sorted(open_ms, key=lambda x: (x.current_due_date is None, x.current_due_date or ctx.today))[:1]
    overdue = [x for x in open_ms if x.status == "overdue"]
    facts["milestone_detail"] = {
        "current": [x.name for x in current],
        "completed": [x.name for x in milestones if x.milestone_status == "completed"],
        "pending": [x.name for x in open_ms],
        "overdue": [{"name": x.name, "current_due_date": x.current_due_date, "days_overdue": x.days_overdue} for x in overdue],
    }
    sources = [project_source(project)]
    limitations = _limitations([m])
    actions: list[str] = [f"Overdue milestone '{x.name}' ({x.days_overdue} day(s) overdue)." for x in overdue]
    if ctx.can_view_reports:
        findings, state, message = _findings_for(ctx, project)
        facts["control_tower"] = {"state": state, "state_message": message,
                                  "open_findings": [_finding_dict(f) for f in findings]}
        actions.extend(clip(f.recommended_action, 200) for f in findings if f.recommended_action)
        sources.extend(_finding_source(f) for f in findings)
        if state != "ok":
            limitations.append(message)
    else:
        limitations.append("Control Tower findings are not included: they require Reports access.")
    facts["outstanding_actions"] = actions
    table = Table(
        title=f"Milestones — {project_label(project)}",
        columns=["Milestone", "Status", "Current due", "Original baseline", "Completed", "Days overdue"],
        rows=[[x.name, x.milestone_status, x.current_due_date, x.original_baseline_finish_date,
               x.actual_completion_date, x.days_overdue] for x in milestones],
    )
    return ToolResult(data=facts, record_count=1, sources=sources, tables=[table] if milestones else [],
                      limitations=limitations, summary=f"Summary of {project_label(project)}.")


def _project_milestones(ctx: AssistantContext, args: dict) -> ToolResult:
    project = resolve_project(ctx, args["project"])
    m = _metrics(ctx, [project])[project.id]
    which = args.get("status", "all")
    rows = m.delivery.milestones
    if which == "open":
        rows = [x for x in rows if x.milestone_status not in CLOSED_MILESTONE]
    elif which == "overdue":
        rows = [x for x in rows if x.status == "overdue"]
    elif which == "completed":
        rows = [x for x in rows if x.milestone_status == "completed"]
    data = [{"milestone": x.name, "stage": x.stage_label, "status": x.milestone_status, "delivery_status": x.status,
             "current_due_date": x.current_due_date, "original_baseline_finish_date": x.original_baseline_finish_date,
             "actual_completion_date": x.actual_completion_date, "schedule_variance_days": x.schedule_variance_days,
             "days_overdue": x.days_overdue} for x in rows]
    return ToolResult(
        data={"project": project.code or project.tool_number, "filter": which, "as_of": ctx.today,
              "sign_convention": m.delivery.sign_convention, "milestones": data},
        record_count=len(rows),
        sources=[project_source(project, f"{len(rows)} milestone(s)")],
        tables=[Table(title=f"Milestones — {project_label(project)}",
                      columns=["Milestone", "Status", "Current due", "Original baseline", "Completed", "Days overdue"],
                      rows=[[x.name, x.milestone_status, x.current_due_date, x.original_baseline_finish_date,
                             x.actual_completion_date, x.days_overdue] for x in rows])] if rows else [],
        limitations=["Merged, superseded and archived milestones are excluded, as in the project workspace."],
    )


# ---------------------------------------------------------------- Control Tower findings


def _risk_findings(ctx: AssistantContext, args: dict) -> ToolResult:
    scope = ct.FindingScope(visibility_clause=ctx.visibility_clause, team_ids=ctx.report_team_ids)
    project_id = resolve_project(ctx, args["project"]).id if args.get("project") else None
    query = ct.FindingQuery(view=args.get("view", "risks"), severity=args.get("severity"),
                            category=args.get("category"), project_id=project_id)
    rows, total = ct.list_findings(ctx.db, scope, query, page=1, page_size=args.get("limit", 15))
    latest, succeeded = ct.latest_runs(ctx.db)
    state, message = ct.control_tower_state(latest, succeeded, ctx.today)
    limitations = [] if state == "ok" else [message]
    if total > len(rows):
        limitations.append(f"{total} findings matched; the {len(rows)} most severe are shown.")
    for f in rows:
        ctx.seen_project_ids.add(f.project.id)
    return ToolResult(
        data={"control_tower_state": state, "state_message": message, "matched": total,
              "findings": [{"project": f.project.code or f.project.tool_number, **_finding_dict(f)} for f in rows]},
        record_count=total,
        sources=[_finding_source(f) for f in rows],
        tables=[Table(title="Control Tower findings",
                      columns=["Project", "Finding", "Severity", "Category", "Owner", "Recommended action"],
                      rows=[[f.project.code or f.project.tool_number, clip(f.title, 80), f.severity, f.category_label,
                             f.owner.name, clip(f.recommended_action, 100)] for f in rows])] if rows else [],
        limitations=limitations,
    )


_PROJECT_REF = {"type": "string", "maxLength": 80, "description": "Project code or tool number, e.g. 'P-1042' or 'T-100'."}

SPECS = [
    ToolSpec(
        name="find_projects",
        module="projects",
        description=(
            "List projects the user can access with hours (approved estimate, actual, remaining) and dates. "
            "Use for due-soon, overdue, over-estimate, by-customer or by-person questions."
        ),
        parameters={
            "type": "object",
            "properties": {
                "search": {"type": "string", "maxLength": 100, "description": "Text in project code, tool number, description or customer name."},
                "status": {"type": "string", "enum": ["open", "planning", "currently_being_worked_on", "on_hold", "completed", "cancelled", "any"]},
                "person": {"type": "string", "maxLength": 80, "description": "Name of an assigned design leader, designer or surfacer."},
                "due_within_days": {"type": "integer", "minimum": 0, "maximum": 365, "description": "Current due date between today and today + N days."},
                "overdue_only": {"type": "boolean"},
                "over_estimate_only": {"type": "boolean", "description": "Actual hours above the current approved estimate."},
                "sort_by": {"type": "string", "enum": ["due_date", "days_overdue", "hours_over_estimate", "tool_number"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25},
            },
            "additionalProperties": False,
        },
        allowed=lambda ctx: True,
        handler=_find_projects,
        denied_message="",
    ),
    ToolSpec(
        name="get_project_summary",
        module="projects",
        description=(
            "Full summary of one project: customer, design leader, designer, surfacer, status, milestones "
            "(current, completed, pending, overdue), quoted/approved/actual/remaining hours, original and current due "
            "date, delivery variance, Control Tower findings and outstanding actions."
        ),
        parameters={"type": "object", "properties": {"project": _PROJECT_REF}, "required": ["project"], "additionalProperties": False},
        allowed=lambda ctx: True,
        handler=_project_summary,
        denied_message="",
    ),
    ToolSpec(
        name="list_project_milestones",
        module="projects",
        description="Milestones of one project with current due date, original baseline, completion and days overdue.",
        parameters={
            "type": "object",
            "properties": {"project": _PROJECT_REF, "status": {"type": "string", "enum": ["all", "open", "overdue", "completed"]}},
            "required": ["project"],
            "additionalProperties": False,
        },
        allowed=lambda ctx: True,
        handler=_project_milestones,
        denied_message="",
    ),
    ToolSpec(
        name="list_risk_findings",
        module="projects",
        description=(
            "Open Control Tower findings (the official risk evaluation) with evidence and recommended action. "
            "Use to explain why a project is at risk. Never invent risks that are not listed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "project": _PROJECT_REF,
                "view": {"type": "string", "enum": ["risks", "data_quality"]},
                "severity": {"type": "string", "enum": ["critical", "high", "medium", "info"]},
                "category": {"type": "string", "enum": ["schedule", "effort", "delivery", "capability"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25},
            },
            "additionalProperties": False,
        },
        allowed=lambda ctx: ctx.can_view_reports,
        handler=_risk_findings,
        denied_message="Control Tower findings require Reports access.",
    ),
]
