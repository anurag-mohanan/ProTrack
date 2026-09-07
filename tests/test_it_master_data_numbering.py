"""IT master data cascading + asset number generation (highest+1)."""

from __future__ import annotations

from app.models.it_operations import Asset, AssetMake, AssetModel, AssetType
from app.models.models import User
from app.services import it_asset_service, it_master_data_service as masters
from app.services.it_asset_service import (
    preview_next_asset_number,
    preview_next_asset_numbers,
)


def test_normalize_dedupes_make_case(session):
    a = masters.get_or_create_make(session, name="Dell")
    b = masters.get_or_create_make(session, name="  DELL  ")
    c = masters.get_or_create_make(session, name="dell")
    session.commit()
    assert a.id == b.id == c.id
    assert a.name == "Dell"


def test_cascading_make_model_context(session):
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    monitor = session.query(AssetType).filter(AssetType.code == "MONITOR").first()
    assert laptop and monitor

    dell = masters.get_or_create_make(session, name="Dell", asset_type_id=laptop.id)
    masters.get_or_create_model(
        session, name="Latitude 5440", make_id=dell.id, asset_type_id=laptop.id
    )
    masters.get_or_create_make(session, name="Dell", asset_type_id=monitor.id)
    masters.get_or_create_model(
        session, name="P2422H", make_id=dell.id, asset_type_id=monitor.id
    )
    session.commit()

    laptop_models = masters.list_models_for_context(
        session, make_id=dell.id, asset_type_id=laptop.id
    )
    monitor_models = masters.list_models_for_context(
        session, make_id=dell.id, asset_type_id=monitor.id
    )
    assert [m.name for m in laptop_models] == ["Latitude 5440"]
    assert [m.name for m in monitor_models] == ["P2422H"]


def test_next_number_highest_via_service(session):
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    assert laptop
    actor = session.query(User).filter(User.email == "admin@prosohm.com").first()
    assert actor

    it_asset_service.create_asset(
        session,
        actor=actor,
        asset_type_id=laptop.id,
        asset_number="PRO-LT-0140",
        make="Dell",
        model="GapLeft",
    )
    it_asset_service.create_asset(
        session,
        actor=actor,
        asset_type_id=laptop.id,
        asset_number="PRO-LT-0137",
        make="Dell",
        model="Lower",
    )
    preview = preview_next_asset_number(session, laptop)
    assert preview["highest_existing_sequence"] >= 140
    assert preview["sequence"] == preview["highest_existing_sequence"] + 1
    assert not str(preview["asset_number"]).endswith("138")
    assert preview["sequence"] == 141


def test_master_api_and_next_number(client, auth_headers, session):
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    assert laptop

    cats = client.get("/api/v1/it/master/categories", headers=auth_headers)
    assert cats.status_code == 200
    assert isinstance(cats.json(), list)

    make = client.post(
        "/api/v1/it/master/makes",
        headers=auth_headers,
        json={"name": "Lenovo", "asset_type_id": str(laptop.id)},
    )
    assert make.status_code == 201
    make_id = make.json()["id"]

    model = client.post(
        "/api/v1/it/master/models",
        headers=auth_headers,
        json={
            "name": "ThinkPad T14",
            "make_id": make_id,
            "asset_type_id": str(laptop.id),
        },
    )
    assert model.status_code == 201

    makes = client.get(
        f"/api/v1/it/master/makes?asset_type_id={laptop.id}",
        headers=auth_headers,
    )
    assert makes.status_code == 200
    assert any(m["name"] == "Lenovo" for m in makes.json())

    nxt = client.get(
        f"/api/v1/it/assets/next-number?asset_type_id={laptop.id}",
        headers=auth_headers,
    )
    assert nxt.status_code == 200
    body = nxt.json()
    assert "asset_number" in body
    assert body["sequence"] >= 1

    created = client.post(
        "/api/v1/it/assets",
        headers=auth_headers,
        json={
            "asset_type_id": str(laptop.id),
            "make_id": make_id,
            "model_id": model.json()["id"],
            "serial_number": "SN-TEST-1",
        },
    )
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["asset_number"]
    assert data.get("make") == "Lenovo"


def test_duplicate_asset_number_suggests_next(client, auth_headers, session):
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    actor = session.query(User).filter(User.email == "admin@prosohm.com").first()
    assert laptop and actor
    first = it_asset_service.create_asset(
        session,
        actor=actor,
        asset_type_id=laptop.id,
        make="HP",
        model="Elite",
    )
    clash = client.post(
        "/api/v1/it/assets",
        headers=auth_headers,
        json={
            "asset_type_id": str(laptop.id),
            "make": "HP",
            "model": "Elite2",
            "asset_number": first.asset_number,
        },
    )
    assert clash.status_code in {400, 422}
    detail = str(clash.json())
    assert "already exists" in detail.lower() or "suggested" in detail.lower()


def test_deactivate_make_keeps_asset_reference(client, auth_headers, session):
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    actor = session.query(User).filter(User.email == "admin@prosohm.com").first()
    assert laptop and actor
    make = masters.get_or_create_make(session, name="Acer", asset_type_id=laptop.id)
    asset = it_asset_service.create_asset(
        session,
        actor=actor,
        asset_type_id=laptop.id,
        make_id=make.id,
    )
    session.commit()

    deactivated = client.patch(
        f"/api/v1/it/master/makes/{make.id}/active",
        headers=auth_headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False
    assert deactivated.json()["usage_count"] == 1

    active = client.get("/api/v1/it/master/makes", headers=auth_headers).json()
    assert all(m["name"] != "Acer" for m in active)
    everything = client.get(
        "/api/v1/it/master/makes?active_only=false", headers=auth_headers
    ).json()
    assert any(m["name"] == "Acer" for m in everything)

    session.expire_all()
    kept = session.get(Asset, asset.id)
    assert kept is not None and kept.make_id == make.id

    reactivated = client.patch(
        f"/api/v1/it/master/makes/{make.id}/active",
        headers=auth_headers,
        json={"is_active": True},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True


def test_merge_makes_moves_assets_and_models(client, auth_headers, session):
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    actor = session.query(User).filter(User.email == "admin@prosohm.com").first()
    assert laptop and actor
    source = masters.get_or_create_make(session, name="HP Inc", asset_type_id=laptop.id)
    target = masters.get_or_create_make(
        session, name="Hewlett Packard", asset_type_id=laptop.id
    )
    model = masters.get_or_create_model(
        session, name="EliteBook 840", make_id=source.id, asset_type_id=laptop.id
    )
    asset = it_asset_service.create_asset(
        session,
        actor=actor,
        asset_type_id=laptop.id,
        make_id=source.id,
        model_id=model.id,
    )
    session.commit()

    merged = client.post(
        f"/api/v1/it/master/makes/{source.id}/merge",
        headers=auth_headers,
        json={"target_make_id": str(target.id)},
    )
    assert merged.status_code == 200, merged.text
    body = merged.json()
    assert body["assets_moved"] == 1
    assert body["models_moved"] == 1

    session.expire_all()
    moved = session.get(Asset, asset.id)
    assert moved is not None
    assert moved.make_id == target.id
    assert moved.make == "Hewlett Packard"
    assert session.get(AssetModel, model.id).make_id == target.id
    assert session.get(AssetMake, source.id).is_active is False


def test_asset_list_filters_by_master_and_category(client, auth_headers, session):
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    actor = session.query(User).filter(User.email == "admin@prosohm.com").first()
    assert laptop and actor
    make = masters.get_or_create_make(session, name="Asus", asset_type_id=laptop.id)
    model = masters.get_or_create_model(
        session, name="ExpertBook B9", make_id=make.id, asset_type_id=laptop.id
    )
    other_make = masters.get_or_create_make(session, name="MSI", asset_type_id=laptop.id)
    it_asset_service.create_asset(
        session,
        actor=actor,
        asset_type_id=laptop.id,
        make_id=make.id,
        model_id=model.id,
    )
    it_asset_service.create_asset(
        session,
        actor=actor,
        asset_type_id=laptop.id,
        make_id=other_make.id,
    )
    session.commit()

    by_make = client.get(
        f"/api/v1/it/assets?make_id={make.id}", headers=auth_headers
    ).json()
    assert by_make["total"] == 1
    assert by_make["items"][0]["make"] == "Asus"

    by_model = client.get(
        f"/api/v1/it/assets?model_id={model.id}", headers=auth_headers
    ).json()
    assert by_model["total"] == 1
    assert by_model["items"][0]["model"] == "ExpertBook B9"

    by_category = client.get(
        f"/api/v1/it/assets?category={laptop.category}", headers=auth_headers
    ).json()
    assert by_category["total"] >= 2

    no_match = client.get(
        "/api/v1/it/assets?category=furniture", headers=auth_headers
    ).json()
    assert no_match["total"] == 0


def test_next_numbers_preview_does_not_allocate(client, auth_headers, session):
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    assert laptop

    numbers = preview_next_asset_numbers(session, laptop.id, 3)
    assert len(numbers) == 3
    assert len(set(numbers)) == 3
    assert numbers[0] == preview_next_asset_number(session, laptop)["asset_number"]

    response = client.get(
        f"/api/v1/it/assets/next-numbers?asset_type_id={laptop.id}&count=4",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 4
    assert body["asset_numbers"][:3] == numbers

    # Preview is read-only: asking again returns the same suggestions.
    again = client.get(
        f"/api/v1/it/assets/next-numbers?asset_type_id={laptop.id}&count=4",
        headers=auth_headers,
    ).json()
    assert again["asset_numbers"] == body["asset_numbers"]
