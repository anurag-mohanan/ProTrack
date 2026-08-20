"""IT spreadsheet migration — analyze / preview / import without storing secrets."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.access_control import MODULE_IT_OPERATIONS
from app.core.config import UPLOAD_DIR
from app.core.exceptions import ProTrackValidationError
from app.models.enums import ActivityAction, EntityType
from app.models.it_operations import (
    Asset,
    AssetType,
    Computer,
    InventoryItem,
    ITSupplier,
    ITUserAccount,
    SoftwareAssignment,
    SoftwareCatalog,
    SoftwareLicensePool,
)
from app.models.models import Customer, User
from app.services import it_asset_service
from app.services.activity_service import log_activity

MODULE = MODULE_IT_OPERATIONS

SOURCE_TYPES = frozenset(
    {
        "hardware",
        "accounts",
        "software",
        "inventory",
        "consumables",
        "suppliers",
    }
)

_SENSITIVE_HEADER_RE = re.compile(
    r"(pass|pwd|secret|credential|teamviewer|windows\s*license|license\s*#)",
    re.I,
)

_SESSIONS_DIR = UPLOAD_DIR / "it_migration"

_SHEET_HINTS: dict[str, list[str]] = {
    "hardware": ["1.hardwares", "hardwares", "hardware"],
    "accounts": ["2.user_credentials", "user_credentials", "credentials", "accounts"],
    "software": ["3.softwares", "softwares", "licenses", "software"],
    "inventory": ["inventory list", "inventory"],
    "consumables": ["consumables"],
    "suppliers": ["supplier list", "suppliers"],
}

# Fallback header rows for original multi-row inventory layouts only.
_HEADER_ROW_FALLBACK: dict[str, int] = {
    "inventory": 3,
    "consumables": 3,
    "suppliers": 3,
}

# Logical field → accepted source header aliases (after _norm_header).
# Supports Format A (PP-INF-FO-7 / Asset Inventory) and Format B (normalized ProTrack import).
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "source_id": (
        "external_id",
        "legacy_asset_number",
        "asset_number",
        "asset_id",
        "id_tag",
        "id",
    ),
    "description": ("description",),
    "name": ("name",),
    "customer_used_for": ("customer_used_for", "customer_used"),
    "asset_type": ("asset_type", "type", "category"),
    "assigned_to": (
        "assigned_to",
        "assigned_user",
        "current_user",
        "current_designer_user",
        "current_designer_or_user",
    ),
    "make": ("make", "manufacturer"),
    "model": ("model", "model_number"),
    "current_status": ("current_status", "status", "condition"),
    "purchase_date": ("purchase_date", "date_of_purchase", "date"),
    "warranty_expiry": (
        "warranty_expiry",
        "warranty_valid_upto",
        "warranty_valid_until",
        "warranty_expiration",
    ),
    "warranty": ("warranty",),
    "service_tag": ("service_tag", "service_tag_number", "service_serial"),
    "serial_number": ("serial_number", "serial"),
    "ownership_type": ("ownership_type", "owner_type", "purchased_by"),
    "owner_customer": ("owner_customer", "owner", "cust_paid", "customer_paid"),
    "location": ("location", "room", "storage_location"),
    "team_or_department": ("team_or_department", "department", "team"),
    "supplier": ("supplier",),
    "invoice_number": ("invoice_number", "invoice_no", "invoice"),
    "purchase_value": ("purchase_value", "value"),
    "computer_name": ("computer_name", "name"),  # Format A NAME = product name
    "os": ("os",),
    "ram_gb": ("ram_gb", "ram"),
    "cpu": ("cpu", "cpu_ghz"),
    "mac_address": ("mac_address", "mac"),
    "ip_address": ("ip_address",),
    "remarks": ("remarks", "remarks_notes", "migration_note", "notes", "return_notes"),
    "software": ("software",),
    "seats": ("seats", "no_of_user_license", "no_of_userlicense"),
    "renewal": ("renewal", "renewal_mode"),
    "expiry": ("expiry", "license_valid_upto"),
    "employee_name": ("employee_name", "employee"),
    "username": ("username",),
    "email": ("email",),
    "teams_id": ("ms_teams_id", "teams_id"),
    "account_status": ("status",),
    "qty": ("qty", "quantity"),
    "in_use": ("in_use", "quantity_in_use"),
    "available": ("available", "quantity_available"),
}


def _norm_header(header: str) -> str:
    """Normalize header text for alias matching. Does not alter cell values."""
    s = (header or "").strip().lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[?#]+", "", s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_")



def _cell_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _is_sensitive_header(header: str) -> bool:
    return bool(_SENSITIVE_HEADER_RE.search(header or ""))


def _norm_id(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").upper())


def _norm_name(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _parse_date(value: str) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw[:19], fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _parse_int(value: str) -> int | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _parse_decimal(value: str) -> Decimal | None:
    raw = (value or "").strip().replace(",", "")
    if not raw:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def _sessions_dir() -> Path:
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return _SESSIONS_DIR


def _session_path(session_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", session_id)
    if not safe:
        raise ProTrackValidationError("Invalid migration session id.")
    return _sessions_dir() / f"{safe}.json"


def _save_session(payload: dict[str, Any]) -> str:
    session_id = str(uuid4())
    _session_path(session_id).write_text(json.dumps(payload), encoding="utf-8")
    return session_id


def _load_session(session_id: str) -> dict[str, Any]:
    path = _session_path(session_id)
    if not path.exists():
        raise ProTrackValidationError("Migration session not found or expired.")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_sheet_name(sheetnames: list[str], source_type: str) -> str | None:
    hints = _SHEET_HINTS.get(source_type, [])
    lowered = {s.lower().strip(): s for s in sheetnames}
    for hint in hints:
        for key, original in lowered.items():
            if hint in key:
                return original
    return None


def _find_header_row(rows: list[tuple[Any, ...]], source_type: str) -> int:
    """Prefer a row that contains known ID / ownership headers (works for Format A + B)."""
    id_tokens = {
        "id",
        "id_tag",
        "external_id",
        "asset_number",
        "legacy_asset_number",
        "asset_id",
        "software",
        "employee_name",
        "supplier_name",
        "name",
    }
    for i, row in enumerate(rows[:20]):
        norms = {_norm_header(_cell_str(c)) for c in (row or ()) if _cell_str(c)}
        if len(norms) >= 3 and norms & id_tokens:
            return i
    if source_type in _HEADER_ROW_FALLBACK:
        return _HEADER_ROW_FALLBACK[source_type]
    for i, row in enumerate(rows[:40]):
        vals = [_cell_str(c) for c in (row or ())]
        nonempty = [v for v in vals if v]
        if len(nonempty) >= 3:
            return i
    return 0


def _row_header_index(row: dict[str, str]) -> dict[str, str]:
    """Map normalized header → original header key in the row dict."""
    index: dict[str, str] = {}
    for key in row:
        norm = _norm_header(key)
        if norm and norm not in index:
            index[norm] = key
    return index


def _resolve_field(
    row: dict[str, str],
    logical: str,
    *,
    header_index: dict[str, str] | None = None,
    extra_aliases: tuple[str, ...] = (),
) -> tuple[str, str | None]:
    """
    Resolve a logical field from a source row using aliases.
    Returns (value, matched_original_header_or_None).
    """
    index = header_index or _row_header_index(row)
    aliases = list(extra_aliases) + list(_FIELD_ALIASES.get(logical, ()))
    for alias in aliases:
        key = index.get(_norm_header(alias))
        if key is None:
            continue
        return (row.get(key) or "").strip(), key
    return "", None


def _build_column_bindings(headers: list[str], source_type: str) -> dict[str, str | None]:
    """Show which source header maps to each logical field (for preview/debug)."""
    index = {_norm_header(h): h for h in headers if h}
    relevant = [
        "source_id",
        "description",
        "name",
        "ownership_type",
        "owner_customer",
        "customer_used_for",
        "assigned_to",
        "asset_type",
        "service_tag",
        "serial_number",
        "current_status",
        "purchase_date",
        "location",
        "supplier",
        "make",
        "model",
    ]
    if source_type == "software":
        relevant = ["software", "ownership_type", "owner_customer", "assigned_to", "seats", "expiry"]
    elif source_type == "accounts":
        relevant = ["employee_name", "username", "email", "assigned_to", "account_status"]
    bindings: dict[str, str | None] = {}
    for logical in relevant:
        matched = None
        for alias in _FIELD_ALIASES.get(logical, ()):
            if _norm_header(alias) in index:
                matched = index[_norm_header(alias)]
                break
        bindings[logical] = matched
    return bindings


def _detect_workbook_format(headers: list[str]) -> str:
    norms = {_norm_header(h) for h in headers}
    if {"external_id", "ownership_type", "owner_customer"} & norms:
        return "normalized_protrack"
    if {"id", "customer_used_for", "service_tag"} & norms or "id_tag" in norms:
        return "original_source"
    if "cust_paid" in norms or "id_tag" in norms:
        return "original_inventory"
    return "unknown"


def _get_exact(row: dict[str, str], *candidates: str) -> str:
    """Legacy helper — exact/normalized alias match via _resolve_field path."""
    index = _row_header_index(row)
    for cand in candidates:
        key = index.get(_norm_header(cand))
        if key is not None:
            return (row.get(key) or "").strip()
    return ""


def _get(row: dict[str, str], *candidates: str) -> str:
    return _get_exact(row, *candidates)


def _extract_asset_fields(row: dict[str, str]) -> dict[str, str]:
    """Central hardware/inventory field extraction (Format A + B)."""
    index = _row_header_index(row)
    out: dict[str, str] = {}
    for logical in (
        "source_id",
        "description",
        "name",
        "customer_used_for",
        "asset_type",
        "assigned_to",
        "make",
        "model",
        "current_status",
        "purchase_date",
        "warranty_expiry",
        "warranty",
        "service_tag",
        "serial_number",
        "ownership_type",
        "owner_customer",
        "location",
        "team_or_department",
        "supplier",
        "invoice_number",
        "purchase_value",
        "computer_name",
        "os",
        "ram_gb",
        "cpu",
        "mac_address",
        "ip_address",
        "remarks",
    ):
        value, _hdr = _resolve_field(row, logical, header_index=index)
        out[logical] = value
    # Format A inventory: Name is item name, not make.
    if not out["description"] and out["name"]:
        out["description"] = out["name"]
    # Prefer dedicated computer_name; Format A hardware uses NAME for product name.
    if not out["computer_name"] and out["name"] and out["make"]:
        out["computer_name"] = out["name"]
    return out


def _resolve_ownership_from_fields(
    fields: dict[str, str],
    customers: dict[str, Customer],
) -> tuple[str, UUID | None, str | None, list[dict[str, str]]]:
    """
    ownership_type / owner_customer from explicit source fields only.
    Returns (purchased_by, owner_customer_id, owner_label, warnings).
    """
    warnings: list[dict[str, str]] = []
    ownership_raw = (fields.get("ownership_type") or "").strip()
    owner_raw = (fields.get("owner_customer") or "").strip()

    def _as_org() -> tuple[str, UUID | None, str | None, list[dict[str, str]]]:
        return "organization", None, "Prosohm", warnings

    def _as_customer(label: str) -> tuple[str, UUID | None, str | None, list[dict[str, str]]]:
        cust = _match_customer(customers, label)
        if cust:
            return "customer", cust.id, cust.name, warnings
        warnings.append(
            {
                "code": "CUSTOMER_UNKNOWN",
                "severity": "review",
                "detail": f"Owner customer '{label}' not matched; ownership left unknown.",
            }
        )
        return "unknown", None, None, warnings

    if ownership_raw:
        n = _norm_name(ownership_raw)
        if n in {"prosohm", "organization", "company", "prosohm eng", "ps"}:
            return _as_org()
        if n in {"customer", "client"}:
            if owner_raw:
                return _as_customer(owner_raw)
            warnings.append(
                {
                    "code": "OWNERSHIP_UNCLEAR",
                    "severity": "review",
                    "detail": "ownership_type=Customer but owner_customer is blank.",
                }
            )
            return "unknown", None, None, warnings
        # ownership_type may itself be a customer name (e.g. Sybridge / PURCHASED BY)
        if n not in {"unknown", "n/a", "na", "none", "null"}:
            return _as_customer(ownership_raw)

    if owner_raw:
        n = _norm_name(owner_raw)
        if n in {"yes", "y", "true", "1"}:
            warnings.append(
                {
                    "code": "OWNERSHIP_UNCLEAR",
                    "severity": "review",
                    "detail": f"Owner/CUST PAID is '{owner_raw}' without a customer name.",
                }
            )
            return "unknown", None, None, warnings
        if n in {"prosohm", "organization", "no", "n", "false", "0"}:
            return _as_org()
        return _as_customer(owner_raw)

    warnings.append(
        {
            "code": "OWNERSHIP_UNCLEAR",
            "severity": "review",
            "detail": (
                "No ownership_type / purchased_by / owner_customer / CUST PAID value "
                "in source row; ownership left unknown."
            ),
        }
    )
    return "unknown", None, None, warnings



def _read_sheet_rows(
    content: bytes, source_type: str
) -> tuple[str, list[str], list[dict[str, str]], list[str]]:
    wb = load_workbook(BytesIO(content), data_only=True, read_only=True)
    try:
        sheet_name = _resolve_sheet_name(wb.sheetnames, source_type)
        if sheet_name is None:
            raise ProTrackValidationError(
                f"Could not find a sheet for source type '{source_type}'. "
                f"Available: {', '.join(wb.sheetnames)}"
            )
        ws = wb[sheet_name]
        raw_rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    if not raw_rows:
        return sheet_name, [], [], []

    header_idx = _find_header_row(raw_rows, source_type)
    headers_raw = [_cell_str(c) for c in (raw_rows[header_idx] or ())]
    while headers_raw and not headers_raw[-1]:
        headers_raw.pop()

    headers: list[str] = []
    seen: dict[str, int] = {}
    for h in headers_raw:
        key = h or f"col_{len(headers)}"
        if key in seen:
            seen[key] += 1
            key = f"{key}_{seen[key]}"
        else:
            seen[key] = 1
        headers.append(key)

    sensitive = [h for h in headers if _is_sensitive_header(h)]
    safe_headers = [h for h in headers if h not in sensitive]

    rows: list[dict[str, str]] = []
    for row in raw_rows[header_idx + 1 :]:
        vals = [_cell_str(c) for c in (row or ())]
        if len(vals) < len(headers):
            vals += [""] * (len(headers) - len(vals))
        record = {headers[i]: vals[i] for i in range(len(headers))}
        meaningful = [v for k, v in record.items() if v and k not in sensitive]
        if not meaningful:
            continue
        rows.append({k: record.get(k, "") for k in safe_headers})

    return sheet_name, safe_headers, rows, sensitive


def _customer_index(db: Session) -> dict[str, Customer]:
    customers = list(db.scalars(select(Customer).where(Customer.is_active.is_(True))).all())
    index: dict[str, Customer] = {}
    for c in customers:
        index[_norm_name(c.name)] = c
        if c.code:
            index[_norm_name(c.code)] = c
    return index


def _user_index(db: Session) -> dict[str, User]:
    users = list(db.scalars(select(User).where(User.is_deleted.is_(False))).all())
    index: dict[str, User] = {}
    for u in users:
        full = f"{u.first_name} {u.last_name}".strip()
        if full:
            index[_norm_name(full)] = u
        if u.email:
            index[_norm_name(u.email)] = u
            index[_norm_name(u.email.split("@")[0])] = u
    return index


def _match_customer(index: dict[str, Customer], label: str) -> Customer | None:
    key = _norm_name(label)
    if not key:
        return None
    if key in {"prosohm", "prosohm eng", "prosohm admin", "generic", "admin", "organization"}:
        return None
    if key in index:
        return index[key]
    for k, cust in index.items():
        if key in k or k in key:
            return cust
    return None


def _match_user(index: dict[str, User], label: str) -> User | None:
    key = _norm_name(label)
    if not key:
        return None
    if key in {
        "all",
        "open",
        "n/a",
        "servprosohm",
        "conference room",
        "planning board",
        "eng planning board",
        "prosohm eng team",
    }:
        return None
    if key in index:
        return index[key]
    base = re.sub(r"\(.*?\)", "", key).strip()
    if base in index:
        return index[base]
    for k, user in index.items():
        if base and (base in k or k in base):
            return user
    return None


def _existing_asset_keys(db: Session) -> dict[str, set[str]]:
    assets = list(db.scalars(select(Asset).where(Asset.is_deleted.is_(False))).all())
    return {
        "legacy": {_norm_id(a.legacy_asset_number or "") for a in assets if a.legacy_asset_number},
        "serial": {_norm_id(a.serial_number or "") for a in assets if a.serial_number},
        "service_tag": {_norm_id(a.service_tag or "") for a in assets if a.service_tag},
        "asset_number": {_norm_id(a.asset_number or "") for a in assets if a.asset_number},
    }


def list_source_types() -> list[dict[str, str]]:
    return [
        {
            "id": "hardware",
            "label": "Hardware (original or normalized)",
            "sheet_hint": "1.HARDWARES or hardware",
            "description": (
                "Supports PP-INF-FO-7 (ID, Service Tag#) and normalized sheets "
                "(external_id, ownership_type, service_tag)."
            ),
        },
        {
            "id": "accounts",
            "label": "Users & Accounts",
            "sheet_hint": "2.USER_CREDENTIALS",
            "description": "Account metadata only — passwords are never imported.",
        },
        {
            "id": "software",
            "label": "Software & Licenses",
            "sheet_hint": "3.SOFTWARES_&_LICENSES",
            "description": "Software catalog, seats, ownership, assignments.",
        },
        {
            "id": "inventory",
            "label": "Asset Inventory",
            "sheet_hint": "INVENTORY LIST",
            "description": "Original inventory list or normalized inventory sheet.",
        },
        {
            "id": "consumables",
            "label": "Consumables",
            "sheet_hint": "CONSUMABLES",
            "description": "Stock quantities (cables, mice, keyboards, …).",
        },
        {
            "id": "suppliers",
            "label": "Suppliers",
            "sheet_hint": "SUPPLIER LIST",
            "description": "Vendor master (sheet may be empty).",
        },
    ]


def analyze_upload(
    db: Session,
    *,
    actor: User,
    content: bytes,
    filename: str,
    source_type: str,
) -> dict[str, Any]:
    source_type = (source_type or "").strip().lower()
    if source_type not in SOURCE_TYPES:
        raise ProTrackValidationError(
            f"Invalid source_type. Allowed: {', '.join(sorted(SOURCE_TYPES))}"
        )
    if not content:
        raise ProTrackValidationError("Uploaded file is empty.")

    sheet_name, headers, rows, sensitive = _read_sheet_rows(content, source_type)
    workbook_format = _detect_workbook_format(headers)
    column_bindings = _build_column_bindings(headers, source_type)
    customers = _customer_index(db)
    users = _user_index(db)
    existing = _existing_asset_keys(db)

    exceptions: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    preview_rows: list[dict[str, str]] = []
    new_count = 0
    skip_count = 0
    review_count = 0
    warning_count = 0
    error_count = 0
    seen_ids: dict[str, int] = {}

    if column_bindings.get("source_id") is None and source_type in {"hardware", "inventory"}:
        exceptions.append(
            {
                "exception_id": "EX-HEADER_LAYOUT-0000",
                "id": "EX-HEADER_LAYOUT-0000",
                "row": None,
                "source_key": None,
                "code": "HEADER_LAYOUT",
                "severity": "error",
                "detail": (
                    "No ID column detected among aliases "
                    "(ID, ID Tag, external_id, asset_number, legacy_asset_number). "
                    f"Detected headers: {', '.join(headers[:20])}"
                ),
            }
        )
        error_count += 1

    for idx, row in enumerate(rows, start=1):
        row_exceptions: list[dict[str, Any]] = []
        action = "import"
        match_key = None
        legacy = ""
        serial = ""
        service = ""
        fields: dict[str, str] = {}
        owner_preview = ""
        strong = None

        if source_type in {"hardware", "inventory"}:
            fields = _extract_asset_fields(row)
            legacy = fields["source_id"]
            serial = fields["serial_number"]
            service = fields["service_tag"]

            if not legacy:
                row_exceptions.append(
                    {
                        "code": "MISSING_SOURCE_ID",
                        "severity": "error",
                        "detail": "Source ID is blank after column mapping.",
                    }
                )
                error_count += 1
                action = "skip"
                skip_count += 1
            else:
                norm_legacy = _norm_id(legacy)
                norm_serial = _norm_id(serial)
                norm_service = _norm_id(service)
                seen_ids[norm_legacy] = seen_ids.get(norm_legacy, 0) + 1

                if norm_service and norm_service in existing["service_tag"]:
                    strong = "service_tag"
                elif norm_serial and norm_serial in existing["serial"]:
                    strong = "serial_number"
                elif norm_legacy in existing["legacy"] or norm_legacy in existing["asset_number"]:
                    strong = "legacy_asset_number"

                if strong:
                    action = "skip_duplicate"
                    skip_count += 1
                    duplicates.append(
                        {
                            "row": idx,
                            "match_type": "strong",
                            "matched_on": strong,
                            "legacy_id": legacy,
                            "serial": serial or None,
                            "service_tag": service or None,
                        }
                    )
                else:
                    new_count += 1

                purchased_by, _owner_id, owner_label, own_warns = _resolve_ownership_from_fields(
                    fields, customers
                )
                owner_preview = owner_label or purchased_by
                for w in own_warns:
                    row_exceptions.append(w)
                    if w["severity"] == "review":
                        review_count += 1
                        if action == "import":
                            action = "review"
                    elif w["severity"] == "warning":
                        warning_count += 1

                cust_used = fields["customer_used_for"]
                if cust_used and _match_customer(customers, cust_used) is None:
                    if _norm_name(cust_used) not in {
                        "generic",
                        "prosohm eng",
                        "prosohm admin",
                        "prosohm",
                    }:
                        row_exceptions.append(
                            {
                                "code": "CUSTOMER_UNKNOWN",
                                "severity": "warning",
                                "detail": f"customer_used_for '{cust_used}' not matched.",
                            }
                        )
                        warning_count += 1

                assignee = fields["assigned_to"]
                if assignee and _match_user(users, assignee) is None:
                    row_exceptions.append(
                        {
                            "code": "USER_UNKNOWN",
                            "severity": "warning",
                            "detail": f"Assigned user '{assignee}' not matched.",
                        }
                    )
                    warning_count += 1

                if not service and not serial:
                    row_exceptions.append(
                        {
                            "code": "SERIAL_MISSING",
                            "severity": "warning",
                            "detail": "No service tag / serial in source row (fields stay null).",
                        }
                    )
                    warning_count += 1

                if source_type == "inventory":
                    category = (fields.get("asset_type") or "").upper()
                    if category in {"FURNITURE", "KITCHEN", "TOOLS"}:
                        if not strong:
                            new_count = max(0, new_count - 1)
                        action = "skip"
                        skip_count += 1

                match_key = legacy

            if len(preview_rows) < 40 and action != "skip":
                preview_rows.append(
                    {
                        "source_id": legacy or "(missing)",
                        "description": fields.get("description") or fields.get("name") or "",
                        "mapped_asset_number": legacy or "",
                        "owner": owner_preview if legacy else "",
                        "owner_customer": fields.get("owner_customer") or "",
                        "customer_used_for": fields.get("customer_used_for") or "",
                        "status": fields.get("current_status") or "",
                        "serial": serial or "",
                        "service_tag": service or "",
                        "assigned_user": fields.get("assigned_to") or "",
                        "location": fields.get("location")
                        or fields.get("team_or_department")
                        or "",
                        "import_action": action,
                    }
                )

        elif source_type == "accounts":
            name = _get(row, "EMPLOYEE NAME", "Employee", "employee_name")
            email = _get(row, "EMAIL", "Email", "email")
            username = _get(row, "USERNAME", "Username", "username")
            user = (
                _match_user(users, email)
                or _match_user(users, name)
                or _match_user(users, username)
            )
            if user is None:
                action = "skip"
                skip_count += 1
                row_exceptions.append(
                    {
                        "code": "USER_UNKNOWN",
                        "severity": "review",
                        "detail": f"Employee '{name or username}' not matched.",
                    }
                )
                review_count += 1
            else:
                new_count += 1
                action = "import_metadata"
            if sensitive:
                row_exceptions.append(
                    {
                        "code": "SENSITIVE_EXCLUDED",
                        "severity": "info",
                        "detail": "Password columns excluded; credential_status=migration_required.",
                    }
                )
            match_key = username or email or name
            if len(preview_rows) < 40 and action != "skip":
                preview_rows.append({k: v for k, v in row.items() if v})

        elif source_type == "software":
            software = _get(row, "SOFTWARE", "Software", "software")
            purchased = _get(
                row, "PURCHASED BY", "Purchased By", "ownership_type", "purchased_by"
            )
            assignee = _get(row, "USER", "User", "assigned_to")
            if not software:
                action = "skip"
                skip_count += 1
            else:
                new_count += 1
            if purchased and _norm_name(purchased) not in {"prosohm", "organization"}:
                if _match_customer(customers, purchased) is None:
                    row_exceptions.append(
                        {
                            "code": "CUSTOMER_UNKNOWN",
                            "severity": "review",
                            "detail": f"PURCHASED BY '{purchased}' not matched.",
                        }
                    )
                    review_count += 1
            if assignee and _match_user(users, assignee) is None:
                row_exceptions.append(
                    {
                        "code": "USER_UNKNOWN",
                        "severity": "warning",
                        "detail": f"Assigned USER '{assignee}' not matched.",
                    }
                )
                warning_count += 1
            match_key = software
            if len(preview_rows) < 40 and action != "skip":
                preview_rows.append({k: v for k, v in row.items() if v})

        elif source_type == "consumables":
            name = _get(row, "Name", "NAME", "name")
            if not name:
                action = "skip"
                skip_count += 1
            else:
                new_count += 1
                qty = _parse_int(_get(row, "QTY", "Qty", "quantity"))
                issued = _parse_int(_get(row, "IN USE", "In Use", "quantity_in_use"))
                available = _parse_int(
                    _get(row, "AVAILABLE", "Available", "quantity_available")
                )
                if (
                    qty is not None
                    and issued is not None
                    and available is not None
                    and qty != issued + available
                ):
                    row_exceptions.append(
                        {
                            "code": "QTY_INCONSISTENT",
                            "severity": "warning",
                            "detail": f"QTY {qty} != IN USE {issued} + AVAILABLE {available}",
                        }
                    )
                    warning_count += 1
            match_key = name
            if len(preview_rows) < 40 and action != "skip":
                preview_rows.append({k: v for k, v in row.items() if v})

        elif source_type == "suppliers":
            name = _get(row, "SUPPLIER NAME", "Supplier Name", "Name", "name")
            if not name:
                action = "skip"
                skip_count += 1
            else:
                new_count += 1
            match_key = name

        for exc in row_exceptions:
            exceptions.append(
                {
                    "exception_id": f"EX-{exc['code']}-{idx:04d}",
                    "id": f"EX-{exc['code']}-{idx:04d}",
                    "row": idx,
                    "source_key": match_key,
                    **exc,
                }
            )

    for lid, count in seen_ids.items():
        if count > 1:
            exceptions.append(
                {
                    "exception_id": f"EX-LEGACY_ID_COLLISION-{lid}",
                    "id": f"EX-LEGACY_ID_COLLISION-{lid}",
                    "row": None,
                    "source_key": lid,
                    "code": "LEGACY_ID_COLLISION",
                    "severity": "blocker",
                    "detail": f"Legacy ID {lid} appears {count} times in the source file.",
                }
            )
            review_count += 1

    if source_type == "suppliers" and new_count == 0:
        exceptions.append(
            {
                "exception_id": "EX-SUP-EMPTY",
                "id": "EX-SUP-EMPTY",
                "row": None,
                "source_key": None,
                "code": "SHEET_EMPTY",
                "severity": "warning",
                "detail": "Supplier sheet has no data.",
            }
        )
        warning_count += 1

    session_payload = {
        "source_type": source_type,
        "filename": filename,
        "sheet_name": sheet_name,
        "workbook_format": workbook_format,
        "column_bindings": column_bindings,
        "headers": headers,
        "sensitive_columns_excluded": sensitive,
        "rows": rows,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "actor_id": str(actor.id),
        "batch_id": str(uuid4()),
    }
    session_id = _save_session(session_payload)

    log_activity(
        db,
        user=actor,
        entity_type=EntityType.it_settings,
        entity_id=actor.id,
        action=ActivityAction.it_migration_analyzed,
        new_value={
            "source_type": source_type,
            "filename": filename,
            "workbook_format": workbook_format,
            "records": len(rows),
            "sensitive_columns_excluded": sensitive,
            "session_id": session_id,
            "column_bindings": column_bindings,
        },
        outcome="success",
        module=MODULE,
        commit=True,
    )

    return {
        "session_id": session_id,
        "source_type": source_type,
        "filename": filename,
        "sheet_name": sheet_name,
        "workbook_format": workbook_format,
        "column_bindings": column_bindings,
        "records_found": len(rows),
        "new_records": new_count,
        "potential_duplicates": len(duplicates),
        "skipped_records": skip_count,
        "requires_review": review_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "sensitive_columns_excluded": sensitive,
        "sensitive_data_excluded_count": len(sensitive),
        "headers": headers,
        "duplicates": duplicates[:100],
        "exceptions": exceptions[:300],
        "preview_rows": preview_rows,
        "first_five_mapped": preview_rows[:5],
        "confirm_required": True,
        "message": (
            f"Preview only ({workbook_format}). "
            f"ID column → {column_bindings.get('source_id')!r}. "
            f"Ownership → {column_bindings.get('ownership_type')!r}. "
            f"Service tag → {column_bindings.get('service_tag')!r}. "
            "Secrets excluded. Confirm to commit."
        ),
    }



def _resolve_asset_type(db: Session, type_label: str) -> AssetType:
    code_map = {
        "laptop": "LAPTOP",
        "desktop": "DESKTOP",
        "workstation": "DESKTOP",
        "monitor": "MONITOR",
        "server": "SERVER",
        "firewall": "OTHER",
        "printer": "OTHER",
        "keyboard": "KEYBOARD",
        "mouse": "MOUSE",
        "it": "OTHER",
    }
    label = (type_label or "OTHER").strip().lower()
    code = code_map.get(label, "OTHER")
    at = db.scalar(select(AssetType).where(AssetType.code == code))
    if at is None:
        at = db.scalar(select(AssetType).where(AssetType.code == "OTHER"))
    if at is None:
        raise ProTrackValidationError("No asset types configured.")
    return at


def _infer_purchased_by(
    *,
    legacy_id: str,
    cust_paid: str,
    customers: dict[str, Customer],
    source_type: str,
) -> tuple[str, UUID | None, list[dict[str, str]]]:
    """Ownership from explicit source fields only. Never infer from ID prefix."""
    warnings: list[dict[str, str]] = []
    if cust_paid:
        cust = _match_customer(customers, cust_paid)
        if cust:
            return "customer", cust.id, warnings
        warnings.append(
            {
                "code": "CUSTOMER_UNKNOWN",
                "severity": "review",
                "detail": f"CUST PAID '{cust_paid}' not matched; ownership left unknown.",
            }
        )
        return "unknown", None, warnings

    if source_type == "inventory":
        warnings.append(
            {
                "code": "OWNERSHIP_UNCLEAR",
                "severity": "review",
                "detail": "CUST PAID blank — ownership left unknown (not defaulted to Prosohm).",
            }
        )
        return "unknown", None, warnings

    # Hardware has no purchased-by column in PP-INF-FO-7.
    warnings.append(
        {
            "code": "OWNERSHIP_UNCLEAR",
            "severity": "review",
            "detail": (
                f"ID '{legacy_id}' has no Purchased By column; "
                "ownership left unknown for admin review."
            ),
        }
    )
    return "unknown", None, warnings


def _get_or_create_supplier(db: Session, name: str) -> UUID | None:
    norm = _norm_name(name)
    if not norm:
        return None
    existing = list(db.scalars(select(ITSupplier)).all())
    for s in existing:
        if _norm_name(s.name) == norm:
            return s.id
    for s in existing:
        if norm in _norm_name(s.name) or _norm_name(s.name) in norm:
            return s.id
    supplier = ITSupplier(id=uuid4(), name=name.strip(), is_active=True)
    db.add(supplier)
    db.flush()
    return supplier.id


def commit_import(
    db: Session,
    *,
    actor: User,
    session_id: str,
    confirm: bool,
    skip_duplicates: bool = True,
    skip_review_rows: bool = False,
) -> dict[str, Any]:
    if not confirm:
        raise ProTrackValidationError(
            "Import requires confirm=true after reviewing the analyze preview."
        )
    session = _load_session(session_id)
    source_type = session["source_type"]
    rows: list[dict[str, str]] = session.get("rows") or []
    customers = _customer_index(db)
    users = _user_index(db)
    existing = _existing_asset_keys(db)

    imported = 0
    skipped = 0
    duplicated = 0
    conflicted = 0
    errors: list[str] = []
    owned_org = 0
    owned_cust = 0
    sensitive_excluded = len(session.get("sensitive_columns_excluded") or [])

    try:
        if source_type in {"hardware", "inventory"}:
            for idx, row in enumerate(rows, start=1):
                fields = _extract_asset_fields(row)
                legacy = fields["source_id"]
                serial = fields["serial_number"]
                service = fields["service_tag"]
                make = fields["make"] or None
                model = fields["model"] or None
                desc = fields["description"] or fields["name"] or None
                location = fields["location"] or fields["team_or_department"] or None
                type_label = fields["asset_type"]
                cust_used = fields["customer_used_for"]
                purchase_date = _parse_date(fields["purchase_date"])
                warranty = _parse_date(fields["warranty_expiry"])
                cost = _parse_decimal(fields["purchase_value"])
                condition = fields["current_status"] or None
                supplier_name = fields["supplier"]
                invoice = fields["invoice_number"] or None
                computer_name = fields["computer_name"] or None
                if source_type != "hardware":
                    computer_name = None
                os_name = fields["os"] or None
                ram = _parse_int(fields["ram_gb"])
                cpu = fields["cpu"] or None
                mac = fields["mac_address"] or ""
                current_user_label = fields["assigned_to"]
                remarks_only = fields["remarks"] or None

                if source_type == "inventory":
                    category = (type_label or "").upper()
                    if category in {"FURNITURE", "KITCHEN", "TOOLS"}:
                        skipped += 1
                        continue

                if not legacy:
                    errors.append(f"Row {idx}: missing source ID after column mapping")
                    skipped += 1
                    continue

                norm_legacy = _norm_id(legacy)
                norm_serial = _norm_id(serial)
                norm_service = _norm_id(service)
                if (
                    (norm_service and norm_service in existing["service_tag"])
                    or (norm_serial and norm_serial in existing["serial"])
                    or (
                        norm_legacy in existing["legacy"]
                        or norm_legacy in existing["asset_number"]
                    )
                ):
                    duplicated += 1
                    if skip_duplicates:
                        skipped += 1
                        continue
                    conflicted += 1
                    continue

                purchased_by, owner_id, _owner_label, _own_warns = _resolve_ownership_from_fields(
                    fields, customers
                )
                if purchased_by == "customer" and owner_id is None:
                    purchased_by = "unknown"
                if purchased_by == "unknown" and skip_review_rows:
                    skipped += 1
                    conflicted += 1
                    continue

                used_for = _match_customer(customers, cust_used) if cust_used else None
                supplier_id = (
                    _get_or_create_supplier(db, supplier_name) if supplier_name else None
                )

                status = "available"
                cond_u = (condition or "").upper()
                if "DISPOSE" in cond_u or "SCRAP" in cond_u:
                    status = "disposed"
                elif "RETURN" in cond_u and "CUSTOMER" in cond_u:
                    status = "returned_to_customer"
                elif "NOT WORKING" in cond_u or "DAMAGE" in cond_u:
                    status = "damaged"
                elif "RETIRE" in cond_u:
                    status = "retired"

                try:
                    at = _resolve_asset_type(db, type_label)
                    warranty_clean = warranty if warranty and warranty.year < 2090 else None
                    asset = it_asset_service.create_asset(
                        db,
                        actor=actor,
                        asset_type_id=at.id,
                        asset_number=legacy,
                        legacy_asset_number=legacy,
                        serial_number=serial or None,
                        make=make,
                        model=model,
                        purchase_date=purchase_date,
                        purchase_cost=cost,
                        warranty_expiry=warranty_clean,
                        location=location,
                        notes=remarks_only,
                        description=desc,
                        service_tag=service or None,
                        purchased_by=purchased_by,
                        owner_customer_id=owner_id,
                        customer_used_for_id=used_for.id if used_for else None,
                        supplier_id=supplier_id,
                        invoice_number=invoice,
                        condition=condition,
                        commit=False,
                    )
                    if status != "available":
                        asset.status = status
                        db.add(asset)

                    if source_type == "hardware" and (type_label or "").lower() in {
                        "laptop",
                        "workstation",
                        "server",
                        "desktop",
                    }:
                        cname = (computer_name or desc or legacy or asset.asset_number)[:40]
                        existing_c = db.scalar(
                            select(Computer).where(Computer.computer_name == cname)
                        )
                        if existing_c is None:
                            db.add(
                                Computer(
                                    id=uuid4(),
                                    asset_id=asset.id,
                                    computer_name=cname,
                                    os=os_name,
                                    processor=cpu,
                                    ram_gb=ram,
                                    mac_address=(mac[:17] if mac else None),
                                )
                            )

                    assignee = (
                        _match_user(users, current_user_label) if current_user_label else None
                    )
                    if assignee and asset.status == "available":
                        try:
                            it_asset_service.assign_asset(
                                db,
                                asset,
                                user_id=assignee.id,
                                by_user=actor,
                                notes="Imported assignment",
                                commit=False,
                            )
                        except Exception:
                            pass

                    if purchased_by == "customer":
                        owned_cust += 1
                    elif purchased_by == "organization":
                        owned_org += 1
                    imported += 1
                    existing["legacy"].add(norm_legacy)
                    existing["asset_number"].add(norm_legacy)
                    if norm_serial:
                        existing["serial"].add(norm_serial)
                    if norm_service:
                        existing["service_tag"].add(norm_service)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"Row {idx}: {exc}")
                    skipped += 1

        elif source_type == "accounts":
            for row in rows:
                name = _get(row, "EMPLOYEE NAME")
                email = _get(row, "EMAIL")
                username = _get(row, "USERNAME")
                status_raw = _get(row, "STATUS")
                user = (
                    _match_user(users, email)
                    or _match_user(users, name)
                    or _match_user(users, username)
                )
                if user is None:
                    skipped += 1
                    continue
                acct_status = "active"
                if "ex-" in status_raw.lower():
                    acct_status = "deactivated"
                if username:
                    existing_acct = db.scalar(
                        select(ITUserAccount).where(
                            ITUserAccount.user_id == user.id,
                            ITUserAccount.account_type == "domain",
                            ITUserAccount.username == username,
                        )
                    )
                    if existing_acct:
                        skipped += 1
                        duplicated += 1
                    else:
                        db.add(
                            ITUserAccount(
                                id=uuid4(),
                                user_id=user.id,
                                account_type="domain",
                                username=username,
                                display_name=name or None,
                                status=acct_status,
                                credential_status="migration_required",
                                notes="Legacy Credential — Migration Required (passwords not imported)",
                            )
                        )
                        imported += 1
                teams = _get(row, "MS TEAMS ID")
                if teams:
                    existing_t = db.scalar(
                        select(ITUserAccount).where(
                            ITUserAccount.user_id == user.id,
                            ITUserAccount.account_type == "email",
                            ITUserAccount.username == teams,
                        )
                    )
                    if not existing_t:
                        db.add(
                            ITUserAccount(
                                id=uuid4(),
                                user_id=user.id,
                                account_type="email",
                                username=teams,
                                display_name=name or None,
                                status=acct_status,
                                credential_status="migration_required",
                                notes="Imported Teams/email identity — Migration Required",
                            )
                        )
                        imported += 1

        elif source_type == "software":
            for row in rows:
                software = _get(row, "SOFTWARE")
                if not software:
                    skipped += 1
                    continue
                purchased = _get(row, "PURCHASED BY")
                seats = _parse_int(_get(row, "NO OF USER\\LICENSE", "NO OF USER/LICENSE")) or 1
                expiry = _parse_date(_get(row, "LICENSE VALID UPTO"))
                renewal = _get(row, "RENEWAL MODE")
                assignee_label = _get(row, "USER")
                dept = _get(row, "DEPARTMENT")
                comments = _get(row, "COMMENTS")

                catalog = db.scalar(
                    select(SoftwareCatalog).where(
                        func.lower(SoftwareCatalog.name) == software.lower()
                    )
                )
                if catalog is None:
                    catalog = SoftwareCatalog(id=uuid4(), name=software, is_active=True)
                    db.add(catalog)
                    db.flush()

                purchased_by = "organization"
                owner_id = None
                if purchased and _norm_name(purchased) not in {"prosohm", "organization"}:
                    cust = _match_customer(customers, purchased)
                    if cust:
                        purchased_by = "customer"
                        owner_id = cust.id
                        owned_cust += 1
                    else:
                        owned_org += 1
                else:
                    owned_org += 1

                pool = SoftwareLicensePool(
                    id=uuid4(),
                    software_id=catalog.id,
                    purchased_by=purchased_by,
                    owner_customer_id=owner_id,
                    seat_count=seats,
                    expiry_date=expiry,
                    renewal_mode=renewal or None,
                    notes=comments or None,
                )
                db.add(pool)
                db.flush()
                assignee = _match_user(users, assignee_label) if assignee_label else None
                if assignee:
                    db.add(
                        SoftwareAssignment(
                            id=uuid4(),
                            license_pool_id=pool.id,
                            user_id=assignee.id,
                            assigned_date=date.today(),
                            department=dept or None,
                        )
                    )
                imported += 1

        elif source_type == "consumables":
            for row in rows:
                name = _get(row, "Name", "NAME")
                if not name:
                    skipped += 1
                    continue
                total = _parse_int(_get(row, "QTY")) or 0
                issued = _parse_int(_get(row, "IN USE")) or 0
                existing_item = db.scalar(
                    select(InventoryItem).where(
                        func.lower(InventoryItem.name) == name.lower(),
                        InventoryItem.is_deleted.is_(False),
                    )
                )
                if existing_item:
                    duplicated += 1
                    skipped += 1
                    continue
                db.add(
                    InventoryItem(
                        id=uuid4(),
                        name=name,
                        description=_get(row, "Description") or None,
                        category=_get(row, "Category") or None,
                        total_qty=total,
                        issued_qty=issued,
                        location=_get(row, "STORAGE LOCATION") or None,
                        condition=_get(row, "CONDITION") or None,
                        unit_cost=_parse_decimal(_get(row, "VALUE")),
                        status="current",
                        purchased_by="unknown",
                    )
                )
                imported += 1

        elif source_type == "suppliers":
            for row in rows:
                name = _get(row, "SUPPLIER NAME", "Name")
                if not name:
                    skipped += 1
                    continue
                before = db.scalar(
                    select(func.count()).select_from(ITSupplier).where(
                        func.lower(ITSupplier.name) == name.lower()
                    )
                )
                _get_or_create_supplier(db, name)
                after_exists = db.scalar(
                    select(ITSupplier).where(func.lower(ITSupplier.name) == name.lower())
                )
                if before and before > 0:
                    duplicated += 1
                elif after_exists:
                    imported += 1

        db.flush()
        log_activity(
            db,
            user=actor,
            entity_type=EntityType.it_settings,
            entity_id=actor.id,
            action=ActivityAction.it_migration_imported,
            new_value={
                "source_type": source_type,
                "session_id": session_id,
                "imported": imported,
                "skipped": skipped,
                "duplicated": duplicated,
                "sensitive_excluded": sensitive_excluded,
            },
            outcome="success",
            module=MODULE,
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    try:
        _session_path(session_id).unlink(missing_ok=True)
    except OSError:
        pass

    result = {
        "session_id": session_id,
        "source_type": source_type,
        "filename": session.get("filename"),
        "imported": imported,
        "skipped": skipped,
        "duplicated": duplicated,
        "conflicted": conflicted,
        "requires_review": conflicted,
        "sensitive_data_excluded": sensitive_excluded,
        "organization_owned": owned_org,
        "customer_owned": owned_cust,
        "returned_assets": 0,
        "errors": errors[:50],
        "message": (
            "Import committed. Source IDs preserved as asset numbers; "
            "validation codes were not written into asset fields."
        ),
    }
    try:
        report = Path(__file__).resolve().parents[2] / "docs" / "IT_IMPORT_RESULT.md"
        report.write_text(
            "\n".join(
                [
                    "# IT Import Result",
                    "",
                    f"> Generated: {datetime.utcnow().isoformat()}Z",
                    "",
                    f"- **Source file:** {result.get('filename')}",
                    f"- **Source type:** {result.get('source_type')}",
                    f"- **Imported:** {result.get('imported')}",
                    f"- **Skipped:** {result.get('skipped')}",
                    f"- **Duplicated:** {result.get('duplicated')}",
                    f"- **Organization-owned:** {result.get('organization_owned')}",
                    f"- **Customer-owned:** {result.get('customer_owned')}",
                    f"- **Credential secrets excluded:** {result.get('sensitive_data_excluded')}",
                    f"- **Errors:** {len(result.get('errors') or [])}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    except OSError:
        pass
    return result
