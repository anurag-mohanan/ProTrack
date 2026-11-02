"""Resource tools: Phase 3 capacity, Phase 4 matching and gaps. Recommendations only; nothing is assigned."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.foundation import Skill
from app.services.assistant.context import AssistantContext
from app.services.assistant.tools.common import num
from app.services.assistant.types import Source, Table, ToolInputError, ToolResult, ToolSpec
from app.services.forecasting.capacity import build_capacity_forecast
from app.services.skills import gaps, matching
from app.services.skills.errors import SkillError

RESOURCE_NOTES = [
    "Capacity uses each person's shifts, company holidays, employment dates, availability status and allocation "
    "percentage. It does not assume 8 hours a day. Planned leave is not recorded in ProTrack, so availability is indicative.",
    "Remaining work is the approved remaining estimate on open projects. It is not phased by week, so load per week is not known.",
]


def _capacity(ctx: AssistantContext, args: dict) -> ToolResult:
    granularity = args.get("granularity", "week")
    forecast = build_capacity_forecast(
        ctx.db, start=ctx.today, granularity=granularity, periods=args.get("periods", 4),
        team_ids=ctx.capacity_team_ids, project_visibility_clause=ctx.visibility_clause, as_of=ctx.today,
    )
    demand = {d.user_id: d for d in forecast.demand.by_designer}
    people = []
    for person in forecast.people:
        d = demand.get(person.user_id)
        people.append({
            "name": person.name, "team": person.team_name, "hours_source": person.hours_source,
            "availability_status": person.availability_status, "max_allocation_percent": person.max_allocation_percent,
            "scheduled_hours": num(person.total.scheduled_hours), "holiday_hours": num(person.total.holiday_hours),
            "allocatable_hours": num(person.total.allocatable_hours),
            "approved_remaining_hours_as_designer": num(d.approved_remaining_hours) if d else 0.0,
            "open_projects_as_designer": d.projects if d else 0,
        })
    if args.get("name"):
        needle = args["name"].lower()
        people = [p for p in people if needle in (p["name"] or "").lower()]
    people.sort(key=lambda p: (p["allocatable_hours"] or 0) - (p["approved_remaining_hours_as_designer"] or 0), reverse=True)
    meta = forecast.metadata
    limitations = [*RESOURCE_NOTES, *meta.limitations]
    if forecast.demand.projects_without_approved_estimate:
        limitations.append(f"{forecast.demand.projects_without_approved_estimate} open project(s) have no approved estimate; their load is unknown.")
    return ToolResult(
        data={"horizon_start": meta.period_start, "horizon_end": meta.period_end, "granularity": granularity,
              "status": meta.status, "assumptions": meta.assumptions, "people": people,
              "demand_note": forecast.demand.phasing_reason},
        record_count=len(people),
        sources=[Source(kind="forecast", ref="capacity", label=f"Capacity forecast {meta.period_start} – {meta.period_end}",
                        route="/resource-planning")],
        tables=[Table(title=f"Capacity {meta.period_start} – {meta.period_end}",
                      columns=["Person", "Team", "Hours source", "Allocatable (h)", "Approved remaining as designer (h)", "Open projects"],
                      rows=[[p["name"], p["team"], p["hours_source"], p["allocatable_hours"],
                             p["approved_remaining_hours_as_designer"], p["open_projects_as_designer"]] for p in people[:25]])] if people else [],
        limitations=limitations,
    )


def _skill_ids(ctx: AssistantContext, names: list[str]) -> list[Skill]:
    found = []
    for name in names:
        exact = ctx.db.scalars(select(Skill).where(Skill.is_active.is_(True), func.lower(Skill.name) == name.lower())).all()
        rows = exact or ctx.db.scalars(
            select(Skill).where(Skill.is_active.is_(True), Skill.name.ilike(f"%{name}%")).limit(6)
        ).all()
        if not rows:
            raise ToolInputError(f"No active skill called '{name}' exists in the skills taxonomy.")
        if len(rows) > 1:
            raise ToolInputError(f"'{name}' matches several skills: {', '.join(s.name for s in rows)}. Use the exact name.")
        found.append(rows[0])
    return found


def _candidates(ctx: AssistantContext, args: dict) -> ToolResult:
    skills = _skill_ids(ctx, args["skills"])
    level = args.get("min_level", 3)
    try:
        result = matching.recommend_candidates(
            ctx.db,
            requirements=[matching.RequirementSpec(skill_id=s.id, min_level=level) for s in skills],
            team_ids=ctx.capacity_team_ids, start=ctx.today, periods=args.get("periods", 4), today=ctx.today,
        )
    except SkillError as exc:
        raise ToolInputError(str(exc)) from exc
    candidates = result["candidates"][: args.get("limit", 10)]
    rows = [{
        "name": c["name"], "team": c["team_name"], "suitability": c["suitability_label"],
        "availability": c["availability_label"], "availability_reason": c["availability_reason"],
        "allocatable_hours": num(c["allocatable_hours"]), "approved_remaining_hours": num(c["approved_remaining_hours"]),
        "open_assignments": c["open_assignments"], "skill_evidence": c["explanation"],
    } for c in candidates]
    return ToolResult(
        data={"requirements": [{"skill": s.name, "min_level": level} for s in skills],
              "horizon_start": result["horizon_start"], "horizon_end": result["horizon_end"],
              "summary": result["summary"], "candidates": rows},
        record_count=len(result["candidates"]),
        sources=[Source(kind="skill", ref=str(s.id), label=s.name, route="/skills") for s in skills],
        tables=[Table(title="Candidates", columns=["Person", "Suitability", "Availability", "Allocatable (h)", "Approved remaining (h)"],
                      rows=[[r["name"], r["suitability"], r["availability"], r["allocatable_hours"], r["approved_remaining_hours"]] for r in rows])] if rows else [],
        limitations=[
            "Suitability uses verified skill records only. Self-declared levels are shown as claims and never treated as verified; "
            "past assignments are not used to infer skills.",
            *RESOURCE_NOTES,
            "This is a recommendation. Nobody is assigned until a manager changes the project assignment.",
        ],
    )


def _skill_gaps(ctx: AssistantContext, args: dict) -> ToolResult:
    report = gaps.build_gap_report(ctx.db, ctx.skill_access, category=args.get("category"),
                                   critical_only=bool(args.get("critical_only")), today=ctx.today)
    rows = [{k: r[k] for k in ("skill_name", "category", "is_critical", "verified_count", "verified_specialists",
                               "claimed_unverified", "reassessment_due", "no_record", "population", "flags")}
            for r in report["skills"]][:40]
    findings = [{"severity": f["severity"], "skill": f["skill_name"], "explanation": f["explanation"]} for f in report["findings"]][:20]
    return ToolResult(
        data={"as_of": report["as_of"], "population": report["population"], "skills": rows, "findings": findings,
              "rules": report["rules"]},
        record_count=len(report["skills"]),
        sources=[Source(kind="report", ref="skill-gaps", label="Skills gap analysis", route="/skills")],
        tables=[Table(title="Skill coverage (verified only)",
                      columns=["Skill", "Critical", "Verified", "Verified specialists", "Unverified claims", "No record"],
                      rows=[[r["skill_name"], r["is_critical"], r["verified_count"], r["verified_specialists"],
                             r["claimed_unverified"], r["no_record"]] for r in rows])] if rows else [],
        limitations=report["rules"][:3],
    )


SPECS = [
    ToolSpec(
        name="get_capacity_overview",
        module="resources",
        description=(
            "Allocatable hours per person for the coming weeks or months (from shifts, holidays and availability) "
            "next to their approved remaining work as designer. Use for 'who has capacity' and workload questions."
        ),
        parameters={
            "type": "object",
            "properties": {
                "granularity": {"type": "string", "enum": ["week", "month"]},
                "periods": {"type": "integer", "minimum": 1, "maximum": 12},
                "name": {"type": "string", "maxLength": 80, "description": "Optional person name filter."},
            },
            "additionalProperties": False,
        },
        allowed=lambda ctx: ctx.can_view_capacity,
        handler=_capacity,
        denied_message="Capacity and workload require Resource Planning access.",
    ),
    ToolSpec(
        name="find_resource_candidates",
        module="resources",
        description=(
            "Rank people for work needing given skills, using verified skill levels and capacity. "
            "Returns suitability, availability and the evidence for each person."
        ),
        parameters={
            "type": "object",
            "properties": {
                "skills": {"type": "array", "items": {"type": "string", "maxLength": 100}, "maxItems": 5,
                           "description": "Skill names from the skills taxonomy."},
                "min_level": {"type": "integer", "minimum": 1, "maximum": 5},
                "periods": {"type": "integer", "minimum": 1, "maximum": 12},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["skills"],
            "additionalProperties": False,
        },
        allowed=lambda ctx: ctx.skill_access.can_match_resources,
        handler=_candidates,
        denied_message="Candidate recommendations require Resource Planning access.",
    ),
    ToolSpec(
        name="get_skill_gaps",
        module="resources",
        description="Verified skill coverage, single-specialist dependencies and critical-skill gaps for the people in the user's scope.",
        parameters={
            "type": "object",
            "properties": {
                "category": {"type": "string", "maxLength": 100},
                "critical_only": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        allowed=lambda ctx: ctx.skill_access.can_view_others,
        handler=_skill_gaps,
        denied_message="Skills gap analysis is available to managers, reviewers, HR and resource planners.",
    ),
]
