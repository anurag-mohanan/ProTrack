"""Report catalog — single registry for all engineering reports."""

from __future__ import annotations

from app.schemas.reporting import ReportCatalog, ReportCatalogEntry

REPORT_CATALOG: list[ReportCatalogEntry] = [
    ReportCatalogEntry(
        id="monthly-engineering",
        title="Monthly Engineering Report",
        description="Executive dashboard, designer productivity, tool hours, customers, teams, NP/leave, and AI insights.",
        category="executive",
        supported_periods=["monthly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="weekly-engineering",
        title="Weekly Engineering Report",
        description="Condensed weekly engineering summary with hours, utilization, and top projects.",
        category="executive",
        supported_periods=["weekly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="quarterly-engineering",
        title="Quarterly Engineering Report",
        description="Quarterly executive rollup with portfolio and customer analytics.",
        category="executive",
        supported_periods=["quarterly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="yearly-engineering",
        title="Yearly Engineering Report",
        description="Annual engineering performance and capacity review.",
        category="executive",
        supported_periods=["yearly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="designer-productivity",
        title="Designer Productivity",
        description="Per-designer hours, billable %, utilization, projects, and customers.",
        category="productivity",
        supported_periods=["daily", "weekly", "monthly", "quarterly", "yearly"],
        export_formats=["xlsx", "json"],
        drill_down_routes={"designer": "/dashboard?user={user_id}"},
    ),
    ReportCatalogEntry(
        id="team-productivity",
        title="Team Productivity",
        description="Team-level hours, utilization, and project counts.",
        category="productivity",
        supported_periods=["weekly", "monthly", "quarterly", "yearly"],
        export_formats=["xlsx", "json"],
        drill_down_routes={"team": "/admin/teams"},
    ),
    ReportCatalogEntry(
        id="customer-productivity",
        title="Customer Productivity",
        description="Customer hours distribution and average hours per project.",
        category="productivity",
        supported_periods=["monthly", "quarterly", "yearly"],
        export_formats=["xlsx", "json"],
        drill_down_routes={"customer": "/admin/customers"},
    ),
    ReportCatalogEntry(
        id="tool-hours",
        title="Tool Hours",
        description="Quoted vs actual hours per project with completion and health.",
        category="projects",
        supported_periods=["monthly", "quarterly", "yearly"],
        export_formats=["xlsx", "json"],
        drill_down_routes={"project": "/projects/{project_id}"},
    ),
    ReportCatalogEntry(
        id="project-performance",
        title="Project Performance",
        description="Milestone completion, health, and predicted finish by project.",
        category="projects",
        supported_periods=["monthly", "quarterly", "yearly"],
        export_formats=["xlsx", "json"],
        drill_down_routes={"project": "/projects/{project_id}"},
    ),
    ReportCatalogEntry(
        id="quoted-vs-actual",
        title="Quoted vs Actual",
        description="Variance analysis with late milestone counts.",
        category="projects",
        supported_periods=["monthly", "quarterly", "yearly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="designer-summary",
        title="Designer Timesheet Summary",
        description="Designer-level timesheet rollup for the selected period.",
        category="timesheets",
        supported_periods=["daily", "weekly", "monthly", "quarterly", "yearly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="detailed-entries",
        title="Detailed Timesheet Entries",
        description="Full entry-level export compatible with legacy Prosohm reports.",
        category="timesheets",
        supported_periods=["daily", "weekly", "monthly", "quarterly", "yearly"],
        export_formats=["xlsx", "json", "csv"],
    ),
    ReportCatalogEntry(
        id="non-productive-analysis",
        title="Non-Productive Analysis",
        description="NP code breakdown with hours and percentages.",
        category="timesheets",
        supported_periods=["monthly", "quarterly", "yearly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="leave-analysis",
        title="Leave Analysis",
        description="Leave days and hours by designer for resource planning.",
        category="timesheets",
        supported_periods=["monthly", "quarterly", "yearly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="customer-hours",
        title="Customer Hours",
        description="Customer engineering hours and designer involvement.",
        category="customers",
        supported_periods=["monthly", "quarterly", "yearly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="customer-utilization",
        title="Customer Utilization",
        description="Share of engineering capacity consumed by each customer.",
        category="customers",
        supported_periods=["monthly", "quarterly", "yearly"],
        export_formats=["xlsx", "json"],
    ),
    ReportCatalogEntry(
        id="customer-timesheet-pack",
        title="Customer Timesheet Pack",
        description=(
            "Customer-facing weekly/monthly timesheet (Prosohm-style) with associate "
            "productive/NP hours, utilization, and tool rollup for subscription / fixed resources."
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
