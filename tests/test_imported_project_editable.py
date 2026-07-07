"""Imported projects must be fully editable like manually created projects."""

from decimal import Decimal

import pytest

from app.models.models import Project
from app.schemas.historical_import import DuplicateAction
from app.services.historical_import_service import IMPORT_NOTE_MARKER, run_import, save_upload
from tests.conftest import IDS, login
from tests.test_historical_import import build_sample_workbook


@pytest.fixture
def imported_project(session):
    upload_id = "editable-import-upload"
    save_upload(upload_id, "historical.xlsx", build_sample_workbook(
        [
            [
                "T-EDIT-001",
                "Acme Plastics",
                "Logesh",
                "Akhil",
                120,
                80,
                "Roughing",
                40,
                "In Progress",
                "Editable imported mold",
                "2026-12-31",
            ],
        ]
    ))
    summary, _ = run_import(
        session,
        upload_id,
        dry_run=False,
        duplicate_action=DuplicateAction.skip,
    )
    assert summary.projects_imported == 1
    project = session.query(Project).filter(Project.tool_number == "T-EDIT-001").one()
    return project


def test_imported_project_has_no_import_restrictions(session, imported_project):
    """Imported projects use the same model as manual projects — no lock/import flags."""
    project = imported_project
    assert project.is_archived is False
    assert project.is_deleted is False
    assert IMPORT_NOTE_MARKER in (project.notes or "")
    assert not hasattr(project, "is_imported")
    assert not hasattr(project, "is_locked")
    assert not hasattr(project, "historical_only")
    assert not hasattr(project, "read_only")


def test_imported_project_full_edit_workflow(client, session, imported_project):
    """Regression: edit team, assignments, dates, notes, milestones, and timesheets."""
    headers = login(client, "admin@prosohm.com")
    project_id = str(imported_project.id)

    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Imported Edit Team",
            "colour": "#3f51b5",
            "team_lead_id": str(IDS["user_anurag"]),
            "is_active": True,
        },
        headers=headers,
    )
    assert team.status_code == 201
    team_id = team.json()["id"]

    patch = client.patch(
        f"/api/v1/projects/{project_id}",
        json={
            "team_id": team_id,
            "design_leader_id": str(IDS["user_anurag"]),
            "designer_id": str(IDS["user_binil"]),
            "surfacer_id": str(IDS["user_ranjith"]),
            "due_date": "2027-01-15",
            "notes": "Updated after historical import",
            "health": "yellow",
            "code": "EDIT-001",
            "quoted_hours": 150,
        },
        headers=headers,
    )
    assert patch.status_code == 200, patch.text
    body = patch.json()
    assert body["team_id"] == team_id
    assert body["design_leader_id"] == str(IDS["user_anurag"])
    assert body["designer_id"] == str(IDS["user_binil"])
    assert body["surfacer_id"] == str(IDS["user_ranjith"])
    assert body["due_date"] == "2027-01-15"
    assert body["notes"] == "Updated after historical import"
    assert body["health"] == "yellow"
    assert body["code"] == "EDIT-001"
    assert Decimal(str(body["quoted_hours"])) == Decimal("150")

    milestone = client.post(
        "/api/v1/milestones",
        json={
            "project_id": project_id,
            "name": "Post-import milestone",
            "description": "Added after import",
            "status": "not_started",
            "due_date": "2027-02-01",
            "sort_order": 99,
        },
        headers=headers,
    )
    assert milestone.status_code == 201, milestone.text
    milestone_id = milestone.json()["id"]

    timesheet = client.post(
        "/api/v1/timesheets",
        json={
            "user_id": str(IDS["user_binil"]),
            "week_start": "2026-06-16",
            "status": "draft",
        },
        headers=headers,
    )
    assert timesheet.status_code == 201

    entry = client.post(
        "/api/v1/timesheet-entries",
        json={
            "timesheet_id": timesheet.json()["id"],
            "work_category": "productive",
            "project_id": project_id,
            "task_type_id": str(client.task_type_id),
            "entry_date": "2026-06-17",
            "hours": 5,
            "description": "Post-import design work",
        },
        headers=headers,
    )
    assert entry.status_code == 201, entry.text

    reloaded = client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert reloaded.status_code == 200
    data = reloaded.json()
    assert data["team_id"] == team_id
    assert data["design_leader_id"] == str(IDS["user_anurag"])
    assert data["designer_id"] == str(IDS["user_binil"])
    assert data["surfacer_id"] == str(IDS["user_ranjith"])
    assert data["due_date"] == "2027-01-15"
    assert data["notes"] == "Updated after historical import"
    assert Decimal(str(data["quoted_hours"])) == Decimal("150")

    milestones = client.get(
        f"/api/v1/milestones?project_id={project_id}",
        headers=headers,
    )
    assert milestones.status_code == 200
    assert any(m["id"] == milestone_id for m in milestones.json())

    project_after = client.get(f"/api/v1/projects/{project_id}", headers=headers).json()
    assert Decimal(str(project_after["actual_hours"])) >= Decimal("5")


def test_archived_imported_project_can_be_edited_and_restored(client, session):
    """Archived historical imports remain editable; restore clears archive state."""
    upload_id = "archived-import-upload"
    save_upload(
        upload_id,
        "historical.xlsx",
        build_sample_workbook(
            [
                [
                    "T-ARCH-001",
                    "Beta Manufacturing",
                    "Sarath",
                    "",
                    90,
                    90,
                    "BOM Release",
                    100,
                    "Completed",
                    "Old completed tool",
                    "2020-01-01",
                ],
            ]
        ),
    )
    summary, _ = run_import(
        session,
        upload_id,
        dry_run=False,
        duplicate_action=DuplicateAction.skip,
        import_as_archived=True,
    )
    assert summary.projects_imported == 1
    project = session.query(Project).filter(Project.tool_number == "T-ARCH-001").one()
    assert project.is_archived is True

    headers = login(client, "admin@prosohm.com")
    project_id = str(project.id)

    patch = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"notes": "Edited while archived", "health": "green"},
        headers=headers,
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["notes"] == "Edited while archived"

    restore = client.post(f"/api/v1/projects/{project_id}/restore", headers=headers)
    assert restore.status_code == 200, restore.text
    assert restore.json()["is_archived"] is False

    reloaded = client.get(f"/api/v1/projects/{project_id}", headers=headers).json()
    assert reloaded["is_archived"] is False
    assert reloaded["notes"] == "Edited while archived"
