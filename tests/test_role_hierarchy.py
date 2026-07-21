"""Role hierarchy endpoint + standardized-role permission aliasing."""

from __future__ import annotations


def test_hierarchy_groups_roles_by_department(client, auth_headers):
    resp = client.get("/api/v1/roles/hierarchy", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    depts = {d["department_code"]: d for d in data["departments"]}

    # Engineering department exists and contains standardized + legacy roles.
    assert "engineering" in depts
    eng_roles = [r["name"] for r in depts["engineering"]["roles"]]
    for expected in [
        "Director of Engineering",
        "Engineering Manager",
        "Design Leader",
        "Team Leader",
        "Senior Design Engineer",
        "Design Engineer",
        "Junior Design Engineer",
        "Trainee Design Engineer",
    ]:
        assert expected in eng_roles, f"{expected} missing from Engineering"

    # Ordered top -> bottom by rank.
    eng_ranks = [r["rank"] for r in depts["engineering"]["roles"]]
    assert eng_ranks == sorted(eng_ranks)

    # New Accounts department was seeded.
    assert "accounts" in depts
    acct_roles = [r["name"] for r in depts["accounts"]["roles"]]
    assert "Director of Accounts" in acct_roles


def test_create_role_places_it_in_hierarchy(client, auth_headers):
    hierarchy = client.get("/api/v1/roles/hierarchy", headers=auth_headers).json()
    it_dept = next(d for d in hierarchy["departments"] if d["department_code"] == "it")
    it_manager = next(r for r in it_dept["roles"] if r["name"] == "IT Manager")

    created = client.post(
        "/api/v1/roles",
        headers=auth_headers,
        json={
            "name": "Network Engineer",
            "description": "Network operations",
            "org_department_id": it_dept["department_id"],
            "rank": 7,
            "parent_role_id": it_manager["id"],
        },
    )
    assert created.status_code == 201, created.text

    hierarchy2 = client.get("/api/v1/roles/hierarchy", headers=auth_headers).json()
    it_dept2 = next(d for d in hierarchy2["departments"] if d["department_code"] == "it")
    node = next((r for r in it_dept2["roles"] if r["name"] == "Network Engineer"), None)
    assert node is not None
    assert node["parent_role_name"] == "IT Manager"
    assert node["rank"] == 7


def test_new_engineering_roles_alias_to_existing_permissions():
    from app.core.access_control import (
        default_modules_for_role,
        default_special_permissions_for_role,
    )
    from app.core.permissions import normalize_role_name

    assert normalize_role_name("Design Engineer") == "Designer"
    assert normalize_role_name("Senior Design Engineer") == "Senior Designer"
    assert normalize_role_name("Trainee Design Engineer") == "Junior Designer"

    assert default_modules_for_role("Design Engineer") == default_modules_for_role("Designer")
    assert default_special_permissions_for_role(
        "Senior Design Engineer"
    ) == default_special_permissions_for_role("Senior Designer")
