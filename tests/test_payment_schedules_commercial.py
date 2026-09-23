"""Customer commercial profiles + payment milestone schedule scenarios.

ABC / Crest / B&B / Integrity — future milestones must never appear overdue.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import uuid

from app.models.finance import Quote, QuoteRevision
from app.models.models import Customer, Team
from app.services.finance.payment_schedule_service import (
    STATUS_NOT_YET_TRIGGERED,
    list_quote_milestones,
    mark_milestone_triggered,
    replace_customer_milestones,
    replace_quote_schedule,
    seed_quote_schedule_from_customer,
    summarize_quote_payment_schedule,
)
from app.services.finance.payment_terms_service import (
    TIMING_NOT_YET_DUE,
    TIMING_OVERDUE,
    resolve_invoice_payment_terms,
)
from app.services.finance.quote_cash_ledger_service import (
    add_invoice_line,
    add_payment_line,
)


def _seed_customer_quote(
    session,
    *,
    name: str,
    awarded: Decimal,
    model: str,
    terms: str | None,
    days: int | None,
) -> tuple[Customer, Quote]:
    team = Team(id=uuid.uuid4(), name=f"PT {uuid.uuid4().hex[:6]}", is_active=True)
    customer = Customer(
        id=uuid.uuid4(),
        name=name,
        code=f"C{uuid.uuid4().hex[:5]}",
        is_active=True,
        default_currency_code="USD",
        default_payment_model=model,
        default_payment_terms=terms,
        default_payment_terms_days=days,
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
            quoted_hours=Decimal("100"),
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
    session.flush()
    return customer, quote


def test_abc_oktt_net90_lifecycle(session):
    customer, quote = _seed_customer_quote(
        session,
        name="ABC",
        awarded=Decimal("10000"),
        model="NET_TERMS",
        terms="Net 90",
        days=90,
    )
    replace_customer_milestones(
        session,
        customer=customer,
        milestones=[
            {
                "sequence": 1,
                "name": "OKTT invoice",
                "percentage": 100,
                "trigger_type": "OKTT_PART_DATA_RECEIVED",
                "payment_timing": "NET_DAYS",
                "payment_terms_days": 90,
            }
        ],
    )
    seed_quote_schedule_from_customer(session, quote=quote, customer=customer)
    session.commit()

    summary = summarize_quote_payment_schedule(session, quote=quote, as_of=date(2026, 2, 1))
    assert summary["future_milestone_amount"] == 10000.0
    assert summary["overdue_amount"] == 0.0
    assert summary["milestones"][0]["trigger_status"] == STATUS_NOT_YET_TRIGGERED

    mark_milestone_triggered(session, quote=quote, trigger_type="OKTT_PART_DATA_RECEIVED")
    session.commit()
    summary = summarize_quote_payment_schedule(session, quote=quote)
    assert summary["ready_to_invoice_amount"] == 10000.0
    mid = list_quote_milestones(session, quote.id)[0].id

    inv_date = date(2026, 3, 1)
    line = add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("10000"),
        line_date=inv_date,
        payment_terms="Net 90",
        payment_terms_days=90,
        payment_terms_source="CUSTOMER_DEFAULT",
        due_date=inv_date + timedelta(days=90),
        payment_milestone_id=mid,
    )
    session.commit()

    summary = summarize_quote_payment_schedule(session, quote=quote, as_of=date(2026, 4, 1))
    assert summary["overdue_amount"] == 0.0
    assert summary["not_yet_due_amount"] == 10000.0
    assert summary["milestones"][0]["payment_status"] == TIMING_NOT_YET_DUE

    summary = summarize_quote_payment_schedule(
        session, quote=quote, as_of=inv_date + timedelta(days=91)
    )
    assert summary["overdue_amount"] == 10000.0
    assert summary["milestones"][0]["payment_status"] == TIMING_OVERDUE

    add_payment_line(session, quote=quote, amount=Decimal("10000"), line_date=date(2026, 7, 1))
    session.commit()
    summary = summarize_quote_payment_schedule(session, quote=quote, as_of=date(2026, 7, 2))
    assert summary["overdue_amount"] == 0.0
    assert summary["outstanding_amount"] == 0.0
    assert line.payment_terms_days == 90


def test_crest_50_50_due_on_receipt_future_not_overdue(session):
    customer, quote = _seed_customer_quote(
        session,
        name="Crest",
        awarded=Decimal("4500"),
        model="MILESTONE_BASED",
        terms="Due on Receipt",
        days=0,
    )
    replace_customer_milestones(
        session,
        customer=customer,
        milestones=[
            {
                "sequence": 1,
                "name": "Advance",
                "percentage": 50,
                "trigger_type": "PROJECT_KICKOFF",
                "payment_timing": "DUE_ON_RECEIPT",
                "payment_terms_days": 0,
            },
            {
                "sequence": 2,
                "name": "Completion",
                "percentage": 50,
                "trigger_type": "PROJECT_COMPLETION",
                "payment_timing": "DUE_ON_RECEIPT",
                "payment_terms_days": 0,
            },
        ],
    )
    seed_quote_schedule_from_customer(session, quote=quote, customer=customer)
    session.commit()

    summary = summarize_quote_payment_schedule(session, quote=quote)
    assert summary["future_milestone_amount"] == 4500.0
    assert summary["overdue_amount"] == 0.0

    mark_milestone_triggered(session, quote=quote, trigger_type="PROJECT_KICKOFF")
    m1 = next(m for m in list_quote_milestones(session, quote.id) if m.sequence == 1)
    line = add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("2250"),
        line_date=date(2026, 2, 1),
        payment_terms="Due on Receipt",
        payment_terms_days=0,
        due_date=date(2026, 2, 1),
        payment_milestone_id=m1.id,
    )
    add_payment_line(session, quote=quote, amount=Decimal("2250"), line_date=date(2026, 2, 2))
    session.commit()

    summary = summarize_quote_payment_schedule(session, quote=quote, as_of=date(2026, 6, 1))
    assert summary["future_milestone_amount"] == 2250.0
    assert summary["overdue_amount"] == 0.0
    assert summary["outstanding_amount"] == 0.0
    m2 = next(m for m in summary["milestones"] if m["sequence"] == 2)
    assert m2["payment_status"] == "FUTURE_MILESTONE"
    assert line.payment_terms_days == 0


def test_bb_25_75_completion_stays_future(session):
    _customer, quote = _seed_customer_quote(
        session,
        name="B & B",
        awarded=Decimal("10000"),
        model="MILESTONE_BASED",
        terms="Due on Receipt",
        days=0,
    )
    replace_quote_schedule(
        session,
        quote=quote,
        payment_model="MILESTONE_BASED",
        milestones=[
            {
                "sequence": 1,
                "name": "Kickoff 25%",
                "percentage": 25,
                "trigger_type": "PROJECT_KICKOFF",
                "payment_timing": "DUE_ON_RECEIPT",
            },
            {
                "sequence": 2,
                "name": "Completion 75%",
                "percentage": 75,
                "trigger_type": "PROJECT_COMPLETION",
                "payment_timing": "DUE_ON_RECEIPT",
            },
        ],
    )
    mark_milestone_triggered(session, quote=quote, trigger_type="PROJECT_KICKOFF")
    m1 = next(m for m in list_quote_milestones(session, quote.id) if m.sequence == 1)
    add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("2500"),
        line_date=date(2026, 1, 10),
        payment_terms_days=0,
        due_date=date(2026, 1, 10),
        payment_milestone_id=m1.id,
    )
    add_payment_line(session, quote=quote, amount=Decimal("2500"), line_date=date(2026, 1, 11))
    session.commit()
    summary = summarize_quote_payment_schedule(session, quote=quote, as_of=date(2026, 12, 1))
    assert summary["future_milestone_amount"] == 7500.0
    assert summary["overdue_amount"] == 0.0
    assert any(m["payment_status"] == "FUTURE_MILESTONE" for m in summary["milestones"])


def test_integrity_completion_net90(session):
    _customer, quote = _seed_customer_quote(
        session,
        name="Integrity",
        awarded=Decimal("8000"),
        model="MIXED",
        terms="Net 90",
        days=90,
    )
    replace_quote_schedule(
        session,
        quote=quote,
        payment_model="MILESTONE_BASED",
        payment_terms="Net 90",
        payment_terms_days=90,
        milestones=[
            {
                "sequence": 1,
                "name": "Completion",
                "percentage": 100,
                "trigger_type": "PROJECT_COMPLETION",
                "payment_timing": "NET_DAYS",
                "payment_terms_days": 90,
            }
        ],
    )
    session.commit()
    summary = summarize_quote_payment_schedule(session, quote=quote)
    assert summary["milestones"][0]["trigger_status"] == STATUS_NOT_YET_TRIGGERED

    mark_milestone_triggered(session, quote=quote, trigger_type="PROJECT_COMPLETION")
    mid = list_quote_milestones(session, quote.id)[0].id
    inv = date(2026, 5, 1)
    add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("8000"),
        line_date=inv,
        payment_terms="Net 90",
        payment_terms_days=90,
        due_date=inv + timedelta(days=90),
        payment_milestone_id=mid,
        payment_terms_source="PROJECT_OVERRIDE",
    )
    session.commit()
    summary = summarize_quote_payment_schedule(session, quote=quote, as_of=date(2026, 6, 1))
    assert summary["not_yet_due_amount"] == 8000.0
    assert summary["overdue_amount"] == 0.0


def test_customer_terms_change_does_not_mutate_invoice_snapshot(session):
    customer, quote = _seed_customer_quote(
        session,
        name="SnapCust",
        awarded=Decimal("1000"),
        model="NET_TERMS",
        terms="Net 90",
        days=90,
    )
    line = add_invoice_line(
        session,
        quote=quote,
        amount=Decimal("1000"),
        line_date=date(2026, 1, 1),
        payment_terms="Net 90",
        payment_terms_days=90,
        payment_terms_source="CUSTOMER_DEFAULT",
        due_date=date(2026, 4, 1),
    )
    session.commit()
    customer.default_payment_terms = "Net 60"
    customer.default_payment_terms_days = 60
    session.add(customer)
    session.commit()
    session.refresh(line)
    assert line.payment_terms == "Net 90"
    assert line.payment_terms_days == 90


def test_document_due_date_differs_from_customer_warns():
    resolved = resolve_invoice_payment_terms(
        document_due_date=date(2026, 12, 15),
        invoice_date=date(2026, 9, 15),
        customer_default_terms="Net 90",
        customer_default_days=90,
    )
    assert resolved["due_date"] == date(2026, 12, 15)
    assert resolved["due_date_source"] == "DOCUMENT"
    assert any("differs from the customer" in w.lower() for w in resolved["warnings"])


def test_project_override_beats_customer_default():
    resolved = resolve_invoice_payment_terms(
        invoice_date=date(2026, 1, 1),
        customer_default_terms="Net 90",
        customer_default_days=90,
        project_terms="Net 30",
        project_days=30,
    )
    assert resolved["payment_terms_days"] == 30
    assert resolved["payment_terms_source"] == "PROJECT_OVERRIDE"
    assert resolved["due_date"] == date(2026, 1, 31)
