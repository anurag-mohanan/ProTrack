"""Excel export for the Quote-to-Delivery report.

Written from the same ``QuoteToDeliveryReport`` payload the screen renders. The
Projects sheet holds every row matching the filters, search and segment (the
export is never limited to the on-screen page).
"""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from app.schemas.quote_to_delivery import QuoteToDeliveryReport
from app.services.delivery_variance_service import REFERENCE_LABELS
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

EXCEL_MAX_DATA_ROWS = 1_048_575

_DATA_QUALITY_LABELS = {
    "available": "Complete",
    "available_with_limitations": "Limited",
    "unavailable": "Unavailable",
}
_DELIVERY_STATUS_LABELS = {
    "early": "Early",
    "on_time": "On time",
    "late": "Late",
    "overdue": "Overdue",
    "not_due": "Not due",
    "no_target": "No target date",
    "completion_date_missing": "Completion date missing",
    "not_applicable": "Not applicable",
}


def _num(value):
    return float(value) if value is not None else None


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


def _scope_lines(report: QuoteToDeliveryReport) -> list[str]:
    page = report.projects
    lines = [f"Population: {report.population.label} — {report.population.date_basis}"]
    if report.population.key == "completed":
        lines.append(f"Period applies to: {report.period.applies_to}")
    else:
        lines.append(f"As of {report.population.as_of:%d %b %Y}")
    lines += [f"{key.replace('_', ' ').title()}: {value}" for key, value in report.filters.items() if value]
    if page.search:
        lines.append(f"Search: {page.search}")
    if page.segment:
        lines.append(f"Drill-down: {page.segment.replace('_', ' ')}" + (f" ({page.stage})" if page.stage else ""))
    lines.append(
        f"Export scope: all {page.total} project row(s) matching the filters above — not limited "
        "to the on-screen page. Summary, stage and delivery figures cover the whole population."
    )
    return lines


def _summary_sheet(workbook: Workbook, report: QuoteToDeliveryReport, company_name: str) -> None:
    sheet = workbook.active
    sheet.title = "Summary"
    period = (
        f"{report.period.label} ({report.period.start_date:%d %b %Y} – {report.period.end_date:%d %b %Y})"
        if report.population.key == "completed"
        else f"Open projects as of {report.population.as_of:%d %b %Y}"
    )
    row = write_report_letterhead(
        sheet,
        company_name=company_name,
        report_title="Quote-to-Delivery Report",
        period_label=period,
        extra_lines=_scope_lines(report),
        col_span=8,
    )
    if report.empty_message:
        sheet.cell(row=row, column=1, value=report.empty_message).font = BODY_BOLD_FONT
        row += 2
    s = report.summary
    kpis = [
        ("Eligible projects", s.eligible_projects),
        (f"Original quoted hours (h) — {s.projects_with_quoted_hours} project(s)", _num(s.quoted_hours_total)),
        (
            f"Current approved estimate (h) — {s.projects_with_current_estimate} project(s)",
            _num(s.current_estimate_total),
        ),
        (f"Actual hours (h) — {s.projects_with_actual_hours} project(s)", _num(s.actual_hours_total)),
        ("Comparable projects", s.comparable_projects),
        ("Aggregate variance (h, comparable)", _num(s.variance_hours)),
        ("Utilization % (Σ actual ÷ Σ estimate)", _num(s.utilization_percent)),
        ("Over / under / on estimate", f"{s.projects_over_estimate} / {s.projects_under_estimate} / {s.projects_on_estimate}"),
        ("Not comparable", s.projects_not_comparable),
        ("Metrics unavailable", s.projects_metrics_unavailable),
        ("Metrics limited", s.projects_metrics_limited),
        ("Actual hours missing", s.projects_actual_missing),
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
    if s.estimate_source_counts:
        sheet.cell(row=row, column=1, value="Estimate source").font = SECTION_FONT
        row += 1
        for source, count in sorted(s.estimate_source_counts.items()):
            sheet.cell(row=row, column=1, value=source.replace("_", " "))
            sheet.cell(row=row, column=2, value=count)
            row += 1
        row += 1
    if report.warnings:
        sheet.cell(row=row, column=1, value="Data quality").font = SECTION_FONT
        row += 1
        for warning in report.warnings:
            sheet.cell(row=row, column=1, value=warning.message).font = NOTES_FONT
            row += 1
            if warning.project_codes:
                sheet.cell(row=row, column=1, value=", ".join(warning.project_codes)).font = NOTES_FONT
                row += 1
    autofit_columns(sheet, max_width=40)


def _projects_sheet(workbook: Workbook, report: QuoteToDeliveryReport) -> None:
    sheet = workbook.create_sheet("Projects")
    headers = [
        "Code", "Tool #", "Part", "Customer", "Classification", "Project type", "Status",
        "Design leader / PM", "Designer", "Quoted (h)", "Current estimate (h)", "Estimate source",
        "Actual (h)", "Actual status", "Variance (h)", "Utilization (%)", "In totals",
        "Original baseline completion", "Current baseline completion", "Current target",
        "Delivery reference", "Actual completion", "Delivery variance (days)", "Delivery status",
        "Days overdue", "Overdue milestones", "Stage attribution", "Data quality",
        "Data-quality issues",
    ]
    rows = [
        [
            p.code, p.tool_number, p.part_description, p.customer_name, p.classification_label,
            p.project_type_name, p.execution_status.replace("_", " "), p.design_leader_name,
            p.designer_name, _num(p.quoted_hours), _num(p.current_estimate_hours),
            p.estimate_source_label, _num(p.actual_hours), p.actual_status.replace("_", " "),
            _num(p.variance_hours), _num(p.utilization_percent), "Yes" if p.comparable else "No",
            p.original_baseline_completion_date, p.current_baseline_completion_date,
            p.current_target_date,
            REFERENCE_LABELS.get(p.delivery_reference_source, p.delivery_reference_source),
            p.actual_completion_date, p.delivery_variance_days,
            _DELIVERY_STATUS_LABELS.get(p.delivery_status, p.delivery_status), p.days_overdue,
            p.open_overdue_milestones, p.stage_attribution_status.replace("_", " "),
            _DATA_QUALITY_LABELS[p.data_quality_status], ", ".join(p.data_quality_issues),
        ]
        for p in report.projects.items
    ]
    if len(rows) > EXCEL_MAX_DATA_ROWS:
        raise ValueError(
            f"{len(rows)} rows exceed the Excel sheet limit; narrow the filters instead of truncating."
        )
    end = _table(sheet, 1, headers, rows, {10, 11, 13, 15})
    if not rows:
        sheet.cell(row=3, column=1, value=report.empty_message or "No projects match.").font = BODY_BOLD_FONT
    sheet.cell(
        row=end + 1,
        column=1,
        value=f"{len(rows)} row(s). Blank means unavailable, not zero.",
    ).font = NOTES_FONT
    freeze_and_filter(sheet, 1, len(headers), end_row=max(end - 1, 1))
    autofit_columns(sheet, max_width=30)


def _stage_sheet(workbook: Workbook, report: QuoteToDeliveryReport) -> None:
    sheet = workbook.create_sheet("Stages")
    headers = [
        "Stage", "Projects in plan", "Eligible projects", "Approved estimate (h)", "Actual (h)",
        "Variance (h)", "Utilization (%)", "Over stage estimate", "Missing attribution",
        "No stage estimate", "Explanation",
    ]
    rows = [
        [
            r.label, r.projects_in_plan, r.eligible_projects, _num(r.estimate_hours),
            _num(r.actual_hours), _num(r.variance_hours), _num(r.utilization_percent),
            r.projects_over_estimate, r.projects_missing_attribution, r.projects_without_estimate,
            r.explanation or "",
        ]
        for r in report.stages.rows
    ]
    end = _table(sheet, 1, headers, rows, {4, 5, 6})
    sheet.cell(row=end + 1, column=1, value=report.stages.eligibility_rule).font = NOTES_FONT
    sheet.cell(row=end + 2, column=1, value=report.stages.source).font = NOTES_FONT
    autofit_columns(sheet, max_width=40)


def _delivery_sheet(workbook: Workbook, report: QuoteToDeliveryReport) -> None:
    sheet = workbook.create_sheet("Delivery")
    h = report.delivery.historical
    o = report.delivery.operational
    sheet.cell(row=1, column=1, value="Historical delivery (completed in period)").font = SECTION_FONT
    sheet.cell(row=2, column=1, value=h.population_rule).font = NOTES_FONT
    historical = [
        ["Completed projects in period", h.completed_projects],
        ["Eligible (original baseline)", h.eligible_projects],
        ["On or before baseline", h.on_or_before_baseline],
        ["After baseline", h.after_baseline],
        ["Average variance (days)", h.average_variance_days],
        ["Median variance (days)", h.median_variance_days],
        ["Excluded: baseline without revision history", h.excluded_baseline_unverified],
        ["Excluded: due date only", h.excluded_due_date_only],
        ["Excluded: no reference date", h.excluded_no_reference],
        ["Completed without completion date (any period)", h.completed_without_completion_date],
    ]
    end = _table(sheet, 3, ["Measure", "Value"], historical, set())
    start = end + 2
    sheet.cell(row=start, column=1, value=f"Current overdue work (as of {o.as_of:%d %b %Y})").font = SECTION_FONT
    sheet.cell(row=start + 1, column=1, value=o.population_rule).font = NOTES_FONT
    operational = [
        ["Open projects", o.active_projects],
        ["Projects with overdue milestones", o.projects_with_overdue_milestones],
        ["Overdue milestones", o.overdue_milestones],
        ["Projects past current target", o.projects_past_current_target],
        ["Projects without a current target", o.projects_without_current_target],
        ["Projects without an original baseline", o.projects_without_original_baseline],
    ]
    end = _table(sheet, start + 2, ["Measure", "Value"], operational, set())
    sheet.cell(row=end + 1, column=1, value=report.delivery.sign_convention).font = NOTES_FONT
    sheet.column_dimensions["A"].width = 52
    sheet.column_dimensions["B"].width = 14


def _definitions_sheet(workbook: Workbook, report: QuoteToDeliveryReport) -> None:
    sheet = workbook.create_sheet("Definitions")
    rows = [[d.label, d.definition] for d in report.definitions]
    _table(sheet, 1, ["KPI", "Definition"], rows, set())
    sheet.column_dimensions["A"].width = 30
    sheet.column_dimensions["B"].width = 110


def generate_quote_to_delivery_excel(report: QuoteToDeliveryReport, *, company_name: str) -> bytes:
    workbook = Workbook()
    workbook.properties.title = "Quote-to-Delivery Report"
    workbook.properties.subject = report.period.label
    _summary_sheet(workbook, report, company_name)
    _projects_sheet(workbook, report)
    _stage_sheet(workbook, report)
    _delivery_sheet(workbook, report)
    _definitions_sheet(workbook, report)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
