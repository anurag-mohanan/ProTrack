"""Excel export for the Engineering Performance report.

Every sheet is written from the same ``EngineeringPerformanceReport`` payload the
screen renders, so totals reconcile with the UI.
"""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference

from app.schemas.engineering_performance import EngineeringPerformanceReport
from app.services.reporting.excel.letterhead import write_report_letterhead
from app.services.reporting.excel.styles import (
    BODY_BOLD_FONT,
    HOURS_FORMAT_2,
    KPI_FILL,
    KPI_LABEL_FONT,
    KPI_VALUE_FONT,
    NOTES_FONT,
    SECTION_FONT,
    autofit_columns,
    freeze_and_filter,
    style_body_rows,
    style_header_row,
)

_REFERENCE_LABELS = {"baseline": "Baseline", "legacy_due_date": "Legacy due date", "none": "None"}
_PLAN_SOURCE_LABELS = {
    "stage_estimates": "Stage estimates",
    "milestone_hours": "Milestone hours",
    "quoted_hours": "Quoted hours",
    "none": "Not planned",
}


def _table(sheet, start_row: int, headers: list[str], rows: list[list[object]], hour_cols: set[int]) -> int:
    for col, header in enumerate(headers, start=1):
        sheet.cell(row=start_row, column=col, value=header)
    style_header_row(sheet, start_row, len(headers))
    for offset, values in enumerate(rows, start=1):
        for col, value in enumerate(values, start=1):
            cell = sheet.cell(row=start_row + offset, column=col, value=value)
            if col in hour_cols and isinstance(value, (int, float)):
                cell.number_format = HOURS_FORMAT_2
    if rows:
        style_body_rows(sheet, start_row + 1, start_row + len(rows), len(headers))
    return start_row + len(rows) + 1


def _summary_sheet(workbook: Workbook, report: EngineeringPerformanceReport, company_name: str) -> None:
    sheet = workbook.active
    sheet.title = "Summary"
    filters = [f"{key.replace('_', ' ').title()}: {value}" for key, value in report.filters.items() if value]
    row = write_report_letterhead(
        sheet,
        company_name=company_name,
        report_title="Engineering Performance Report",
        period_label=f"{report.period.label} ({report.period.start_date:%d %b %Y} – {report.period.end_date:%d %b %Y})",
        extra_lines=filters or ["All projects in scope"],
        col_span=8,
    )
    summary = report.summary
    if report.empty_message:
        sheet.cell(row=row, column=1, value=report.empty_message).font = BODY_BOLD_FONT
        row += 2
    basis = "current approved estimate" if summary.plan_basis == "current" else "original estimate"
    kpis = [
        ("Projects completed", summary.projects_completed),
        (f"Planned hours ({basis})", summary.planned_hours),
        ("Actual hours", summary.actual_hours),
        ("EAC hours", summary.eac_hours),
        ("Variance hours", summary.variance_hours),
        ("Variance %", summary.variance_percent),
        ("On-time rate %", summary.on_time_rate),
        ("On time / late", f"{summary.on_time_projects} / {summary.late_projects}"),
        ("Average days late", summary.average_days_late),
        ("Milestones completed", f"{summary.milestones_completed} of {summary.milestones_total}"),
        ("Milestone on-time rate %", summary.milestone_on_time_rate),
        ("Projects without a plan", summary.projects_without_plan),
    ]
    for index, (label, value) in enumerate(kpis):
        r = row + (index // 4) * 3
        c = 1 + (index % 4) * 2
        label_cell = sheet.cell(row=r, column=c, value=label)
        value_cell = sheet.cell(row=r + 1, column=c, value="—" if value is None else value)
        label_cell.font = KPI_LABEL_FONT
        value_cell.font = KPI_VALUE_FONT
        label_cell.fill = KPI_FILL
        value_cell.fill = KPI_FILL
    row += ((len(kpis) + 3) // 4) * 3 + 1

    if report.warnings:
        sheet.cell(row=row, column=1, value="Data quality").font = SECTION_FONT
        row += 1
        for warning in report.warnings:
            sheet.cell(row=row, column=1, value=warning.message).font = NOTES_FONT
            row += 1
            if warning.project_codes:
                sheet.cell(row=row, column=1, value=", ".join(warning.project_codes)).font = NOTES_FONT
                row += 1
    autofit_columns(sheet, max_width=36)


def _stage_sheet(workbook: Workbook, report: EngineeringPerformanceReport) -> None:
    sheet = workbook.create_sheet("Stage Performance")
    stage = report.stage_performance
    sheet.cell(
        row=1,
        column=1,
        value=(
            f"{stage.projects_with_stage_plan} project(s) with stage estimates; "
            f"{stage.projects_without_stage_plan} without (excluded from stage rows)."
        ),
    ).font = NOTES_FONT
    headers = ["Stage", "Projects", "Original hours", "Current hours", "Actual hours", "Variance hours", "Variance %"]
    rows = [
        [r.label, r.projects, r.original_hours, r.current_hours, r.actual_hours, r.variance_hours, r.variance_percent]
        for r in stage.rows
    ]
    end = _table(sheet, 3, headers, rows, {3, 4, 5, 6})
    sheet.cell(
        row=end + 1,
        column=1,
        value=f"Hours on milestones outside the three stages: {stage.unstaged_actual_hours}",
    ).font = NOTES_FONT
    if rows:
        chart = BarChart()
        chart.title = "Stage hours: current plan vs actual"
        chart.y_axis.title = "Hours"
        data = Reference(sheet, min_col=4, max_col=5, min_row=3, max_row=3 + len(rows))
        cats = Reference(sheet, min_col=1, min_row=4, max_row=3 + len(rows))
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        chart.height = 8
        chart.width = 16
        sheet.add_chart(chart, f"A{end + 3}")
    autofit_columns(sheet)


def _breakdown_sheet(workbook: Workbook, report: EngineeringPerformanceReport) -> None:
    sheet = workbook.create_sheet("Breakdowns")
    row = 1
    headers = ["Group", "Projects", "Planned hours", "Actual hours", "Variance hours", "Variance %", "On time", "On-time rate %"]
    for breakdown in report.breakdowns:
        sheet.cell(row=row, column=1, value=f"By {breakdown.label}").font = SECTION_FONT
        rows = [
            [r.label, r.projects, r.planned_hours, r.actual_hours, r.variance_hours,
             r.variance_percent, r.on_time_projects, r.on_time_rate]
            for r in breakdown.rows
        ]
        row = _table(sheet, row + 1, headers, rows, {3, 4, 5}) + 1
    autofit_columns(sheet)


def _projects_sheet(workbook: Workbook, report: EngineeringPerformanceReport) -> None:
    sheet = workbook.create_sheet("Project Details")
    headers = [
        "Code", "Tool #", "Part", "Customer", "End customer", "Team", "Design leader / PM",
        "Designer", "Surfacer", "Project type", "Template", "Start date", "Actual start",
        "Actual completion", "Reference completion", "Reference source", "On time", "Days late",
        "Original planned h", "Current planned h", "Planned h (report basis)", "Plan source",
        "Actual h", "Variance h", "Variance %", "Stage planned", "Milestones completed",
        "Milestones on time",
    ]
    rows = [
        [
            p.code, p.tool_number, p.part_description, p.customer_name, p.end_customer_name,
            p.team_name, p.design_leader_name, p.designer_name, p.surfacer_name,
            p.project_type_name, p.template_name, p.start_date, p.actual_start_date,
            p.actual_completion_date, p.reference_completion_date,
            _REFERENCE_LABELS.get(p.reference_source, p.reference_source),
            "—" if p.on_time is None else ("Yes" if p.on_time else "No"),
            p.days_late, p.original_planned_hours, p.current_planned_hours, p.planned_hours,
            _PLAN_SOURCE_LABELS.get(p.plan_source, p.plan_source), p.actual_hours,
            p.variance_hours, p.variance_percent, "Yes" if p.stage_planned else "No",
            f"{p.milestones_completed}/{p.milestones_total}", p.milestones_on_time,
        ]
        for p in report.projects
    ]
    end = _table(sheet, 1, headers, rows, {19, 20, 21, 23, 24})
    if rows:
        total_row = end
        sheet.cell(row=total_row, column=1, value="Total").font = BODY_BOLD_FONT
        sheet.cell(row=total_row, column=21, value=report.summary.planned_hours).font = BODY_BOLD_FONT
        sheet.cell(row=total_row, column=23, value=report.summary.actual_hours).font = BODY_BOLD_FONT
        sheet.cell(row=total_row, column=24, value=report.summary.variance_hours).font = BODY_BOLD_FONT
    else:
        sheet.cell(row=3, column=1, value=report.empty_message or "").font = BODY_BOLD_FONT
    freeze_and_filter(sheet, 1, len(headers), end_row=max(end - 1, 1))
    autofit_columns(sheet, max_width=30)


def _definitions_sheet(workbook: Workbook, report: EngineeringPerformanceReport) -> None:
    sheet = workbook.create_sheet("Definitions")
    rows = [[d.label, d.definition] for d in report.definitions]
    _table(sheet, 1, ["KPI", "Definition"], rows, set())
    sheet.column_dimensions["A"].width = 28
    sheet.column_dimensions["B"].width = 110


def generate_engineering_performance_excel(
    report: EngineeringPerformanceReport, *, company_name: str
) -> bytes:
    workbook = Workbook()
    workbook.properties.title = "Engineering Performance Report"
    workbook.properties.subject = report.period.label
    _summary_sheet(workbook, report, company_name)
    _stage_sheet(workbook, report)
    _breakdown_sheet(workbook, report)
    _projects_sheet(workbook, report)
    _definitions_sheet(workbook, report)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
