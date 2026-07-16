"""Phase L — Corporate / Management single overhead home merge."""

from sqlalchemy import select

from app.db.phase23_finance_team_scope_schema_sync import CORPORATE_TEAM_NAME
from app.db.phase33_management_team_schema_sync import (
    LEGACY_MANAGEMENT_TEAM_NAME,
    ensure_management_team,
)
from app.db.phase35_overhead_team_merge_schema_sync import (
    ensure_phase35_overhead_team_merge_foundation,
)
from app.models.models import Team


def test_overhead_team_merge_unifies_management_into_corporate_home(client, auth_headers, session):
    ensure_phase35_overhead_team_merge_foundation(session.get_bind())
    session.commit()

    home = session.scalar(select(Team).where(Team.name == CORPORATE_TEAM_NAME))
    assert home is not None
    assert home.is_active is True

    legacy_mgmt = session.scalar(
        select(Team).where(Team.name == LEGACY_MANAGEMENT_TEAM_NAME)
    )
    if legacy_mgmt is not None:
        assert legacy_mgmt.is_active is False

    assert ensure_management_team(session).id == home.id

    teams = client.get("/api/v1/lookups/teams", headers=auth_headers)
    assert teams.status_code == 200
    active_names = {row["name"] for row in teams.json() if row.get("is_active", True)}
    assert CORPORATE_TEAM_NAME in active_names
    assert LEGACY_MANAGEMENT_TEAM_NAME not in active_names


def test_dashboard_overhead_single_home_ids(client, auth_headers):
    response = client.get("/api/v1/finance/dashboard", headers=auth_headers)
    assert response.status_code == 200
    overhead = response.json()["overhead"]
    assert overhead.get("corporate_team_name") == CORPORATE_TEAM_NAME
    assert overhead.get("management_team_name") == CORPORATE_TEAM_NAME
    assert overhead.get("corporate_team_id") == overhead.get("management_team_id")
