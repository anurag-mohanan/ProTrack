"""Design team roster for development and test databases."""

from __future__ import annotations

import uuid
from typing import NamedTuple

from sqlalchemy import select


class DesignTeamMember(NamedTuple):
    id: uuid.UUID
    role_name: str
    email: str
    first_name: str
    last_name: str


DESIGN_TEAM: tuple[DesignTeamMember, ...] = (
    DesignTeamMember(
        uuid.UUID("10000001-0001-4001-8001-000000000001"),
        "Senior Designer",
        "sandrarag@prosohm.com",
        "Sandrarag",
        "Sandrarag",
    ),
    DesignTeamMember(
        uuid.UUID("10000002-0002-4002-8002-000000000002"),
        "Designer",
        "logesh@prosohm.com",
        "Logesh",
        "Logesh",
    ),
    DesignTeamMember(
        uuid.UUID("10000003-0003-4003-8003-000000000003"),
        "Junior Designer",
        "akhil@prosohm.com",
        "Akhil",
        "Akhil",
    ),
    DesignTeamMember(
        uuid.UUID("10000004-0004-4004-8004-000000000004"),
        "Senior Designer",
        "umesh@prosohm.com",
        "Umesh",
        "Umesh",
    ),
    DesignTeamMember(
        uuid.UUID("10000005-0005-4005-8005-000000000005"),
        "Junior Designer",
        "abhay@prosohm.com",
        "Abhay",
        "Abhay",
    ),
    DesignTeamMember(
        uuid.UUID("10000006-0006-4006-8006-000000000006"),
        "Designer",
        "sarath@prosohm.com",
        "Sarath",
        "Sarath",
    ),
    DesignTeamMember(
        uuid.UUID("10000007-0007-4007-8007-000000000007"),
        "Senior Designer",
        "ramkumar@prosohm.com",
        "Ramkumar",
        "Ramkumar",
    ),
)


def build_design_team_users(password_hash: str, role_by_name: dict[str, uuid.UUID]):
    from app.models.models import User

    return [
        User(
            id=member.id,
            role_id=role_by_name[member.role_name],
            email=member.email,
            password_hash=password_hash,
            first_name=member.first_name,
            last_name=member.last_name,
            is_active=True,
        )
        for member in DESIGN_TEAM
    ]


def ensure_design_team_users(session, password_hash: str) -> None:
    from app.models.models import Role, User

    roles = {
        role.name: role.id
        for role in session.scalars(select(Role)).all()
    }
    for member in DESIGN_TEAM:
        existing = session.scalar(select(User).where(User.email == member.email))
        if existing is not None:
            continue
        role_id = roles.get(member.role_name)
        if role_id is None:
            continue
        session.add(
            User(
                id=member.id,
                role_id=role_id,
                email=member.email,
                password_hash=password_hash,
                first_name=member.first_name,
                last_name=member.last_name,
                is_active=True,
            )
        )
    session.commit()
