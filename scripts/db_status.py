"""Print active database connection and row counts."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, inspect, select, text

from app.db.session import DATABASE_URL, SessionLocal
from app.models.models import Customer, Project, Team, Timesheet, User


def resolve_db_path(url: str) -> str:
    if not url.startswith("sqlite"):
        return url
    raw = url.replace("sqlite:///", "")
    if raw == ":memory:":
        return ":memory:"
    if raw.startswith("./"):
        return str((Path.cwd() / raw[2:]).resolve())
    return str(Path(raw).resolve())


def main() -> None:
    db_path = resolve_db_path(DATABASE_URL)
    print("=== Connection ===")
    print("DATABASE_URL env:", os.getenv("DATABASE_URL") or "(not set — using default)")
    print("Effective connection string:", DATABASE_URL)
    print("Resolved database file:", db_path)
    path = Path(db_path) if db_path != ":memory:" else None
    if path and path.exists():
        print("File size (bytes):", path.stat().st_size)

    db = SessionLocal()
    try:
        print("\n=== Row counts ===")
        for label, model in [
            ("Projects", Project),
            ("Customers", Customer),
            ("Users", User),
            ("Teams", Team),
            ("Timesheets", Timesheet),
        ]:
            count = db.scalar(select(func.count()).select_from(model)) or 0
            print(f"{label}: {count}")

        print("\n=== Imported data ===")
        imported_projects = (
            db.scalar(
                select(func.count())
                .select_from(Project)
                .where(Project.notes.like("%Imported from historical%"))
            )
            or 0
        )
        total_projects = db.scalar(select(func.count()).select_from(Project)) or 0
        print(f"Projects with historical import note: {imported_projects} / {total_projects}")

        samples = db.scalars(
            select(Project.tool_number)
            .where(Project.notes.like("%Imported from historical%"))
            .limit(8)
        ).all()
        if samples:
            print("Sample imported tool numbers:", ", ".join(samples))
        else:
            print("No projects with import marker in notes")

        inspector = inspect(db.bind)
        tables = set(inspector.get_table_names())
        if "import_jobs" in tables:
            count = db.scalar(text("SELECT COUNT(*) FROM import_jobs")) or 0
            print(f"Historical project import jobs: {count}")
        if "timesheet_import_jobs" in tables:
            count = db.scalar(text("SELECT COUNT(*) FROM timesheet_import_jobs")) or 0
            print(f"Timesheet import jobs: {count}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
