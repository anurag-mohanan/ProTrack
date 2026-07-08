"""Reporting engine orchestrator."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.schemas.reporting import EngineeringReportPayload, ReportCatalog
from app.services.reporting.data_service import build_engineering_report
from app.services.reporting.excel.generator import generate_engineering_excel
from app.services.reporting.registry import get_report_catalog, get_report_definition


class ReportingEngine:
    def catalog(self) -> ReportCatalog:
        return get_report_catalog()

    def build_report(
        self,
        db: Session,
        *,
        report_id: str,
        period_type: str = "monthly",
        anchor: date | None = None,
        include_archived: bool = True,
        include_deleted: bool = False,
        ai_insights: list[str] | None = None,
    ) -> EngineeringReportPayload:
        definition = get_report_definition(report_id)
        if definition is None:
            raise KeyError(f"Unknown report: {report_id}")

        resolved_period = period_type
        if report_id == "weekly-engineering":
            resolved_period = "weekly"
        elif report_id == "quarterly-engineering":
            resolved_period = "quarterly"
        elif report_id == "yearly-engineering":
            resolved_period = "yearly"
        elif report_id.endswith("-engineering") or report_id == "monthly-engineering":
            resolved_period = period_type or "monthly"

        if resolved_period not in definition.supported_periods and definition.supported_periods:
            resolved_period = definition.supported_periods[0]

        insights = ai_insights
        if insights is None and definition.category == "executive":
            from app.services.ai.modules.report_insights import generate_report_insights

            insights = generate_report_insights(
                db,
                period_type=resolved_period,
                anchor=anchor,
            )

        return build_engineering_report(
            db,
            period_type=resolved_period,
            anchor=anchor,
            include_archived=include_archived,
            include_deleted=include_deleted,
            report_id=report_id,
            ai_insights=insights,
        )

    def export_excel(self, payload: EngineeringReportPayload) -> bytes:
        return generate_engineering_excel(payload)


reporting_engine = ReportingEngine()
