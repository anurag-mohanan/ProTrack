"""Multi-NIC interfaces + intentional multi-homing data quality."""

from uuid import uuid4

from sqlalchemy import select

from app.models.it_operations import AssetType, IPAddress, Network
from app.models.models import User
from app.services import it_asset_service, it_data_quality_service, it_network_service
from tests.conftest import IDS


def _ensure_desktop_type(session) -> AssetType:
    existing = session.scalar(select(AssetType).where(AssetType.code == "DESKTOP"))
    if existing:
        return existing
    row = AssetType(
        id=uuid4(),
        code="DESKTOP",
        name="Desktop",
        category="computer",
        is_active=True,
    )
    session.add(row)
    session.commit()
    return row


def test_multi_nic_and_intentional_multi_homing(session):
    admin = session.get(User, IDS["user_admin"])
    at = _ensure_desktop_type(session)
    computer = it_asset_service.create_computer(
        session,
        actor=admin,
        asset_type_id=at.id,
        mac_address="AA:BB:CC:DD:EE:01",
    )
    interfaces = it_asset_service.list_computer_interfaces(session, computer.id)
    assert len(interfaces) == 1
    assert interfaces[0].is_primary is True
    assert interfaces[0].mac_address == "AA:BB:CC:DD:EE:01"

    wifi = it_asset_service.create_computer_interface(
        session,
        computer,
        name="Wi-Fi",
        role="wifi",
        mac_address="AA:BB:CC:DD:EE:02",
        commit=True,
    )
    assert wifi.is_primary is False
    assert len(it_asset_service.list_computer_interfaces(session, computer.id)) == 2

    network = Network(
        id=uuid4(),
        name=f"Lab-{uuid4().hex[:4]}",
        cidr="10.55.0.0/30",
        is_active=True,
    )
    session.add(network)
    session.flush()
    ip1 = IPAddress(id=uuid4(), network_id=network.id, address="10.55.0.1", status="available")
    ip2 = IPAddress(id=uuid4(), network_id=network.id, address="10.55.0.2", status="available")
    session.add_all([ip1, ip2])
    session.commit()

    lan = it_asset_service.list_computer_interfaces(session, computer.id)[0]
    it_network_service.allocate_ip(
        session,
        actor=admin,
        ip_address_id=ip1.id,
        assigned_to_asset_id=computer.asset_id,
        interface_id=lan.id,
    )
    it_network_service.allocate_ip(
        session,
        actor=admin,
        ip_address_id=ip2.id,
        assigned_to_asset_id=computer.asset_id,
        interface_id=wifi.id,
    )

    report = it_data_quality_service.build_data_quality_report(session)
    by_code = {issue["code"]: issue for issue in report["issues"]}
    assert by_code["asset_multi_homed_ips"]["count"] >= 1
    assert by_code["asset_multiple_active_ips"]["count"] == 0 or computer.asset_id not in {
        sample.get("asset_id") for sample in by_code["asset_multiple_active_ips"]["samples"]
    }
