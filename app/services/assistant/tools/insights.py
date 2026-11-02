"""Management insight tools: delivery performance, Control Tower summary, effort forecast."""

from __future__ import annotations

from datetime import date

from app.services import control_tower_service as ct
from app.services.assistant.context import AssistantContext
from app.services.assistant.tools.common import clip, num
from app.services.assistant.types import Source, Table, ToolInputError, ToolResult, ToolSpec
from app.services.forecasting.effort import build_engineering_forecast
from app.services.reporting.engineering_performance import PerformanceFilters, build_engineering_performance

# Below this many completed projects a rate or average describes individual projects, not a trend.
MIN_TREND_SAMPLE = 5


def _anchor(args: dict) -> date | None:
    raw = args.get("anchor_date")
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ToolInputError("anchor_date must be YYYY-MM-DD.") from exc


def _delivery_performance(ctx: AssistantContext, args: dict) -> ToolResult:
    filters = PerformanceFilters(
        period_type=args.get("period_type", "quarterly"),
        anchor=_anchor(args) or ctx.today,
        plan_basis=args.get("plan_basis", "current"),
        team_ids=ctx.report_team_ids,
        visibility_clause=ctx.visibility_clause,
    )
    report = build_engineering_performance(ctx.db, filters)
    s = report.summary
    sample = s.projects_completed
    insufficient = sample < MIN_TREND_SAMPLE
    stages = [{"stage": r.label, "projects": r.eligible_projects or r.projects, "current_estimate_hours": num(r.current_hours),
               "actual_hours": num(r.actual_hours), "variance_hours": num(r.variance_hours),
               "variance_percent": num(r.variance_percent), "projects_over_estimate": r.projects_over_estimate}
              for r in report.stage_performance.rows]
    limitations = [w.message for w in report.warnings][:6]
    if insufficient:
        limitations.insert(0, f"Only {sample} completed project(s) in {report.period.label}; this is too few to describe a trend. "
                              "Report the individual projects instead of rates.")
    if report.empty_message:
        limitations.append(report.empty_message)
    return ToolResult(
        data={
            "period": {"label": report.period.label, "start": report.period.start_date, "end": report.period.end_date},
            "plan_basis": s.plan_basis, "record_count": sample, "insufficient_sample": insufficient,
            "minimum_sample_for_trend": MIN_TREND_SAMPLE,
            "summary": {
                "projects_completed": sample, "on_time_projects": s.on_time_projects, "late_projects": s.late_projects,
                "projects_without_reference_date": s.projects_without_reference_date,
                "on_time_rate": None if insufficient else num(s.on_time_rate),
                "average_days_late": None if insufficient else num(s.average_days_late),
                "planned_hours": num(s.planned_hours), "actual_hours": num(s.actual_hours),
                "variance_hours": num(s.variance_hours), "variance_percent": None if insufficient else num(s.variance_percent),
                "projects_without_plan": s.projects_without_plan,
                "milestones_completed": s.milestones_completed, "milestones_on_time": s.milestones_on_time,
            },
            "stage_performance": stages,
            "projects": [{"project": p.code or p.tool_number, "completed": p.actual_completion_date,
                          "reference_date": p.reference_completion_date, "days_late": p.days_late,
                          "planned_hours": num(p.planned_hours), "actual_hours": num(p.actual_hours),
                          "variance_percent": num(p.variance_percent)} for p in report.projects][:25],
            "definitions": [{"kpi": d.label, "definition": clip(d.definition, 240)} for d in report.definitions][:10],
        },
        record_count=sample,
        sources=[Source(kind="report", ref=f"engineering-performance:{report.period.start_date}",
                        label=f"Engineering performance — {report.period.label}", route="/analytics")],
        tables=[Table(title=f"Stage hours — {report.period.label}",
                      columns=["Stage", "Projects", "Current estimate (h)", "Actual (h)", "Variance (h)", "Over estimate"],
                      rows=[[x["stage"], x["projects"], x["current_estimate_hours"], x["actual_hours"], x["variance_hours"],
                             x["projects_over_estimate"]] for x in stages])] if stages else [],
        limitations=limitations,
    )


def _control_tower_summary(ctx: AssistantContext, args: dict) -> ToolResult:
    scope = ct.FindingScope(visibility_clause=ctx.visibility_clause, team_ids=ctx.report_team_ids)
    summary = ct.build_summary(ctx.db, scope, ctx.today)
    latest, succeeded = ct.latest_runs(ctx.db)
    state, message = ct.control_tower_state(latest, succeeded, ctx.today)
    return ToolResult(
        data={"state": state, "state_message": message,
              "last_successful_evaluation": succeeded.evaluation_date if succeeded else None,
              **summary.model_dump(mode="json")},
        record_count=summary.open_risks + summary.open_data_quality,
        sources=[Source(kind="report", ref="control-tower", label="Control Tower", route="/reports")],
        tables=[Table(title="Open findings by severity", columns=["Severity", "Open"],
                      rows=[[c.severity, c.count] for c in summary.by_severity])] if summary.by_severity else [],
        limitations=[] if state == "ok" else [message],
    )


def _effort_forecast(ctx: AssistantContext, args: dict) -> ToolResult:
    fc = build_engineering_forecast(ctx.db, as_of=ctx.today, visibility_clause=ctx.visibility_clause,
                                    team_ids=ctx.report_team_ids)
    projects = sorted(fc.projects, key=lambda p: -(p.forecast_remaining_hours or p.approved_remaining_hours or 0))
    rows = [{"project": p.code or p.tool_number, "approved_current_estimate": num(p.approved_current_estimate_hours),
             "actual": num(p.actual_hours), "approved_remaining": num(p.approved_remaining_hours),
             "forecast_status": p.forecast_status, "forecast_remaining": num(p.forecast_remaining_hours),
             "forecast_at_completion": num(p.forecast_at_completion_hours), "forecast_reason": p.forecast_reason,
             "current_target_date": p.current_target_date} for p in projects[: args.get("limit", 15)]]
    return ToolResult(
        data={"value_kind": "forecast", "as_of": fc.metadata.as_of, "status": fc.metadata.status,
              "history_sample_size": fc.history.sample_size, "minimum_sample": fc.history.minimum_sample,
              "history_factor": num(fc.history.factor), "factor_status": fc.history.factor_status,
              "summary": fc.summary.model_dump(mode="json"), "assumptions": fc.metadata.assumptions, "projects": rows},
        record_count=len(fc.projects),
        sources=[Source(kind="forecast", ref="engineering", label="Remaining effort forecast", route="/analytics")],
        tables=[Table(title="Remaining effort (approved plan vs forecast)",
                      columns=["Project", "Approved estimate (h)", "Actual (h)", "Approved remaining (h)", "Forecast remaining (h)", "Forecast status"],
                      rows=[[r["project"], r["approved_current_estimate"], r["actual"], r["approved_remaining"],
                             r["forecast_remaining"], r["forecast_status"]] for r in rows])] if rows else [],
        limitations=[*fc.metadata.limitations, fc.metadata.confidence_note],
    )


_REPORTS = lambda ctx: ctx.can_view_reports  # noqa: E731
_DENIED = "Management insights require Reports access."

SPECS = [
    ToolSpec(
        name="get_delivery_performance",
        module="management",
        description=(
            "Completed-project delivery performance for a period: on-time rate, days late, estimate vs actual hours "
            "and stage-hour variance, with the number of projects behind each figure."
        ),
        parameters={
            "type": "object",
            "properties": {
                "period_type": {"type": "string", "enum": ["monthly", "quarterly", "yearly"]},
                "anchor_date": {"type": "string", "maxLength": 10, "description": "Any date inside the period, YYYY-MM-DD. Defaults to today."},
                "plan_basis": {"type": "string", "enum": ["current", "original"]},
            },
            "additionalProperties": False,
        },
        allowed=_REPORTS, handler=_delivery_performance, denied_message=_DENIED,
    ),
    ToolSpec(
        name="get_control_tower_summary",
        module="management",
        description="Counts of open Control Tower risks and data-quality findings by severity and category, with evaluation freshness.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        allowed=_REPORTS, handler=_control_tower_summary, denied_message=_DENIED,
    ),
    ToolSpec(
        name="get_effort_forecast",
        module="management",
        description="Remaining-effort forecast for open projects: approved remaining hours versus history-based forecast.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 25}},
            "additionalProperties": False,
        },
        allowed=_REPORTS, handler=_effort_forecast, denied_message=_DENIED,
    ),
]
