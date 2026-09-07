"""Connected ProTrack Waves 4–5 — IT gaps, hire impact, OCR fallback."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models.it_operations import (
    Asset,
    AssetAssignment,
    AssetType,
    Computer,
    EmployeeSoftwareRequirement,
    SoftwareAssignment,
    SoftwareCatalog,
    SoftwareLicensePool,
)
from app.models.models import Team, TeamMember, User
from app.services import resource_it_gap_service
from app.services.finance.hire_impact_service import estimate_hire_impact
from app.services.finance import pdf_ocr
from tests.conftest import IDS


def _laptop_type(session) -> AssetType:
    laptop = session.scalars(select(AssetType).where(AssetType.code == "LAPTOP")).first()
    assert laptop is not None
    return laptop


def _make_computer(session, *, asset_number: str, status: str = "available", cost=None):
    asset = Asset(
        id=uuid.uuid4(),
        asset_number=asset_number,
        asset_type_id=_laptop_type(session).id,
        status=status,
        purchase_cost=cost,
        is_deleted=False,
    )
    session.add(asset)
    session.flush()
    computer = Computer(
        id=uuid.uuid4(),
        asset_id=asset.id,
        computer_name=f"PC-{asset_number}",
    )
    session.add(computer)
    session.flush()
    return asset, computer


def _make_software(session, *, name: str) -> SoftwareCatalog:
    software = SoftwareCatalog(id=uuid.uuid4(), name=name, is_active=True)
    session.add(software)
    session.flush()
    return software


def _active_user(session) -> User:
    user = session.scalars(
        select(User).where(
            User.is_active.is_(True),
            User.is_deleted.is_(False),
            User.is_archived.is_(False),
        )
    ).first()
    assert user is not None
    return user


# ---------------------------------------------------------------------------
# Wave 4 — license demand gaps
# ---------------------------------------------------------------------------


def test_license_demand_gap_structure(session):
    user = _active_user(session)
    software = _make_software(session, name="NX CAD")
    session.add(
        EmployeeSoftwareRequirement(
            id=uuid.uuid4(),
            user_id=user.id,
            software_id=software.id,
            requirement_level="required",
        )
    )
    session.add(
        SoftwareLicensePool(
            id=uuid.uuid4(),
            software_id=software.id,
            seat_count=1,
            license_type="named_user",
        )
    )
    session.commit()

    gaps = resource_it_gap_service.get_resource_gaps(session)

    assert set(gaps) >= {
        "users_without_computer",
        "users_missing_licenses",
        "license_demand",
        "oversubscribed_software",
        "expiring_pools",
        "spare_computers",
        "alerts",
    }
    demand = {row["software_id"]: row for row in gaps["license_demand"]}
    assert software.id in demand
    row = demand[software.id]
    assert row["software_name"] == "NX CAD"
    assert row["required_headcount"] >= 1
    assert row["unmet_headcount"] >= 1
    assert row["has_pool"] is True
    assert row["seat_count"] == 1
    assert row["peak_estimate"] == row["required_headcount"]

    missing_user_ids = {row["user_id"] for row in gaps["users_missing_licenses"]}
    assert user.id in missing_user_ids
    assert any(alert["code"] == "users_missing_licenses" for alert in gaps["alerts"])


def test_gaps_flag_software_without_pool_and_clear_when_licensed(session):
    user = _active_user(session)
    unpooled = _make_software(session, name="Unpooled Tool")
    pooled = _make_software(session, name="Pooled Tool")
    pool = SoftwareLicensePool(
        id=uuid.uuid4(),
        software_id=pooled.id,
        seat_count=5,
        license_type="named_user",
    )
    session.add_all(
        [
            pool,
            EmployeeSoftwareRequirement(
                id=uuid.uuid4(),
                user_id=user.id,
                software_id=unpooled.id,
                requirement_level="required",
            ),
            EmployeeSoftwareRequirement(
                id=uuid.uuid4(),
                user_id=user.id,
                software_id=pooled.id,
                requirement_level="required",
            ),
        ]
    )
    session.flush()
    session.add(
        SoftwareAssignment(
            id=uuid.uuid4(),
            license_pool_id=pool.id,
            user_id=user.id,
            assigned_date=date.today(),
        )
    )
    session.commit()

    gaps = resource_it_gap_service.get_resource_gaps(session)
    no_pool_ids = {row["software_id"] for row in gaps["software_without_pool"]}
    assert unpooled.id in no_pool_ids
    assert pooled.id not in no_pool_ids

    missing = {
        row["user_id"]: [item["software_id"] for item in row["missing"]]
        for row in gaps["users_missing_licenses"]
    }
    assert pooled.id not in missing.get(user.id, [])


def test_expiring_pool_raises_alert(session):
    software = _make_software(session, name="Expiring Suite")
    session.add(
        SoftwareLicensePool(
            id=uuid.uuid4(),
            software_id=software.id,
            seat_count=2,
            license_type="subscription",
            expiry_date=date.today() + timedelta(days=10),
        )
    )
    session.commit()

    gaps = resource_it_gap_service.get_resource_gaps(session)
    assert any(row["software_id"] == software.id for row in gaps["expiring_pools"])
    assert any(alert["code"] == "licenses_expiring" for alert in gaps["alerts"])


def test_computer_availability_counts_open_assignment(session):
    asset, _ = _make_computer(session, asset_number="PRO-LT-9001")
    user = _active_user(session)
    session.commit()

    before = resource_it_gap_service.get_computer_availability(session)
    spare_before = before["spare_computers"]

    session.add(
        AssetAssignment(
            id=uuid.uuid4(),
            asset_id=asset.id,
            assigned_to_user_id=user.id,
            assigned_by_user_id=IDS["user_admin"],
            assigned_date=date.today(),
        )
    )
    session.commit()

    after = resource_it_gap_service.get_computer_availability(session)
    assert after["spare_computers"] == spare_before - 1
    assert after["assigned_computers"] == before["assigned_computers"] + 1


# ---------------------------------------------------------------------------
# Wave 4 — matrix endpoint
# ---------------------------------------------------------------------------


def test_it_matrix_endpoint_returns_200(client, auth_headers):
    today = date.today().isoformat()
    response = client.get(
        f"/api/v1/dashboard/resource-planning/it-matrix?from_date={today}&to_date={today}",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["from_date"] == today
    assert body["headcount"] == len(body["rows"])
    assert body["ready_count"] + body["not_ready_count"] == body["headcount"]
    for row in body["rows"]:
        assert set(row) >= {"user_id", "full_name", "has_computer", "is_compliant"}


def test_it_gaps_endpoint_returns_200(client, auth_headers):
    response = client.get(
        "/api/v1/dashboard/resource-planning/it-gaps", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "alerts" in body
    assert isinstance(body["license_demand"], list)


def test_matrix_marks_person_with_computer_and_license(session):
    team = Team(id=uuid.uuid4(), name=f"Readiness {uuid.uuid4().hex[:4]}", is_active=True)
    session.add(team)
    session.flush()
    user = _active_user(session)
    session.add(TeamMember(id=uuid.uuid4(), team_id=team.id, user_id=user.id))
    asset, _ = _make_computer(session, asset_number="PRO-LT-9101")
    session.add(
        AssetAssignment(
            id=uuid.uuid4(),
            asset_id=asset.id,
            assigned_to_user_id=user.id,
            assigned_by_user_id=IDS["user_admin"],
            assigned_date=date.today() - timedelta(days=1),
        )
    )
    session.commit()

    matrix = resource_it_gap_service.get_resource_matrix(
        session,
        from_date=date.today(),
        to_date=date.today(),
        team_id=team.id,
    )
    assert matrix["headcount"] == 1
    row = matrix["rows"][0]
    assert row["user_id"] == user.id
    assert row["has_computer"] is True
    assert row["is_ready"] is True


# ---------------------------------------------------------------------------
# Wave 5A — hire impact
# ---------------------------------------------------------------------------


def test_hire_impact_returns_zeros_without_data(session):
    impact = estimate_hire_impact(session, headcount=0)
    assert impact["headcount"] == 0
    assert impact["required_computers"] == 0
    assert impact["computers_to_procure"] == 0
    assert impact["required_license_seats"] == 0


def test_hire_impact_never_invents_costs(session):
    user = _active_user(session)
    software = _make_software(session, name="Costless CAM")
    session.add_all(
        [
            EmployeeSoftwareRequirement(
                id=uuid.uuid4(),
                user_id=user.id,
                software_id=software.id,
                requirement_level="required",
            ),
            SoftwareLicensePool(
                id=uuid.uuid4(),
                software_id=software.id,
                seat_count=3,
                license_type="named_user",
                cost=None,
            ),
        ]
    )
    session.commit()

    impact = estimate_hire_impact(session, headcount=2)
    row = next(r for r in impact["software"] if r["software_id"] == software.id)
    assert row["seats_needed"] == 2
    assert row["cost_per_seat"] is None
    assert row["estimated_cost"] is None
    assert row["cost_basis"] == "not_recorded"
    assert any("no cost recorded" in w for w in impact["warnings"])


def test_hire_impact_uses_recorded_costs(session):
    user = _active_user(session)
    software = _make_software(session, name="Priced Suite")
    session.add_all(
        [
            EmployeeSoftwareRequirement(
                id=uuid.uuid4(),
                user_id=user.id,
                software_id=software.id,
                requirement_level="required",
            ),
            SoftwareLicensePool(
                id=uuid.uuid4(),
                software_id=software.id,
                seat_count=4,
                license_type="subscription",
                cost=Decimal("4800.00"),
                currency_code="INR",
            ),
        ]
    )
    _make_computer(session, asset_number="PRO-LT-9201", cost=Decimal("60000.00"))
    session.commit()

    impact = estimate_hire_impact(session, headcount=2)
    row = next(r for r in impact["software"] if r["software_id"] == software.id)
    assert row["cost_per_seat"] == Decimal("1200.00")
    assert row["estimated_cost"] == Decimal("2400.00")
    assert row["estimated_monthly_cost"] == Decimal("200.00")
    assert row["cost_basis"] == "annual_subscription"
    assert impact["required_computers"] == 2
    assert impact["estimated_hardware_cost"] is not None


def test_hire_impact_endpoint(client, auth_headers):
    response = client.get("/api/v1/finance/hire-impact?headcount=3", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["headcount"] == 3
    assert body["required_computers"] == 3
    assert isinstance(body["assumptions"], list)


# ---------------------------------------------------------------------------
# Wave 5C — OCR fallback
# ---------------------------------------------------------------------------


def test_ocr_helper_reports_unavailable_when_libs_missing(monkeypatch):
    monkeypatch.setattr(pdf_ocr, "ocr_available", lambda: False)
    outcome = pdf_ocr.extract_text_with_optional_ocr(b"%PDF-scan", existing_text="")
    assert outcome.ocr_used is False
    assert outcome.ocr_available is False
    assert pdf_ocr.OCR_UNAVAILABLE_MESSAGE in outcome.warnings


def test_ocr_skipped_when_text_already_extracted():
    text = "Invoice Number: INV-1001\nGrand Total: 1,000.00\nBill To: Acme Ltd"
    outcome = pdf_ocr.extract_text_with_optional_ocr(b"%PDF", existing_text=text)
    assert outcome.ocr_used is False
    assert outcome.ocr_attempted is False
    assert outcome.text == text


def test_ocr_pdf_text_returns_message_without_libraries(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name in {"pdf2image", "pytesseract"}:
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    outcome = pdf_ocr.ocr_pdf_text(b"%PDF-scan")
    assert outcome.ocr_used is False
    assert outcome.warnings == [pdf_ocr.OCR_UNAVAILABLE_MESSAGE]


def test_quote_extract_reports_ocr_unavailable_for_scanned_pdf(session, monkeypatch):
    from app.services.finance import quote_pdf_import_service

    monkeypatch.setattr(
        quote_pdf_import_service,
        "extract_prosohm_quote_text",
        lambda content: "",
    )
    monkeypatch.setattr(pdf_ocr, "ocr_available", lambda: False)

    result = quote_pdf_import_service.extract_quote_pdf(
        session, content=b"%PDF-scan", filename="scan.pdf"
    )
    assert result["text_extractable"] is False
    assert result["ocr_used"] is False
    assert any(pdf_ocr.OCR_UNAVAILABLE_MESSAGE in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# Wave 5B — profile enrichment
# ---------------------------------------------------------------------------


def test_employee_it_snapshot_aggregates_reads(session):
    user = _active_user(session)
    asset, computer = _make_computer(session, asset_number="PRO-LT-9301")
    software = _make_software(session, name="Snapshot CAD")
    pool = SoftwareLicensePool(
        id=uuid.uuid4(), software_id=software.id, seat_count=2, license_type="named_user"
    )
    session.add(pool)
    session.flush()
    session.add_all(
        [
            AssetAssignment(
                id=uuid.uuid4(),
                asset_id=asset.id,
                assigned_to_user_id=user.id,
                assigned_by_user_id=IDS["user_admin"],
                assigned_date=date.today(),
            ),
            SoftwareAssignment(
                id=uuid.uuid4(),
                license_pool_id=pool.id,
                user_id=user.id,
                assigned_date=date.today(),
            ),
        ]
    )
    session.commit()

    snapshot = resource_it_gap_service.get_employee_it_snapshot(session, user.id)
    assert snapshot["computer"]["computer_name"] == computer.computer_name
    assert [row["software_name"] for row in snapshot["software"]] == ["Snapshot CAD"]
    # No shift module is installed — the optional lookup degrades to None.
    assert snapshot["shift"] is None
    assert snapshot["is_compliant"] is True


def test_it_dashboard_summary_exposes_gap_counts(client, auth_headers):
    response = client.get("/api/v1/it/dashboard", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    for key in (
        "gap_users_without_computer",
        "gap_users_missing_licenses",
        "gap_oversubscribed_software",
        "gap_software_without_pool",
        "gap_spare_computers",
    ):
        assert key in body
        assert isinstance(body[key], int)
