"""Durable asset-number history + identity SoT read paths."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.models.it_operations import (
    AssetType,
    SoftwareCatalog,
    SoftwareLicensePool,
)
from app.models.models import User
from app.services import it_asset_service, it_software_service
from app.services.resource_it_gap_service import resolve_primary_tool
from tests.conftest import IDS


def _laptop(session) -> AssetType:
    row = session.scalar(select(AssetType).where(AssetType.code == "LAPTOP"))
    assert row is not None
    return row


def test_renumber_writes_history_and_blocks_reuse(client, session, auth_headers):
    laptop = _laptop(session)
    created = client.post(
        "/api/v1/it/assets",
        headers=auth_headers,
        json={
            "asset_type_id": str(laptop.id),
            "asset_number": "HIST-9001",
            "make": "Dell",
        },
    )
    assert created.status_code == 201, created.text
    asset_id = created.json()["id"]

    renamed = client.patch(
        f"/api/v1/it/assets/{asset_id}",
        headers=auth_headers,
        json={"asset_number": "HIST-9002"},
    )
    assert renamed.status_code == 200, renamed.text
    body = renamed.json()
    assert body["asset_number"] == "HIST-9002"
    assert "HIST-9001" in (body.get("previous_asset_numbers") or [])

    history = client.get(
        f"/api/v1/it/assets/{asset_id}/lifecycle-history",
        headers=auth_headers,
    )
    assert history.status_code == 200, history.text
    numbers = history.json().get("asset_numbers") or []
    recorded = {row["asset_number"] for row in numbers}
    assert "HIST-9001" in recorded
    assert "HIST-9002" in recorded
    assert any(row["asset_number"] == "HIST-9002" and row["effective_to"] is None for row in numbers)

    clash = client.post(
        "/api/v1/it/assets",
        headers=auth_headers,
        json={
            "asset_type_id": str(laptop.id),
            "asset_number": "HIST-9001",
            "make": "Dell",
        },
    )
    assert clash.status_code == 422, clash.text

    found = client.get(
        "/api/v1/it/assets",
        headers=auth_headers,
        params={"search": "HIST-9001", "inventory_scope": "all"},
    )
    assert found.status_code == 200, found.text
    payload = found.json()
    items = payload.get("items") if isinstance(payload, dict) else payload
    assert any(row["id"] == asset_id for row in items)


def test_next_number_skips_historical_sequence(session):
    laptop = _laptop(session)
    actor = session.get(User, IDS["user_admin"])
    assert actor is not None
    prefix = it_asset_service._prefix_for_type(laptop)
    high = f"{prefix}-8888"
    low = f"{prefix}-8870"
    first = it_asset_service.create_asset(
        session,
        actor=actor,
        asset_type_id=laptop.id,
        asset_number=high,
        make="Dell",
    )
    it_asset_service.apply_asset_number_change(
        session, first, low, actor=actor, reason="test"
    )
    session.commit()
    preview = it_asset_service.preview_next_asset_number(session, laptop)
    assert preview["highest_existing_sequence"] >= 8888
    assert preview["sequence"] >= 8889


def test_computer_mac_writes_primary_nic(session):
    admin = session.get(User, IDS["user_admin"])
    laptop = _laptop(session)
    computer = it_asset_service.create_computer(
        session,
        actor=admin,
        asset_type_id=laptop.id,
        mac_address="AA:BB:CC:DD:EE:10",
    )
    it_asset_service.update_computer(
        session,
        computer,
        actor=admin,
        mac_address="AA:BB:CC:DD:EE:99",
        fields_set={"mac_address"},
    )
    nics = it_asset_service.list_computer_interfaces(session, computer.id)
    primary = next(row for row in nics if row.is_primary)
    assert primary.mac_address == "AA:BB:CC:DD:EE:99"
    refreshed = it_asset_service.get_computer(session, computer.id)
    assert it_asset_service.effective_mac_address(refreshed) == "AA:BB:CC:DD:EE:99"

    # Stale denorm must not win over the primary NIC.
    refreshed.mac_address = "00:00:00:00:00:00"
    session.add(refreshed)
    session.flush()
    session.refresh(refreshed)
    assert it_asset_service.effective_mac_address(refreshed) == "AA:BB:CC:DD:EE:99"


def test_primary_tool_prefers_assigned_software(session):
    user = session.get(User, IDS["user_anurag"])
    assert user is not None
    user.primary_tool = "Legacy CAD"
    session.add(user)
    session.commit()

    fallback = resolve_primary_tool(session, user.id)
    assert fallback["primary_tool"] == "Legacy CAD"
    assert fallback["primary_tool_source"] == "user_profile"

    catalog = SoftwareCatalog(id=uuid4(), name="Siemens NX", is_active=True)
    session.add(catalog)
    session.flush()
    pool = SoftwareLicensePool(
        id=uuid4(),
        software_id=catalog.id,
        license_type="named",
        seat_count=5,
        status="active",
    )
    session.add(pool)
    session.commit()
    it_software_service.assign_license(
        session, license_pool_id=pool.id, user_id=user.id
    )

    resolved = resolve_primary_tool(session, user.id)
    assert resolved["primary_tool"] == "Siemens NX"
    assert resolved["primary_tool_source"] == "software_assignment"

    empty = session.get(User, IDS["user_admin"])
    empty.primary_tool = None
    session.add(empty)
    session.commit()
    none = resolve_primary_tool(session, empty.id)
    assert none["primary_tool"] is None
    assert none["primary_tool_source"] is None
