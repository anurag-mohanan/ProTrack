"""Report catalog — lean set of operational reports only."""

from __future__ import annotations

from app.schemas.reporting import ReportCatalog, ReportCatalogEntry

REPORT_CATALOG: list[ReportCatalogEntry] = [
    ReportCatalogEntry(
        id="weekly-engineering",
        title="Weekly Engineering Overview",
        description="Weekly engineering summary with hours, utilization, and top projects.",
        category="executive",
        supported_periods=["weekly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="monthly-engineering",
        title="Monthly Engineering Overview",
        description="Executive dashboard: designer productivity, tool hours, customers, teams, and NP/leave.",
        category="executive",
        supported_periods=["monthly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="quarterly-engineering",
        title="Quarterly Engineering Overview",
        description="Quarterly executive rollup with portfolio and customer analytics.",
        category="executive",
        supported_periods=["quarterly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="yearly-engineering",
        title="Yearly Engineering Overview",
        description="Annual engineering performance and capacity review.",
        category="executive",
        supported_periods=["yearly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="weekly-timesheet",
        title="Weekly Timesheet Report",
        description="Individual designer hours by team for the week, plus total project hours to date.",
        category="timesheets",
        supported_periods=["weekly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="monthly-timesheet",
        title="Monthly Timesheet Report",
        description="Individual designer hours by team for the month, plus total project hours to date.",
        category="timesheets",
        supported_periods=["monthly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="quarterly-timesheet",
        title="Quarterly Timesheet Report",
        description="Individual designer hours by team for the quarter, plus total project hours to date.",
        category="timesheets",
        supported_periods=["quarterly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="yearly-timesheet",
        title="Yearly Timesheet Report",
        description="Individual designer hours by team for the year, plus total project hours to date.",
        category="timesheets",
        supported_periods=["yearly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="customer-timesheet-pack",
        title="Customer Timesheet Pack",
        description=(
            "Customer-facing weekly/monthly timesheet with associate productive/NP hours, "
            "utilization, and tool rollup."
        ),
        category="customers",
        supported_periods=["weekly", "monthly"],
        export_formats=["xlsx", "json"],
    ),
]


def get_report_catalog() -> ReportCatalog:
    return ReportCatalog(reports=REPORT_CATALOG)


def get_report_definition(report_id: str) -> ReportCatalogEntry | None:
    for entry in REPORT_CATALOG:
        if entry.id == report_id:
            return entry
    return None
