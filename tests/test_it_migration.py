"""IT migration analyze / import — secrets excluded, duplicates skipped."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import select

from app.models.it_operations import Asset, ITUserAccount
from app.models.models import User


def _hardware_workbook_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "1.HARDWARES"
    ws.append(
        [
            "SL NO",
            "ID",
            "DESCRIPTION",
            "CUSTOMER USED FOR",
            "TYPE",
            "CURRENT USER",
            "MAKE",
            "MODEL",
            "CURRENT STATUS",
            "SERVICE TAG#",
            "PWD",
            "Teamviewer ID/pwd",
        ]
    )
    ws.append(
        [
            "1",
            "PP-MIG-01",
            "Test workstation",
            "Generic",
            "Workstation",
            "All",
            "DELL",
            "3680",
            "WORKING",
            "MIGTAG001",
            "should-never-appear",
            "tv-secret",
        ]
    )
    ws.append(
        [
            "2",
            "IT-136",
            "Unclear ownership",
            "Sybridge",
            "Workstation",
            "Nobody",
            "DELL",
            "5820",
            "WORKING",
            "MIGTAG002",
            "secret2",
            "",
        ]
    )
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _accounts_workbook_bytes(email: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "2.USER_CREDENTIALS"
    ws.append(
        [
            "SL NO.",
            "EMPLOYEE NAME",
            "DEPARTMENT",
            "STATUS",
            "USERNAME",
            "PWD",
            "EMAIL",
            "PWD3",
        ]
    )
    ws.append(
        [
            "1",
            "Migration User",
            "Admin",
            "Current",
            "miguser",
            "plaintext-password",
            email,
            "another-secret",
        ]
    )
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_migration_analyze_excludes_secrets_and_requires_confirm(client):
    content = _hardware_workbook_bytes()
    response = client.post(
        "/api/v1/it/migration/analyze",
        headers=client.auth_headers,
        data={"source_type": "hardware"},
        files={
            "file": (
                "hardware.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["records_found"] == 2
    assert body["confirm_required"] is True
    assert "PWD" in body["sensitive_columns_excluded"]
    assert any("Teamviewer" in c for c in body["sensitive_columns_excluded"])
    preview_blob = str(body["preview_rows"]).lower()
    assert "should-never-appear" not in preview_blob
    assert "tv-secret" not in preview_blob
    assert body["session_id"]

    # Import without confirm must fail
    denied = client.post(
        "/api/v1/it/migration/import",
        headers=client.auth_headers,
        data={"session_id": body["session_id"], "confirm": "false"},
    )
    assert denied.status_code == 422


def test_migration_import_hardware_and_skip_duplicate(client, session):
    content = _hardware_workbook_bytes()
    analyzed = client.post(
        "/api/v1/it/migration/analyze",
        headers=client.auth_headers,
        data={"source_type": "hardware"},
        files={
            "file": (
                "hardware.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert analyzed.status_code == 200, analyzed.text
    session_id = analyzed.json()["session_id"]

    imported = client.post(
        "/api/v1/it/migration/import",
        headers=client.auth_headers,
        data={
            "session_id": session_id,
            "confirm": "true",
            "skip_duplicates": "true",
        },
    )
    assert imported.status_code == 200, imported.text
    result = imported.json()
    assert result["imported"] >= 1

    assets = list(session.scalars(select(Asset).where(Asset.is_deleted.is_(False))).all())
    legacy_ids = {a.legacy_asset_number for a in assets}
    assert "PP-MIG-01" in legacy_ids
    # No password anywhere on notes
    for a in assets:
        assert a.notes is None or "should-never-appear" not in (a.notes or "")
        assert a.notes is None or "tv-secret" not in (a.notes or "")

    # Re-analyze same file → duplicates detected against DB
    analyzed2 = client.post(
        "/api/v1/it/migration/analyze",
        headers=client.auth_headers,
        data={"source_type": "hardware"},
        files={
            "file": (
                "hardware.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert analyzed2.status_code == 200
    assert analyzed2.json()["potential_duplicates"] >= 1


def test_migration_accounts_never_store_passwords(client, session):
    admin = session.scalar(select(User).where(User.email == "admin@prosohm.com"))
    assert admin is not None
    content = _accounts_workbook_bytes(admin.email)

    analyzed = client.post(
        "/api/v1/it/migration/analyze",
        headers=client.auth_headers,
        data={"source_type": "accounts"},
        files={
            "file": (
                "accounts.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert analyzed.status_code == 200, analyzed.text
    body = analyzed.json()
    assert body["sensitive_data_excluded_count"] >= 1
    assert "plaintext-password" not in str(body).lower()

    imported = client.post(
        "/api/v1/it/migration/import",
        headers=client.auth_headers,
        data={"session_id": body["session_id"], "confirm": "true"},
    )
    assert imported.status_code == 200, imported.text

    accounts = list(
        session.scalars(
            select(ITUserAccount).where(ITUserAccount.user_id == admin.id)
        ).all()
    )
    assert accounts
    for acct in accounts:
        assert acct.credential_status == "migration_required"
        blob = f"{acct.username} {acct.notes} {acct.display_name}".lower()
        assert "plaintext" not in blob
        assert "password" not in blob or "passwords not imported" in blob
