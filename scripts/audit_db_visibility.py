"""Audit imported record visibility flags in the local database."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select, text

from app.db.session import SessionLocal
from app.models.enums import ExecutionStatus
from app.models.models import Customer, Project, Team, Timesheet, User


def main() -> None:
    db = SessionLocal()
    try:
        print("=== Table counts ===")
        for model in (Project, Customer, User, Team, Timesheet):
            count = db.scalar(select(func.count()).select_from(model))
            print(f"{model.__tablename__}: {count}")

        print("\n=== Projects by visibility ===")
        total = db.scalar(select(func.count()).select_from(Project)) or 0
        deleted = db.scalar(
            select(func.count()).select_from(Project).where(Project.is_deleted.is_(True))
        ) or 0
        archived = db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.is_deleted.is_(False), Project.is_archived.is_(True))
        ) or 0
        active_lifecycle = db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                Project.execution_status.in_(
                    (
                        ExecutionStatus.currently_being_worked_on,
                        ExecutionStatus.on_hold,
                    )
                ),
            )
        ) or 0
        completed_visible = db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(False),
                Project.execution_status == ExecutionStatus.completed,
            )
        ) or 0
        completed_archived = db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.is_deleted.is_(False),
                Project.is_archived.is_(True),
                Project.execution_status == ExecutionStatus.completed,
            )
        ) or 0
        imported_notes = db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.notes.like("%Imported from historical%"))
        ) or 0
        all_lifecycle = db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.is_deleted.is_(False))
        ) or 0

        print(f"total: {total}")
        print(f"deleted: {deleted}")
        print(f"archived (not deleted): {archived}")
        print(f"visible under lifecycle=all: {all_lifecycle}")
        print(f"visible under lifecycle=active: {active_lifecycle}")
        print(f"visible under lifecycle=completed: {completed_visible}")
        print(f"completed + archived (only in Archived tab): {completed_archived}")
        print(f"imported (notes marker): {imported_notes}")
        hidden_from_default = total - deleted - active_lifecycle
        print(f"hidden from Active tab (non-deleted): {hidden_from_default}")

        print("\n=== Customers ===")
        inactive = db.scalar(
            select(func.count()).select_from(Customer).where(Customer.is_active.is_(False))
        ) or 0
        print(f"inactive customers: {inactive}")

        print("\n=== Users ===")
        for label, clause in [
            ("active visible in lookups", (User.is_active.is_(True), User.is_archived.is_(False), User.is_deleted.is_(False))),
            ("archived", (User.is_archived.is_(True),)),
            ("deleted", (User.is_deleted.is_(True),)),
            ("inactive", (User.is_active.is_(False),)),
        ]:
            count = db.scalar(select(func.count()).select_from(User).where(*clause)) or 0
            print(f"{label}: {count}")

        print("\n=== Sample imported projects not in active lifecycle ===")
        rows = db.scalars(
            select(Project.tool_number, Project.execution_status, Project.is_archived)
            .where(Project.notes.like("%Imported from historical%"))
            .limit(5)
        ).all()
        for row in rows:
            print(row)
    finally:
        db.close()


if __name__ == "__main__":
    main()
