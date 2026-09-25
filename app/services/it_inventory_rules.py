"""Central IT inventory business rules.

One place for: component roles (what an asset or stock item *is* for a seat),
inventory groups (Computing / Display / Peripherals / …) and the configurable
Virtual Seat setup requirements per computer type. Frontends read these through
the API instead of hard-coding them.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.it_operations import COMPUTER_TYPE_LABELS, AssetType

ROLE_COMPUTER = "computer"
ROLE_MONITOR = "monitor"
ROLE_MOUSE_3D = "mouse_3d"
ROLE_KEYBOARD = "keyboard"
ROLE_MOUSE = "mouse"
ROLE_HEADSET = "headset"
ROLE_DOCK = "dock"
ROLE_WEBCAM = "webcam"
ROLE_SPEAKERS = "speakers"
ROLE_BAG = "bag"
ROLE_ADAPTER = "adapter"
ROLE_CABLE = "cable"
ROLE_NETWORK = "network"
ROLE_OTHER = "other"

ROLE_LABELS: dict[str, str] = {
    ROLE_COMPUTER: "Computer",
    ROLE_MONITOR: "Monitor",
    ROLE_MOUSE_3D: "3D Mouse",
    ROLE_KEYBOARD: "Keyboard",
    ROLE_MOUSE: "Mouse",
    ROLE_HEADSET: "Headset",
    ROLE_DOCK: "Dock",
    ROLE_WEBCAM: "Webcam",
    ROLE_SPEAKERS: "Speakers",
    ROLE_BAG: "Laptop Bag",
    ROLE_ADAPTER: "Adapter / Charger",
    ROLE_CABLE: "Cable",
    ROLE_NETWORK: "Network / IT equipment",
    ROLE_OTHER: "Other",
}

# Roles a stock (quantity-based) item may represent.
STOCK_KINDS = (
    ROLE_KEYBOARD,
    ROLE_MOUSE,
    ROLE_HEADSET,
    ROLE_DOCK,
    ROLE_WEBCAM,
    ROLE_SPEAKERS,
    ROLE_BAG,
    ROLE_ADAPTER,
    ROLE_CABLE,
    ROLE_OTHER,
)

GROUP_COMPUTING = "computing"
GROUP_DISPLAY = "display"
GROUP_PERIPHERALS = "peripherals"
GROUP_ACCESSORIES = "accessories"
GROUP_NETWORK = "network_it"
GROUP_LABELS = {
    GROUP_COMPUTING: "Computing",
    GROUP_DISPLAY: "Display",
    GROUP_PERIPHERALS: "Peripherals",
    GROUP_ACCESSORIES: "Accessories",
    GROUP_NETWORK: "Network / IT equipment",
}
_ROLE_GROUP = {
    ROLE_COMPUTER: GROUP_COMPUTING,
    ROLE_MONITOR: GROUP_DISPLAY,
    ROLE_MOUSE_3D: GROUP_PERIPHERALS,
    ROLE_KEYBOARD: GROUP_PERIPHERALS,
    ROLE_MOUSE: GROUP_PERIPHERALS,
    ROLE_HEADSET: GROUP_PERIPHERALS,
    ROLE_DOCK: GROUP_PERIPHERALS,
    ROLE_WEBCAM: GROUP_PERIPHERALS,
    ROLE_SPEAKERS: GROUP_PERIPHERALS,
    ROLE_BAG: GROUP_ACCESSORIES,
    ROLE_ADAPTER: GROUP_ACCESSORIES,
    ROLE_CABLE: GROUP_ACCESSORIES,
    ROLE_NETWORK: GROUP_NETWORK,
    ROLE_OTHER: GROUP_ACCESSORIES,
}

# Ordered keyword rules; first match wins ("3D MOUSE" before "MOUSE").
_KEYWORD_ROLES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("3D MOUSE", "3DMOUSE", "SPACEMOUSE", "SPACE MOUSE", "3DM"), ROLE_MOUSE_3D),
    (("MONITOR", "DISPLAY", "SCREEN"), ROLE_MONITOR),
    (("KEYBOARD",), ROLE_KEYBOARD),
    (("DOCK",), ROLE_DOCK),
    (("WEBCAM", "CAMERA"), ROLE_WEBCAM),
    (("HEADSET", "HEADPHONE"), ROLE_HEADSET),
    (("SPEAKER",), ROLE_SPEAKERS),
    (("BAG", "BACKPACK"), ROLE_BAG),
    (("ADAPTER", "ADAPTOR", "CHARGER", "POWER SUPPLY"), ROLE_ADAPTER),
    (("CABLE", "HDMI", "USB-C", "DISPLAYPORT"), ROLE_CABLE),
    (("MOUSE",), ROLE_MOUSE),
    (("ROUTER", "SWITCH", "FIREWALL", "ACCESS POINT", "UPS", "PRINTER", "SERVER"), ROLE_NETWORK),
)
_COMPUTER_WORDS = ("LAPTOP", "NOTEBOOK", "WORKSTATION", "DESKTOP")


def role_for_text(text: str) -> str | None:
    blob = f" {(text or '').upper()} "
    for words, role in _KEYWORD_ROLES:
        if any(word in blob for word in words):
            return role
    return None


def role_for_asset_type(asset_type: AssetType | None) -> str:
    if asset_type is None:
        return ROLE_OTHER
    blob = f"{asset_type.code or ''} {asset_type.name or ''}"
    upper = blob.upper()
    category = (asset_type.category or "").lower()
    if category == "network_equipment":
        return ROLE_NETWORK
    if category == "computer" or any(word in upper for word in _COMPUTER_WORDS):
        if "SERVER" in upper:
            return ROLE_NETWORK
        return ROLE_COMPUTER
    return role_for_text(blob) or ROLE_OTHER


def kind_for_stock_item(item_kind: str | None, name: str | None, category: str | None) -> str:
    if item_kind in STOCK_KINDS:
        return item_kind
    guessed = role_for_text(f"{name or ''} {category or ''}")
    return guessed if guessed in STOCK_KINDS else ROLE_OTHER


def group_for_role(role: str) -> str:
    return _ROLE_GROUP.get(role, GROUP_ACCESSORIES)


def is_laptop_type(asset_type: AssetType | None) -> bool:
    if asset_type is None:
        return False
    blob = f"{asset_type.code or ''} {asset_type.name or ''}".upper()
    return "LAPTOP" in blob or "NOTEBOOK" in blob


# --- Virtual Seat setup requirements -------------------------------------------------

UNCLASSIFIED_DESKTOP = "DESKTOP"
UNCLASSIFIED_LAPTOP = "LAPTOP"
SEAT_TYPE_LABELS: dict[str, str] = {
    **COMPUTER_TYPE_LABELS,
    UNCLASSIFIED_DESKTOP: "Workstation (type not set)",
    UNCLASSIFIED_LAPTOP: "Laptop (type not set)",
}


def _line(role: str, required: int, recommended: int) -> dict[str, Any]:
    return {"role": role, "required": required, "recommended": max(required, recommended)}


DEFAULT_SEAT_REQUIREMENTS: dict[str, list[dict[str, Any]]] = {
    "ENG_WS": [
        _line(ROLE_MONITOR, 1, 2),
        _line(ROLE_MOUSE_3D, 0, 1),
        _line(ROLE_KEYBOARD, 0, 1),
        _line(ROLE_MOUSE, 0, 1),
        _line(ROLE_HEADSET, 0, 1),
    ],
    "GENERAL_WS": [
        _line(ROLE_MONITOR, 1, 1),
        _line(ROLE_KEYBOARD, 0, 1),
        _line(ROLE_MOUSE, 0, 1),
        _line(ROLE_HEADSET, 0, 1),
    ],
    "IT_WS": [
        _line(ROLE_MONITOR, 1, 2),
        _line(ROLE_KEYBOARD, 0, 1),
        _line(ROLE_MOUSE, 0, 1),
        _line(ROLE_HEADSET, 0, 1),
    ],
    "ENG_LAPTOP": [
        _line(ROLE_MONITOR, 0, 1),
        _line(ROLE_DOCK, 0, 1),
        _line(ROLE_KEYBOARD, 0, 1),
        _line(ROLE_MOUSE, 0, 1),
        _line(ROLE_HEADSET, 0, 1),
        _line(ROLE_BAG, 0, 1),
    ],
    "GENERAL_LAPTOP": [
        _line(ROLE_MOUSE, 0, 1),
        _line(ROLE_HEADSET, 0, 1),
        _line(ROLE_BAG, 0, 1),
    ],
    UNCLASSIFIED_DESKTOP: [
        _line(ROLE_MONITOR, 1, 1),
        _line(ROLE_KEYBOARD, 0, 1),
        _line(ROLE_MOUSE, 0, 1),
    ],
    UNCLASSIFIED_LAPTOP: [
        _line(ROLE_MOUSE, 0, 1),
        _line(ROLE_BAG, 0, 1),
    ],
}

_SETTINGS_KEY = "virtual_seat_requirements"


def _settings_blob(db: Session) -> dict[str, Any]:
    from sqlalchemy import select

    from app.models.it_operations import ITSettings

    raw = db.scalar(select(ITSettings.settings_json).limit(1))
    try:
        data = json.loads(raw or "{}")
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def seat_requirements(db: Session) -> dict[str, list[dict[str, Any]]]:
    overrides = _settings_blob(db).get(_SETTINGS_KEY) or {}
    merged = {code: [dict(line) for line in lines] for code, lines in DEFAULT_SEAT_REQUIREMENTS.items()}
    if isinstance(overrides, dict):
        for code, lines in overrides.items():
            if code in SEAT_TYPE_LABELS and isinstance(lines, list):
                merged[code] = [dict(line) for line in lines]
    return merged


def validate_requirement_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in lines:
        role = str(raw.get("role") or "").strip()
        if role not in ROLE_LABELS or role in {ROLE_COMPUTER, ROLE_NETWORK}:
            raise ProTrackValidationError(f"Invalid seat component role: {role or '(blank)'}")
        if role in seen:
            raise ProTrackValidationError(f"Duplicate seat component role: {role}")
        seen.add(role)
        required = int(raw.get("required") or 0)
        recommended = int(raw.get("recommended") or 0)
        if required < 0 or recommended < 0 or required > 8 or recommended > 8:
            raise ProTrackValidationError("Quantities must be between 0 and 8.")
        clean.append(_line(role, required, recommended))
    return clean


def save_seat_requirements(
    db: Session, computer_type: str, lines: list[dict[str, Any]], *, actor: Any = None
) -> None:
    from app.models.enums import ActivityAction, EntityType
    from app.services.activity_service import log_activity
    from app.services.it_asset_service import get_or_create_settings

    if computer_type not in SEAT_TYPE_LABELS:
        raise ProTrackValidationError(f"Unknown computer type: {computer_type}")
    clean = validate_requirement_lines(lines)
    previous = seat_requirements(db).get(computer_type, [])
    settings = get_or_create_settings(db)
    data = _settings_blob(db)
    overrides = data.get(_SETTINGS_KEY) if isinstance(data.get(_SETTINGS_KEY), dict) else {}
    overrides[computer_type] = clean
    data[_SETTINGS_KEY] = overrides
    settings.settings_json = json.dumps(data)
    db.add(settings)
    db.flush()
    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_settings,
        entity_id=settings.id,
        action=ActivityAction.it_settings_updated,
        old_value={"virtual_seat_requirements": {computer_type: previous}},
        new_value={"virtual_seat_requirements": {computer_type: clean}},
        outcome="success",
        module="it_operations",
        commit=False,
    )
