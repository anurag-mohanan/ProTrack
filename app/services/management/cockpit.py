"""Management Cockpit: one filtered view over the existing Finance, delivery, workforce and customer services."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.services.management.access import ManagementAccess
from app.services.management.business import build_business
from app.services.management.customers import build_customer_table
from app.services.management.filters import CockpitFilters
from app.services.management.metrics import definitions
from app.services.management.operations import build_operations, qtd_reports
from app.services.management.workforce import build_workforce

TOP_CUSTOMERS = 15


def visible_definitions(access: ManagementAccess) -> list[dict]:
    return [d for d in definitions() if access.finance or not d["finance"]]


def build_cockpit(db: Session, access: ManagementAccess, filters: CockpitFilters, today: date | None = None) -> dict:
    today = today or date.today()
    reports = qtd_reports(db, access, filters, today)
    customers = build_customer_table(db, access, filters, today, reports=reports)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": today.isoformat(),
        "filters": filters.as_dict(),
        "can": access.flags(),
        "business": build_business(db, access, filters, today),
        "operations": build_operations(db, access, filters, today, reports=reports),
        "workforce": build_workforce(db, access, filters, today),
        "customers": {**customers, "rows": customers["rows"][:TOP_CUSTOMERS], "total": len(customers["rows"])},
        "definitions": visible_definitions(access),
        "principle": "Actuals, approved plans, forecasts and targets are labelled separately and never combined.",
    }
