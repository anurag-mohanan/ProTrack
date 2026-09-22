"""Smart computer ranking, duplicate checks, and assignment preview."""

from __future__ import annotations

from app.models.it_operations import AssetType, IPAddress
from app.models.models import User
from app.services import it_asset_service, it_computer_recommend_service as recommend
from app.services import it_network_service


def test_duplicate_check_flags_computer_name_and_serial(session):
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    actor = session.query(User).filter(User.email == "admin@prosohm.com").first()
    assert laptop and actor
    computer = it_asset_service.create_computer(
        session,
        actor=actor,
        asset_type_id=laptop.id,
        computer_name="PROENG300",
        serial_number="SN-DUP-300",
        mac_address="AA:BB:CC:DD:EE:30",
    )
    asset = it_asset_service.get_asset(session, computer.asset_id)
    assert asset
    it_asset_service.update_asset(session, asset, actor=actor, service_tag="SVCTAG300")
    assert computer.computer_name == "PROENG300"

    result = recommend.check_duplicates(
        session,
        computer_name="PROENG300",
        serial_number="SN-DUP-300",
        service_tag="SVCTAG300",
        mac_address="AA:BB:CC:DD:EE:30",
    )
    fields = {row["field"] for row in result["conflicts"]}
    assert "computer_name" in fields
    assert "serial_number" in fields
    assert "service_tag" in fields
    assert "mac_address" in fields
    assert result["ok"] is False


def test_recommend_computers_ranks_available(session):
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    actor = session.query(User).filter(User.email == "admin@prosohm.com").first()
    assert laptop and actor
    it_asset_service.create_computer(
        session,
        actor=actor,
        asset_type_id=laptop.id,
        computer_name="PROENG400",
        location="Bangalore",
    )
    ranked = recommend.recommend_computers(session, user_id=actor.id, limit=5)
    assert ranked["recommendations"]
    top = ranked["recommendations"][0]
    assert top["computer_name"]
    assert top["score"] >= 100
    assert any("Available" in reason for reason in top["reasons"])


def test_assignment_preview_blocks_retired(session):
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    actor = session.query(User).filter(User.email == "admin@prosohm.com").first()
    computer = it_asset_service.create_computer(
        session, actor=actor, asset_type_id=laptop.id, computer_name="PROENG401"
    )
    asset = it_asset_service.get_asset(session, computer.asset_id)
    assert asset
    it_asset_service.update_asset(session, asset, actor=actor, status="retired")
    preview = recommend.assignment_preview(session, asset_id=asset.id, user_id=actor.id)
    assert preview["ok"] is False
    assert any(row["code"] == "status" and row["ok"] is False for row in preview["checks"])


def test_duplicate_ip_conflict_message_names_computer(session):
    actor = session.query(User).filter(User.email == "admin@prosohm.com").first()
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    assert actor and laptop
    network = it_network_service.create_network(
        session, actor=actor, name="Reco LAN", cidr="10.40.0.0/24"
    )
    ip = (
        session.query(IPAddress)
        .filter(IPAddress.network_id == network.id, IPAddress.address == "10.40.0.10")
        .first()
    )
    assert ip
    it_asset_service.create_computer(
        session,
        actor=actor,
        asset_type_id=laptop.id,
        computer_name="PROENG410",
        ip_address_id=ip.id,
    )
    result = recommend.check_duplicates(session, ip_address="10.40.0.10")
    assert result["ok"] is False
    ip_conflict = next(row for row in result["conflicts"] if row["field"] == "ip_address")
    assert "PROENG410" in ip_conflict["message"]
