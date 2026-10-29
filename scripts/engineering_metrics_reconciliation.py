"""Read-only reconciliation of engineering metrics against source records.

Usage: python scripts/engineering_metrics_reconciliation.py path/to/copy-of-protrack.db

Opens the SQLite file in read-only mode and, for every non-deleted project, compares:
* metrics actual hours vs a raw SUM of non-deleted timesheet entries;
* metrics actual hours vs the project page rule (calculate_hours);
* stage buckets vs actual total;
* the cached projects.actual_hours column vs the live sum.
Prints project codes and numbers only.
"""

from __future__ import annotations

import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.models import Project, TimesheetEntry  # noqa: E402
from app.services.engineering_metrics_service import (  # noqa: E402
    build_project_engineering_metrics,
    stage_hour_buckets,
)
from app.services.project_calculation_service import calculate_hours  # noqa: E402


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
            checks = {
                "raw_sum": metric_actual is None or metric_actual == raw,
                "project_page": metric_actual is None or metric_actual == page,
                "stage_buckets": buckets.total == raw,
                "cached_column": Decimal(str(project.actual_hours or 0)) == raw,
            }
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
    return 1 if mismatches else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
