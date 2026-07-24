"""Employee training catalog, assignments, onboarding gate, notifications."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ProTrackValidationError
from app.models.enums import EntityType, NotificationType
from app.models.models import OnboardingChecklist, User
from app.models.training import TrainingAssignment, TrainingCourse
from app.services.notification_service import create_notification

REQUIRED_TRAINING_SLA_DAYS = 14


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def list_courses(
    db: Session,
    *,
    active_only: bool = True,
    required_only: bool = False,
) -> list[TrainingCourse]:
    stmt = select(TrainingCourse).order_by(TrainingCourse.sort_order, TrainingCourse.title)
    if active_only:
        stmt = stmt.where(TrainingCourse.is_active.is_(True))
    if required_only:
        stmt = stmt.where(TrainingCourse.is_required_for_onboarding.is_(True))
    return list(db.scalars(stmt).all())


def create_course(
    db: Session,
    *,
    code: str,
    title: str,
    description: str | None = None,
    owner_department: str | None = None,
    estimated_minutes: int = 30,
    external_url: str | None = None,
    is_required_for_onboarding: bool = False,
    sort_order: int = 100,
) -> TrainingCourse:
    code_norm = code.strip().upper().replace(" ", "_")
    if not code_norm:
        raise ProTrackValidationError("Course code is required.")
    existing = db.scalar(select(TrainingCourse).where(TrainingCourse.code == code_norm))
    if existing is not None:
        raise ProTrackValidationError(f"Course code '{code_norm}' already exists.")
    course = TrainingCourse(
        id=uuid4(),
        code=code_norm,
        title=title.strip(),
        description=(description or "").strip() or None,
        owner_department=(owner_department or "").strip() or None,
        estimated_minutes=max(1, int(estimated_minutes)),
        external_url=(external_url or "").strip() or None,
        is_required_for_onboarding=bool(is_required_for_onboarding),
        is_active=True,
        sort_order=sort_order,
    )
    db.add(course)
    db.flush()
    return course


def _existing_open_assignment(
    db: Session, *, user_id: UUID, course_id: UUID
) -> TrainingAssignment | None:
    return db.scalar(
        select(TrainingAssignment).where(
            TrainingAssignment.user_id == user_id,
            TrainingAssignment.course_id == course_id,
            TrainingAssignment.status.in_(("assigned", "in_progress")),
        )
    )


def assign_course(
    db: Session,
    *,
    course: TrainingCourse,
    user: User,
    assigned_by: User | None,
    due_date: date | None = None,
    onboarding_checklist_id: UUID | None = None,
    notes: str | None = None,
    notify: bool = True,
) -> TrainingAssignment:
    existing = _existing_open_assignment(db, user_id=user.id, course_id=course.id)
    if existing is not None:
        return existing
    done = db.scalar(
        select(TrainingAssignment).where(
            TrainingAssignment.user_id == user.id,
            TrainingAssignment.course_id == course.id,
            TrainingAssignment.status == "completed",
        )
    )
    if done is not None and course.is_required_for_onboarding:
        return done

    assignment = TrainingAssignment(
        id=uuid4(),
        course_id=course.id,
        user_id=user.id,
        status="assigned",
        due_date=due_date,
        assigned_by_id=assigned_by.id if assigned_by else None,
        notes=(notes or "").strip() or None,
        onboarding_checklist_id=onboarding_checklist_id,
    )
    db.add(assignment)
    db.flush()

    if notify:
        due_label = f" Due {due_date.isoformat()}." if due_date else ""
        create_notification(
            db,
            user_id=user.id,
            notification_type=NotificationType.training_assigned,
            title=f"Training assigned: {course.title}"[:200],
            message=(
                f"Please complete “{course.title}” "
                f"({course.estimated_minutes} min).{due_label} "
                f"Open HR → Training when you have availability."
            ),
            entity_type=EntityType.training_assignment,
            entity_id=assignment.id,
            send_email=False,
            commit=False,
        )
    return assignment


def assign_required_onboarding_trainings(
    db: Session,
    *,
    user: User,
    checklist: OnboardingChecklist,
    assigned_by: User | None,
) -> list[TrainingAssignment]:
    courses = list_courses(db, active_only=True, required_only=True)
    due = (checklist.joining_date or date.today()) + timedelta(days=REQUIRED_TRAINING_SLA_DAYS)
    created: list[TrainingAssignment] = []
    for course in courses:
        row = assign_course(
            db,
            course=course,
            user=user,
            assigned_by=assigned_by,
            due_date=due,
            onboarding_checklist_id=checklist.id,
            notes="Auto-assigned for onboarding",
            notify=True,
        )
        created.append(row)
    return created


def incomplete_required_for_user(db: Session, user_id: UUID) -> list[TrainingAssignment]:
    return list(
        db.scalars(
            select(TrainingAssignment)
            .join(TrainingCourse)
            .where(
                TrainingAssignment.user_id == user_id,
                TrainingCourse.is_required_for_onboarding.is_(True),
                TrainingCourse.is_active.is_(True),
                TrainingAssignment.status.in_(("assigned", "in_progress")),
            )
            .options(selectinload(TrainingAssignment.course))
        ).all()
    )


def assert_required_trainings_complete(db: Session, user_id: UUID | None) -> None:
    if user_id is None:
        return
    open_rows = incomplete_required_for_user(db, user_id)
    if not open_rows:
        return
    titles = ", ".join(
        (row.course.title if row.course else "Training") for row in open_rows[:5]
    )
    raise ProTrackValidationError(
        "Complete required onboarding training before finishing onboarding: "
        f"{titles}."
    )


def complete_assignment(
    db: Session,
    *,
    assignment: TrainingAssignment,
    actor: User,
) -> TrainingAssignment:
    if assignment.status == "completed":
        return assignment
    assignment.status = "completed"
    assignment.completed_at = _utcnow()
    assignment.completed_by_id = actor.id
    db.add(assignment)
    db.flush()
    return assignment


def list_assignments(
    db: Session,
    *,
    user_id: UUID | None = None,
    status: str | None = None,
) -> list[TrainingAssignment]:
    stmt = (
        select(TrainingAssignment)
        .options(selectinload(TrainingAssignment.course))
        .order_by(TrainingAssignment.created_at.desc())
    )
    if user_id is not None:
        stmt = stmt.where(TrainingAssignment.user_id == user_id)
    if status:
        stmt = stmt.where(TrainingAssignment.status == status)
    return list(db.scalars(stmt).all())


def assign_course_to_users(
    db: Session,
    *,
    course: TrainingCourse,
    user_ids: list[UUID],
    assigned_by: User,
    due_date: date | None = None,
) -> list[TrainingAssignment]:
    rows: list[TrainingAssignment] = []
    for uid in user_ids:
        user = db.get(User, uid)
        if user is None or not user.is_active:
            continue
        rows.append(
            assign_course(
                db,
                course=course,
                user=user,
                assigned_by=assigned_by,
                due_date=due_date,
                notify=True,
            )
        )
    return rows


def incomplete_training_audit_rows(
    db: Session,
    *,
    as_of: date | None = None,
    sla_days: int = REQUIRED_TRAINING_SLA_DAYS,
) -> list[dict[str, Any]]:
    today = as_of or date.today()
    rows = db.scalars(
        select(TrainingAssignment)
        .where(TrainingAssignment.status.in_(("assigned", "in_progress")))
        .options(selectinload(TrainingAssignment.course))
        .order_by(TrainingAssignment.created_at.desc())
    ).all()
    result: list[dict[str, Any]] = []
    for row in rows:
        course = row.course
        if course is None or not course.is_active:
            continue
        due = row.due_date
        if due is None:
            created = row.created_at.date() if row.created_at else today
            due = created + timedelta(days=sla_days)
        if today <= due:
            continue
        user = db.get(User, row.user_id)
        name = (
            f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
            if user
            else "Employee"
        )
        if user and not name:
            name = user.email
        days_late = (today - due).days
        result.append(
            {
                "flag": "incomplete_training",
                "title": "Incomplete training past due",
                "severity": "high" if days_late >= 7 else "medium",
                "subject_name": name or "Employee",
                "subject_user_id": str(row.user_id),
                "checklist_id": str(row.onboarding_checklist_id)
                if row.onboarding_checklist_id
                else None,
                "exit_interview_id": None,
                "detail": (
                    f"“{course.title}” due {due.isoformat()}; "
                    f"{days_late} day(s) overdue."
                ),
                "deep_link": "/hr/training",
                "anchor_date": due.isoformat(),
            }
        )
    return result
