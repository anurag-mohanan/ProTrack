"""IT asset bulk selection / bulk-action API."""

from __future__ import annotations


def _first_asset_type_id(client, headers) -> str:
    response = client.get("/api/v1/it/asset-types", headers=headers)
    assert response.status_code == 200, response.text
    rows = response.json()
    assert rows, "asset types should be seeded"
    return rows[0]["id"]


def _create_asset(client, headers, *, asset_type_id: str | None = None, **extra):
    payload = {
        "asset_type_id": asset_type_id or _first_asset_type_id(client, headers),
        "make": extra.pop("make", "Dell"),
        "model": extra.pop("model", "Test"),
        "status": extra.pop("status", "available"),
        **extra,
    }
    response = client.post("/api/v1/it/assets", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_bulk_assign_location_and_status(client):
    headers = client.auth_headers
    a1 = _create_asset(client, headers, make="LocA")
    a2 = _create_asset(client, headers, make="LocB")

    preview = client.post(
        "/api/v1/it/assets/bulk-preview",
        headers=headers,
        json={"asset_ids": [a1["id"], a2["id"]], "action": "assign_location"},
    )
    assert preview.status_code == 200, preview.text

    result = client.post(
        "/api/v1/it/assets/bulk-action",
        headers=headers,
        json={
            "asset_ids": [a1["id"], a2["id"]],
            "action": "assign_location",
            "parameters": {"location": "Ground Floor"},
        },
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["updated"] == 2

    d1 = client.get(f"/api/v1/it/assets/{a1['id']}", headers=headers).json()
    d2 = client.get(f"/api/v1/it/assets/{a2['id']}", headers=headers).json()
    assert d1["location"] == "Ground Floor"
    assert d2["location"] == "Ground Floor"

    status_res = client.post(
        "/api/v1/it/assets/bulk-action",
        headers=headers,
        json={
            "asset_ids": [a1["id"], a2["id"]],
            "action": "change_status",
            "parameters": {"status": "maintenance"},
        },
    )
    assert status_res.status_code == 200, status_res.text
    assert status_res.json()["updated"] == 2


def test_bulk_delete_blocks_assigned(client, session):
    headers = client.auth_headers
    asset = _create_asset(client, headers)
    users = client.get("/api/v1/lookups/users", headers=headers)
    assert users.status_code == 200
    user_id = users.json()[0]["id"] if isinstance(users.json(), list) else users.json()["items"][0]["id"]

    assign = client.post(
        f"/api/v1/it/assets/{asset['id']}/assign",
        headers=headers,
        json={"user_id": user_id},
    )
    assert assign.status_code == 200, assign.text

    free = _create_asset(client, headers, make="Free")

    preview = client.post(
        "/api/v1/it/assets/bulk-preview",
        headers=headers,
        json={
            "asset_ids": [asset["id"], free["id"]],
            "action": "delete",
        },
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["blocked_count"] == 1
    assert body["eligible_count"] == 1

    blocked = client.post(
        "/api/v1/it/assets/bulk-action",
        headers=headers,
        json={
            "asset_ids": [asset["id"], free["id"]],
            "action": "delete",
            "options": {"allow_partial": False},
        },
    )
    assert blocked.status_code == 422

    partial = client.post(
        "/api/v1/it/assets/bulk-action",
        headers=headers,
        json={
            "asset_ids": [asset["id"], free["id"]],
            "action": "delete",
            "options": {"allow_partial": True},
        },
    )
    assert partial.status_code == 200, partial.text
    assert partial.json()["updated"] == 1
    assert partial.json()["skipped"] == 1


def test_bulk_renumber_duplicate_rolls_back(client):
    headers = client.auth_headers
    existing = _create_asset(client, headers, legacy_asset_number="IT-900")
    # Force known number via create preferred path if supported
    a1 = _create_asset(client, headers)
    a2 = _create_asset(client, headers)

    # Try renumbering onto existing asset_number
    target = existing["asset_number"]
    # Use starting that might collide — extract numeric if possible
    conflict = client.post(
        "/api/v1/it/assets/bulk-action",
        headers=headers,
        json={
            "asset_ids": [a1["id"], a2["id"]],
            "action": "renumber",
            "parameters": {
                "prefix": "",
                "starting_number": 0,
                "digits": 1,
                "suffix": target,  # first becomes "0" + target weird — better approach below
            },
        },
    )
    # Better: renumber both to start at the existing number using full prefix match
    # Reset with exact conflict: prefix="", starting such that first number equals existing
    # Use prefix that builds existing number exactly for first asset
    conflict2 = client.post(
        "/api/v1/it/assets/bulk-preview",
        headers=headers,
        json={
            "asset_ids": [a1["id"], a2["id"]],
            "action": "renumber",
            "parameters": {
                "prefix": existing["asset_number"],
                "starting_number": 0,
                "digits": 1,
                "suffix": "",
            },
        },
    )
    assert conflict2.status_code == 200, conflict2.text
    # first generated = existing["asset_number"] + "0" — not a collision with existing itself unless equal

    # Direct: set prefix to empty and use the exact existing number as generated by prefix+start
    # If existing is like "LAP-0001", generate that for a1
    number = existing["asset_number"]
    # Split into prefix (all but last digit group) is hard; instead create with preferred asset_number
    create_named = client.post(
        "/api/v1/it/assets",
        headers=headers,
        json={
            "asset_type_id": _first_asset_type_id(client, headers),
            "legacy_asset_number": "BULK-LOCK-1",
            "make": "Lock",
        },
    )
    assert create_named.status_code == 201

    # Renumber a1,a2 starting at a unique range then verify success
    ok = client.post(
        "/api/v1/it/assets/bulk-action",
        headers=headers,
        json={
            "asset_ids": [a1["id"], a2["id"]],
            "action": "renumber",
            "parameters": {
                "prefix": "BULK-",
                "starting_number": 7000,
                "digits": 4,
                "suffix": "",
            },
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["updated"] == 2

    d1 = client.get(f"/api/v1/it/assets/{a1['id']}", headers=headers).json()
    d2 = client.get(f"/api/v1/it/assets/{a2['id']}", headers=headers).json()
    assert d1["asset_number"] == "BULK-7000"
    assert d2["asset_number"] == "BULK-7001"
    assert d1.get("legacy_asset_number")

    # Duplicate against existing BULK-7000
    a3 = _create_asset(client, headers)
    dup = client.post(
        "/api/v1/it/assets/bulk-action",
        headers=headers,
        json={
            "asset_ids": [a3["id"]],
            "action": "renumber",
            "parameters": {
                "prefix": "BULK-",
                "starting_number": 7000,
                "digits": 4,
                "suffix": "",
            },
        },
    )
    assert dup.status_code == 422
    still = client.get(f"/api/v1/it/assets/{a3['id']}", headers=headers).json()
    assert still["asset_number"] != "BULK-7000"


def test_bulk_assign_user_requires_conflict_choice(client):
    headers = client.auth_headers
    available = _create_asset(client, headers)
    assigned = _create_asset(client, headers)
    users = client.get("/api/v1/lookups/users", headers=headers).json()
    user_rows = users if isinstance(users, list) else users.get("items", [])
    user_id = user_rows[0]["id"]

    assert (
        client.post(
            f"/api/v1/it/assets/{assigned['id']}/assign",
            headers=headers,
            json={"user_id": user_id},
        ).status_code
        == 200
    )

    # No option → 422
    blocked = client.post(
        "/api/v1/it/assets/bulk-action",
        headers=headers,
        json={
            "asset_ids": [available["id"], assigned["id"]],
            "action": "assign_user",
            "parameters": {"user_id": user_id},
        },
    )
    assert blocked.status_code == 422

    only_free = client.post(
        "/api/v1/it/assets/bulk-action",
        headers=headers,
        json={
            "asset_ids": [available["id"], assigned["id"]],
            "action": "assign_user",
            "parameters": {"user_id": user_id},
            "options": {"only_unassigned": True},
        },
    )
    assert only_free.status_code == 200, only_free.text
    assert only_free.json()["updated"] == 1
    assert only_free.json()["skipped"] == 1


def test_viewer_cannot_bulk_delete(client, session):
    from tests.test_it_operations import _grant_it_access, _make_user
    from tests.conftest import login
    from app.core.access_control import SPECIAL_VIEW_IT_OPERATIONS

    headers = client.auth_headers
    asset = _create_asset(client, headers)

    viewer = _make_user(session, "Designer", "it-bulk-viewer@prosohm.com")
    _grant_it_access(session, viewer, specials=[SPECIAL_VIEW_IT_OPERATIONS])
    vheaders = login(client, viewer.email)

    response = client.post(
        "/api/v1/it/assets/bulk-action",
        headers=vheaders,
        json={
            "asset_ids": [asset["id"]],
            "action": "delete",
        },
    )
    assert response.status_code == 422
    assert "manage_it_assets" in response.text or "permission" in response.text.lower()


def test_asset_ids_respects_filters(client):
    headers = client.auth_headers
    _create_asset(client, headers, make="FiltAvail")
    target = _create_asset(client, headers, make="FiltMaint")
    client.patch(
        f"/api/v1/it/assets/{target['id']}",
        headers=headers,
        json={"status": "maintenance"},
    )

    ids = client.get(
        "/api/v1/it/assets/ids",
        headers=headers,
        params={"status": "maintenance", "inventory_scope": "all"},
    )
    assert ids.status_code == 200, ids.text
    body = ids.json()
    assert target["id"] in [str(i) for i in body["ids"]] or target["id"] in body["ids"]
    assert body["total"] >= 1
