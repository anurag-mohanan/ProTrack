"""User-relevant stream / team scope for the projects portfolio (Phase A)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.team_access import get_accessible_team_ids
from app.models.models import Project, Stream, User


def can_view_all_streams(db: Session, user: User) -> bool:
    """Org-wide stream portfolio (Admin / unscoped EM / executives / planning)."""
    return get_accessible_team_ids(db, user) is None


def get_user_relevant_stream_ids(db: Session, user: User) -> set[UUID]:
    """Streams the user should see by default (My stream(s)).

    Sources:
    - ``User.stream_id`` primary stream
    - Distinct ``Project.stream_id`` on projects they are assigned to
    - Distinct streams on projects for their accessible teams (when team-scoped)
    """
    streams: set[UUID] = set()
    if user.stream_id is not None:
        streams.add(user.stream_id)

    assigned_project_streams = db.scalars(
        select(Project.stream_id).where(
            Project.stream_id.is_not(None),
            Project.is_deleted.is_(False),
            (
                (Project.designer_id == user.id)
                | (Project.design_leader_id == user.id)
                | (Project.surfacer_id == user.id)
            ),
        )
    ).all()
    streams.update(sid for sid in assigned_project_streams if sid is not None)

    accessible = get_accessible_team_ids(db, user)
    if accessible is not None and accessible:
        team_project_streams = db.scalars(
            select(Project.stream_id).where(
                Project.stream_id.is_not(None),
                Project.is_deleted.is_(False),
                Project.team_id.in_(accessible),
            )
        ).all()
        streams.update(sid for sid in team_project_streams if sid is not None)

    return streams


def resolve_default_project_stream_id(db: Session) -> UUID | None:
    """Mold Design stream id for create defaults / backfill fallback."""
    mold = db.scalar(select(Stream).where(Stream.name == "Mold Design"))
    if mold is not None:
        return mold.id
    for row in db.scalars(select(Stream).where(Stream.is_active.is_(True))).all():
        if "mold" in row.name.lower():
            return row.id
    first = db.scalar(select(Stream).where(Stream.is_active.is_(True)).order_by(Stream.name))
    return first.id if first is not None else None


def is_mold_stream(db: Session, stream_id: UUID | None) -> bool:
    if stream_id is None:
        return True
    stream = db.get(Stream, stream_id)
    if stream is None:
        return True
    return "mold" in stream.name.lower()


def stream_display_name(db: Session, stream_id: UUID | None) -> str | None:
    if stream_id is None:
        return None
    stream = db.get(Stream, stream_id)
    return stream.name if stream is not None else None
