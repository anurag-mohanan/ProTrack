"""Cross-team hours on designer timesheet reports."""

from datetime import date
from decimal import Decimal
import uuid

from app.models.enums import TeamRelationshipType, TimesheetStatus, WorkCategory
from app.models.models import Project, Team, TeamMember, Timesheet, TimesheetEntry, User
from app.services.reporting.cross_team_hours import build_cross_team_hours
from app.services.reporting.designer_team_timesheet import build_designer_team_timesheet
from tests.conftest import IDS


def _seed_cross_team(session):
    home = Team(id=uuid.uuid4(), name="Home Team CT", is_active=True)
    other = Team(id=uuid.uuid4(), name="Other Team CT", is_active=True)
    session.add_all([home, other])
    session.flush()

    designer = session.get(User, IDS["user_binil"])
    assert designer is not None
    designer.team_id = home.id
    session.add(
        TeamMember(
            team_id=home.id,
            user_id=designer.id,
            relationship_type=TeamRelationshipType.member,
            is_primary=True,
        )
    )

    project = session.get(Project, IDS["project"])
    assert project is not None
    project.team_id = other.id  # other team's project

    week_start = date(2026, 7, 6)
    timesheet = Timesheet(
        user_id=designer.id,
        week_start=week_start,
        status=TimesheetStatus.approved,
    )
    session.add(timesheet)
    session.flush()
    session.add(
        TimesheetEntry(
            timesheet_id=timesheet.id,
            entry_date=week_start,
            hours=Decimal("6"),
            work_category=WorkCategory.productive,
            is_billable=True,
            customer_id=IDS["customer"],
            project_id=project.id,
        )
    )
    session.commit()
    return home, other, designer, project, week_start


def test_build_cross_team_hours_detects_outbound(session):
    home, other, designer, project, week_start = _seed_cross_team(session)
    rows, outbound, inbound = build_cross_team_hours(
        session,
        start_date=week_start,
        end_date=week_start,
        team_id=home.id,
    )
    assert outbound == Decimal("6")
    assert inbound == Decimal("0")
    assert len(rows) == 1
    assert rows[0].direction == "outbound"
    assert rows[0].user_id == designer.id
    assert rows[0].project_id == project.id
    assert rows[0].home_team_name == "Home Team CT"
    assert rows[0].project_team_name == "Other Team CT"


def test_build_cross_team_hours_inbound_for_project_team(session):
    home, other, designer, project, week_start = _seed_cross_team(session)
    rows, outbound, inbound = build_cross_team_hours(
        session,
        start_date=week_start,
        end_date=week_start,
        team_id=other.id,
    )
    assert outbound == Decimal("0")
    assert inbound == Decimal("6")
    assert len(rows) == 1
    assert rows[0].direction == "inbound"


def test_designer_team_timesheet_includes_cross_team_section(session):
    home, _other, designer, _project, week_start = _seed_cross_team(session)
    admin = session.get(User, IDS["user_admin"])
    assert admin is not None
    payload = build_designer_team_timesheet(
        session,
        current_user=admin,
        report_id="weekly-timesheet",
        anchor=week_start,
        team_id=home.id,
    )
    assert payload.cross_team_hours_outbound == Decimal("6")
    assert any(r.user_id == designer.id for r in payload.cross_team_hours)
