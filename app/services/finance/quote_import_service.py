"""Quote import and revision history."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.finance import Quote, QuoteRevision
from app.models.models import Customer, Project, User, WorkingModel
from app.services.finance.fx_service import to_base_amount


def _parse_decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, AttributeError) as exc:
        raise ProTrackValidationError(f"Invalid decimal for {field}: {value}") from exc


def _parse_date(value: object | None) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ProTrackValidationError(f"Invalid date: {value}")


def _find_customer(db: Session, name_or_code: str) -> Customer:
    key = name_or_code.strip()
    customer = db.scalar(
        select(Customer).where(
            (Customer.name == key) | (Customer.code == key),
            Customer.is_active.is_(True),
        )
    )
    if customer is None:
        raise ProTrackValidationError(f"Customer not found: {key}")
    return customer


def _find_working_model(db: Session, name_or_code: str | None) -> WorkingModel | None:
    if not name_or_code or not str(name_or_code).strip():
        return None
    key = str(name_or_code).strip()
    model = db.scalar(
        select(WorkingModel).where(
            (WorkingModel.code == key) | (WorkingModel.name == key),
            WorkingModel.is_active.is_(True),
        )
    )
    return model


def import_quote_row(
    db: Session,
    *,
    row: dict[str, object],
    actor: User,
    source: str = "csv",
) -> Quote:
    customer_key = str(row.get("customer") or row.get("Customer") or "").strip()
    tool_number = str(row.get("tool_number") or row.get("Tool Number") or "").strip()
    if not customer_key or not tool_number:
        raise ProTrackValidationError("Customer and Tool Number are required")

    currency = str(row.get("currency") or row.get("Currency") or "USD").strip().upper()
    quoted_hours = _parse_decimal(row.get("quoted_hours") or row.get("Quoted Hours") or 0, "quoted_hours")
    estimated_cost = _parse_decimal(
        row.get("estimated_cost") or row.get("Estimated Cost") or 0, "estimated_cost"
    )
    quoted_revenue = _parse_decimal(
        row.get("quoted_revenue") or row.get("Quoted Revenue") or 0, "quoted_revenue"
    )
    margin = quoted_revenue - estimated_cost
    if "margin" in row or "Margin" in row:
        margin = _parse_decimal(row.get("margin") or row.get("Margin") or margin, "margin")
    margin_percent = (
        (margin / quoted_revenue * 100).quantize(Decimal("0.01")) if quoted_revenue else Decimal("0")
    )

    version = int(row.get("version") or row.get("Version") or 1)
    revision = str(row.get("revision") or row.get("Revision") or "A").strip() or "A"
    start_date = _parse_date(row.get("start_date") or row.get("Start Date"))
    end_date = _parse_date(row.get("end_date") or row.get("End Date"))
    fx_date = start_date or date.today()

    base_cost, fx_rate, fx_date = to_base_amount(
        db, amount=estimated_cost, currency_code=currency, on_date=fx_date
    )
    base_revenue, _, _ = to_base_amount(
        db, amount=quoted_revenue, currency_code=currency, on_date=fx_date
    )

    customer = _find_customer(db, customer_key)
    working_model = _find_working_model(
        db, str(row.get("business_model") or row.get("Business Model") or "") or None
    )
    project = db.scalar(
        select(Project).where(
            Project.tool_number == tool_number,
            Project.is_deleted.is_(False),
        )
    )

    quote = db.scalar(
        select(Quote).where(
            Quote.customer_id == customer.id,
            Quote.tool_number == tool_number,
            Quote.is_active.is_(True),
        )
    )
    if quote is None:
        quote = Quote(
            customer_id=customer.id,
            project_id=project.id if project is not None else None,
            tool_number=tool_number,
            business_model_id=working_model.id if working_model else None,
            estimator_id=actor.id,
            currency_code=currency,
            current_version=version,
            current_revision=revision,
        )
        db.add(quote)
        db.flush()
    else:
        existing = db.scalar(
            select(QuoteRevision).where(
                QuoteRevision.quote_id == quote.id,
                QuoteRevision.version == version,
                QuoteRevision.revision == revision,
            )
        )
        if existing is not None:
            raise ProTrackValidationError(
                f"Quote revision {version}-{revision} already exists for {tool_number}"
            )
        quote.current_version = version
        quote.current_revision = revision
        quote.currency_code = currency
        if working_model is not None:
            quote.business_model_id = working_model.id
        if project is not None:
            quote.project_id = project.id

    revision_row = QuoteRevision(
        quote_id=quote.id,
        version=version,
        revision=revision,
        quoted_hours=quoted_hours,
        estimated_cost=estimated_cost,
        quoted_revenue=quoted_revenue,
        margin=margin,
        margin_percent=margin_percent,
        base_estimated_cost_inr=base_cost,
        base_quoted_revenue_inr=base_revenue,
        fx_rate=fx_rate,
        fx_date=fx_date,
        start_date=start_date,
        end_date=end_date,
        imported_from=source,
        imported_at=datetime.now(timezone.utc).replace(tzinfo=None),
        imported_by_id=actor.id,
    )
    db.add(revision_row)
    db.flush()
    return quote


def import_quotes_from_csv(
    db: Session,
    *,
    content: bytes,
    actor: User,
) -> list[Quote]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ProTrackValidationError("CSV has no header row")
    quotes: list[Quote] = []
    for index, row in enumerate(reader, start=2):
        try:
            quotes.append(import_quote_row(db, row=row, actor=actor, source="csv"))
        except ProTrackValidationError as exc:
            raise ProTrackValidationError(f"Row {index}: {exc}") from exc
    return quotes


def import_quotes_from_excel(
    db: Session,
    *,
    content: bytes,
    actor: User,
) -> list[Quote]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise ProTrackValidationError(
            "Excel import requires openpyxl. Upload CSV instead."
        ) from exc

    workbook = load_workbook(filename=io.BytesIO(content), read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ProTrackValidationError("Excel sheet is empty")
    headers = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
    quotes: list[Quote] = []
    for index, values in enumerate(rows[1:], start=2):
        if values is None or all(v is None or str(v).strip() == "" for v in values):
            continue
        row = {headers[i]: values[i] for i in range(min(len(headers), len(values)))}
        try:
            quotes.append(import_quote_row(db, row=row, actor=actor, source="excel"))
        except ProTrackValidationError as exc:
            raise ProTrackValidationError(f"Row {index}: {exc}") from exc
    return quotes
