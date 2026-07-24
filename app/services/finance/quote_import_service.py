"""Quote import and revision history."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProTrackValidationError
from app.models.finance import Quote, QuoteRevision
from app.models.models import Customer, Project, User, WorkingModel
from app.services.finance.fx_service import to_base_amount


@dataclass
class QuoteImportOutcome:
    quote: Quote
    project_created: bool = False
    warnings: list[str] = field(default_factory=list)
    quoted_hours: Decimal | None = None
    quoted_revenue: Decimal | None = None


def _parse_decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, AttributeError) as exc:
        raise ProTrackValidationError(f"Invalid decimal for {field}: {value}") from exc


def _parse_date(value: object | None) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    # DD/MM/YYYY first (Prosohm Indian commercial docs), then ISO / US.
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ProTrackValidationError(f"Invalid date: {value}")


def _customer_name_variants(name: str) -> list[str]:
    key = name.strip()
    variants = [key]
    if "-" in key:
        variants.append(key.rsplit("-", 1)[0].strip())
    if " - " in key:
        variants.append(key.split(" - ", 1)[0].strip())
    # de-dupe preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for item in variants:
        if item and item.lower() not in seen:
            seen.add(item.lower())
            ordered.append(item)
    return ordered


def _find_customer(db: Session, name_or_code: str, *, soft_match: bool = False) -> Customer:
    key = name_or_code.strip()
    customer = db.scalar(
        select(Customer).where(
            (Customer.name == key) | (Customer.code == key),
            Customer.is_active.is_(True),
        )
    )
    if customer is not None:
        return customer

    if soft_match:
        customers = list(
            db.scalars(select(Customer).where(Customer.is_active.is_(True))).all()
        )
        for variant in _customer_name_variants(key):
            customer = db.scalar(
                select(Customer).where(
                    (Customer.name == variant) | (Customer.code == variant),
                    Customer.is_active.is_(True),
                )
            )
            if customer is not None:
                return customer
            customer = db.scalar(
                select(Customer).where(
                    Customer.is_active.is_(True),
                    func.lower(Customer.name).contains(variant.lower()),
                )
            )
            if customer is not None:
                return customer

            # Prefix / short Prepared For names: "Crest Mold" → "Crest Mold Technologies (CMT)"
            variant_l = variant.lower()
            best: Customer | None = None
            best_score = 0
            for candidate in customers:
                name_l = (candidate.name or "").lower()
                code_l = (candidate.code or "").lower()
                score = 0
                if name_l == variant_l or code_l == variant_l:
                    score = 10_000
                elif name_l.startswith(variant_l) or variant_l.startswith(name_l):
                    score = 5_000 + len(variant_l)
                elif variant_l in name_l or name_l in variant_l:
                    score = 1_000 + len(variant_l)
                elif code_l and (variant_l in code_l or code_l in variant_l):
                    score = 500 + len(variant_l)
                if score > best_score:
                    best_score = score
                    best = candidate
            if best is not None and best_score >= 1_000:
                return best

    raise ProTrackValidationError(f"Customer not found: {key}")


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


def ensure_project_for_quote_import(
    db: Session,
    *,
    tool_number: str,
    customer_id: UUID,
    team_id: UUID | None,
    quoted_hours: Decimal,
    name_hint: str | None,
    create_if_missing: bool,
) -> tuple[Project | None, bool]:
    """Match project by tool_number; optionally create a minimal project."""
    project = db.scalar(
        select(Project).where(
            func.lower(Project.tool_number) == tool_number.strip().lower(),
            Project.is_deleted.is_(False),
        )
    )
    if project is not None:
        if (project.quoted_hours is None or project.quoted_hours == 0) and quoted_hours:
            project.quoted_hours = quoted_hours
        return project, False

    if not create_if_missing:
        return None, False

    # Shell project only: tool #, customer, optional team. Remaining fields stay blank
    # so Engineering fills them from Projects (due date, description, hours, etc.).
    project = Project(
        tool_number=tool_number.strip(),
        part_description="",
        customer_id=customer_id,
        team_id=team_id,
        quoted_hours=Decimal("0"),
        notes=None,
    )
    db.add(project)
    db.flush()
    return project, True


def import_manual_quote(
    db: Session,
    *,
    actor: User,
    team_id: UUID,
    customer_id: UUID,
    tool_number: str,
    quoted_revenue: Decimal,
    external_quote_number: str | None = None,
    currency_code: str | None = None,
    quoted_hours: Decimal = Decimal("0"),
    quoted_date: date | None = None,
    create_project: bool = True,
) -> QuoteImportOutcome:
    """Create/update an awarded quote from typed fields (no file / AI parse)."""
    customer = db.get(Customer, customer_id)
    if customer is None or not customer.is_active:
        raise ProTrackValidationError("Customer not found or inactive.")
    tool = tool_number.strip()
    if not tool:
        raise ProTrackValidationError("Project # (tool number) is required.")
    quote_no = (external_quote_number or "").strip() or None
    currency = (currency_code or "").strip().upper() or None
    row: dict[str, object] = {
        "customer": customer.name,
        "Customer": customer.name,
        "tool_number": tool,
        "Tool Number": tool,
        "quoted_revenue": quoted_revenue,
        "Quoted Revenue": quoted_revenue,
        "quoted_hours": quoted_hours,
        "Quoted Hours": quoted_hours,
        "estimated_cost": Decimal("0"),
        "Estimated Cost": Decimal("0"),
    }
    if quote_no:
        row["external_quote_number"] = quote_no
        row["Quote#"] = quote_no
    if currency:
        row["currency"] = currency
        row["Currency"] = currency
    if quoted_date is not None:
        row["quoted_date"] = quoted_date
        row["start_date"] = quoted_date
        row["Start Date"] = quoted_date
    return import_quote_row(
        db,
        row=row,
        actor=actor,
        source="manual",
        team_id=team_id,
        create_project=create_project,
    )


def _current_revision(db: Session, quote: Quote) -> QuoteRevision | None:
    return db.scalar(
        select(QuoteRevision).where(
            QuoteRevision.quote_id == quote.id,
            QuoteRevision.version == quote.current_version,
            QuoteRevision.revision == quote.current_revision,
        )
    )


_MISSING = object()


def update_quote(
    db: Session,
    *,
    quote: Quote,
    actor: User,
    team_id: UUID | None = None,
    customer_id: UUID | None = None,
    tool_number: str | None = None,
    quoted_revenue: Decimal | None = None,
    external_quote_number: str | None = None,
    currency_code: str | None = None,
    quoted_hours: Decimal | None = None,
    quoted_date: date | None = None,
    invoiced_date: object = _MISSING,
    is_invoiced: object = _MISSING,
    customer_po_number: object = _MISSING,
    is_paid: object = _MISSING,
    paid_date: object = _MISSING,
    create_project: bool = False,
) -> QuoteImportOutcome:
    """In-place edit of quote header + current revision (expenses-style)."""
    if customer_id is not None:
        customer = db.get(Customer, customer_id)
        if customer is None or not customer.is_active:
            raise ProTrackValidationError("Customer not found or inactive.")
        quote.customer_id = customer_id

    if team_id is not None:
        quote.team_id = team_id

    if tool_number is not None:
        tool = tool_number.strip()
        if not tool:
            raise ProTrackValidationError("Project # (tool number) is required.")
        quote.tool_number = tool

    if external_quote_number is not None:
        quote.external_quote_number = external_quote_number.strip() or None

    if currency_code is not None:
        currency = currency_code.strip().upper()
        if currency:
            quote.currency_code = currency

    if quoted_date is not None:
        quote.quoted_date = quoted_date

    from app.services.finance.quote_cash_ledger_service import (
        ensure_invoice_from_legacy_flags,
        ensure_payment_from_legacy_flags,
        list_invoice_lines,
        list_payment_lines,
        sync_quote_cash_flags,
    )

    has_invoice_lines = bool(list_invoice_lines(db, quote.id))
    has_payment_lines = bool(list_payment_lines(db, quote.id))

    # Legacy boolean convenience: only when ledger is empty, materialize lines.
    want_invoiced = None
    if is_invoiced is not _MISSING:
        want_invoiced = bool(is_invoiced)
    if invoiced_date is not _MISSING and invoiced_date is not None and want_invoiced is None:
        want_invoiced = True
    if invoiced_date is not _MISSING and invoiced_date is None and want_invoiced is None:
        want_invoiced = False

    if not has_invoice_lines and want_invoiced:
        ensure_invoice_from_legacy_flags(
            db,
            quote=quote,
            line_date=invoiced_date if invoiced_date is not _MISSING else None,
        )
        has_invoice_lines = True
    elif not has_invoice_lines:
        # Preserve prior boolean path when still no lines
        if is_invoiced is not _MISSING:
            quote.is_invoiced = bool(is_invoiced)
        if invoiced_date is not _MISSING:
            quote.invoiced_date = invoiced_date
            if invoiced_date is not None and is_invoiced is _MISSING:
                quote.is_invoiced = True
            elif invoiced_date is None and is_invoiced is _MISSING:
                quote.is_invoiced = False
        if quote.is_invoiced:
            if quote.invoiced_date is None:
                quote.invoiced_date = date.today()
        else:
            quote.invoiced_date = None
            quote.is_paid = False
            quote.paid_date = None

    if customer_po_number is not _MISSING:
        if customer_po_number is None:
            quote.customer_po_number = None
        else:
            quote.customer_po_number = str(customer_po_number).strip() or None

    want_paid = None
    if is_paid is not _MISSING:
        want_paid = bool(is_paid)
    if paid_date is not _MISSING and paid_date is not None and want_paid is None:
        want_paid = True
    if paid_date is not _MISSING and paid_date is None and want_paid is None:
        want_paid = False

    if has_invoice_lines and not has_payment_lines and want_paid:
        ensure_payment_from_legacy_flags(
            db,
            quote=quote,
            line_date=paid_date if paid_date is not _MISSING else None,
        )
    elif not has_invoice_lines and not has_payment_lines:
        if is_paid is not _MISSING:
            quote.is_paid = bool(is_paid)
        if paid_date is not _MISSING:
            quote.paid_date = paid_date
            if paid_date is not None and is_paid is _MISSING:
                quote.is_paid = True
            elif paid_date is None and is_paid is _MISSING:
                quote.is_paid = False
        if quote.is_paid:
            if not quote.is_invoiced:
                raise ProTrackValidationError(
                    "Mark the quote invoiced before recording payment."
                )
            if quote.paid_date is None:
                quote.paid_date = date.today()
        else:
            quote.paid_date = None

    if list_invoice_lines(db, quote.id) or list_payment_lines(db, quote.id):
        sync_quote_cash_flags(db, quote)

    customer = db.get(Customer, quote.customer_id)
    if customer is None:
        raise ProTrackValidationError("Customer not found or inactive.")

    revision = _current_revision(db, quote)
    if revision is None:
        raise ProTrackValidationError("Quote has no current revision to update.")

    if quoted_hours is not None:
        revision.quoted_hours = quoted_hours
    if quoted_revenue is not None:
        revision.quoted_revenue = quoted_revenue
    if quoted_date is not None:
        revision.start_date = quoted_date

    revision.margin = revision.quoted_revenue - revision.estimated_cost
    revision.margin_percent = (
        (revision.margin / revision.quoted_revenue * 100).quantize(Decimal("0.01"))
        if revision.quoted_revenue
        else Decimal("0")
    )

    fx_date = quote.quoted_date or revision.start_date or revision.fx_date or date.today()
    base_cost, fx_rate, fx_date = to_base_amount(
        db,
        amount=revision.estimated_cost,
        currency_code=quote.currency_code,
        on_date=fx_date,
    )
    base_revenue, _, _ = to_base_amount(
        db,
        amount=revision.quoted_revenue,
        currency_code=quote.currency_code,
        on_date=fx_date,
    )
    revision.base_estimated_cost_inr = base_cost
    revision.base_quoted_revenue_inr = base_revenue
    revision.fx_rate = fx_rate
    revision.fx_date = fx_date

    project, project_created = ensure_project_for_quote_import(
        db,
        tool_number=quote.tool_number,
        customer_id=quote.customer_id,
        team_id=quote.team_id,
        quoted_hours=revision.quoted_hours,
        name_hint=f"{quote.tool_number} — {customer.name}",
        create_if_missing=create_project,
    )
    if project is not None:
        quote.project_id = project.id
    elif tool_number is not None:
        # Tool changed and no match / create — clear stale link.
        quote.project_id = None

    db.flush()
    _ = actor  # reserved for future audit identity on revision
    return QuoteImportOutcome(
        quote=quote,
        project_created=project_created,
        warnings=[],
        quoted_hours=revision.quoted_hours,
        quoted_revenue=revision.quoted_revenue,
    )


def soft_delete_quote(db: Session, *, quote: Quote) -> None:
    quote.is_active = False
    db.flush()


def import_quote_row(
    db: Session,
    *,
    row: dict[str, object],
    actor: User,
    source: str = "csv",
    team_id: UUID | None = None,
    create_project: bool = True,
) -> QuoteImportOutcome:
    customer_key = str(row.get("customer") or row.get("Customer") or "").strip()
    tool_number = str(row.get("tool_number") or row.get("Tool Number") or "").strip()
    if not customer_key or not tool_number:
        raise ProTrackValidationError("Customer and Tool Number are required")

    soft_match = bool(row.get("_soft_customer_match"))
    customer = _find_customer(db, customer_key, soft_match=soft_match)
    currency_raw = str(row.get("currency") or row.get("Currency") or "").strip().upper()
    currency = currency_raw or (customer.default_currency_code or "INR").strip().upper()
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
    quoted_date = _parse_date(
        row.get("quoted_date") or row.get("Quoted Date") or row.get("Quote Date")
    ) or start_date
    fx_date = quoted_date or start_date or date.today()

    base_cost, fx_rate, fx_date = to_base_amount(
        db, amount=estimated_cost, currency_code=currency, on_date=fx_date
    )
    base_revenue, _, _ = to_base_amount(
        db, amount=quoted_revenue, currency_code=currency, on_date=fx_date
    )

    working_model = _find_working_model(
        db, str(row.get("business_model") or row.get("Business Model") or "") or None
    )

    name_hint = str(
        row.get("line_description")
        or row.get("part_description")
        or f"{tool_number} — {customer.name}"
    ).strip()
    project, project_created = ensure_project_for_quote_import(
        db,
        tool_number=tool_number,
        customer_id=customer.id,
        team_id=team_id,
        quoted_hours=quoted_hours,
        name_hint=name_hint,
        create_if_missing=create_project,
    )

    external_quote_number = str(
        row.get("external_quote_number") or row.get("Quote#") or ""
    ).strip() or None
    notes_value = row.get("notes") or row.get("Notes")
    notes_text = str(notes_value).strip() if notes_value not in (None, "") else None

    warnings: list[str] = []
    raw_warnings = row.get("_warnings")
    if isinstance(raw_warnings, list):
        warnings.extend(str(item) for item in raw_warnings)

    rate_raw = row.get("_rate")
    if rate_raw not in (None, ""):
        try:
            rate = Decimal(str(rate_raw))
            expected = (quoted_hours * rate).quantize(Decimal("0.01"))
            if abs(expected - quoted_revenue) > Decimal("0.05"):
                warnings.append(
                    f"Hours × rate ({expected}) does not match revenue ({quoted_revenue})"
                )
        except (InvalidOperation, TypeError):
            pass

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
            team_id=team_id,
            project_id=project.id if project is not None else None,
            tool_number=tool_number,
            external_quote_number=external_quote_number,
            business_model_id=working_model.id if working_model else None,
            estimator_id=actor.id,
            currency_code=currency,
            quoted_date=quoted_date,
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
        if quoted_date is not None:
            quote.quoted_date = quoted_date
        if team_id is not None:
            quote.team_id = team_id
        if working_model is not None:
            quote.business_model_id = working_model.id
        if project is not None:
            quote.project_id = project.id
        if external_quote_number:
            quote.external_quote_number = external_quote_number

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
        start_date=start_date or quoted_date,
        end_date=end_date,
        notes=notes_text,
        imported_from=source,
        imported_at=datetime.now(timezone.utc).replace(tzinfo=None),
        imported_by_id=actor.id,
    )
    db.add(revision_row)
    db.flush()
    return QuoteImportOutcome(
        quote=quote,
        project_created=project_created,
        warnings=warnings,
        quoted_hours=quoted_hours,
        quoted_revenue=quoted_revenue,
    )


def import_quotes_from_csv(
    db: Session,
    *,
    content: bytes,
    actor: User,
    team_id: UUID | None = None,
    create_project: bool = True,
    filename: str | None = None,
) -> list[QuoteImportOutcome]:
    from app.services.finance.quote_field_recognizer import enrich_import_row

    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ProTrackValidationError("CSV has no header row")
    outcomes: list[QuoteImportOutcome] = []
    for index, row in enumerate(reader, start=2):
        try:
            outcomes.append(
                import_quote_row(
                    db,
                    row=enrich_import_row(dict(row), filename=filename),
                    actor=actor,
                    source="csv",
                    team_id=team_id,
                    create_project=create_project,
                )
            )
        except ProTrackValidationError as exc:
            raise ProTrackValidationError(f"Row {index}: {exc}") from exc
    return outcomes


def import_quotes_from_excel(
    db: Session,
    *,
    content: bytes,
    actor: User,
    team_id: UUID | None = None,
    create_project: bool = True,
    filename: str | None = None,
) -> list[QuoteImportOutcome]:
    from app.services.finance.quote_field_recognizer import enrich_import_row

    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise ProTrackValidationError(
            "Excel import requires openpyxl. Upload CSV or PDF instead."
        ) from exc

    workbook = load_workbook(filename=io.BytesIO(content), read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ProTrackValidationError("Excel sheet is empty")
    headers = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
    outcomes: list[QuoteImportOutcome] = []
    for index, values in enumerate(rows[1:], start=2):
        if values is None or all(v is None or str(v).strip() == "" for v in values):
            continue
        row = {headers[i]: values[i] for i in range(min(len(headers), len(values)))}
        try:
            outcomes.append(
                import_quote_row(
                    db,
                    row=enrich_import_row(row, filename=filename),
                    actor=actor,
                    source="excel",
                    team_id=team_id,
                    create_project=create_project,
                )
            )
        except ProTrackValidationError as exc:
            raise ProTrackValidationError(f"Row {index}: {exc}") from exc
    return outcomes


def import_quotes_from_pdf(
    db: Session,
    *,
    content: bytes,
    actor: User,
    team_id: UUID | None = None,
    create_project: bool = True,
    filename: str | None = None,
) -> list[QuoteImportOutcome]:
    from app.services.finance.prosohm_quote_pdf_parser import (
        extract_prosohm_quote_text,
        looks_like_prosohm_qt_pdf,
        parse_prosohm_quote_text,
    )
    from app.services.finance.quote_field_recognizer import enrich_import_row
    from app.services.pdf_table_import import extract_tables_as_dicts

    # Prefer Prosohm QT layout when filename or text markers match.
    try:
        text = extract_prosohm_quote_text(content)
    except ProTrackValidationError:
        text = ""

    if looks_like_prosohm_qt_pdf(filename=filename, text=text) or (
        filename and "QT-" in filename.upper()
    ):
        if not text.strip():
            raise ProTrackValidationError(
                "Prosohm QT PDF has no extractable text. Use a text-based PDF."
            )
        from app.models.models import Customer

        customers = db.scalars(
            select(Customer).where(Customer.is_active.is_(True))
        ).all()
        candidates = [(c.name or "", c.code or "") for c in customers]
        extract = parse_prosohm_quote_text(
            text,
            filename=filename,
            customer_candidates=candidates,
        )
        return [
            import_quote_row(
                db,
                row=enrich_import_row(extract.to_import_row(), filename=filename),
                actor=actor,
                source="pdf_qt",
                team_id=team_id,
                create_project=create_project,
            )
        ]

    rows = extract_tables_as_dicts(content)
    outcomes: list[QuoteImportOutcome] = []
    for index, row in enumerate(rows, start=2):
        try:
            outcomes.append(
                import_quote_row(
                    db,
                    row=enrich_import_row(row, filename=filename),
                    actor=actor,
                    source="pdf",
                    team_id=team_id,
                    create_project=create_project,
                )
            )
        except ProTrackValidationError as exc:
            raise ProTrackValidationError(f"Row {index}: {exc}") from exc
    return outcomes


def import_quotes_from_upload(
    db: Session,
    *,
    filename: str,
    content: bytes,
    actor: User,
    team_id: UUID | None = None,
    create_project: bool = True,
) -> list[QuoteImportOutcome]:
    from app.services.import_file_formats import (
        assert_supported_suffix,
        is_csv,
        is_excel,
        is_pdf,
        with_csv,
    )

    suffix = assert_supported_suffix(filename, allowed=with_csv())
    if is_csv(suffix):
        return import_quotes_from_csv(
            db,
            content=content,
            actor=actor,
            team_id=team_id,
            create_project=create_project,
            filename=filename,
        )
    if is_excel(suffix):
        return import_quotes_from_excel(
            db,
            content=content,
            actor=actor,
            team_id=team_id,
            create_project=create_project,
            filename=filename,
        )
    if is_pdf(suffix):
        return import_quotes_from_pdf(
            db,
            content=content,
            actor=actor,
            team_id=team_id,
            create_project=create_project,
            filename=filename,
        )
    raise ProTrackValidationError(
        "Supported formats: Excel (.xlsx/.xlsm), Prosohm QT PDF, flat PDF table, CSV."
    )
