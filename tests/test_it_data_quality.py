"""Unified IT / Resource Planning data-quality report."""

from datetime import date
from uuid import uuid4

from sqlalchemy import select

from app.models.it_operations import (
    Asset,
    AssetType,
    Computer,
    IPAddress,
    IPAssignmentHistory,
    Network,
)
from app.models.models import User
from app.services import it_asset_service
from app.services import it_data_quality_service as dq
from tests.conftest import IDS


def _ensure_desktop_type(session) -> AssetType:
    existing = session.scalar(select(AssetType).where(AssetType.code == "DESKTOP"))
    if existing:
        return existing
    row = AssetType(
        id=uuid4(),
        code="DESKTOP",
        name="Desktop",
        category="computer",
        is_active=True,
    )
    session.add(row)
    session.commit()
    return row


def test_data_quality_flags_orphan_assigned_and_repair_catalog(session, auth_headers, client):
    at = _ensure_desktop_type(session)
    asset = it_asset_service.create_asset(
        session,
        actor=session.get(User, IDS["user_admin"]),
        asset_type_id=at.id,
        asset_number=f"IT-DQ-{uuid4().hex[:6].upper()}",
        commit=True,
    )
    asset.status = "assigned"
    session.add(asset)
    session.commit()
    session.add(
        Computer(
            id=uuid4(),
            asset_id=asset.id,
            computer_name=f"DqPc{uuid4().hex[:4]}",
            ram_gb=32,
        )
    )
    session.commit()

    report = dq.build_data_quality_report(session)
    assert report["totals"]["computers_total"] >= 1
    codes = {row["code"] for row in report["open_issues"]}
    assert "assigned_without_employee" in codes
    orphan = next(row for row in report["issues"] if row["code"] == "assigned_without_employee")
    assert orphan["repair_code"] == "repair_orphan_assigned"
    assert any(r["code"] == "repair_orphan_assigned" and r["available"] for r in report["repairs"])

    response = client.get("/api/v1/it/data-quality", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "open_issues" in body
    assert body["totals"]["issue_types"] >= 1

    dash = client.get("/api/v1/dashboard/resource-planning/data-quality", headers=auth_headers)
    assert dash.status_code == 200
    assert "issues" in dash.json()


def test_data_quality_flags_computer_without_ip_and_customer_owner(session):
    at = _ensure_desktop_type(session)
    admin = session.get(User, IDS["user_admin"])
    asset = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=at.id,
        asset_number=f"IT-DQIP-{uuid4().hex[:6].upper()}",
        commit=True,
    )
    asset.purchased_by = "customer"
    asset.owner_customer_id = None
    session.add(asset)
    session.add(
        Computer(
            id=uuid4(),
            asset_id=asset.id,
            computer_name=f"NoIp{uuid4().hex[:4]}",
        )
    )
    session.commit()

    report = dq.build_data_quality_report(session)
    codes = {row["code"]: row for row in report["open_issues"]}
    assert "computers_without_ip" in codes
    assert codes["computers_without_ip"]["count"] >= 1
    assert "customer_owned_without_owner" in codes


def test_data_quality_flags_inactive_asset_with_active_ip(session):
    at = _ensure_desktop_type(session)
    admin = session.get(User, IDS["user_admin"])
    asset = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=at.id,
        asset_number=f"IT-DQRET-{uuid4().hex[:6].upper()}",
        commit=True,
    )
    asset.status = "retired"
    session.add(asset)
    session.commit()

    network = Network(
        id=uuid4(),
        name=f"DQ Net {uuid4().hex[:4]}",
        cidr="10.250.0.0/24",
        is_active=True,
    )
    session.add(network)
    session.flush()
    ip = IPAddress(
        id=uuid4(),
        network_id=network.id,
        address="10.250.0.44",
        status="allocated",
    )
    session.add(ip)
    session.flush()
    session.add(
        IPAssignmentHistory(
            id=uuid4(),
            ip_address_id=ip.id,
            assigned_to_asset_id=asset.id,
            assigned_by_user_id=admin.id,
            assigned_date=date.today(),
            released_date=None,
        )
    )
    session.commit()

    report = dq.build_data_quality_report(session)
    codes = {row["code"] for row in report["open_issues"]}
    assert "inactive_asset_with_active_ip" in codes
