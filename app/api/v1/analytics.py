"""Reports & Analytics hub catalog — ACL-gated deep links."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth_deps import get_current_user
from app.api.deps import get_db
from app.core.access_control import (
    MODULE_FINANCIAL_PLANNING,
    MODULE_HUMAN_RESOURCES,
    MODULE_REPORTS,
    MODULE_REPORTS_ANALYTICS,
)
from app.core.module_actions import MODULE_ACTION_VIEW, user_has_module_action
from app.core.permissions import get_role_name
from app.models.models import User

router = APIRouter(prefix="/analytics", tags=["reports-analytics"])


@router.get("/catalog")
def analytics_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role_name = get_role_name(db, current_user)
    catalog = []

    if user_has_module_action(
        current_user, role_name, MODULE_REPORTS_ANALYTICS, MODULE_ACTION_VIEW
    ) or user_has_module_action(current_user, role_name, MODULE_REPORTS, MODULE_ACTION_VIEW):
        catalog.append(
            {
                "category": "Engineering Reports",
                "module": MODULE_REPORTS,
                "items": [
                    {"title": "Engineering Reports Suite", "path": "/reports"},
                    {"title": "Productivity Reports", "path": "/reports"},
                    {"title": "Resource Reports", "path": "/reports"},
                    {"title": "Timesheet Reports", "path": "/reports"},
                    {"title": "Customer Reports", "path": "/reports"},
                    {
                        "title": "Customer Timesheet Pack",
                        "path": "/reports?tab=customer-timesheet-pack",
                    },
                ],
            }
        )

    if user_has_module_action(
        current_user, role_name, MODULE_FINANCIAL_PLANNING, MODULE_ACTION_VIEW
    ):
        catalog.append(
            {
                "category": "Financial Reports",
                "module": MODULE_FINANCIAL_PLANNING,
                "items": [
                    {"title": "Profit & Loss", "path": "/finance/reports"},
                    {"title": "Project Profitability", "path": "/finance/reports"},
                    {"title": "Budget vs Actual", "path": "/finance/budgets"},
                    {"title": "Revenue Trend", "path": "/finance"},
                    {"title": "AI Insights (placeholders)", "path": "/finance"},
                ],
            }
        )

    if user_has_module_action(
        current_user, role_name, MODULE_HUMAN_RESOURCES, MODULE_ACTION_VIEW
    ):
        catalog.append(
            {
                "category": "HR Reports",
                "module": MODULE_HUMAN_RESOURCES,
                "items": [
                    {"title": "Team Productivity", "path": "/hr"},
                    {"title": "Timesheet Completion", "path": "/hr"},
                    {"title": "Leave (future)", "path": "/hr"},
                    {"title": "Attendance (future)", "path": "/hr"},
                ],
            }
        )

    return {"categories": catalog}
