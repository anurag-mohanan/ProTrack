"""Finance treasury services — loans, OD, investments, cash position.

Accounting rules:
- Loan/OD principal = financing / position (not P&L revenue or expense)
- Loan/OD interest = P&L finance cost
- Investment purchase = cash + asset (not automatic OpEx)
- Investment income = cash + income
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ProTrackValidationError
from app.models.enums import (
    FinanceInvestmentStatus,
    FinanceInvestmentType,
    FinanceLoanInterestType,
    FinanceLoanStatus,
    FinanceOdStatus,
    FinanceRecordSource,
)
from app.models.finance import (
    FinanceCashPosition,
    FinanceInvestment,
    FinanceInvestmentIncome,
    FinanceLoan,
    FinanceLoanRepayment,
    FinanceOdInterestCharge,
    FinanceOverdraftFacility,
)


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _money_fields(payload: dict, keys: list[str]) -> dict:
    out = dict(payload)
    for key in keys:
        if key in out and out[key] is not None:
            out[key] = _d(out[key])
    return out


# --- Loans -----------------------------------------------------------------


def list_loans(db: Session, *, include_inactive: bool = False) -> list[FinanceLoan]:
    stmt = select(FinanceLoan).options(selectinload(FinanceLoan.repayments))
    if not include_inactive:
        stmt = stmt.where(FinanceLoan.is_active.is_(True))
    return list(db.scalars(stmt.order_by(FinanceLoan.name)).all())


def get_loan(db: Session, loan_id: UUID) -> FinanceLoan:
    loan = db.scalar(
        select(FinanceLoan)
        .where(FinanceLoan.id == loan_id)
        .options(selectinload(FinanceLoan.repayments))
    )
    if loan is None:
        raise ProTrackValidationError("Loan not found")
    return loan


def create_loan(db: Session, payload: dict) -> FinanceLoan:
    data = _money_fields(
        payload,
        ["original_principal", "outstanding_principal", "emi_amount", "interest_rate_percent"],
    )
    original = _d(data.get("original_principal"))
    outstanding = data.get("outstanding_principal")
    if outstanding is None:
        outstanding = original
    else:
        outstanding = _d(outstanding)
    loan = FinanceLoan(
        id=uuid4(),
        lender_name=str(data["lender_name"]).strip(),
        name=str(data["name"]).strip(),
        loan_type=(str(data["loan_type"]).strip() if data.get("loan_type") else None),
        reference=(str(data["reference"]).strip() if data.get("reference") else None),
        original_principal=original,
        outstanding_principal=outstanding,
        currency_code=str(data.get("currency_code") or "INR"),
        interest_rate_percent=data.get("interest_rate_percent"),
        interest_type=(
            data["interest_type"]
            if isinstance(data.get("interest_type"), FinanceLoanInterestType)
            else FinanceLoanInterestType(str(data.get("interest_type") or "reducing"))
        ),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
        tenure_months=data.get("tenure_months"),
        emi_amount=data.get("emi_amount"),
        payment_frequency=data.get("payment_frequency"),
        next_payment_date=data.get("next_payment_date"),
        security_notes=data.get("security_notes"),
        status=data.get("status") or FinanceLoanStatus.active,
        notes=data.get("notes"),
        source=data.get("source") or FinanceRecordSource.manual,
        is_active=True,
    )
    db.add(loan)
    db.commit()
    db.refresh(loan)
    return get_loan(db, loan.id)


def update_loan(db: Session, loan_id: UUID, payload: dict) -> FinanceLoan:
    loan = get_loan(db, loan_id)
    data = _money_fields(
        payload,
        ["original_principal", "outstanding_principal", "emi_amount", "interest_rate_percent"],
    )
    for key, value in data.items():
        if value is None and key in {
            "loan_type",
            "reference",
            "interest_rate_percent",
            "start_date",
            "end_date",
            "tenure_months",
            "emi_amount",
            "payment_frequency",
            "next_payment_date",
            "security_notes",
            "notes",
        }:
            setattr(loan, key, None)
        elif value is not None and hasattr(loan, key):
            setattr(loan, key, value)
    db.commit()
    return get_loan(db, loan.id)


def record_loan_repayment(db: Session, loan_id: UUID, payload: dict) -> FinanceLoan:
    loan = get_loan(db, loan_id)
    total = _d(payload.get("total_amount"))
    interest = _d(payload.get("interest_amount"))
    principal = payload.get("principal_amount")
    if principal is None:
        principal = total - interest
    else:
        principal = _d(principal)
    if total <= 0:
        raise ProTrackValidationError("Repayment total must be greater than zero")
    if principal < 0 or interest < 0:
        raise ProTrackValidationError("Principal and interest cannot be negative")
    if (principal + interest - total).copy_abs() > Decimal("0.05"):
        raise ProTrackValidationError("Principal + interest must equal total repayment")
    if principal > loan.outstanding_principal + Decimal("0.01"):
        raise ProTrackValidationError("Principal exceeds outstanding balance")

    payment_date = payload.get("payment_date") or date.today()
    row = FinanceLoanRepayment(
        id=uuid4(),
        loan_id=loan.id,
        payment_date=payment_date,
        total_amount=total,
        principal_amount=principal,
        interest_amount=interest,
        reference=payload.get("reference"),
        notes=payload.get("notes"),
        source=payload.get("source") or FinanceRecordSource.manual,
    )
    loan.outstanding_principal = _d(loan.outstanding_principal - principal)
    if loan.outstanding_principal <= Decimal("0.01"):
        loan.outstanding_principal = Decimal("0.00")
        loan.status = FinanceLoanStatus.closed
    db.add(row)
    db.commit()
    return get_loan(db, loan.id)


def loan_to_dict(loan: FinanceLoan) -> dict:
    interest_paid = sum((_d(r.interest_amount) for r in loan.repayments), Decimal("0.00"))
    principal_paid = sum((_d(r.principal_amount) for r in loan.repayments), Decimal("0.00"))
    return {
        "id": str(loan.id),
        "lender_name": loan.lender_name,
        "name": loan.name,
        "loan_type": loan.loan_type,
        "reference": loan.reference,
        "original_principal": loan.original_principal,
        "outstanding_principal": loan.outstanding_principal,
        "currency_code": loan.currency_code,
        "interest_rate_percent": loan.interest_rate_percent,
        "interest_type": loan.interest_type.value if loan.interest_type else None,
        "start_date": loan.start_date,
        "end_date": loan.end_date,
        "tenure_months": loan.tenure_months,
        "emi_amount": loan.emi_amount,
        "payment_frequency": loan.payment_frequency,
        "next_payment_date": loan.next_payment_date,
        "security_notes": loan.security_notes,
        "status": loan.status.value if loan.status else None,
        "notes": loan.notes,
        "source": loan.source.value if loan.source else None,
        "is_active": loan.is_active,
        "interest_paid_total": interest_paid.quantize(Decimal("0.01")),
        "principal_paid_total": principal_paid.quantize(Decimal("0.01")),
        "repayments": [
            {
                "id": str(r.id),
                "payment_date": r.payment_date,
                "total_amount": r.total_amount,
                "principal_amount": r.principal_amount,
                "interest_amount": r.interest_amount,
                "reference": r.reference,
                "notes": r.notes,
                "source": r.source.value if r.source else None,
                "cash_outflow": r.total_amount,
                "pnl_finance_expense": r.interest_amount,
                "debt_reduction": r.principal_amount,
            }
            for r in loan.repayments
        ],
    }


# --- OD --------------------------------------------------------------------


def list_od_facilities(db: Session, *, include_inactive: bool = False) -> list[FinanceOverdraftFacility]:
    stmt = select(FinanceOverdraftFacility).options(
        selectinload(FinanceOverdraftFacility.interest_charges)
    )
    if not include_inactive:
        stmt = stmt.where(FinanceOverdraftFacility.is_active.is_(True))
    return list(db.scalars(stmt.order_by(FinanceOverdraftFacility.name)).all())


def get_od_facility(db: Session, facility_id: UUID) -> FinanceOverdraftFacility:
    row = db.scalar(
        select(FinanceOverdraftFacility)
        .where(FinanceOverdraftFacility.id == facility_id)
        .options(selectinload(FinanceOverdraftFacility.interest_charges))
    )
    if row is None:
        raise ProTrackValidationError("OD facility not found")
    return row


def create_od_facility(db: Session, payload: dict) -> FinanceOverdraftFacility:
    data = _money_fields(
        payload,
        [
            "sanctioned_limit",
            "current_utilization",
            "interest_rate_percent",
            "warning_utilization_percent",
        ],
    )
    facility = FinanceOverdraftFacility(
        id=uuid4(),
        bank_name=str(data["bank_name"]).strip(),
        name=str(data["name"]).strip(),
        sanctioned_limit=_d(data.get("sanctioned_limit")),
        current_utilization=_d(data.get("current_utilization")),
        currency_code=str(data.get("currency_code") or "INR"),
        interest_rate_percent=data.get("interest_rate_percent"),
        interest_basis_notes=data.get("interest_basis_notes"),
        start_date=data.get("start_date"),
        review_date=data.get("review_date"),
        warning_utilization_percent=_d(data.get("warning_utilization_percent") or 80),
        security_notes=data.get("security_notes"),
        status=data.get("status") or FinanceOdStatus.active,
        notes=data.get("notes"),
        source=data.get("source") or FinanceRecordSource.manual,
        is_active=True,
    )
    if facility.current_utilization > facility.sanctioned_limit:
        raise ProTrackValidationError("Utilization cannot exceed sanctioned limit")
    db.add(facility)
    db.commit()
    return get_od_facility(db, facility.id)


def update_od_facility(db: Session, facility_id: UUID, payload: dict) -> FinanceOverdraftFacility:
    facility = get_od_facility(db, facility_id)
    data = _money_fields(
        payload,
        [
            "sanctioned_limit",
            "current_utilization",
            "interest_rate_percent",
            "warning_utilization_percent",
        ],
    )
    for key, value in data.items():
        if value is not None and hasattr(facility, key):
            setattr(facility, key, value)
    if facility.current_utilization > facility.sanctioned_limit:
        raise ProTrackValidationError("Utilization cannot exceed sanctioned limit")
    db.commit()
    return get_od_facility(db, facility.id)


def record_od_interest(db: Session, facility_id: UUID, payload: dict) -> FinanceOverdraftFacility:
    facility = get_od_facility(db, facility_id)
    amount = _d(payload.get("amount"))
    if amount <= 0:
        raise ProTrackValidationError("OD interest amount must be greater than zero")
    db.add(
        FinanceOdInterestCharge(
            id=uuid4(),
            facility_id=facility.id,
            charge_date=payload.get("charge_date") or date.today(),
            amount=amount,
            notes=payload.get("notes"),
            source=payload.get("source") or FinanceRecordSource.manual,
        )
    )
    db.commit()
    return get_od_facility(db, facility.id)


def od_to_dict(facility: FinanceOverdraftFacility) -> dict:
    limit = _d(facility.sanctioned_limit)
    used = _d(facility.current_utilization)
    available = max(Decimal("0.00"), limit - used)
    utilization_percent = (
        (used / limit * Decimal("100")).quantize(Decimal("0.01")) if limit > 0 else Decimal("0.00")
    )
    warning = _d(facility.warning_utilization_percent)
    return {
        "id": str(facility.id),
        "bank_name": facility.bank_name,
        "name": facility.name,
        "sanctioned_limit": limit,
        "current_utilization": used,
        "available_limit": available,
        "utilization_percent": utilization_percent,
        "warning_utilization_percent": warning,
        "is_near_limit": utilization_percent >= warning,
        "currency_code": facility.currency_code,
        "interest_rate_percent": facility.interest_rate_percent,
        "interest_basis_notes": facility.interest_basis_notes,
        "start_date": facility.start_date,
        "review_date": facility.review_date,
        "security_notes": facility.security_notes,
        "status": facility.status.value if facility.status else None,
        "notes": facility.notes,
        "source": facility.source.value if facility.source else None,
        "is_active": facility.is_active,
        "interest_charged_total": sum(
            (_d(c.amount) for c in facility.interest_charges), Decimal("0.00")
        ).quantize(Decimal("0.01")),
        "interest_charges": [
            {
                "id": str(c.id),
                "charge_date": c.charge_date,
                "amount": c.amount,
                "notes": c.notes,
                "pnl_finance_expense": c.amount,
            }
            for c in facility.interest_charges
        ],
    }


# --- Investments -----------------------------------------------------------


def list_investments(db: Session, *, include_inactive: bool = False) -> list[FinanceInvestment]:
    stmt = select(FinanceInvestment).options(selectinload(FinanceInvestment.income_entries))
    if not include_inactive:
        stmt = stmt.where(FinanceInvestment.is_active.is_(True))
    return list(db.scalars(stmt.order_by(FinanceInvestment.name)).all())


def get_investment(db: Session, investment_id: UUID) -> FinanceInvestment:
    row = db.scalar(
        select(FinanceInvestment)
        .where(FinanceInvestment.id == investment_id)
        .options(selectinload(FinanceInvestment.income_entries))
    )
    if row is None:
        raise ProTrackValidationError("Investment not found")
    return row


def create_investment(db: Session, payload: dict) -> FinanceInvestment:
    data = _money_fields(
        payload,
        [
            "amount_invested",
            "current_value",
            "expected_return_percent",
            "actual_return_amount",
            "income_received",
        ],
    )
    invested = _d(data.get("amount_invested"))
    current = data.get("current_value")
    current = invested if current is None else _d(current)
    row = FinanceInvestment(
        id=uuid4(),
        name=str(data["name"]).strip(),
        investment_type=(
            data["investment_type"]
            if isinstance(data.get("investment_type"), FinanceInvestmentType)
            else FinanceInvestmentType(str(data.get("investment_type") or "other"))
        ),
        institution=data.get("institution"),
        investment_date=data.get("investment_date"),
        amount_invested=invested,
        current_value=current,
        currency_code=str(data.get("currency_code") or "INR"),
        maturity_date=data.get("maturity_date"),
        expected_return_percent=data.get("expected_return_percent"),
        actual_return_amount=_d(data.get("actual_return_amount")),
        income_received=_d(data.get("income_received")),
        status=data.get("status") or FinanceInvestmentStatus.active,
        notes=data.get("notes"),
        source=data.get("source") or FinanceRecordSource.manual,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return get_investment(db, row.id)


def update_investment(db: Session, investment_id: UUID, payload: dict) -> FinanceInvestment:
    row = get_investment(db, investment_id)
    data = _money_fields(
        payload,
        [
            "amount_invested",
            "current_value",
            "expected_return_percent",
            "actual_return_amount",
            "income_received",
        ],
    )
    for key, value in data.items():
        if value is not None and hasattr(row, key):
            setattr(row, key, value)
    db.commit()
    return get_investment(db, row.id)


def record_investment_income(db: Session, investment_id: UUID, payload: dict) -> FinanceInvestment:
    investment = get_investment(db, investment_id)
    amount = _d(payload.get("amount"))
    if amount <= 0:
        raise ProTrackValidationError("Investment income must be greater than zero")
    db.add(
        FinanceInvestmentIncome(
            id=uuid4(),
            investment_id=investment.id,
            income_date=payload.get("income_date") or date.today(),
            amount=amount,
            notes=payload.get("notes"),
            source=payload.get("source") or FinanceRecordSource.manual,
        )
    )
    investment.income_received = _d(investment.income_received) + amount
    db.commit()
    return get_investment(db, investment.id)


def investment_to_dict(row: FinanceInvestment) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "investment_type": row.investment_type.value if row.investment_type else None,
        "institution": row.institution,
        "investment_date": row.investment_date,
        "amount_invested": row.amount_invested,
        "current_value": row.current_value,
        "currency_code": row.currency_code,
        "maturity_date": row.maturity_date,
        "expected_return_percent": row.expected_return_percent,
        "actual_return_amount": row.actual_return_amount,
        "income_received": row.income_received,
        "status": row.status.value if row.status else None,
        "notes": row.notes,
        "source": row.source.value if row.source else None,
        "is_active": row.is_active,
        "accounting_note": (
            "Purchase reduces cash and increases investment asset; "
            "it is not automatic operating expense."
        ),
        "income_entries": [
            {
                "id": str(e.id),
                "income_date": e.income_date,
                "amount": e.amount,
                "notes": e.notes,
                "cash_inflow": e.amount,
            }
            for e in row.income_entries
        ],
    }


# --- Cash position + treasury summary --------------------------------------


def upsert_cash_position(db: Session, payload: dict) -> FinanceCashPosition:
    data = _money_fields(payload, ["bank_balance", "cash_balance"])
    as_of = data.get("as_of_date") or date.today()
    existing = db.scalar(
        select(FinanceCashPosition)
        .where(
            FinanceCashPosition.as_of_date == as_of,
            FinanceCashPosition.is_active.is_(True),
        )
        .limit(1)
    )
    if existing is None:
        existing = FinanceCashPosition(
            id=uuid4(),
            as_of_date=as_of,
            bank_balance=_d(data.get("bank_balance")),
            cash_balance=_d(data.get("cash_balance")),
            currency_code=str(data.get("currency_code") or "INR"),
            notes=data.get("notes"),
            source=data.get("source") or FinanceRecordSource.manual,
            is_active=True,
        )
        db.add(existing)
    else:
        if "bank_balance" in data:
            existing.bank_balance = _d(data.get("bank_balance"))
        if "cash_balance" in data:
            existing.cash_balance = _d(data.get("cash_balance"))
        if data.get("notes") is not None:
            existing.notes = data.get("notes")
        if data.get("currency_code"):
            existing.currency_code = data["currency_code"]
    db.commit()
    db.refresh(existing)
    return existing


def latest_cash_position(db: Session) -> FinanceCashPosition | None:
    return db.scalar(
        select(FinanceCashPosition)
        .where(FinanceCashPosition.is_active.is_(True))
        .order_by(FinanceCashPosition.as_of_date.desc())
        .limit(1)
    )


def treasury_summary(db: Session) -> dict:
    loans = list_loans(db)
    ods = list_od_facilities(db)
    investments = list_investments(db)
    cash = latest_cash_position(db)
    loan_outstanding = sum((_d(l.outstanding_principal) for l in loans), Decimal("0.00"))
    od_limit = sum((_d(o.sanctioned_limit) for o in ods), Decimal("0.00"))
    od_used = sum((_d(o.current_utilization) for o in ods), Decimal("0.00"))
    invest_value = sum((_d(i.current_value) for i in investments), Decimal("0.00"))
    bank = _d(cash.bank_balance) if cash else Decimal("0.00")
    cash_bal = _d(cash.cash_balance) if cash else Decimal("0.00")
    return {
        "cash": {
            "as_of_date": cash.as_of_date if cash else None,
            "bank_balance": bank,
            "cash_balance": cash_bal,
            "available_cash": (bank + cash_bal).quantize(Decimal("0.01")),
            "currency_code": cash.currency_code if cash else "INR",
            "has_manual_position": cash is not None,
        },
        "debt": {
            "loan_outstanding_principal": loan_outstanding.quantize(Decimal("0.01")),
            "loan_count": len(loans),
            "od_sanctioned_limit": od_limit.quantize(Decimal("0.01")),
            "od_utilized": od_used.quantize(Decimal("0.01")),
            "od_available": max(Decimal("0.00"), od_limit - od_used).quantize(Decimal("0.01")),
            "od_utilization_percent": (
                (od_used / od_limit * Decimal("100")).quantize(Decimal("0.01"))
                if od_limit > 0
                else Decimal("0.00")
            ),
        },
        "investments": {
            "current_value": invest_value.quantize(Decimal("0.01")),
            "amount_invested": sum(
                (_d(i.amount_invested) for i in investments), Decimal("0.00")
            ).quantize(Decimal("0.01")),
            "count": len(investments),
        },
        "notes": {
            "loan_principal": "Outstanding loan principal is a financing liability, not a P&L expense.",
            "od_utilization": "OD utilization is financing position; OD interest is finance cost.",
            "investments": "Investment purchase is cash + asset, not automatic operating expense.",
        },
    }
