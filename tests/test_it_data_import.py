"""Sequential IT Data Import — assets preview fidelity + commit batch tagging."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.models.it_operations import Asset, ITImportBatch
from app.models.models import Customer, Project, User

SPLIT = Path(__file__).resolve().parents[1] / "docs" / "migration-sources" / "split"


def test_assets_analyze_first_10_preserves_source_ids(client):
    path = SPLIT / "01_Assets.xlsx"
    assert path.exists(), f"Missing {path}"
    with path.open("rb") as fh:
        response = client.post(
            "/api/v1/it/data-import/analyze",
            headers=client.auth_headers,
            data={"import_type": "assets"},
            files={
                "file": (
                    "01_Assets.xlsx",
                    fh,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sheet_name"] == "Assets"
    assert body["stats"]["records_found"] == 306
    assert body["stats"]["id_blank_ratio"] == 0
    assert body["commit_allowed"] is True
    assert body["block_commit"] is False
    assert body["column_bindings"]["asset_number"] == "asset_number"
    assert body["column_bindings"]["ownership_type"] == "ownership_type"

    first = body["first_10_records"]
    assert len(first) == 10
    assert first[0]["asset_number"] == "IT - 001"
    assert first[0]["name"] == "LG DISPLAY 1"
    assert first[0]["ownership_type"] == "Prosohm"
    assert first[1]["asset_number"] == "IT - 002"
    assert first[1]["ownership_type"] == "Customer"
    assert first[1]["owner_customer"] == "Sybridge"
    for row in first:
        for value in row.values():
            if isinstance(value, str):
                assert "SERIAL_MISSING" not in value
                assert "OWNERSHIP_UNCLEAR" not in value
                assert not value.startswith("EX-HAR")


def test_assets_commit_and_rollback_batch_only(client, session):
    path = SPLIT / "01_Assets.xlsx"
    with path.open("rb") as fh:
        analyzed = client.post(
            "/api/v1/it/data-import/analyze",
            headers=client.auth_headers,
            data={"import_type": "assets"},
            files={
                "file": (
                    "01_Assets.xlsx",
                    fh,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert analyzed.status_code == 200, analyzed.text
    batch_id = analyzed.json()["batch_id"]

    committed = client.post(
        "/api/v1/it/data-import/commit",
        headers=client.auth_headers,
        data={"batch_id": batch_id, "confirm": "true", "skip_duplicates": "true"},
    )
    assert committed.status_code == 200, committed.text
    result = committed.json()
    assert result["status"] == "committed"
    assert result["imported"] > 0

    assets = list(session.scalars(select(Asset).where(Asset.is_deleted.is_(False))).all())
    assert len(assets) == result["imported"]
    assert all(a.import_batch_id is not None for a in assets)
    assert any(a.asset_number == "IT - 001" for a in assets)

    user_count = len(list(session.scalars(select(User)).all()))
    customer_count = len(list(session.scalars(select(Customer)).all()))
    project_count = len(list(session.scalars(select(Project)).all()))

    rolled = client.post(
        "/api/v1/it/data-import/rollback",
        headers=client.auth_headers,
        data={"batch_id": batch_id, "confirm": "true"},
    )
    assert rolled.status_code == 200, rolled.text
    assert rolled.json()["status"] == "rolled_back"

    session.expire_all()
    remaining = list(session.scalars(select(Asset).where(Asset.is_deleted.is_(False))).all())
    assert remaining == []
    batch = session.get(ITImportBatch, UUID(batch_id))
    assert batch is not None
    assert batch.status == "rolled_back"

    assert len(list(session.scalars(select(User)).all())) == user_count
    assert len(list(session.scalars(select(Customer)).all())) == customer_count
    assert len(list(session.scalars(select(Project)).all())) == project_count


def test_wrong_file_type_rejected(client):
    path = SPLIT / "05_Software_Licenses.xlsx"
    with path.open("rb") as fh:
        response = client.post(
            "/api/v1/it/data-import/analyze",
            headers=client.auth_headers,
            data={"import_type": "assets"},
            files={
                "file": (
                    "05_Software_Licenses.xlsx",
                    fh,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert response.status_code == 422
