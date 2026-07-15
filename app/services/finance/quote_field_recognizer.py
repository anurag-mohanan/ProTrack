"""AI-assisted recognition of awarded-quote import fields (Prosohm QT + table packs)."""

from __future__ import annotations

import re

# Canonical import keys expected by quote_import_service.import_quote_row
_HEADER_SYNONYMS: dict[str, tuple[str, ...]] = {
    "customer": (
        "customer",
        "customer name",
        "prepared for",
        "client",
        "buyer",
        "account",
    ),
    "tool_number": (
        "tool number",
        "tool no",
        "tool #",
        "customer project #",
        "customer project",
        "project #",
        "project number",
        "job number",
        "wo",
        "work order",
    ),
    "quoted_hours": (
        "quoted hours",
        "hours",
        "qty/hrs",
        "qty hrs",
        "qty",
        "quantity",
        "hrs",
    ),
    "quoted_revenue": (
        "quoted revenue",
        "revenue",
        "amount",
        "total",
        "quote value",
        "value",
        "price",
    ),
    "estimated_cost": (
        "estimated cost",
        "cost",
        "est cost",
        "internal cost",
    ),
    "currency": (
        "currency",
        "curr",
        "ccy",
    ),
    "start_date": (
        "start date",
        "quote date",
        "date",
        "award date",
    ),
    "external_quote_number": (
        "quote#",
        "quote #",
        "quote number",
        "quote no",
        "qt number",
        "external quote",
    ),
    "version": ("version", "ver"),
    "revision": ("revision", "rev"),
    "business_model": ("business model", "working model", "model"),
}


def _normalize_header(value: object) -> str:
    text = " ".join(str(value or "").strip().lower().replace("_", " ").split())
    text = text.replace("：", ":")
    return text.rstrip(":")


def recognize_header_key(header: str) -> str | None:
    """Map a free-form column header to a canonical quote import field."""
    norm = _normalize_header(header)
    if not norm:
        return None
    if norm in _HEADER_SYNONYMS:
        return norm

    best: tuple[int, str] | None = None
    for canonical, aliases in _HEADER_SYNONYMS.items():
        for alias in aliases:
            if norm == alias or norm == canonical:
                return canonical
            if norm.startswith(alias + " ") or norm.startswith(alias + "/") or norm == alias:
                length = len(alias)
                if best is None or length > best[0]:
                    best = (length, canonical)
            elif alias.startswith(norm) and len(norm) >= 4:
                length = len(norm)
                if best is None or length > best[0]:
                    best = (length, canonical)
    return best[1] if best else None


def recognize_table_row(row: dict[str, object]) -> dict[str, object]:
    """Rewrite a raw spreadsheet/PDF-table dict into canonical quote import keys.

    Unmapped original keys are kept so explicit headers still work. Synonyms fill
    missing required fields (customer, tool_number, hours, revenue).
    """
    recognized: dict[str, object] = dict(row)
    mapped: dict[str, object] = {}
    for key, value in row.items():
        canonical = recognize_header_key(str(key))
        if canonical is None:
            continue
        if value is None or str(value).strip() == "":
            continue
        if canonical not in mapped:
            mapped[canonical] = value
    recognized.update(mapped)
    # Convenience aliases still used by import_quote_row
    if "customer" in mapped and "Customer" not in recognized:
        recognized["Customer"] = mapped["customer"]
    if "tool_number" in mapped and "Tool Number" not in recognized:
        recognized["Tool Number"] = mapped["tool_number"]
    if "quoted_hours" in mapped and "Quoted Hours" not in recognized:
        recognized["Quoted Hours"] = mapped["quoted_hours"]
    if "quoted_revenue" in mapped and "Quoted Revenue" not in recognized:
        recognized["Quoted Revenue"] = mapped["quoted_revenue"]
    if "estimated_cost" in mapped and "Estimated Cost" not in recognized:
        recognized["Estimated Cost"] = mapped["estimated_cost"]
    if "currency" in mapped and "Currency" not in recognized:
        recognized["Currency"] = mapped["currency"]
    if "start_date" in mapped and "Start Date" not in recognized:
        recognized["Start Date"] = mapped["start_date"]
    return recognized


def recognize_from_filename(filename: str | None) -> dict[str, object]:
    """Infer Quote# / Customer Project # from Prosohm filenames like QT-…-SY#17974.pdf."""
    if not filename:
        return {}
    out: dict[str, object] = {}
    stem = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    # QT-YYYY-YY-NNN before optional -SY# / customer suffix
    qt = re.search(r"(QT-\d{4}-\d{2}-\d+)", stem, re.IGNORECASE)
    if not qt:
        qt = re.search(r"(QT-[A-Z0-9]+(?:-\d+)+)", stem, re.IGNORECASE)
    if qt:
        out["external_quote_number"] = qt.group(1).upper()
    proj = re.search(r"(?:SY)?#(\d+)", stem, re.IGNORECASE)
    if proj:
        out["tool_number"] = proj.group(1)
        out["Tool Number"] = proj.group(1)
    return out


def enrich_import_row(row: dict[str, object], *, filename: str | None = None) -> dict[str, object]:
    """Full recognition pass used by CSV/Excel/PDF table imports."""
    enriched = recognize_table_row(row)
    for key, value in recognize_from_filename(filename).items():
        existing = enriched.get(key)
        if existing is None or str(existing).strip() == "":
            enriched[key] = value
    return enriched
