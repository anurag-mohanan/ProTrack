"""History data import packs for EMP onboarding (employment, finance, org)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import CostFrequency, CostNature, EmploymentType, ExpensePaidBy
from app.models.finance import CostCentre, EmployeeCostProfile, Expense
from app.models.models import Customer, User

HISTORY_PACKS: tuple[dict[str, Any], ...] = (
    {
        "id": "employment",
        "title": "Employment history",
        "description": "Joining/leaving dates, employment type, designation for existing users (match by email).",
        "template": "employment",
        "columns": [
            "email",
            "joining_date",
            "leaving_date",
            "first_job_date",
            "employment_type",
            "designation",
        ],
    },
    {
        "id": "compensation",
        "title": "Compensation / cost profiles",
        "description": "Historical monthly salary and hourly cost profiles (match user by email).",
        "template": "compensation",
        "columns": [
            "email",
            "monthly_salary",
            "hourly_cost",
            "currency_code",
            "effective_from",
            "notes",
        ],
    },
    {
        "id": "expenses",
        "title": "Expense history",
        "description": "Past opex/capex rows by cost centre code.",
        "template": "expenses",
        "columns": [
            "cost_centre_code",
            "name",
            "amount",
            "currency_code",
            "purchase_date",
            "nature",
            "frequency",
            "vendor_name",
            "description",
        ],
    },
    {
        "id": "customers",
        "title": "Customer master",
        "description": "Historical customers required before project/quote imports.",
        "template": "customers",
        "columns": ["code", "name"],
    },
    {
        "id": "projects_legacy",
        "title": "Historical projects",
        "description": "Legacy project workbooks (existing importer).",
        "href": "/admin/imports/historical-projects",
        "template": None,
        "columns": [],
    },
    {
        "id": "timesheets_legacy",
        "title": "Historical timesheets",
        "description": "Designer timesheet files (existing importer).",
        "href": "/admin/imports/historical-timesheets",
        "template": None,
        "columns": [],
    },
    {
        "id": "quotes",
        "title": "Awarded quotes",
        "description": "Use Finance → Quotes import (PDF/table) for commercial history.",
        "href": "/finance",
        "template": None,
        "columns": [],
        "note": "Open Finance Quotes and use Import.",
    },
)


@dataclass
class ImportResult:
    pack: str
    dry_run: bool
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def list_packs() -> list[dict[str, Any]]:
    return list(HISTORY_PACKS)


def template_csv(pack_id: str) -> str:
    pack = next((p for p in HISTORY_PACKS if p["id"] == pack_id and p.get("template")), None)
    if pack is None:
        raise ValueError(f"No CSV template for pack: {pack_id}")
    columns: list[str] = list(pack["columns"])
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    # Sample row hints
    samples = {
        "employment": [
            "designer@example.com",
            "2020-01-15",
            "",
            "2018-06-01",
            "full_time",
            "Senior Designer",
        ],
        "compensation": [
            "designer@example.com",
            "85000",
            "500",
            "INR",
            "2024-01-01",
            "FY24 band",
        ],
        "expenses": [
            "OPS",
            "Office rent Jan 2024",
            "120000",
            "INR",
            "2024-01-01",
            "opex",
            "monthly",
            "Landlord Co",
            "",
        ],
        "customers": ["ACME", "Acme Automotive"],
    }
    if pack_id in samples:
        writer.writerow(samples[pack_id])
    return buf.getvalue()


def _parse_date(raw: str | None) -> date | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {text}")


def _parse_decimal(raw: str | None, default: str = "0") -> Decimal:
    text = (raw or default).strip().replace(",", "")
    if not text:
        text = default
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid number: {raw}") from exc


def _read_rows(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")
    rows: list[dict[str, str]] = []
    for row in reader:
        cleaned = {
            (k or "").strip().lower(): (v or "").strip()
            for k, v in row.items()
            if k is not None
        }
        if any(cleaned.values()):
            rows.append(cleaned)
    return rows


def import_employment(
    db: Session, content: bytes, *, dry_run: bool = True
) -> ImportResult:
    result = ImportResult(pack="employment", dry_run=dry_run)
    rows = _read_rows(content)
    for idx, row in enumerate(rows, start=2):
        email = (row.get("email") or "").lower()
        if not email:
            result.errors.append(f"Row {idx}: email required")
            result.skipped += 1
            continue
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            result.errors.append(f"Row {idx}: user not found for {email}")
            result.skipped += 1
            continue
        try:
            joining = _parse_date(row.get("joining_date"))
            leaving = _parse_date(row.get("leaving_date"))
            first_job = _parse_date(row.get("first_job_date"))
        except ValueError as exc:
            result.errors.append(f"Row {idx}: {exc}")
            result.skipped += 1
            continue
        emp_raw = (row.get("employment_type") or "").strip()
        emp_type = None
        if emp_raw:
            try:
                emp_type = EmploymentType(emp_raw)
            except ValueError:
                result.warnings.append(
                    f"Row {idx}: unknown employment_type '{emp_raw}' — left unchanged"
                )
        if dry_run:
            result.updated += 1
            continue
        if joining is not None:
            user.joining_date = joining
        if leaving is not None:
            user.leaving_date = leaving
        if first_job is not None:
            user.first_job_date = first_job
        if emp_type is not None:
            user.employment_type = emp_type
        if row.get("designation"):
            user.designation = row["designation"][:100]
        db.add(user)
        result.updated += 1
    if not dry_run:
        db.flush()
    return result


def import_compensation(
    db: Session, content: bytes, *, dry_run: bool = True
) -> ImportResult:
    result = ImportResult(pack="compensation", dry_run=dry_run)
    rows = _read_rows(content)
    for idx, row in enumerate(rows, start=2):
        email = (row.get("email") or "").lower()
        if not email:
            result.errors.append(f"Row {idx}: email required")
            result.skipped += 1
            continue
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            result.errors.append(f"Row {idx}: user not found for {email}")
            result.skipped += 1
            continue
        try:
            monthly = _parse_decimal(row.get("monthly_salary"))
            hourly = _parse_decimal(row.get("hourly_cost"), "0")
            effective = _parse_date(row.get("effective_from")) or date.today()
        except ValueError as exc:
            result.errors.append(f"Row {idx}: {exc}")
            result.skipped += 1
            continue
        currency = (row.get("currency_code") or "INR").upper()[:3]
        existing = db.scalar(
            select(EmployeeCostProfile).where(EmployeeCostProfile.user_id == user.id)
        )
        if dry_run:
            if existing:
                result.updated += 1
            else:
                result.created += 1
            continue
        if existing is None:
            existing = EmployeeCostProfile(
                user_id=user.id,
                currency_code=currency,
                monthly_salary=monthly,
                hourly_cost=hourly,
                base_monthly_salary_inr=monthly if currency == "INR" else monthly,
                base_hourly_cost_inr=hourly if currency == "INR" else hourly,
                fx_rate=Decimal("1"),
                effective_from=effective,
                notes=row.get("notes") or None,
                is_active=True,
            )
            db.add(existing)
            result.created += 1
        else:
            existing.monthly_salary = monthly
            existing.hourly_cost = hourly
            existing.currency_code = currency
            existing.effective_from = effective
            if row.get("notes"):
                existing.notes = row["notes"]
            if currency == "INR":
                existing.base_monthly_salary_inr = monthly
                existing.base_hourly_cost_inr = hourly
            db.add(existing)
            result.updated += 1
    if not dry_run:
        db.flush()
    return result


def import_expenses(db: Session, content: bytes, *, dry_run: bool = True) -> ImportResult:
    result = ImportResult(pack="expenses", dry_run=dry_run)
    rows = _read_rows(content)
    centres = {
        c.code.upper(): c
        for c in db.scalars(select(CostCentre)).all()
    }
    for idx, row in enumerate(rows, start=2):
        code = (row.get("cost_centre_code") or "").upper()
        name = row.get("name") or ""
        if not code or not name:
            result.errors.append(f"Row {idx}: cost_centre_code and name required")
            result.skipped += 1
            continue
        centre = centres.get(code)
        if centre is None:
            result.errors.append(f"Row {idx}: cost centre '{code}' not found")
            result.skipped += 1
            continue
        try:
            amount = _parse_decimal(row.get("amount"))
            purchase = _parse_date(row.get("purchase_date")) or date.today()
        except ValueError as exc:
            result.errors.append(f"Row {idx}: {exc}")
            result.skipped += 1
            continue
        currency = (row.get("currency_code") or "INR").upper()[:3]
        nature_raw = (row.get("nature") or "opex").lower()
        freq_raw = (row.get("frequency") or "monthly").lower()
        try:
            nature = CostNature(nature_raw)
        except ValueError:
            nature = CostNature.opex
            result.warnings.append(f"Row {idx}: nature defaulted to opex")
        try:
            frequency = CostFrequency(freq_raw)
        except ValueError:
            frequency = CostFrequency.monthly
            result.warnings.append(f"Row {idx}: frequency defaulted to monthly")
        if dry_run:
            result.created += 1
            continue
        expense = Expense(
            cost_centre_id=centre.id,
            name=name[:200],
            description=row.get("description") or None,
            nature=nature,
            frequency=frequency,
            currency_code=currency,
            amount=amount,
            base_amount_inr=amount if currency == "INR" else amount,
            fx_rate=Decimal("1"),
            fx_date=purchase,
            purchase_date=purchase,
            start_date=purchase,
            vendor_name=row.get("vendor_name") or None,
            paid_by=ExpensePaidBy.prosohm,
            is_active=True,
        )
        db.add(expense)
        result.created += 1
    if not dry_run:
        db.flush()
    return result


def import_customers(db: Session, content: bytes, *, dry_run: bool = True) -> ImportResult:
    result = ImportResult(pack="customers", dry_run=dry_run)
    rows = _read_rows(content)
    for idx, row in enumerate(rows, start=2):
        code = (row.get("code") or "").strip()
        name = (row.get("name") or "").strip()
        if not code or not name:
            result.errors.append(f"Row {idx}: code and name required")
            result.skipped += 1
            continue
        existing = db.scalar(select(Customer).where(Customer.code == code))
        if dry_run:
            if existing:
                result.updated += 1
            else:
                result.created += 1
            continue
        if existing is None:
            db.add(Customer(code=code[:50], name=name[:200]))
            result.created += 1
        else:
            existing.name = name[:200]
            db.add(existing)
            result.updated += 1
    if not dry_run:
        db.flush()
    return result


IMPORTERS = {
    "employment": import_employment,
    "compensation": import_compensation,
    "expenses": import_expenses,
    "customers": import_customers,
}


def run_pack(
    db: Session, pack_id: str, content: bytes, *, dry_run: bool = True
) -> ImportResult:
    fn = IMPORTERS.get(pack_id)
    if fn is None:
        raise ValueError(f"Unsupported import pack: {pack_id}")
    return fn(db, content, dry_run=dry_run)
