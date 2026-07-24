"""Phase 62 — employee training courses + assignments; seed common courses."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


COMMON_COURSES = [
    {
        "code": "ORIENTATION",
        "title": "Company orientation & code of conduct",
        "description": "Welcome, values, workplace policies, and expected conduct.",
        "owner_department": "HR",
        "estimated_minutes": 30,
        "sort_order": 10,
    },
    {
        "code": "IT_SECURITY",
        "title": "IT security & data handling",
        "description": "Passwords, phishing awareness, and handling customer/project data.",
        "owner_department": "IT",
        "estimated_minutes": 20,
        "sort_order": 20,
    },
    {
        "code": "PROTRACK_BASICS",
        "title": "ProTrack basics: timesheets & projects",
        "description": "Logging time, reading project status, and using milestones.",
        "owner_department": "Engineering",
        "estimated_minutes": 45,
        "sort_order": 30,
    },
    {
        "code": "LEAVE_PAYSLIPS",
        "title": "Leave & payslips (GreytHR / HRIS)",
        "description": "How to apply leave and access payslips in the HRIS.",
        "owner_department": "HR",
        "estimated_minutes": 20,
        "sort_order": 40,
    },
    {
        "code": "HEALTH_SAFETY",
        "title": "Workplace health & safety overview",
        "description": "Office safety basics, emergency contacts, and reporting incidents.",
        "owner_department": "Admin",
        "estimated_minutes": 15,
        "sort_order": 50,
    },
]


def _ensure_pg_enum_value(engine: Engine, enum_name: str, value: str) -> None:
    with engine.begin() as connection:
        exists = connection.execute(
            text(
                """
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = :enum_name AND e.enumlabel = :value
                """
            ),
            {"enum_name": enum_name, "value": value},
        ).scalar()
        if exists:
            return
        connection.execute(text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"))


def _create_tables(engine: Engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as connection:
        if dialect == "sqlite":
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS training_courses (
                        id CHAR(36) NOT NULL PRIMARY KEY,
                        code VARCHAR(40) NOT NULL UNIQUE,
                        title VARCHAR(200) NOT NULL,
                        description TEXT,
                        owner_department VARCHAR(80),
                        estimated_minutes INTEGER NOT NULL DEFAULT 30,
                        external_url VARCHAR(500),
                        is_required_for_onboarding BOOLEAN NOT NULL DEFAULT 0,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS training_assignments (
                        id CHAR(36) NOT NULL PRIMARY KEY,
                        course_id CHAR(36) NOT NULL,
                        user_id CHAR(36) NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'assigned',
                        due_date DATE,
                        assigned_by_id CHAR(36),
                        completed_at DATETIME,
                        completed_by_id CHAR(36),
                        notes TEXT,
                        onboarding_checklist_id CHAR(36),
                        created_at DATETIME,
                        updated_at DATETIME,
                        FOREIGN KEY(course_id) REFERENCES training_courses(id),
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_training_assignments_user_id "
                    "ON training_assignments (user_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_training_assignments_course_id "
                    "ON training_assignments (course_id)"
                )
            )
        else:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS training_courses (
                        id UUID PRIMARY KEY,
                        code VARCHAR(40) NOT NULL UNIQUE,
                        title VARCHAR(200) NOT NULL,
                        description TEXT,
                        owner_department VARCHAR(80),
                        estimated_minutes INTEGER NOT NULL DEFAULT 30,
                        external_url VARCHAR(500),
                        is_required_for_onboarding BOOLEAN NOT NULL DEFAULT FALSE,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS training_assignments (
                        id UUID PRIMARY KEY,
                        course_id UUID NOT NULL REFERENCES training_courses(id),
                        user_id UUID NOT NULL REFERENCES users(id),
                        status VARCHAR(32) NOT NULL DEFAULT 'assigned',
                        due_date DATE,
                        assigned_by_id UUID,
                        completed_at TIMESTAMP,
                        completed_by_id UUID,
                        notes TEXT,
                        onboarding_checklist_id UUID,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_training_assignments_user_id "
                    "ON training_assignments (user_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_training_assignments_course_id "
                    "ON training_assignments (course_id)"
                )
            )


def seed_common_training_courses(db: Session) -> int:
    from app.models.training import TrainingCourse
    from sqlalchemy import select

    created = 0
    now = datetime.now(timezone.utc)
    for row in COMMON_COURSES:
        existing = db.scalar(
            select(TrainingCourse).where(TrainingCourse.code == row["code"])
        )
        if existing is not None:
            continue
        db.add(
            TrainingCourse(
                id=uuid.uuid4(),
                code=row["code"],
                title=row["title"],
                description=row["description"],
                owner_department=row["owner_department"],
                estimated_minutes=row["estimated_minutes"],
                is_required_for_onboarding=True,
                is_active=True,
                sort_order=row["sort_order"],
                created_at=now,
                updated_at=now,
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def ensure_phase62_employee_training_foundation(engine: Engine) -> None:
    _create_tables(engine)
    if engine.dialect.name == "postgresql":
        _ensure_pg_enum_value(engine, "notification_type", "training_assigned")
        _ensure_pg_enum_value(engine, "entity_type", "training_course")
        _ensure_pg_enum_value(engine, "entity_type", "training_assignment")
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        seed_common_training_courses(session)
    finally:
        session.close()
