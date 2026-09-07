"""Finance → IT software license bridge end-to-end tests."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select

from app.models.enums import CostFrequency, CostNature, ExpensePaidBy
from app.models.finance import CostCentre, Expense
from app.models.it_operations import SoftwareCatalog, SoftwareLicensePool
from app.models.models import Team
from app.services import finance_software_bridge_service as bridge
from app.services import it_software_service
from tests.conftest import IDS


def _software_centre(session) -> CostCentre:
    centre = session.scalar(select(CostCentre).where(CostCentre.code == "SW_LICENSES"))
    assert centre is not None
    return centre


def _any_team(session) -> Team:
    team = session.scalar(select(Team).limit(1))
    assert team is not None
    return team


def test_renewal_period_math():
    start = date(2026, 3, 8)
    assert bridge.add_renewal_period(start, "monthly") == date(2026, 4, 8)
    assert bridge.add_renewal_period(start, "quarterly") == date(2026, 6, 8)
    assert bridge.add_renewal_period(start, "yearly") == date(2027, 3, 8)


def test_amc_calculation():
    assert bridge.calculate_amc_amount(Decimal("1000000"), Decimal("15")) == Decimal("150000.00")
    assert bridge.calculate_amc_amount(Decimal("1000000"), Decimal("20")) == Decimal("200000.00")


def test_finance_expense_creates_it_license_and_assignment_flow(client, session, auth_headers):
    centre = _software_centre(session)
    team = _any_team(session)

    created = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": str(centre.id),
            "name": "Siemens NX",
            "amount": "600000",
            "currency_code": "INR",
            "purchase_date": "2026-03-08",
            "frequency": "yearly",
            "nature": "opex",
            "paid_by": "prosohm",
            "team_id": str(team.id),
            "vendor_name": "Siemens",
            "create_it_license": True,
            "it_license": {
                "software_name": "Siemens NX",
                "vendor": "Siemens",
                "commercial_model": "subscription",
                "assignment_model": "named_user",
                "seat_count": 4,
                "renewal_frequency": "yearly",
            },
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["license_pool_id"]
    assert body["software_id"]
    assert body["it_software_name"] == "Siemens NX"
    assert body["it_license_code"]

    pool_id = UUID(body["license_pool_id"])
    licenses = client.get("/api/v1/it/software/licenses", headers=auth_headers)
    assert licenses.status_code == 200
    pool = next(item for item in licenses.json() if item["id"] == str(pool_id))
    assert pool["seat_count"] == 4
    assert pool["available_count"] == 4
    assert pool["assigned_count"] == 0
    assert pool["commercial_model"] == "subscription"
    assert pool["expiry_date"] == "2027-03-08"

    session.expire_all()
    pool_row = session.get(SoftwareLicensePool, pool_id)
    users = [IDS["user_binil"], IDS["user_anurag"], IDS["user_admin"], IDS["user_pm"]]
    for user_id in users:
        it_software_service.assign_license(
            session, license_pool_id=pool_row.id, user_id=user_id, assigned_date=date(2026, 9, 7)
        )
    session.commit()
    session.refresh(pool_row)
    assert it_software_service.available_seats(session, pool_row) == 0

    blocked = False
    try:
        it_software_service.assign_license(
            session,
            license_pool_id=pool_row.id,
            user_id=IDS["user_ranjith"],
            assigned_date=date(2026, 9, 7),
        )
    except Exception as exc:
        blocked = "No available" in str(exc)
    assert blocked

    active = it_software_service.list_assignments(session, license_pool_id=pool_row.id, active_only=True)
    it_software_service.unassign_license(session, active[0], released_date=date(2026, 9, 8))
    session.commit()
    session.refresh(pool_row)
    assert it_software_service.available_seats(session, pool_row) == 1

    term = client.post(
        f"/api/v1/it/software/licenses/{pool_id}/terminate",
        headers=auth_headers,
        json={"termination_date": "2026-09-15", "reason": "No longer needed"},
    )
    assert term.status_code == 200, term.text
    assert term.json()["status"] == "terminated"
    assert term.json()["available_count"] == 0

    again = client.post(
        "/api/v1/it/software/assignments",
        headers=auth_headers,
        json={"license_pool_id": str(pool_id), "user_id": str(IDS["user_binil"])},
    )
    assert again.status_code == 422, again.text
    assert "terminated" in again.text.lower()


def test_perpetual_amc_from_finance(client, session, auth_headers):
    centre = _software_centre(session)
    team = _any_team(session)
    created = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={
            "cost_centre_id": str(centre.id),
            "name": "AutoCAD",
            "amount": "1000000",
            "currency_code": "INR",
            "purchase_date": "2026-01-01",
            "frequency": "one_time",
            "nature": "opex",
            "paid_by": "prosohm",
            "team_id": str(team.id),
            "create_it_license": True,
            "it_license": {
                "software_name": "AutoCAD",
                "commercial_model": "perpetual",
                "seat_count": 2,
                "amc_required": True,
                "amc_percent": "15",
            },
        },
    )
    assert created.status_code == 201, created.text
    pool_id = created.json()["license_pool_id"]
    pool = client.get("/api/v1/it/software/licenses", headers=auth_headers).json()
    row = next(item for item in pool if item["id"] == pool_id)
    assert row["commercial_model"] == "perpetual"
    assert row["amc_required"] is True
    assert Decimal(str(row["amc_amount"])) == Decimal("150000.00")


def test_duplicate_software_master_reused(client, session, auth_headers):
    centre = _software_centre(session)
    team = _any_team(session)
    payload = {
        "cost_centre_id": str(centre.id),
        "name": "SolidWorks",
        "amount": "100000",
        "currency_code": "INR",
        "purchase_date": "2026-02-01",
        "frequency": "yearly",
        "nature": "opex",
        "paid_by": "prosohm",
        "team_id": str(team.id),
        "create_it_license": True,
        "it_license": {
            "software_name": "SolidWorks",
            "commercial_model": "subscription",
            "seat_count": 1,
            "renewal_frequency": "yearly",
        },
    }
    first = client.post("/api/v1/finance/expenses", headers=auth_headers, json=payload)
    assert first.status_code == 201, first.text
    second = client.post(
        "/api/v1/finance/expenses",
        headers=auth_headers,
        json={**payload, "purchase_date": "2026-03-01", "amount": "110000"},
    )
    assert second.status_code == 201, second.text
    assert first.json()["software_id"] == second.json()["software_id"]
    assert first.json()["license_pool_id"] != second.json()["license_pool_id"]
    count = session.scalars(
        select(SoftwareCatalog).where(SoftwareCatalog.name == "SolidWorks")
    ).all()
    assert len(count) == 1


def test_migration_candidates_list(client, session, auth_headers):
    centre = _software_centre(session)
    team = _any_team(session)
    raw = Expense(
        id=uuid4(),
        cost_centre_id=centre.id,
        name="NX Mach 3",
        nature=CostNature.opex,
        frequency=CostFrequency.yearly,
        currency_code="INR",
        amount=Decimal("600000"),
        base_amount_inr=Decimal("600000"),
        fx_rate=Decimal("1"),
        fx_date=date(2025, 12, 21),
        purchase_date=date(2025, 12, 21),
        next_renewal_date=date(2026, 12, 21),
        paid_by=ExpensePaidBy.prosohm,
        team_id=team.id,
        is_active=True,
    )
    session.add(raw)
    session.commit()

    listed = client.get(
        "/api/v1/finance/expenses/software-license-candidates", headers=auth_headers
    )
    assert listed.status_code == 200, listed.text
    ids = {item["expense_id"] for item in listed.json()}
    assert str(raw.id) in ids

    linked = client.post(
        f"/api/v1/finance/expenses/{raw.id}/create-it-license",
        headers=auth_headers,
        json={
            "software_name": "Siemens NX",
            "commercial_model": "subscription",
            "seat_count": 1,
            "renewal_frequency": "yearly",
        },
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["license_pool_id"]
