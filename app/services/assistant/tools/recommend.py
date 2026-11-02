"""The only write the model can request: record a recommendation (status New) for a person to decide."""

from __future__ import annotations

import json

from app.models.assistant import AIRecommendation, REC_NEW
from app.services.assistant.context import AssistantContext
from app.services.assistant.tools.common import clip, person_name, resolve_project
from app.services.assistant.types import ToolInputError, ToolResult, ToolSpec

MAX_PER_TURN = 3
CATEGORIES = ["schedule", "effort", "delivery", "resourcing", "skills", "billing", "receivables", "data_quality", "process"]
MODULE_FOR_CATEGORY = {
    "schedule": "projects", "effort": "projects", "delivery": "projects", "data_quality": "projects", "process": "management",
    "resourcing": "resources", "skills": "resources", "billing": "finance", "receivables": "finance",
}


def _record(ctx: AssistantContext, args: dict) -> ToolResult:
    if len(ctx.created_recommendation_ids) >= MAX_PER_TURN:
        raise ToolInputError(f"At most {MAX_PER_TURN} recommendations can be recorded per answer.")
    keys = args["evidence"]
    unknown = [k for k in keys if k not in ctx.seen_sources]
    if not keys or unknown:
        raise ToolInputError(
            "Every recommendation must cite source keys returned by tools in this answer; "
            f"not retrieved: {', '.join(unknown) or 'none given'}."
        )
    module = MODULE_FOR_CATEGORY[args["category"]]
    if module == "finance" and not ctx.finance_visible:
        raise ToolInputError("Finance recommendations require Finance access.")
    project = resolve_project(ctx, args["project"]) if args.get("project") else None
    notes = []
    owner_id = None
    if args.get("suggested_owner"):
        assigned = [u for u in (project.design_leader, project.designer, project.surfacer) if u is not None] if project else []
        needle = args["suggested_owner"].lower()
        match = [u for u in assigned if needle in (person_name(u) or "").lower()]
        if len(match) == 1:
            owner_id = match[0].id
        else:
            notes.append("Suggested owner was not recorded: an owner must be the project's design leader, designer or surfacer.")
    row = AIRecommendation(
        conversation_id=ctx.conversation_id,
        created_by_id=ctx.user.id,
        project_id=project.id if project else None,
        module=module,
        category=args["category"],
        title=clip(args["title"], 200),
        description=args["description"],
        evidence_json=json.dumps([ctx.seen_sources[k] for k in keys], default=str),
        suggested_action=args["suggested_action"],
        suggested_owner_id=owner_id,
        priority=args.get("priority", "medium"),
        status=REC_NEW,
    )
    ctx.db.add(row)
    ctx.db.flush()
    ctx.created_recommendation_ids.append(row.id)
    return ToolResult(
        data={"recorded": True, "recommendation_id": str(row.id), "status": REC_NEW,
              "note": "Recorded for review. Nothing has been changed in ProTrack."},
        record_count=1,
        limitations=notes,
    )


SPECS = [
    ToolSpec(
        name="record_recommendation",
        module="recommendations",
        description=(
            "Record a recommendation for the user to accept, reject or defer later. It changes nothing in ProTrack. "
            "Only use when the user asks for recommendations or actions, and cite the source keys (e.g. 'project:<id>', "
            "'finding:<id>') returned by tools in this answer as evidence."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": 200},
                "description": {"type": "string", "maxLength": 2000, "description": "Observation and why it matters."},
                "category": {"type": "string", "enum": CATEGORIES},
                "project": {"type": "string", "maxLength": 80},
                "evidence": {"type": "array", "items": {"type": "string", "maxLength": 120}, "maxItems": 10},
                "suggested_action": {"type": "string", "maxLength": 1000},
                "suggested_owner": {"type": "string", "maxLength": 80},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["title", "description", "category", "evidence", "suggested_action"],
            "additionalProperties": False,
        },
        allowed=lambda ctx: True,
        handler=_record,
        denied_message="",
        writes_recommendation=True,
    ),
]
