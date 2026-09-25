"""HR & IT redesign acceptance: seats, offboarding, data quality, IT/HR dashboards."""

from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.models.it_operations import AssetType, WorkstationPackageAssignment
from app.models.models import Ticket, User
from app.models.resource_shifts import ResourceShift
from app.services import it_asset_service, it_data_quality_service, it_deprovision_service
from app.services import resource_shift_service as shifts
from app.services import ticketing_service
from app.services import workstation_package_service as packages
from tests.conftest import IDS, login


def _type(session, code: str, name: str, category: str) -> AssetType:
    existing = session.scalar(select(AssetType).where(AssetType.code == code))
    if existing:
        return existing
    row = AssetType(id=uuid4(), code=code, name=name, category=category, is_active=True)
    session.add(row)
    session.commit()
    return row


def _shift(session, code: str) -> ResourceShift:
    shifts.ensure_company_standard_shifts(session)
    row = session.scalar(select(ResourceShift).where(ResourceShift.code == code))
    assert row is not None
    return row


def _seat(session, admin: User, *, monitors: int = 2):
    desktop = _type(session, "DESKTOP", "Desktop", "computer")
    monitor = _type(session, "MONITOR", "Monitor", "peripheral")
    computer = it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=desktop.id,
        asset_number=f"ENG-WS-{uuid4().hex[:5].upper()}",
        commit=True,
    )
    roles = ["PRIMARY_MONITOR", "SECONDARY_MONITOR"]
    members = []
    for index in range(monitors):
        mon = it_asset_service.create_asset(
            session,
            actor=admin,
            asset_type_id=monitor.id,
            asset_number=f"MON-{uuid4().hex[:5].upper()}",
            commit=True,
        )
        members.append({"asset_id": mon.id, "role": roles[index]})
    package = packages.create_package(
        session,
        actor=admin,
        code=f"VSEAT-{computer.asset_number}",
        name=f"Seat {computer.asset_number}",
        primary_computer_asset_id=computer.id,
        computer_type="ENG_WS",
        members=members,
        commit=True,
    )
    return package, computer


def test_vseat_first_only_is_found_for_second_shift_not_general(session):
    first, second, general = (_shift(session, c) for c in ("FIRST", "SECOND", "GENERAL"))
    admin = session.get(User, IDS["user_admin"])
    anurag = session.get(User, IDS["user_anurag"])
    package, computer = _seat(session, admin)
    packages.assign_package(
        session, package, actor=admin, user_id=anurag.id, shift_id=first.id, commit=True
    )

    for_second = packages.find_available_packages(
        session, on_date=date.today(), shift_id=second.id, computer_type="ENG_WS", monitor_quantity=2
    )
    assert str(package.id) in {row["id"] for row in for_second["exact_matches"]}

    for_general = packages.find_available_packages(
        session, on_date=date.today(), shift_id=general.id, computer_type="ENG_WS", monitor_quantity=2
    )
    assert str(package.id) not in {row["id"] for row in for_general["exact_matches"]}

    enrich = packages.inventory_availability_for_asset(session, computer)
    by_code = {row["shift_code"]: row["status"] for row in enrich["shift_availability"]}
    assert by_code["FIRST"] == "ASSIGNED"
    assert by_code["SECOND"] == "AVAILABLE"
    assert by_code["GENERAL"] == "CONFLICT"


def test_offboarding_releases_only_the_leavers_seat_shift(session):
    first, second = _shift(session, "FIRST"), _shift(session, "SECOND")
    admin = session.get(User, IDS["user_admin"])
    anurag = session.get(User, IDS["user_anurag"])
    binil = session.get(User, IDS["user_binil"])
    package, _computer = _seat(session, admin)
    packages.assign_package(session, package, actor=admin, user_id=anurag.id, shift_id=first.id, commit=True)
    packages.assign_package(session, package, actor=admin, user_id=binil.id, shift_id=second.id, commit=True)

    leaving = date.today() + timedelta(days=10)
    binil.leaving_date = leaving
    session.commit()

    ticket = it_deprovision_service.ensure_offboard_tasks(session, user=binil, actor=admin)
    session.commit()
    assert ticket is not None
    assert ticket.due_date == leaving
    assert package.code in (ticket.description or "")

    it_asset_service.return_assets_for_user(session, user_id=binil.id, by_user=admin)
    session.expire_all()

    open_seat_rows = session.scalars(
        select(WorkstationPackageAssignment).where(
            WorkstationPackageAssignment.user_id == binil.id,
            WorkstationPackageAssignment.status == "ACTIVE",
        )
    ).all()
    assert open_seat_rows == []
    second_avail = packages.package_shift_availability(
        session, package, shift_id=second.id, on_date=date.today()
    )
    assert second_avail["status"] == "AVAILABLE", second_avail
    assert packages.package_shift_availability(
        session, package, shift_id=first.id, on_date=date.today()
    )["status"] == "ASSIGNED"
    assert it_asset_service.list_assets_for_user(session, binil.id) == []


def test_data_quality_flags_duplicate_serials_and_inactive_seat_holders(session):
    first = _shift(session, "FIRST")
    admin = session.get(User, IDS["user_admin"])
    ranjith = session.get(User, IDS["user_ranjith"])
    monitor = _type(session, "MONITOR", "Monitor", "peripheral")
    duplicates = [
        it_asset_service.create_asset(
            session,
            actor=admin,
            asset_type_id=monitor.id,
            asset_number=f"DUP-{uuid4().hex[:5].upper()}",
            serial_number=f"SN-{index}",
            commit=True,
        )
        for index in range(2)
    ]
    # Imports can bypass create-time uniqueness; the report must still catch it.
    duplicates[1].serial_number = duplicates[0].serial_number
    session.commit()
    package, _computer = _seat(session, admin, monitors=1)
    packages.assign_package(session, package, actor=admin, user_id=ranjith.id, shift_id=first.id, commit=True)
    ranjith.is_active = False
    session.commit()

    report = it_data_quality_service.build_data_quality_report(session)
    by_code = {row["code"]: row for row in report["issues"]}
    dup = by_code["duplicate_asset_identifiers"]
    assert dup["count"] >= 2
    assert all(s["href"].startswith("/it/assets?search=") for s in dup["samples"])
    seat_issue = by_code["seat_assigned_to_inactive_employee"]
    assert seat_issue["count"] == 1
    assert seat_issue["samples"][0]["href"].startswith(f"/it/accounts?user={ranjith.id}")


def test_it_dashboard_warranty_window_and_overdue_requests(client, session):
    admin = session.get(User, IDS["user_admin"])
    monitor = _type(session, "MONITOR", "Monitor", "peripheral")
    it_asset_service.create_asset(
        session,
        actor=admin,
        asset_type_id=monitor.id,
        asset_number=f"WAR-{uuid4().hex[:5].upper()}",
        warranty_expiry=date.today() + timedelta(days=20),
        commit=True,
    )
    session.add(
        Ticket(
            ticket_number=ticketing_service.next_ticket_number(session),
            title="Broken keyboard",
            category="it",
            priority="medium",
            status="in_progress",
            requester_id=admin.id,
            due_date=date.today() - timedelta(days=1),
        )
    )
    session.commit()

    wide = client.get("/api/v1/it/dashboard?warranty_days=30", headers=client.auth_headers)
    assert wide.status_code == 200, wide.text
    narrow = client.get("/api/v1/it/dashboard?warranty_days=7", headers=client.auth_headers)
    assert narrow.status_code == 200, narrow.text
    assert wide.json()["warranty_expiring_assets"] == narrow.json()["warranty_expiring_assets"] + 1
    assert wide.json()["warranty_window_days"] == 30
    assert wide.json()["overdue_it_requests"] >= 1

    listed = client.get(
        "/api/v1/it/assets?warranty_status=expiring_soon&warranty_within_days=30",
        headers=client.auth_headers,
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == wide.json()["warranty_expiring_assets"]

    bad = client.get("/api/v1/it/dashboard?warranty_days=15", headers=client.auth_headers)
    assert bad.status_code == 400


def test_hr_overview_counts_match_drilldowns(client, session):
    today = date.today()
    ranjith = session.get(User, IDS["user_ranjith"])
    binil = session.get(User, IDS["user_binil"])
    anurag = session.get(User, IDS["user_anurag"])
    ranjith.joining_date = today
    binil.leaving_date = today + timedelta(days=5)
    anurag.designation = "QA Probe Designer"
    session.commit()

    response = client.get("/api/v1/hr/dashboard/overview", headers=client.auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    cards = body["cards"]
    assert cards["new_joiners"] >= 1
    assert cards["upcoming_exits"] >= 1

    for segment, card in (("joiners", "new_joiners"), ("upcoming_exits", "upcoming_exits"), ("active", "active_employees")):
        rows = client.get(
            f"/api/v1/hr/dashboard/employees?segment={segment}", headers=client.auth_headers
        )
        assert rows.status_code == 200, rows.text
        assert len(rows.json()) == cards[card], segment
    joiner_ids = {
        r["user_id"]
        for r in client.get(
            "/api/v1/hr/dashboard/employees?segment=joiners", headers=client.auth_headers
        ).json()
    }
    assert str(ranjith.id) in joiner_ids

    for row in body["trend"]:
        assert row["closing"] == row["opening"] + row["joiners"] - row["exits"]
    assert body["trend"][-1]["month"] == today.strftime("%Y-%m")

    action_codes = {a["code"] for a in body["actions"]}
    assert "exits_without_exit_process" in action_codes
    assert cards["open_hr_actions"] == sum(a["count"] for a in body["actions"])

    for group in body["breakdowns"].values():
        assert sum(r["count"] for r in group) == cards["active_employees"]

    filtered = client.get(
        "/api/v1/hr/dashboard/overview?designation=QA%20Probe%20Designer",
        headers=client.auth_headers,
    ).json()
    assert filtered["cards"]["active_employees"] == 1

    forbidden = client.get(
        "/api/v1/hr/dashboard/overview", headers=login(client, "binil@prosohm.com")
    )
    assert forbidden.status_code == 403
