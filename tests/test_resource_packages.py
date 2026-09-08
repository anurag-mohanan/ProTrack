"""Resource package templates and transactional RP → IT assignment."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.it_operations import (
    Asset,
    AssetAssignment,
    AssetType,
    EmployeeSoftwareRequirement,
    SoftwareAssignment,
    SoftwareCatalog,
    SoftwareLicensePool,
)
from tests.conftest import IDS, login


def _laptop_type(session) -> AssetType:
    laptop = session.scalars(select(AssetType).where(AssetType.code == "LAPTOP")).first()
    assert laptop is not None
    return laptop


def _available_asset(session, *, asset_number: str) -> Asset:
    asset = Asset(
        id=uuid.uuid4(),
        asset_number=asset_number,
        asset_type_id=_laptop_type(session).id,
        status="available",
        is_deleted=False,
    )
    session.add(asset)
    session.commit()
    return asset


def test_create_package_and_preview_availability(client, session, auth_headers):
    laptop = _laptop_type(session)
    software = SoftwareCatalog(id=uuid.uuid4(), name="PkgCAD", is_active=True)
    session.add(software)
    session.commit()
    _available_asset(session, asset_number="PKG-AVAIL-1")

    created = client.post(
        "/api/v1/it/resource-packages",
        headers=auth_headers,
        json={
            "code": "DES-STD",
            "name": "Designer standard",
            "requires_ip": False,
            "hardware_lines": [
                {"asset_type_id": str(laptop.id), "quantity": 1, "is_required": True}
            ],
            "software_lines": [
                {
                    "software_id": str(software.id),
                    "requirement_level": "required",
                    "seats": 1,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    package_id = created.json()["id"]

    listed = client.get("/api/v1/it/resource-packages?active_only=true", headers=auth_headers)
    assert listed.status_code == 200
    assert any(row["id"] == package_id for row in listed.json())

    preview = client.post(
        f"/api/v1/dashboard/resource-planning/packages/{package_id}/preview",
        headers=auth_headers,
        json={"user_id": str(IDS["user_binil"])},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["package_code"] == "DES-STD"
    hardware = body["hardware"][0]
    assert hardware["available_count"] >= 1
    assert "PkgCAD" in body["shortages"][0] or body["software"][0]["available_seats"] == 0


def test_assign_package_writes_it_sot_and_survives_reread(client, session, auth_headers):
    laptop = _laptop_type(session)
    software = SoftwareCatalog(id=uuid.uuid4(), name="PkgOffice", is_active=True)
    session.add(software)
    session.flush()
    pool = SoftwareLicensePool(
        id=uuid.uuid4(),
        software_id=software.id,
        seat_count=2,
        status="active",
    )
    session.add(pool)
    session.commit()
    asset = _available_asset(session, asset_number="PKG-ASN-1")

    created = client.post(
        "/api/v1/it/resource-packages",
        headers=auth_headers,
        json={
            "code": "OFF-STD",
            "name": "Office standard",
            "hardware_lines": [
                {"asset_type_id": str(laptop.id), "quantity": 1, "is_required": True}
            ],
            "software_lines": [
                {"software_id": str(software.id), "requirement_level": "required", "seats": 1}
            ],
        },
    )
    assert created.status_code == 201, created.text
    package_id = created.json()["id"]
    user_id = str(IDS["user_binil"])

    assigned = client.post(
        f"/api/v1/dashboard/resource-planning/packages/{package_id}/assign",
        headers=auth_headers,
        json={
            "user_id": user_id,
            "asset_ids": [str(asset.id)],
            "license_pool_ids": [str(pool.id)],
        },
    )
    assert assigned.status_code == 200, assigned.text

    session.expire_all()
    open_hw = session.scalars(
        select(AssetAssignment).where(
            AssetAssignment.asset_id == asset.id,
            AssetAssignment.returned_date.is_(None),
        )
    ).all()
    assert len(open_hw) == 1
    assert open_hw[0].assigned_to_user_id == IDS["user_binil"]

    sw = session.scalars(
        select(SoftwareAssignment).where(
            SoftwareAssignment.user_id == IDS["user_binil"],
            SoftwareAssignment.license_pool_id == pool.id,
            SoftwareAssignment.released_date.is_(None),
        )
    ).all()
    assert len(sw) == 1

    req = session.scalars(
        select(EmployeeSoftwareRequirement).where(
            EmployeeSoftwareRequirement.user_id == IDS["user_binil"],
            EmployeeSoftwareRequirement.software_id == software.id,
        )
    ).all()
    assert len(req) == 1

    profile = client.get(f"/api/v1/it/profile/{user_id}", headers=auth_headers)
    assert profile.status_code == 200, profile.text
    software_names = [row.get("software_name") for row in profile.json().get("software") or []]
    assert "PkgOffice" in software_names or any(
        str(pool.id) == str(row.get("license_pool_id"))
        for row in profile.json().get("software") or []
    )


def test_assign_rolls_back_when_license_unavailable(client, session, auth_headers):
    laptop = _laptop_type(session)
    software = SoftwareCatalog(id=uuid.uuid4(), name="PkgEmpty", is_active=True)
    session.add(software)
    session.flush()
    pool = SoftwareLicensePool(
        id=uuid.uuid4(),
        software_id=software.id,
        seat_count=0,
        status="active",
    )
    session.add(pool)
    session.commit()
    asset = _available_asset(session, asset_number="PKG-ROLL-1")

    created = client.post(
        "/api/v1/it/resource-packages",
        headers=auth_headers,
        json={
            "code": "ROLL-STD",
            "name": "Rollback package",
            "hardware_lines": [
                {"asset_type_id": str(laptop.id), "quantity": 1, "is_required": True}
            ],
            "software_lines": [
                {"software_id": str(software.id), "requirement_level": "required", "seats": 1}
            ],
        },
    )
    assert created.status_code == 201, created.text
    package_id = created.json()["id"]

    assigned = client.post(
        f"/api/v1/dashboard/resource-planning/packages/{package_id}/assign",
        headers=auth_headers,
        json={
            "user_id": str(IDS["user_binil"]),
            "asset_ids": [str(asset.id)],
            "license_pool_ids": [str(pool.id)],
        },
    )
    assert assigned.status_code == 422, assigned.text

    session.expire_all()
    leftover = session.scalars(
        select(AssetAssignment).where(
            AssetAssignment.asset_id == asset.id,
            AssetAssignment.returned_date.is_(None),
        )
    ).all()
    assert leftover == []
    sw = session.scalars(
        select(SoftwareAssignment).where(SoftwareAssignment.license_pool_id == pool.id)
    ).all()
    assert sw == []


def test_assign_package_forbidden_without_assign_assets(client, session):
    laptop = _laptop_type(session)
    created = client.post(
        "/api/v1/it/resource-packages",
        headers=login(client, "admin@prosohm.com"),
        json={
            "code": "FORB-STD",
            "name": "Forbidden package",
            "hardware_lines": [
                {"asset_type_id": str(laptop.id), "quantity": 1, "is_required": True}
            ],
        },
    )
    assert created.status_code == 201, created.text
    headers = login(client, "readonly@prosohm.com")
    preview = client.post(
        f"/api/v1/dashboard/resource-planning/packages/{created.json()['id']}/preview",
        headers=headers,
        json={"user_id": str(IDS["user_binil"])},
    )
    assert preview.status_code == 403
    assigned = client.post(
        f"/api/v1/dashboard/resource-planning/packages/{created.json()['id']}/assign",
        headers=headers,
        json={"user_id": str(IDS["user_binil"]), "asset_ids": []},
    )
    assert assigned.status_code == 403
