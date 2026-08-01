"""HR past employees roster (leaving_date set)."""

from datetime import date, timedelta

from tests.conftest import login


def test_past_employees_lists_leavers(client, session):
    headers = login(client, "admin@prosohm.com")
    roles = client.get("/api/v1/roles", headers=headers).json()
    role_items = roles["items"] if isinstance(roles, dict) and "items" in roles else roles
    designer = next(r for r in role_items if r["name"] == "Designer")
    leaving = (date.today() - timedelta(days=3)).isoformat()

    create = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "role_id": designer["id"],
            "email": f"past.emp.{date.today().toordinal()}@prosohm.com",
            "password": "TempPass@123",
            "first_name": "Past",
            "last_name": "Employee",
            "is_active": True,
            "employment_type": "full_time",
        },
    )
    assert create.status_code == 201, create.text
    user_id = create.json()["id"]

    patch = client.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"leaving_date": leaving, "confirm_left_organisation": True},
    )
    assert patch.status_code == 200, patch.text

    listed = client.get("/api/v1/hr/past-employees", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    match = next((r for r in rows if r["user_id"] == user_id), None)
    assert match is not None
    assert match["leaving_date"] == leaving
    assert match["has_left"] is True
    assert match["is_archived"] is True

    search = client.get(
        "/api/v1/hr/past-employees",
        headers=headers,
        params={"search": "Past"},
    )
    assert search.status_code == 200
    assert any(r["user_id"] == user_id for r in search.json())
