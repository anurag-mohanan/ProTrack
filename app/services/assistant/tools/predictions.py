"""Predictive tools: read stored predictions and backend analyses. The assistant never computes a forecast."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.models.prediction import INSUFFICIENT, PREDICTED
from app.services.assistant.context import AssistantContext
from app.services.assistant.tools.common import clip, project_label, resolve_project
from app.services.assistant.types import Source, Table, ToolDenied, ToolInputError, ToolResult, ToolSpec
from app.services.predictive import read
from app.services.predictive.read import PredictionScope

FORECAST_NOTES = [
    "These are forecasts from comparable completed work, not certainties or actual values. Approved estimates and "
    "dates are unchanged.",
    "A likely range is only given when at least 10 comparable outcomes exist. 'Observed share' is how often comparable "
    "work went past the baseline; it is not a calibrated probability.",
]
TYPE_KEYS = {"delivery": "project_delivery", "final_hours": "project_final_hours", "milestone": "milestone_delay"}


def _scope(ctx: AssistantContext) -> PredictionScope:
    teams = ctx.capacity_team_ids
    return PredictionScope(
        visibility_clause=ctx.visibility_clause,
        can_view_capacity=ctx.can_view_capacity,
        capacity_team_ids=None if teams is None else frozenset(teams),
        finance_visible=ctx.finance_visible,
    )


def _value(row: dict) -> str | None:
    if row["status"] != PREDICTED:
        return None
    if row["predicted_date"]:
        return row["predicted_date"]
    unit = " h" if row["unit"] == "hours" else (f" {row['currency']}" if row.get("currency") else "")
    return f"{row['predicted_value']}{unit}"


def _range(row: dict) -> str | None:
    if row["lower_date"]:
        return f"{row['lower_date']} to {row['upper_date']}"
    if row["lower_value"] is not None:
        return f"{row['lower_value']} to {row['upper_value']}"
    return None


def _baseline(row: dict) -> str | None:
    return row["baseline_date"] or row["baseline_value"]


def _brief(row: dict) -> dict[str, Any]:
    return {
        "subject": clip(row["subject_label"], 120), "type": row["type_label"], "status": row["status"],
        "reason": clip(row["reason"], 300), "forecast": _value(row), "likely_range": _range(row),
        "range_basis": row["range_basis"], "baseline": f"{row['baseline_label']}: {_baseline(row)}" if row["baseline_label"] else None,
        "variance": row["variance_value"], "observed_share_beyond_baseline": row["observed_frequency"],
        "calibrated_probability": row["probability"], "comparable_cases": row["sample_size"],
        "comparison_group": row["comparison_group"], "model_version": row["model_version"], "predicted_on": row["as_of"],
        "horizon_end": row["horizon_end"],
    }


def _source(row: dict) -> Source:
    route = f"/predictive?project={row['project_id']}" if row["project_id"] else "/predictive"
    return Source(kind="forecast", ref=row["id"], label=clip(row["subject_label"], 80) or row["type_label"],
                  detail=f"{row['type_label']}, {row['model_version']}, predicted {row['as_of']}", route=route)


def _limits(ctx: AssistantContext, extra: list[str] | None = None) -> list[str]:
    fresh = read.freshness(ctx.db, ctx.today)
    out = list(FORECAST_NOTES)
    if fresh["stale"]:
        out.insert(0, fresh["message"])
    if fresh["disabled_types"]:
        out.append(f"Disabled by an administrator: {', '.join(fresh['disabled_types'])}.")
    return out + (extra or [])


def _project_predictions(ctx: AssistantContext, args: dict) -> ToolResult:
    ptype = TYPE_KEYS[args.get("type", "delivery")]
    scope = _scope(ctx)
    project_id = resolve_project(ctx, args["project"]).id if args.get("project") else None
    visible = read.visible_project_ids(ctx.db, scope)
    rows = [read.prediction_dict(p, visible) for p in read.latest(ctx.db, scope, prediction_types=[ptype], project_id=project_id)]
    predicted = [r for r in rows if r["status"] == PREDICTED]
    if args.get("at_risk_only", True):
        predicted = [r for r in predicted if r["variance_value"] is not None and Decimal(r["variance_value"]) > 0]
    predicted.sort(key=lambda r: Decimal(r["variance_value"] or 0), reverse=True)
    shown = predicted[: args.get("limit", 10)]
    insufficient = [r for r in rows if r["status"] == INSUFFICIENT]
    reasons: dict[str, int] = {}
    for r in insufficient:
        key = clip(r["reason"], 140) or "No reason recorded"
        reasons[key] = reasons.get(key, 0) + 1
    unit = "days" if ptype != "project_final_hours" else "h"
    return ToolResult(
        data={"prediction_type": ptype, "matched": len(predicted), "predictions": [_brief(r) for r in shown],
              "could_not_be_predicted": len(insufficient),
              "main_reasons_not_predicted": [{"reason": k, "count": v} for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])[:4]]},
        record_count=len(predicted),
        sources=[_source(r) for r in shown],
        tables=[Table(title=shown[0]["type_label"] if shown else ptype,
                      columns=["Subject", "Forecast", "Likely range", "Baseline", f"Variance ({unit})", "Comparable cases"],
                      rows=[[clip(r["subject_label"], 60), _value(r), _range(r) or "Not shown", _baseline(r),
                             r["variance_value"], r["sample_size"]] for r in shown])] if shown else [],
        limitations=_limits(ctx, [f"{len(insufficient)} subject(s) could not be predicted reliably."] if insufficient else None),
    )


def _explain(ctx: AssistantContext, args: dict) -> ToolResult:
    project = resolve_project(ctx, args["project"])
    scope = _scope(ctx)
    visible = read.visible_project_ids(ctx.db, scope)
    rows = [read.prediction_dict(p, visible) for p in read.latest(
        ctx.db, scope, prediction_types=list(TYPE_KEYS.values()), project_id=project.id)]
    if not rows:
        return ToolResult(data={"project": project_label(project), "predictions": []}, record_count=0,
                          limitations=_limits(ctx, ["No stored prediction exists for this project yet."]))
    detail = []
    for r in rows:
        item = _brief(r)
        item["factors"] = [{k: clip(v, 160) if isinstance(v, str) else v for k, v in f.items()} for f in r["factors"]][:10]
        item["warnings"] = [clip(w, 200) for w in r["warnings"]][:6]
        detail.append(item)
    return ToolResult(
        data={"project": project_label(project), "predictions": detail},
        record_count=len(rows),
        sources=[_source(r) for r in rows],
        tables=[Table(title=f"Predictions for {project_label(project)}",
                      columns=["Prediction", "Forecast", "Likely range", "Baseline", "Variance", "Status"],
                      rows=[[clip(r["subject_label"], 60) if r["milestone_id"] else r["type_label"], _value(r) or "Cannot be predicted",
                             _range(r) or "Not shown", _baseline(r), r["variance_value"], r["status"]] for r in rows])],
        limitations=_limits(ctx),
    )


def _resource_demand(ctx: AssistantContext, args: dict) -> ToolResult:
    weeks = args.get("weeks", 8)
    subject = args.get("subject", "person")
    scope = _scope(ctx)
    visible = read.visible_project_ids(ctx.db, scope)
    rows = [read.prediction_dict(p, visible) for p in read.latest(ctx.db, scope, prediction_types=["resource_demand"],
                                                                  subject_type=subject)]
    rows = [r for r in rows if r["subject_key"].endswith(f":{weeks}w")]
    predicted = [r for r in rows if r["status"] == PREDICTED]
    if args.get("shortages_only", True):
        predicted = [r for r in predicted if r["data_used"].get("shortage")]
    predicted.sort(key=lambda r: Decimal(r["data_used"].get("utilisation_percent") or 0), reverse=True)
    shown = predicted[: args.get("limit", 15)]
    items = [{**_brief(r), "utilisation_percent": r["data_used"].get("utilisation_percent"),
              "shortage": r["data_used"].get("shortage"), "demand_complete": r["data_used"].get("demand_complete"),
              "single_person_dependency": r["data_used"].get("single_person_dependency"),
              "overloaded_weeks": r["data_used"].get("overloaded_weeks")} for r in shown]
    insufficient = sum(1 for r in rows if r["status"] == INSUFFICIENT)
    warnings = sorted({w for r in shown for w in r["warnings"]})[:6]
    return ToolResult(
        data={"horizon_weeks": weeks, "subject": subject, "matched": len(predicted), "forecasts": items,
              "could_not_be_predicted": insufficient},
        record_count=len(predicted),
        sources=[Source(kind="forecast", ref=r["id"], label=clip(r["subject_label"], 80), route="/predictive?tab=resources")
                 for r in shown],
        tables=[Table(title=f"Forecast demand vs capacity, next {weeks} weeks",
                      columns=["Subject", "Demand (h)", "Capacity (h)", "Utilisation %", "Complete demand"],
                      rows=[[clip(r["subject_label"], 60), r["predicted_value"], r["baseline_value"],
                             r["data_used"].get("utilisation_percent"), r["data_used"].get("demand_complete")] for r in shown])] if shown else [],
        limitations=_limits(ctx, warnings),
    )


def _finance(ctx: AssistantContext, args: dict) -> ToolResult:
    ptype = "finance_collections" if args.get("type", "collections") == "collections" else "finance_billing"
    scope = _scope(ctx)
    rows = [read.prediction_dict(p) for p in read.latest(ctx.db, scope, prediction_types=[ptype])]
    rows.sort(key=lambda r: (r["currency"] or "", r["horizon_start"] or ""))
    warnings = sorted({w for r in rows for w in r["warnings"]})[:6]
    return ToolResult(
        data={"prediction_type": ptype, "periods": [_brief(r) for r in rows]},
        record_count=len(rows),
        sources=[Source(kind="forecast", ref=r["id"], label=clip(r["subject_label"], 80), route="/predictive")
                 for r in rows[:12]],
        tables=[Table(title="Forecast by period", columns=["Period", "Forecast", "Baseline", "Status"],
                      rows=[[r["subject_label"], _value(r) or "Cannot be predicted", _baseline(r), r["status"]]
                            for r in rows[:12]])] if rows else [],
        limitations=_limits(ctx, ["Awarded, invoiced, collected and outstanding amounts are Phase 3 actuals; only the "
                                  "timing is forecast.", *warnings]),
    )


def _patterns(ctx: AssistantContext, args: dict) -> ToolResult:
    from app.services.predictive.patterns import portfolio_finance_patterns, portfolio_project_patterns

    kind = args.get("kind", "project")
    if kind == "payment":
        if not ctx.finance_visible:
            raise ToolDenied("Payment patterns require Finance access.")
        result = portfolio_finance_patterns(ctx.db, ctx.today)
    else:
        result = portfolio_project_patterns(ctx.db, ctx.today)
    keep = ("metric_label", "dimension", "group_label", "stratum", "n", "comparison_n", "comparison_group",
            "group_median", "comparison_median", "p_value", "finding", "period_start", "period_end")
    patterns = [{k: r.get(k) for k in keep} for r in result["patterns"]]
    if kind == "payment":
        patterns.sort(key=lambda r: -(r["group_median"] or 0))
    return ToolResult(
        data={"kind": kind, "patterns": patterns,
              "groups_without_reliable_difference": len(result["no_reliable_difference"]),
              "groups_too_small_to_compare": [{k: r.get(k) for k in ("dimension", "group_label", "n")} for r in result["too_small"]][:15]},
        record_count=len(patterns),
        sources=[Source(kind="report", ref=f"patterns-{kind}", label=f"Historical {kind} patterns", route="/predictive")],
        tables=[Table(title="Statistically supported patterns",
                      columns=["Group", "Measure", "Median", "Comparison median", "n", "p"],
                      rows=[[r["group_label"], r["metric_label"], r["group_median"], r["comparison_median"], r["n"], r["p_value"]]
                            for r in patterns])] if patterns else [],
        limitations=result["limitations"],
    )


def _accuracy(ctx: AssistantContext, args: dict) -> ToolResult:
    from app.services.predictive.accuracy import MIN_EVALUATED, accuracy_report

    scope = _scope(ctx)
    wanted = [TYPE_KEYS[args["type"]]] if args.get("type") else [t for t in scope.types()]
    report = accuracy_report(ctx.db, [t for t in wanted if t in scope.types()])
    keep = ("evaluated", "reportable", "message", "mean_absolute_error", "median_absolute_error", "mean_bias",
            "mean_absolute_percentage_error", "naive_baseline", "range_coverage")
    items = [{"type": r["label"], "unit": r["unit"], "active_version": r["active_version"], "enabled": r["enabled"],
              "pending": r["pending"], "overall": {k: r["overall"].get(k) for k in keep if k in r["overall"]},
              "by_horizon": [{"horizon": h["horizon"], "evaluated": h["evaluated"],
                              "mean_absolute_error": h.get("mean_absolute_error")} for h in r["by_horizon"]],
              "degradation": r["degradation"]["status"]} for r in report]
    return ToolResult(
        data={"minimum_evaluated_for_figures": MIN_EVALUATED, "accuracy": items},
        record_count=sum(r["overall"]["evaluated"] for r in report),
        sources=[Source(kind="report", ref="prediction-accuracy", label="Prediction accuracy", route="/predictive?tab=accuracy")],
        tables=[Table(title="Prediction accuracy (scored against actual outcomes)",
                      columns=["Prediction", "Scored", "Mean absolute error", "Unit", "Pending"],
                      rows=[[r["label"], r["overall"]["evaluated"], r["overall"].get("mean_absolute_error") or "Not reported",
                             r["unit"], r["pending"]] for r in report])] if report else [],
        limitations=[f"Error figures are only reported once at least {MIN_EVALUATED} predictions have been scored.",
                     "Only the last prediction made on each date counts; predictions for cancelled projects are not scored."],
    )


def _scenario(ctx: AssistantContext, args: dict) -> ToolResult:
    from app.services.predictive.scenarios import Assumptions, ScenarioError, evaluate_scenario

    project = resolve_project(ctx, args["project"])
    assumptions = Assumptions(
        scope_change_percent=Decimal(args.get("scope_change_percent", 0)),
        extra_delay_days=args.get("extra_delay_days", 0),
        target_shift_days=args.get("target_shift_days", 0),
        added_hours_per_week=Decimal(args.get("added_hours_per_week", 0)),
    )
    if assumptions.is_empty():
        raise ToolInputError("Give at least one assumption (scope change, delay, target shift or added hours).")
    try:
        result = evaluate_scenario(ctx.db, project, assumptions, as_of=ctx.today, include_load=ctx.can_view_capacity)
    except ScenarioError as exc:
        raise ToolInputError(str(exc)) from exc
    return ToolResult(
        data={"label": result["label"], "project": result["project"]["label"], "assumptions": result["assumptions"],
              "comparison": result["comparison"], "model_versions": result["model_versions"]},
        record_count=len(result["comparison"]),
        sources=[Source(kind="forecast", ref=f"scenario:{project.id}", label=f"Hypothetical scenario for {project_label(project)}",
                        route=f"/predictive?project={project.id}&tab=scenarios")],
        tables=[Table(title="Hypothetical scenario vs baseline", columns=["Measure", "Baseline", "Scenario", "Difference"],
                      rows=[[r["measure"], r["baseline"], r["scenario"], r["difference"]] for r in result["comparison"]])],
        limitations=[result["label"], *result["warnings"]],
    )


_PROJECT_REF = {"type": "string", "maxLength": 80, "description": "Project code or tool number."}

SPECS = [
    ToolSpec(
        name="list_project_predictions",
        module="projects",
        description=(
            "Stored forecasts for open projects: predicted completion date (type=delivery), predicted final hours "
            "against the approved estimate (type=final_hours) or milestone finish dates (type=milestone). By default "
            "only forecasts past their baseline, largest first. Use for 'which projects will miss their date / exceed "
            "approved hours'. Never compute or adjust the numbers."
        ),
        parameters={
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": list(TYPE_KEYS)},
                "at_risk_only": {"type": "boolean"},
                "project": _PROJECT_REF,
                "limit": {"type": "integer", "minimum": 1, "maximum": 25},
            },
            "additionalProperties": False,
        },
        allowed=lambda ctx: True,
        handler=_project_predictions,
        denied_message="",
    ),
    ToolSpec(
        name="explain_project_prediction",
        module="projects",
        description=(
            "Why a project is forecast to finish late or overrun: the stored predictions for one project with their "
            "contributing factors, comparison group, range, data-quality warnings, or the reason no forecast exists."
        ),
        parameters={"type": "object", "properties": {"project": _PROJECT_REF}, "required": ["project"],
                    "additionalProperties": False},
        allowed=lambda ctx: True,
        handler=_explain,
        denied_message="",
    ),
    ToolSpec(
        name="get_resource_demand_forecast",
        module="resources",
        description=(
            "Stored forecast of project work against capacity per person, team or skill for the next 2, 4, 8 or 12 "
            "weeks, with shortages, overloaded weeks and single-person dependencies. Use for resource bottleneck questions."
        ),
        parameters={
            "type": "object",
            "properties": {
                "weeks": {"type": "integer", "enum": [2, 4, 8, 12]},
                "subject": {"type": "string", "enum": ["person", "team", "skill"]},
                "shortages_only": {"type": "boolean"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25},
            },
            "additionalProperties": False,
        },
        allowed=lambda ctx: ctx.can_view_capacity,
        handler=_resource_demand,
        denied_message="Resource demand forecasts require Resource Planning access.",
    ),
    ToolSpec(
        name="get_finance_timing_forecast",
        module="finance",
        description=(
            "Stored forecast of when billing (type=billing) or collections (type=collections) will happen, per currency "
            "and month, against the contractual baseline."
        ),
        parameters={"type": "object", "properties": {"type": {"type": "string", "enum": ["billing", "collections"]}},
                    "additionalProperties": False},
        allowed=lambda ctx: ctx.finance_visible,
        handler=_finance,
        denied_message="Financial forecasts require Finance access.",
    ),
    ToolSpec(
        name="get_historical_patterns",
        module="management",
        description=(
            "Statistically tested differences in completed work: effort and delivery slip by project type, complexity, "
            "team or customer (kind=project), or customer payment delay and invoicing lag (kind=payment). Only "
            "differences with enough cases and p<0.05 are reported as patterns."
        ),
        parameters={"type": "object", "properties": {"kind": {"type": "string", "enum": ["project", "payment"]}},
                    "additionalProperties": False},
        allowed=lambda ctx: ctx.can_view_reports and ctx.report_team_ids is None,
        handler=_patterns,
        denied_message="Portfolio patterns cover every team and require organisation-wide Reports access.",
    ),
    ToolSpec(
        name="get_prediction_accuracy",
        module="management",
        description=(
            "How accurate past predictions were against actual outcomes: number scored, mean absolute error, error by "
            "forecast horizon, comparison with the naive baseline and degradation status, per prediction type."
        ),
        parameters={"type": "object", "properties": {"type": {"type": "string", "enum": list(TYPE_KEYS)}},
                    "additionalProperties": False},
        allowed=lambda ctx: ctx.can_view_reports,
        handler=_accuracy,
        denied_message="Prediction accuracy requires Reports access.",
    ),
    ToolSpec(
        name="run_what_if_scenario",
        module="projects",
        description=(
            "Hypothetical what-if for one open project, compared with the baseline: scope change in percent, added "
            "delay in days (e.g. customer approval), moving the target date, or extra support hours per week. The "
            "result is hypothetical and is not saved or applied."
        ),
        parameters={
            "type": "object",
            "properties": {
                "project": _PROJECT_REF,
                "scope_change_percent": {"type": "integer", "minimum": -50, "maximum": 200},
                "extra_delay_days": {"type": "integer", "minimum": 0, "maximum": 365},
                "target_shift_days": {"type": "integer", "minimum": -365, "maximum": 365},
                "added_hours_per_week": {"type": "integer", "minimum": 0, "maximum": 80},
            },
            "required": ["project"],
            "additionalProperties": False,
        },
        allowed=lambda ctx: ctx.can_view_reports,
        handler=_scenario,
        denied_message="What-if scenarios require Reports access.",
    ),
]
