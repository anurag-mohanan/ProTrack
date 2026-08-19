"""R1 Critical Platform — health, jobs, SoD, backup dialect helpers."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.exceptions import ProTrackValidationError
from app.core.sod import validate_special_permission_sod
from app.core.access_control import (
    SPECIAL_APPROVE_TIMESHEETS,
    SPECIAL_IMPORT_TIMESHEETS,
    SPECIAL_MANAGE_PERMISSIONS,
    SPECIAL_FINANCIAL_APPROVAL,
)
from app.models.models import BackgroundJob, Role
from app.services import job_queue
from app.services.backup_service import _is_postgres, _is_sqlite, list_database_backups
from tests.conftest import login


def test_health_includes_checks(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert "checks" in body
    assert "database" in body["checks"]
    assert "upload_dir_writable" in body["checks"]


def test_sod_rejects_import_and_approve_timesheets():
    with pytest.raises(ProTrackValidationError) as exc:
        validate_special_permission_sod(
            [SPECIAL_IMPORT_TIMESHEETS, SPECIAL_APPROVE_TIMESHEETS]
        )
    assert "Segregation of duties" in exc.value.detail


def test_sod_allows_admin_delete_and_approve_together():
    from app.core.access_control import SPECIAL_APPROVE_PROJECTS, SPECIAL_DELETE_PROJECTS

    validate_special_permission_sod(
        [SPECIAL_DELETE_PROJECTS, SPECIAL_APPROVE_PROJECTS],
        role_name="Admin",
    )


def test_user_create_sod_conflict(client, session):
    admin = login(client, "admin@prosohm.com")
    role = session.scalar(select(Role).where(Role.name == "Designer"))
    assert role is not None
    response = client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "first_name": "SoD",
            "last_name": "Conflict",
            "email": f"sod-{uuid.uuid4().hex[:8]}@prosohm.com",
            "password": "TempPass123!",
            "role_id": str(role.id),
            "must_change_password": True,
            "special_permissions": [
                SPECIAL_IMPORT_TIMESHEETS,
                SPECIAL_APPROVE_TIMESHEETS,
            ],
        },
    )
    assert response.status_code == 422, response.text
    assert "Segregation of duties" in response.json()["detail"]


def test_enqueue_and_process_email_job(session):
    job = job_queue.enqueue_job(
        session,
        job_type=job_queue.JOB_PROCESS_EMAIL_QUEUE,
        payload={"limit": 1},
    )
    assert job.status == job_queue.STATUS_QUEUED
    # EmailSettings may be disabled — job should still complete without crash.
    job_queue.process_job_by_id(str(job.id))
    refreshed = session.get(BackgroundJob, job.id)
    session.refresh(refreshed)
    assert refreshed.status in {
        job_queue.STATUS_SUCCEEDED,
        job_queue.STATUS_FAILED,
        job_queue.STATUS_QUEUED,
    }


def test_backup_list_does_not_raise():
    rows = list_database_backups()
    assert isinstance(rows, list)


def test_dialect_helpers():
    # Default test / app URL is sqlite unless overridden.
    assert _is_sqlite() or _is_postgres()


def test_manage_permissions_financial_approval_conflict():
    with pytest.raises(ProTrackValidationError):
        validate_special_permission_sod(
            [SPECIAL_MANAGE_PERMISSIONS, SPECIAL_FINANCIAL_APPROVAL]
        )
