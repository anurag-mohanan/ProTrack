"""Phase 0 read-only data-quality audit for a ProTrack SQLite database.

Opens the database with SQLite's ``mode=ro`` URI flag, so no statement can
write to it, and runs SELECT queries only. Point it at a disposable copy:

    python scripts/phase0_data_quality_audit.py path/to/copy.db

Output is counts plus record identifiers (project codes / tool numbers);
no personal or financial values are printed.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

LIVE = "p.is_deleted = 0 AND p.is_archived = 0 AND p.status NOT IN ('completed', 'cancelled')"

CHECKS: list[tuple[str, str]] = [
    # --- Inventory -------------------------------------------------------
    ("Row counts: business tables", """
        SELECT 'projects', COUNT(*) FROM projects UNION ALL
        SELECT 'milestones', COUNT(*) FROM milestones UNION ALL
        SELECT 'timesheets', COUNT(*) FROM timesheets UNION ALL
        SELECT 'timesheet_entries', COUNT(*) FROM timesheet_entries UNION ALL
        SELECT 'quotes', COUNT(*) FROM quotes UNION ALL
        SELECT 'quote_revisions', COUNT(*) FROM quote_revisions UNION ALL
        SELECT 'quote_invoice_lines', COUNT(*) FROM quote_invoice_lines UNION ALL
        SELECT 'quote_payment_lines', COUNT(*) FROM quote_payment_lines UNION ALL
        SELECT 'quote_payment_milestones', COUNT(*) FROM quote_payment_milestones UNION ALL
        SELECT 'project_stage_estimates', COUNT(*) FROM project_stage_estimates UNION ALL
        SELECT 'project_estimate_revisions', COUNT(*) FROM project_estimate_revisions UNION ALL
        SELECT 'project_baseline_revisions', COUNT(*) FROM project_baseline_revisions UNION ALL
        SELECT 'skills', COUNT(*) FROM skills UNION ALL
        SELECT 'user_skills', COUNT(*) FROM user_skills UNION ALL
        SELECT 'rp_shift_assignments', COUNT(*) FROM rp_shift_assignments UNION ALL
        SELECT 'customers', COUNT(*) FROM customers UNION ALL
        SELECT 'users', COUNT(*) FROM users
    """),
    ("Projects by status / classification / archived / deleted", """
        SELECT status, project_classification, is_archived, is_deleted, COUNT(*)
        FROM projects GROUP BY 1, 2, 3, 4 ORDER BY 1, 2
    """),
    # --- Projects --------------------------------------------------------
    ("Completed projects without completed_at", """
        SELECT code, tool_number FROM projects
        WHERE status = 'completed' AND completed_at IS NULL AND is_deleted = 0
    """),
    ("Completed projects with completed_at in the future", """
        SELECT code, tool_number, completed_at FROM projects
        WHERE status = 'completed' AND date(completed_at) > date('now')
    """),
    ("Non-completed projects that still carry completed_at", """
        SELECT code, tool_number, status FROM projects
        WHERE status <> 'completed' AND completed_at IS NOT NULL AND is_deleted = 0
    """),
    ("Live projects missing start_date", f"""
        SELECT COUNT(*) FROM projects p WHERE {LIVE} AND p.start_date IS NULL
    """),
    ("Live projects missing due_date", f"""
        SELECT COUNT(*) FROM projects p WHERE {LIVE} AND p.due_date IS NULL
    """),
    ("Live projects with zero/NULL quoted_hours", f"""
        SELECT COUNT(*) FROM projects p WHERE {LIVE} AND COALESCE(p.quoted_hours, 0) = 0
    """),
    ("Live projects missing team", f"""
        SELECT COUNT(*) FROM projects p WHERE {LIVE} AND p.team_id IS NULL
    """),
    ("Live projects missing baseline completion date", f"""
        SELECT COUNT(*) FROM projects p WHERE {LIVE} AND p.baseline_completion_date IS NULL
    """),
    ("Projects missing template", """
        SELECT COUNT(*) FROM projects WHERE is_deleted = 0 AND project_template_id IS NULL
    """),
    ("Projects still 'unclassified'", """
        SELECT code, tool_number FROM projects
        WHERE is_deleted = 0 AND project_classification = 'unclassified'
    """),
    ("Due date before start date", """
        SELECT code, tool_number FROM projects
        WHERE start_date IS NOT NULL AND due_date IS NOT NULL AND due_date < start_date
    """),
    ("Overdue live projects (due_date < today)", f"""
        SELECT COUNT(*) FROM projects p WHERE {LIVE} AND p.due_date < date('now')
    """),
    ("Stored health on completed/cancelled projects", """
        SELECT status, health, COUNT(*) FROM projects
        WHERE status IN ('completed', 'cancelled') GROUP BY 1, 2
    """),
    ("Duplicate tool numbers / codes (case and space insensitive)", """
        SELECT 'tool_number', lower(trim(tool_number)), COUNT(*) FROM projects
        GROUP BY 2 HAVING COUNT(*) > 1
        UNION ALL
        SELECT 'code', lower(trim(code)), COUNT(*) FROM projects
        WHERE code IS NOT NULL GROUP BY 2 HAVING COUNT(*) > 1
    """),
    ("Full-design projects without stage estimates", """
        SELECT COUNT(*) FROM projects p
        WHERE p.is_deleted = 0 AND p.project_classification = 'full_design'
          AND NOT EXISTS (SELECT 1 FROM project_stage_estimates e WHERE e.project_id = p.id)
    """),
    ("Cached projects.actual_hours vs live timesheet sum (mismatches)", """
        SELECT p.code, p.tool_number, p.actual_hours,
               COALESCE((SELECT SUM(te.hours) FROM timesheet_entries te
                         WHERE te.project_id = p.id AND te.is_deleted = 0), 0) AS live_sum
        FROM projects p
        WHERE ABS(COALESCE(p.actual_hours, 0) - COALESCE((SELECT SUM(te.hours)
              FROM timesheet_entries te WHERE te.project_id = p.id AND te.is_deleted = 0), 0)) > 0.001
    """),
    # --- Milestones ------------------------------------------------------
    ("Milestones by status", "SELECT status, COUNT(*) FROM milestones GROUP BY 1"),
    ("Milestones missing due_date (open)", """
        SELECT COUNT(*) FROM milestones
        WHERE due_date IS NULL AND status NOT IN ('completed', 'cancelled', 'not_applicable')
    """),
    ("Completed milestones missing completed_date", """
        SELECT COUNT(*) FROM milestones WHERE status = 'completed' AND completed_date IS NULL
    """),
    ("Completed milestones missing both completed_date and completed_at", """
        SELECT COUNT(*) FROM milestones
        WHERE status = 'completed' AND completed_date IS NULL AND completed_at IS NULL
    """),
    ("Milestones missing project_stage", "SELECT COUNT(*) FROM milestones WHERE project_stage IS NULL"),
    ("Milestones with no original_planned_hours", "SELECT COUNT(*) FROM milestones WHERE original_planned_hours IS NULL"),
    ("Open milestones past due on completed/cancelled projects", """
        SELECT p.status, COUNT(*) FROM milestones m JOIN projects p ON p.id = m.project_id
        WHERE p.status IN ('completed', 'cancelled')
          AND m.status NOT IN ('completed', 'cancelled', 'not_applicable')
          AND m.due_date < date('now')
        GROUP BY 1
    """),
    ("Milestones whose project is missing (orphans)", """
        SELECT COUNT(*) FROM milestones m
        WHERE NOT EXISTS (SELECT 1 FROM projects p WHERE p.id = m.project_id)
    """),
    ("Milestones completed after project marked completed / project completed with open required milestones", """
        SELECT p.code, COUNT(*) FROM projects p JOIN milestones m ON m.project_id = p.id
        WHERE p.status = 'completed' AND m.is_required = 1
          AND m.status NOT IN ('completed', 'cancelled', 'not_applicable')
        GROUP BY 1
    """),
    # --- Timesheets ------------------------------------------------------
    ("Timesheets by status", "SELECT status, COUNT(*) FROM timesheets GROUP BY 1"),
    ("Timesheet entries by sheet status / deleted / has project / has milestone", """
        SELECT t.status, te.is_deleted, te.project_id IS NOT NULL, te.milestone_id IS NOT NULL,
               COUNT(*), SUM(te.hours)
        FROM timesheet_entries te JOIN timesheets t ON t.id = te.timesheet_id
        GROUP BY 1, 2, 3, 4
    """),
    ("Orphan timesheet entries (missing sheet or project)", """
        SELECT
          (SELECT COUNT(*) FROM timesheet_entries te
            WHERE NOT EXISTS (SELECT 1 FROM timesheets t WHERE t.id = te.timesheet_id)),
          (SELECT COUNT(*) FROM timesheet_entries te
            WHERE te.project_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM projects p WHERE p.id = te.project_id))
    """),
    ("Productive entries without a project", """
        SELECT COUNT(*) FROM timesheet_entries
        WHERE work_category = 'productive' AND project_id IS NULL AND is_deleted = 0
    """),
    ("Timesheet import history", "SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM timesheet_import_history"),
    # --- Finance ---------------------------------------------------------
    ("Quotes without a project link", "SELECT COUNT(*) FROM quotes WHERE project_id IS NULL"),
    ("Projects with more than one active quote", """
        SELECT project_id, COUNT(*) FROM quotes
        WHERE project_id IS NOT NULL AND is_active = 1 GROUP BY 1 HAVING COUNT(*) > 1
    """),
    ("Customers missing default payment terms", """
        SELECT COUNT(*) FROM customers
        WHERE is_active = 1 AND default_payment_terms_days IS NULL AND default_payment_terms IS NULL
    """),
    ("Possible duplicate customers (normalised name)", """
        SELECT lower(replace(replace(replace(name, ' ', ''), '.', ''), ',', '')), COUNT(*)
        FROM customers WHERE is_active = 1 GROUP BY 1 HAVING COUNT(*) > 1
    """),
    # --- People ----------------------------------------------------------
    ("Users by user_type / active", "SELECT user_type, is_active, COUNT(*) FROM users GROUP BY 1, 2"),
    ("Users by role and user_type (shared/system roles still classed as employee?)", """
        SELECT r.name, u.user_type, COUNT(*) FROM users u JOIN roles r ON r.id = u.role_id
        GROUP BY 1, 2 ORDER BY 1
    """),
    ("Completed projects: due date vs completion date availability", """
        SELECT
          SUM(CASE WHEN due_date IS NULL THEN 1 ELSE 0 END) AS no_due,
          SUM(CASE WHEN completed_at IS NULL THEN 1 ELSE 0 END) AS no_completed_at,
          SUM(CASE WHEN due_date IS NOT NULL AND completed_at IS NOT NULL
                    AND date(completed_at) <= due_date THEN 1 ELSE 0 END) AS on_time_vs_due,
          SUM(CASE WHEN due_date IS NOT NULL AND completed_at IS NOT NULL
                    AND date(completed_at) > due_date THEN 1 ELSE 0 END) AS late_vs_due
        FROM projects WHERE status = 'completed' AND is_deleted = 0
    """),
    ("Active employees without any skill record", """
        SELECT COUNT(*) FROM users u
        WHERE u.is_active = 1 AND u.user_type = 'employee'
          AND NOT EXISTS (SELECT 1 FROM user_skills s WHERE s.user_id = u.id)
    """),
    ("Skills catalogue", "SELECT name FROM skills ORDER BY name"),
]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1]).resolve()
    if not path.exists():
        print(f"Database not found: {path}")
        return 2
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    for title, sql in CHECKS:
        print(f"\n## {title}")
        try:
            rows = conn.execute(sql).fetchall()
        except sqlite3.Error as exc:
            print(f"  QUERY ERROR: {exc}")
            continue
        if not rows:
            print("  (none)")
        for row in rows[:40]:
            print("  " + " | ".join("NULL" if value is None else str(value) for value in row))
        if len(rows) > 40:
            print(f"  ... {len(rows) - 40} more")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
