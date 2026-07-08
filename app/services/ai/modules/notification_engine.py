"""Smart notification engine — actionable alerts only."""

from __future__ import annotations

from typing import Any

from app.models.enums import NotificationType
from app.schemas.ai import AiInsight
from app.services.ai.base import AiContext, AiModule
from app.services.ai.modules.dashboard_insights import DashboardInsightsModule
from app.services.notification_service import create_notification
from app.services.timesheet_compliance_service import get_missing_timesheet_rows


class NotificationEngineModule(AiModule):
    name = "notification_engine"

    def run(self, ctx: AiContext, **kwargs: Any) -> list[AiInsight]:
        dry_run = bool(kwargs.get("dry_run", True))
        manager_id = kwargs.get("manager_id")
        insights_module = DashboardInsightsModule()
        insights = insights_module.run(ctx, limit=15)

        actionable = [i for i in insights if i.severity in ("error", "warning")]

        if not dry_run and manager_id:
            for insight in actionable[:5]:
                create_notification(
                    ctx.db,
                    user_id=manager_id,
                    notification_type=NotificationType.project_due_soon,
                    title=insight.title,
                    message=insight.detail or insight.title,
                )

            missing = get_missing_timesheet_rows(ctx.db, limit=10)
            for row in missing:
                create_notification(
                    ctx.db,
                    user_id=row.user_id,
                    notification_type=NotificationType.timesheet_submitted,
                    title="Timesheet reminder",
                    message=f"Missing timesheet for {row.missing_days} working days.",
                )

        return actionable
