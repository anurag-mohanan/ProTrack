"""AI insights for engineering management reports."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select

from app.core.non_productive_categories import standard_np_hours_clause
from app.models.models import Timesheet, TimesheetEntry
from app.services.ai.base import AiContext, AiModule
from app.services.ai.context import get_customer_workload_share, get_designer_utilization
from app.services.ai.risk_analysis import risk_analyzer
from app.services.reporting.periods import period_bounds


class ReportInsightsModule(AiModule):
    name = "report_insights"

    @staticmethod
    def _designer_name(row: dict) -> str:
        user = row.get("user")
        if user is not None:
            return f"{user.first_name} {user.last_name}".strip()
        return str(row.get("name") or "Designer")

    def run(self, ctx: AiContext, **kwargs: Any) -> list[str]:
        period_type = kwargs.get("period_type", "monthly")
        anchor = kwargs.get("anchor")
        anchor_date = date.fromisoformat(anchor) if isinstance(anchor, str) else anchor
        start, end = period_bounds(period_type, anchor=anchor_date)

        insights: list[str] = []

        customer_share = get_customer_workload_share(ctx)
        if customer_share:
            top = customer_share[0]
            insights.append(
                f"{top['customer_name']} consumed {top['share_percent']:.0f}% of engineering capacity this period."
            )

        over_budget = risk_analyzer.projects_over_quoted(ctx, threshold=1.0)
        for project in over_budget[:3]:
            quoted = float(project.quoted_hours or 0)
            actual = float(project.actual_hours or 0)
            if quoted > 0:
                pct = (actual / quoted - 1) * 100
                insights.append(
                    f"Project {project.tool_number} exceeded quoted hours by {pct:.0f}%."
                )

        designers = get_designer_utilization(ctx)
        if designers:
            top = max(designers, key=lambda row: row["utilization"])
            insights.append(
                f"{self._designer_name(top)} maintained a {top['utilization']:.0f}% utilization rate."
            )
            low = [row for row in designers if row["utilization"] < 60]
            if low:
                names = ", ".join(self._designer_name(row) for row in low[:2])
                insights.append(f"{names} have available capacity next week.")

        at_risk = risk_analyzer.projects_at_risk(ctx)
        if at_risk:
            insights.append(f"{len(at_risk)} project(s) are trending over budget or behind schedule.")

        designers_sorted = sorted(designers, key=lambda row: row["utilization"])
        if len(designers_sorted) >= 2:
            low = designers_sorted[0]
            high = designers_sorted[-1]
            if high["utilization"] - low["utilization"] >= 25:
                insights.append(
                    f"Consider rebalancing workload between {self._designer_name(high)} and {self._designer_name(low)}."
                )

        np_hours = float(
            ctx.db.scalar(
                select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
                    TimesheetEntry.is_deleted.is_(False),
                    TimesheetEntry.entry_date >= start,
                    TimesheetEntry.entry_date <= end,
                    standard_np_hours_clause(),
                )
            )
            or 0
        )
        total_hours = float(
            ctx.db.scalar(
                select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
                .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
                .where(
                    TimesheetEntry.is_deleted.is_(False),
                    TimesheetEntry.entry_date >= start,
                    TimesheetEntry.entry_date <= end,
                )
            )
            or 0
        )
        if total_hours > 0 and np_hours / total_hours > 0.2:
            insights.append(
                f"Non-productive hours represent {np_hours / total_hours * 100:.0f}% of logged time this period."
            )

        billable = float(
            ctx.db.scalar(
                select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
                .where(
                    TimesheetEntry.is_deleted.is_(False),
                    TimesheetEntry.entry_date >= start,
                    TimesheetEntry.entry_date <= end,
                    TimesheetEntry.is_billable.is_(True),
                )
            )
            or 0
        )
        if total_hours > 0:
            insights.append(
                f"Billable utilization for the period is {billable / total_hours * 100:.0f}%."
            )

        if not insights:
            insights.append("No significant anomalies detected for this reporting period.")

        try:
            from app.services.ai.providers import get_llm_provider

            provider = get_llm_provider()
            if provider.is_available():
                prompt = (
                    "Summarize the operational takeaway in one sentence given these insights:\n"
                    + "\n".join(f"- {line}" for line in insights[:6])
                )
                enriched = provider.enrich(
                    prompt,
                    context={"module": self.name, "period_type": str(period_type)},
                )
                if enriched:
                    insights = [*insights[:7], enriched]
        except Exception:
            pass

        return insights[:8]


def generate_report_insights(
    db,
    *,
    period_type: str = "monthly",
    anchor: date | None = None,
) -> list[str]:
    from app.services.ai.engine import ai_engine

    return ai_engine.run(
        "report_insights",
        db,
        period_type=period_type,
        anchor=anchor.isoformat() if anchor else None,
        use_cache=False,
    )
