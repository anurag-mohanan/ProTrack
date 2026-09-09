"""Computer name and IP suggestions from live inventory — no hardcoded sequences."""

from __future__ import annotations

from app.models.it_operations import AssetType, IPAddress, Network
from app.models.models import User
from app.services import it_asset_service, it_computer_suggest_service as suggest
from app.services import it_network_service


def test_suggest_computer_name_follows_existing_pattern(session):
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    actor = session.query(User).filter(User.email == "admin@prosohm.com").first()
    assert laptop and actor

    for name in ("PROENG021", "PROENG022", "PROENG025"):
        it_asset_service.create_computer(
            session,
            actor=actor,
            asset_type_id=laptop.id,
            computer_name=name,
        )

    preview = suggest.suggest_computer_name(session, type_code="PC")
    assert preview["computer_name"] == "PROENG026"
    assert preview["source"] == "existing_names"
    assert "PROENG" in preview["message"]

    taken = it_asset_service.create_computer(
        session,
        actor=actor,
        asset_type_id=laptop.id,
        computer_name="PROENG026",
    )
    assert taken.computer_name == "PROENG026"

    preview2 = suggest.suggest_computer_name(session, type_code="PC")
    assert preview2["computer_name"] == "PROENG027"


def test_duplicate_computer_name_rejected(session):
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    actor = session.query(User).filter(User.email == "admin@prosohm.com").first()
    it_asset_service.create_computer(
        session, actor=actor, asset_type_id=laptop.id, computer_name="PROENG100"
    )
    try:
        it_asset_service.create_computer(
            session, actor=actor, asset_type_id=laptop.id, computer_name="PROENG100"
        )
        assert False, "expected duplicate name to fail"
    except Exception as exc:
        assert "PROENG100" in str(exc)


def test_suggest_ip_uses_available_pool_not_name_equals_octet(session):
    actor = session.query(User).filter(User.email == "admin@prosohm.com").first()
    assert actor
    network = it_network_service.create_network(
        session,
        actor=actor,
        name="Engineering LAN",
        cidr="192.168.20.0/24",
    )
    # Skip auto-generated low addresses; mark a gap then used range 121-125.
    ips = list(
        session.query(IPAddress).filter(IPAddress.network_id == network.id).all()
    )
    by_addr = {ip.address: ip for ip in ips}
    for octet in range(121, 126):
        ip = by_addr.get(f"192.168.20.{octet}")
        if ip is None:
            continue
        ip.status = "allocated"
        session.add(ip)
    session.commit()

    preview = suggest.suggest_computer_ip(session, computer_name="PROENG026")
    assert preview["available"] is True
    assert preview["address"]
    assert preview["address"] != "192.168.20.26"
    assert preview["network_cidr"] == "192.168.20.0/24"


def test_asset_create_with_computer_name_creates_one_computer(session):
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    actor = session.query(User).filter(User.email == "admin@prosohm.com").first()
    asset = it_asset_service.create_asset(
        session,
        actor=actor,
        asset_type_id=laptop.id,
        computer_name="PROENG200",
        mac_address="AA:BB:CC:DD:EE:01",
    )
    session.refresh(asset)
    assert asset.computer is not None
    assert asset.computer.computer_name == "PROENG200"
    assert suggest.normalize_mac(asset.computer.mac_address) == "AA:BB:CC:DD:EE:01"


def test_laptop_asset_without_computer_fields_does_not_create_computer(session):
    laptop = session.query(AssetType).filter(AssetType.code == "LAPTOP").first()
    actor = session.query(User).filter(User.email == "admin@prosohm.com").first()
    asset = it_asset_service.create_asset(
        session,
        actor=actor,
        asset_type_id=laptop.id,
        make="Dell",
        model="Precision",
    )
    session.refresh(asset)
    assert asset.computer is None
