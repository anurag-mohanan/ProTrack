"""Read-only reconciliation of engineering metrics against source records.

Usage: python scripts/engineering_metrics_reconciliation.py path/to/copy-of-protrack.db

Opens the SQLite file in read-only mode and, for every non-deleted project, compares:
* metrics actual hours vs a raw SUM of non-deleted timesheet entries;
* metrics actual hours vs the project page rule (calculate_hours);
* stage buckets vs actual total;
* stage rows + unattributed hours vs the raw sum;
* that no completed project is reported overdue;
* the cached projects.actual_hours column vs the live sum;
* the bulk metrics loader vs the per-project builder (identical payloads);
* Quote-to-Delivery report totals vs raw population counts and per-project sums.
Prints project codes and numbers only.
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.enums import ExecutionStatus  # noqa: E402
from app.models.models import Project, TimesheetEntry  # noqa: E402
from app.services.engineering_metrics_service import (  # noqa: E402
    build_engineering_metrics_batch,
    build_project_engineering_metrics,
    stage_hour_buckets,
)
from app.services.project_calculation_service import calculate_hours  # noqa: E402
from app.services.reporting.engineering_performance import (
    PerformanceFilters,  # noqa: E402
)
from app.services.reporting.quote_to_delivery import (  # noqa: E402
    OPEN_STATUSES,
    QtdFilters,
    QtdTableOptions,
    build_quote_to_delivery,
)


def main(path: str) -> int:
    db_path = Path(path).resolve()
    if not db_path.exists():
        print(f"not found: {db_path}")
        return 2
    engine = create_engine(f"sqlite:///file:{db_path.as_posix()}?mode=ro&uri=true")
    mismatches = 0
    quality = Counter()
    sources = Counter()
    issue_codes = Counter()
    stage_status = Counter()
    delivery_status = Counter()
    delivery_reference = Counter()
    milestone_delivery = Counter()
    rebaselined = 0
    with Session(engine) as db:
        projects = db.scalars(select(Project).where(Project.is_deleted.is_(False))).all()
        for project in projects:
            metrics = build_project_engineering_metrics(db, project, finance_details_visible=False)
            raw = Decimal(
                str(
                    db.scalar(
                        select(func.coalesce(func.sum(TimesheetEntry.hours), 0)).where(
                            TimesheetEntry.project_id == project.id,
                            TimesheetEntry.is_deleted.is_(False),
                        )
                    )
                    or 0
                )
            )
            page = calculate_hours(db, project).actual
            buckets = stage_hour_buckets(db, [project.id])[project.id]
            metric_actual = metrics.actual.total_hours
            stage = metrics.stage_attribution
            stage_rows_total = sum(
                (row.actual_hours for row in stage.rows if row.actual_hours is not None), Decimal("0")
            )
            delivery = metrics.delivery.project
            checks = {
                "raw_sum": metric_actual is None or metric_actual == raw,
                "project_page": metric_actual is None or metric_actual == page,
                "stage_buckets": buckets.total == raw,
                "cached_column": Decimal(str(project.actual_hours or 0)) == raw,
                "stage_rows_reconcile": stage.status not in {"complete", "partial"}
                or stage_rows_total + stage.unattributed_hours == raw,
                "completed_not_overdue": not (
                    project.execution_status is not None
                    and project.execution_status.value == "completed"
                    and delivery.status == "overdue"
                ),
            }
            stage_status[stage.status] += 1
            delivery_status[delivery.status] += 1
            delivery_reference[delivery.reference_source] += 1
            milestone_delivery.update(row.status for row in metrics.delivery.milestones)
            if delivery.baseline_revision_count > 1:
                rebaselined += 1
            failed = [name for name, ok in checks.items() if not ok]
            if failed:
                mismatches += 1
                print(
                    f"MISMATCH {project.code or project.tool_number}: {failed} "
                    f"metric={metric_actual} raw={raw} page={page} "
                    f"cached={project.actual_hours} buckets={buckets.total}"
                )
            quality[metrics.data_quality_status] += 1
            sources[metrics.estimate.estimate_source] += 1
            issue_codes.update(issue.code for issue in metrics.issues)
        print(f"projects checked: {len(projects)}")
        print(f"projects with mismatches: {mismatches}")
        print(f"data quality status: {dict(quality)}")
        print(f"estimate source: {dict(sources)}")
        print(f"issue codes: {dict(sorted(issue_codes.items()))}")
        print(f"stage attribution status: {dict(stage_status)}")
        print(f"project delivery status: {dict(delivery_status)}")
        print(f"project delivery reference: {dict(delivery_reference)}")
        print(f"milestone delivery status: {dict(milestone_delivery)}")
        print(f"projects re-baselined (more than one baseline revision): {rebaselined}")
        mismatches += _reconcile_batch(db, projects)
        mismatches += _reconcile_quote_to_delivery(db)
    return 1 if mismatches else 0


def _comparable_dump(metrics) -> dict:
    return metrics.model_dump(exclude={"calculated_at"})


def _reconcile_batch(db: Session, projects: list[Project]) -> int:
    """The report's bulk loader must give exactly the project page's result."""
    batch = build_engineering_metrics_batch(db, list(projects), finance_details_visible=False)
    differing = [
        project.code or project.tool_number
        for project in projects
        if _comparable_dump(batch[project.id])
        != _comparable_dump(build_project_engineering_metrics(db, project, finance_details_visible=False))
    ]
    print(f"batch metrics identical to per-project metrics: {len(projects) - len(differing)}/{len(projects)}")
    for code in differing:
        print(f"MISMATCH batch {code}")
    return len(differing)


def _reconcile_quote_to_delivery(db: Session) -> int:
    """Report totals vs raw population counts and per-project metric sums."""
    today = date.today()
    start = today.replace(year=today.year - 5) + timedelta(days=1)  # longest custom period allowed
    problems = 0
    for population in ("completed", "active"):
        filters = QtdFilters(
            base=PerformanceFilters(period_type="custom", start_date=start, end_date=today),
            population=population,
        )
        report = build_quote_to_delivery(db, filters, QtdTableOptions(page_size=None), today=today)
        if population == "completed":
            raw_count = db.scalar(
                select(func.count(Project.id)).where(
                    Project.execution_status == ExecutionStatus.completed,
                    Project.completed_at >= datetime.combine(start, datetime.min.time()),
                    Project.completed_at < datetime.combine(today + timedelta(days=1), datetime.min.time()),
                    Project.is_deleted.is_(False),
                )
            )
        else:
            raw_count = db.scalar(
                select(func.count(Project.id)).where(
                    Project.execution_status.in_(OPEN_STATUSES), Project.is_deleted.is_(False)
                )
            )
        rows = report.projects.items
        row_actual = sum((row.actual_hours for row in rows if row.actual_hours is not None), Decimal("0"))
        comparable = [row for row in rows if row.comparable]
        checks = {
            "population_count": report.summary.eligible_projects == raw_count,
            "table_rows": report.projects.total == len(rows) == raw_count,
            "actual_total": report.summary.actual_hours_total == row_actual,
            "comparable_count": report.summary.comparable_projects == len(comparable),
            "over_under": report.summary.projects_over_estimate
            + report.summary.projects_under_estimate
            + report.summary.projects_on_estimate
            == len(comparable),
        }
        failed = [name for name, ok in checks.items() if not ok]
        problems += len(failed)
        summary = report.summary
        print(
            f"quote-to-delivery {population}: projects={summary.eligible_projects} raw={raw_count} "
            f"quoted={summary.quoted_hours_total} estimate={summary.current_estimate_total} "
            f"actual={summary.actual_hours_total} comparable={summary.comparable_projects} "
            f"variance={summary.variance_hours} utilization={summary.utilization_percent} "
            f"unavailable={summary.projects_metrics_unavailable} limited={summary.projects_metrics_limited} "
            f"stage_rows={[(r.key, r.eligible_projects) for r in report.stages.rows]}"
            + (f" FAILED {failed}" if failed else "")
        )
    hist = report.delivery.historical
    oper = report.delivery.operational
    print(
        f"historical delivery: completed={hist.completed_projects} eligible={hist.eligible_projects} "
        f"unverified={hist.excluded_baseline_unverified} due_only={hist.excluded_due_date_only} "
        f"none={hist.excluded_no_reference} undated={hist.completed_without_completion_date}"
    )
    print(
        f"operational delivery: open={oper.active_projects} overdue_milestone_projects="
        f"{oper.projects_with_overdue_milestones} past_target={oper.projects_past_current_target} "
        f"no_target={oper.projects_without_current_target}"
    )
    return problems


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
