"""Quote import and revision history."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
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

    description = (name_hint or f"{tool_number} — Quote import").strip()
    if len(description) > 255:
        description = description[:255]
    project = Project(
        tool_number=tool_number.strip(),
        part_description=description,
        customer_id=customer_id,
        team_id=team_id,
        quoted_hours=quoted_hours,
        notes="created_from_quote_import",
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
    return import_quote_row(
        db,
        row=row,
        actor=actor,
        source="manual",
        team_id=team_id,
        create_project=create_project,
    )


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
    fx_date = start_date or date.today()

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
        start_date=start_date,
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
