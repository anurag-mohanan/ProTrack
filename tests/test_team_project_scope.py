"""Team-scoped project visibility includes assignee-linked live projects."""

from decimal import Decimal
import uuid

from sqlalchemy import select

from app.core.team_access import team_project_clause
from app.models.enums import ExecutionStatus, TeamRelationshipType
from app.models.models import Project, Team, TeamMember, User
from tests.conftest import IDS


def _team(db, name: str) -> Team:
    team = Team(id=uuid.uuid4(), name=name, is_active=True)
    db.add(team)
    db.flush()
    return team


def test_team_project_clause_includes_null_team_id_with_team_designer(
    session,
):
    team = _team(session, "Prosohm Eng")
    designer = session.get(User, IDS["user_binil"])
    assert designer is not None
    designer.team_id = team.id
    session.add(
        TeamMember(
            team_id=team.id,
            user_id=designer.id,
            relationship_type=TeamRelationshipType.member,
            is_primary=True,
        )
    )
    explicit = Project(
        id=uuid.uuid4(),
        tool_number="TEAM-EXPLICIT",
        part_description="Explicit team",
        customer_id=IDS["customer"],
        team_id=team.id,
        quoted_hours=Decimal("10"),
        actual_hours=Decimal("5"),
        execution_status=ExecutionStatus.currently_being_worked_on,
    )
    inherited = Project(
        id=uuid.uuid4(),
        tool_number="TEAM-INHERIT",
        part_description="Inherited via designer",
        customer_id=IDS["customer"],
        designer_id=designer.id,
        team_id=None,
        quoted_hours=Decimal("20"),
        actual_hours=Decimal("8"),
        execution_status=ExecutionStatus.on_hold,
    )
    outsider = Project(
        id=uuid.uuid4(),
        tool_number="TEAM-OUT",
        part_description="Other team",
        customer_id=IDS["customer"],
        team_id=uuid.uuid4(),
        quoted_hours=Decimal("30"),
        actual_hours=Decimal("12"),
        execution_status=ExecutionStatus.currently_being_worked_on,
    )
    session.add_all([explicit, inherited, outsider])
    session.commit()

    clause = team_project_clause(session, [team.id])
    matched = session.scalars(select(Project).where(*clause)).all()
    tool_numbers = {project.tool_number for project in matched}

    assert {"TEAM-EXPLICIT", "TEAM-INHERIT"}.issubset(tool_numbers)
    assert "TEAM-OUT" not in tool_numbers
