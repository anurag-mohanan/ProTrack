from tests.conftest import IDS, login
from app.models.models import User


def test_update_allows_unchanged_legacy_design_leader(client, session):
    """Editing an unrelated field must succeed even when the project's existing
    design leader no longer holds the Design Leader role (e.g. imported data).

    The edit form resubmits the full reference set, so the fix must compare
    against the stored values rather than mere presence in the payload.
    """
    leader = session.get(User, IDS["user_anurag"])
    leader.role_id = IDS["role_pm"]  # demote to Engineering Manager
    session.commit()

    headers = login(client, "admin@prosohm.com")
    project_id = client.project_id
    resp = client.patch(
        f"/api/v1/projects/{project_id}",
        json={
            "customer_id": str(IDS["customer"]),
            "customer_contact_id": str(IDS["contact"]),
            "design_leader_id": str(IDS["user_anurag"]),
            "designer_id": str(IDS["user_binil"]),
            "notes": "edited note",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["notes"] == "edited note"


def test_update_rejects_newly_assigned_invalid_design_leader(client):
    """Actually changing the design leader to a user without the Design Leader
    role must still be rejected."""
    headers = login(client, "admin@prosohm.com")
    project_id = client.project_id
    resp = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"design_leader_id": str(IDS["user_binil"])},  # Designer role
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


def test_update_allows_changing_customer_with_matching_contact(client, session):
    """Changing the customer to another customer with a valid contact succeeds."""
    from app.models.models import Customer, Contact
    import uuid

    new_customer_id = uuid.uuid4()
    new_contact_id = uuid.uuid4()
    session.add(Customer(id=new_customer_id, name="New Co", code="NEW", is_active=True))
    session.add(
        Contact(
            id=new_contact_id,
            customer_id=new_customer_id,
            first_name="Jane",
            last_name="Doe",
            is_primary=True,
        )
    )
    session.commit()

    headers = login(client, "admin@prosohm.com")
    project_id = client.project_id
    resp = client.patch(
        f"/api/v1/projects/{project_id}",
        json={
            "customer_id": str(new_customer_id),
            "customer_contact_id": str(new_contact_id),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
