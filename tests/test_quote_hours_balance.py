"""Commercial quote vs invoice hours — partial invoice / keep vs close balance."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import uuid

import pytest

from app.core.exceptions import ProTrackValidationError
from app.models.finance import Quote, QuoteBalanceClosure, QuoteRevision
from app.models.models import Customer, Team, User
from app.services.finance.quote_cash_ledger_service import (
    STATUS_PARTIALLY_INVOICED_PAID,
    STATUS_PARTIALLY_INVOICED_PAYMENT_PENDING,
    add_invoice_line,
    add_payment_line,
    calculate_awarded_quote_financial_status,
    delete_invoice_line,
)
from app.services.finance.quote_hours_balance_service import (
    HOURS_STATUS_BALANCE_CLOSED,
    HOURS_STATUS_FULLY_INVOICED,
    HOURS_STATUS_OVER_INVOICED,
    HOURS_STATUS_PARTIALLY_INVOICED,
    HOURS_STATUS_UNKNOWN,
    calculate_quote_hours_balance,
    close_remaining_balance,
    preview_partial_invoice_for_import,
)
from app.services.finance.invoice_pdf_import_service import confirm_invoice_pdf_import
from tests.conftest import IDS


def _seed_quote(
    session,
    *,
    quoted_hours: Decimal,
    awarded: Decimal,
) -> Quote:
    team = Team(id=uuid.uuid4(), name=f"Hrs {uuid.uuid4().hex[:6]}", is_active=True)
    customer = Customer(
        id=uuid.uuid4(),
        name="Hours Customer",
        code=f"HC{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    session.add_all([team, customer])
    session.flush()
    quote = Quote(
        id=uuid.uuid4(),
        customer_id=customer.id,
        team_id=team.id,
        tool_number=f"TOOL-{uuid.uuid4().hex[:6]}",
        currency_code="USD",
        is_active=True,
    )
    session.add(quote)
    session.flush()
    session.add(
        QuoteRevision(
            id=uuid.uuid4(),
            quote_id=quote.id,
            version=1,
            revision="A",
            quoted_hours=quoted_hours,
            estimated_cost=Decimal("0"),
            quoted_revenue=awarded,
            margin=awarded,
            margin_percent=Decimal("100"),
            base_estimated_cost_inr=Decimal("0"),
            base_quoted_revenue_inr=awarded,
            fx_rate=Decimal("1"),
            fx_date=date(2026, 1, 1),
        )
    )
    session.commit()
    return quote


def test_fully_invoiced_hours(session):
    quote = _seed_quote(session, quoted_hours=Decimal("180"), awarded=Decimal("4500"))
    add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("4500"),
        line_date=date(2026, 3, 1),
        quantity_hours=Decimal("180"),
    )
    session.commit()
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["hours_status"] == HOURS_STATUS_FULLY_INVOICED
    assert snap["quoted_hours"] == Decimal("180")
    assert snap["invoiced_hours"] == Decimal("180")
    assert snap["remaining_hours"] == Decimal("0")


def test_partial_invoice_remaining_60(session):
    quote = _seed_quote(session, quoted_hours=Decimal("180"), awarded=Decimal("4500"))
    add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("3000"),
        line_date=date(2026, 3, 1),
        quantity_hours=Decimal("120"),
    )
    session.commit()
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["hours_status"] == HOURS_STATUS_PARTIALLY_INVOICED
    assert snap["invoiced_hours"] == Decimal("120")
    assert snap["remaining_hours"] == Decimal("60")
    assert snap["remaining_to_invoice"] == Decimal("1500")


def test_cumulative_multi_invoice_partial(session):
    quote = _seed_quote(session, quoted_hours=Decimal("180"), awarded=Decimal("4500"))
    add_invoice_line(
        session, quote=quote, amount=Decimal("1500"), line_date=date(2026, 3, 1), quantity_hours=Decimal("60")
    )
    add_invoice_line(
        session, quote=quote, amount=Decimal("1500"), line_date=date(2026, 4, 1), quantity_hours=Decimal("60")
    )
    session.commit()
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["hours_status"] == HOURS_STATUS_PARTIALLY_INVOICED
    assert snap["invoiced_hours"] == Decimal("120")
    assert snap["remaining_hours"] == Decimal("60")


def test_cumulative_multi_invoice_full(session):
    quote = _seed_quote(session, quoted_hours=Decimal("180"), awarded=Decimal("4500"))
    for hrs, amt, d in (
        (Decimal("60"), Decimal("1500"), date(2026, 3, 1)),
        (Decimal("60"), Decimal("1500"), date(2026, 4, 1)),
        (Decimal("60"), Decimal("1500"), date(2026, 5, 1)),
    ):
        add_invoice_line(
            session, quote=quote, amount=amt, line_date=d, quantity_hours=hrs
        )
    session.commit()
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["hours_status"] == HOURS_STATUS_FULLY_INVOICED
    assert snap["remaining_hours"] == Decimal("0")


def test_over_invoiced_hours_preview(session):
    quote = _seed_quote(session, quoted_hours=Decimal("180"), awarded=Decimal("4500"))
    preview = preview_partial_invoice_for_import(
        session, quote_id=quote.id, this_invoice_hours=Decimal("200")
    )
    assert preview is not None
    assert preview["is_over_invoiced_hours"] is True
    assert preview["over_invoiced_hours"] == Decimal("20")
    assert preview["decision_required"] is False


def test_partial_invoice_payment_independent(session):
    quote = _seed_quote(session, quoted_hours=Decimal("180"), awarded=Decimal("4500"))
    add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("3000"),
        line_date=date(2026, 3, 1),
        quantity_hours=Decimal("120"),
    )
    add_payment_line(
        session, quote=quote, amount=Decimal("3000"), line_date=date(2026, 3, 15)
    )
    session.commit()
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["hours_status"] == HOURS_STATUS_PARTIALLY_INVOICED
    assert snap["financial_status"] == STATUS_PARTIALLY_INVOICED_PAID
    assert snap["outstanding_amount"] == Decimal("0")
    assert snap["remaining_hours"] == Decimal("60")


def test_keep_balance_via_confirm(session):
    quote = _seed_quote(session, quoted_hours=Decimal("180"), awarded=Decimal("4500"))
    admin = session.get(User, IDS["user_admin"])
    assert admin is not None
    confirm_invoice_pdf_import(
        session,
        quote_id=quote.id,
        amount=Decimal("3000"),
        line_date=date(2026, 3, 1),
        notes=None,
        invoice_number="INV-KEEP-1",
        import_anyway=False,
        content=None,
        filename=None,
        content_sha256=None,
        user=admin,
        quantity_hours=Decimal("120"),
        remaining_balance_action="keep_balance",
    )
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["hours_status"] == HOURS_STATUS_PARTIALLY_INVOICED
    assert snap["remaining_hours"] == Decimal("60")
    assert snap["closed_balance_hours"] == Decimal("0")
    closures = session.query(QuoteBalanceClosure).filter_by(quote_id=quote.id).all()
    assert closures == []


def test_close_balance_preserves_quote(session):
    quote = _seed_quote(session, quoted_hours=Decimal("180"), awarded=Decimal("4500"))
    admin = session.get(User, IDS["user_admin"])
    assert admin is not None
    confirm_invoice_pdf_import(
        session,
        quote_id=quote.id,
        amount=Decimal("3000"),
        line_date=date(2026, 3, 1),
        notes=None,
        invoice_number="INV-CLOSE-1",
        import_anyway=False,
        content=None,
        filename=None,
        content_sha256=None,
        user=admin,
        quantity_hours=Decimal("120"),
        remaining_balance_action="close_remaining_balance",
    )
    revision = session.query(QuoteRevision).filter_by(quote_id=quote.id).one()
    assert revision.quoted_hours == Decimal("180")
    assert revision.quoted_revenue == Decimal("4500")
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["hours_status"] == HOURS_STATUS_BALANCE_CLOSED
    assert snap["invoiced_hours"] == Decimal("120")
    assert snap["closed_balance_hours"] == Decimal("60")
    assert snap["remaining_hours"] == Decimal("0")
    assert snap["remaining_to_invoice"] == Decimal("0")
    closure = session.query(QuoteBalanceClosure).filter_by(quote_id=quote.id).one()
    assert closure.closed_hours == Decimal("60")
    assert closure.quoted_hours_snapshot == Decimal("180")


def test_cancelled_invoice_excluded(session):
    quote = _seed_quote(session, quoted_hours=Decimal("180"), awarded=Decimal("4500"))
    line = add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("3000"),
        line_date=date(2026, 3, 1),
        quantity_hours=Decimal("120"),
    )
    session.commit()
    delete_invoice_line(session, quote=quote, line_id=line.id)
    session.commit()
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["invoiced_hours"] == Decimal("0")
    assert snap["hours_status"] != HOURS_STATUS_PARTIALLY_INVOICED


def test_decimal_quantities(session):
    quote = _seed_quote(session, quoted_hours=Decimal("100.5"), awarded=Decimal("2512.50"))
    add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("1256.25"),
        line_date=date(2026, 3, 1),
        quantity_hours=Decimal("50.25"),
    )
    session.commit()
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["hours_status"] == HOURS_STATUS_PARTIALLY_INVOICED
    assert snap["remaining_hours"] == Decimal("50.25")


def test_no_quote_hours_skips_hours_status(session):
    quote = _seed_quote(session, quoted_hours=Decimal("0"), awarded=Decimal("4500"))
    add_invoice_line(
        session, quote=quote, amount=Decimal("2000"), line_date=date(2026, 3, 1)
    )
    session.commit()
    snap = calculate_awarded_quote_financial_status(session, quote.id)
    assert snap["hours_status"] == HOURS_STATUS_UNKNOWN
    assert snap["financial_status"] == STATUS_PARTIALLY_INVOICED_PAYMENT_PENDING


def test_over_hours_requires_ack_on_confirm(session):
    quote = _seed_quote(session, quoted_hours=Decimal("180"), awarded=Decimal("4500"))
    admin = session.get(User, IDS["user_admin"])
    assert admin is not None
    with pytest.raises(ProTrackValidationError, match="exceeds"):
        confirm_invoice_pdf_import(
            session,
            quote_id=quote.id,
            amount=Decimal("4000"),
            line_date=date(2026, 3, 1),
            notes=None,
            invoice_number="INV-OVER-1",
            import_anyway=False,
            content=None,
            filename=None,
            content_sha256=None,
            user=admin,
            quantity_hours=Decimal("200"),
            acknowledge_over_hours=False,
        )


def test_preview_partial_asks_decision(session):
    quote = _seed_quote(session, quoted_hours=Decimal("180"), awarded=Decimal("4500"))
    preview = preview_partial_invoice_for_import(
        session, quote_id=quote.id, this_invoice_hours=Decimal("120")
    )
    assert preview is not None
    assert preview["decision_required"] is True
    assert preview["default_decision"] == "keep_balance"
    assert preview["remaining_hours_before_closure"] == Decimal("60")


def test_close_via_service_after_invoice(session):
    quote = _seed_quote(session, quoted_hours=Decimal("180"), awarded=Decimal("4500"))
    admin = session.get(User, IDS["user_admin"])
    line = add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("3000"),
        line_date=date(2026, 3, 1),
        quantity_hours=Decimal("120"),
    )
    session.flush()
    close_remaining_balance(
        session, quote=quote, related_invoice_line=line, user=admin, reason="Waive remainder"
    )
    session.commit()
    bal = calculate_quote_hours_balance(session, quote)
    assert bal["hours_status"] == HOURS_STATUS_BALANCE_CLOSED
    assert bal["remaining_hours"] == Decimal("0")
