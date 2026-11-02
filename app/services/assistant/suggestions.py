"""Suggested questions. Each is bound to one tool so it can be answered without a provider."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import exists, select

from app.models.finance import Quote
from app.models.foundation import Skill
from app.services.assistant.context import AssistantContext
from app.services.assistant.registry import tool_specs
from app.services.assistant.tools.common import visible_projects_stmt


@dataclass(frozen=True)
class Suggestion:
    id: str
    category: str
    text: str
    tool: str
    args: dict = field(default_factory=dict)
    needs: str = "projects"  # projects | quotes | skills


SUGGESTIONS: tuple[Suggestion, ...] = (
    Suggestion("due-soon", "Projects", "Which projects are due in the next 14 days?", "find_projects",
               {"due_within_days": 14, "sort_by": "due_date"}),
    Suggestion("overdue", "Projects", "Which open projects are overdue?", "find_projects",
               {"overdue_only": True, "sort_by": "days_overdue"}),
    Suggestion("over-estimate", "Projects", "Which projects have used more hours than their approved estimate?",
               "find_projects", {"over_estimate_only": True, "sort_by": "hours_over_estimate"}),
    Suggestion("top-risks", "Projects", "What are the most severe open risks?", "list_risk_findings", {}),
    Suggestion("capacity", "Resources", "Who has capacity over the next four weeks?", "get_capacity_overview", {"periods": 4}),
    Suggestion("skill-gaps", "Resources", "Which critical skills have coverage gaps?", "get_skill_gaps",
               {"critical_only": True}, needs="skills"),
    Suggestion("to-invoice", "Finance", "Which quotes still have work to invoice or payments outstanding?",
               "list_billing_status", {"status": "open"}, needs="quotes"),
    Suggestion("overdue-invoices", "Finance", "Which invoices are overdue?", "get_receivables_aging",
               {"overdue_only": True}, needs="quotes"),
    Suggestion("fy-billing", "Finance", "How is billing tracking this financial year?", "get_fy_billing", {}, needs="quotes"),
    Suggestion("collection-forecast", "Finance", "What collections are forecast for the next six months?",
               "get_finance_forecast", {"periods": 6}, needs="quotes"),
    Suggestion("delivery-quarter", "Management", "How did delivery performance look this quarter?",
               "get_delivery_performance", {"period_type": "quarterly"}),
    Suggestion("control-tower", "Management", "Summarise the Control Tower findings.", "get_control_tower_summary", {}),
    Suggestion("remaining-effort", "Management", "Which open projects have the most remaining effort?",
               "get_effort_forecast", {}),
)


def _has_data(ctx: AssistantContext, needs: str, cache: dict[str, bool]) -> bool:
    if needs not in cache:
        if needs == "quotes":
            cache[needs] = bool(ctx.db.scalar(select(exists().where(Quote.is_active.is_(True)))))
        elif needs == "skills":
            cache[needs] = bool(ctx.db.scalar(select(exists().where(Skill.is_active.is_(True)))))
        else:
            cache[needs] = ctx.db.scalars(visible_projects_stmt(ctx).limit(1)).first() is not None
    return cache[needs]


def available_suggestions(ctx: AssistantContext) -> list[Suggestion]:
    specs = tool_specs()
    cache: dict[str, bool] = {}
    return [s for s in SUGGESTIONS if specs[s.tool].allowed(ctx) and _has_data(ctx, s.needs, cache)]


def find_suggestion(suggestion_id: str | None) -> Suggestion | None:
    return next((s for s in SUGGESTIONS if s.id == suggestion_id), None)
