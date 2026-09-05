"""Compose live financial health indicators from FY turnover, runway, and treasury."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import FinanceLoanStatus
from app.services.finance.cash_flow_forecast_service import build_cash_runway
from app.services.finance.fy_turnover_service import build_fy_turnover_control
from app.services.finance.treasury_service import list_loans, treasury_summary


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _indicator(
    *,
    key: str,
    label: str,
    status: str,
    value: str,
    detail: str,
    accounting_note: str | None = None,
) -> dict:
    return {
        "key": key,
        "label": label,
        "status": status,
        "value": value,
        "detail": detail,
        "accounting_note": accounting_note,
    }


def build_financial_health(
    db: Session,
    *,
    team_id: UUID | None = None,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    runway = build_cash_runway(db, team_id=team_id, today=today)
    turnover = build_fy_turnover_control(db, team_id=team_id, today=today)
    treasury = treasury_summary(db)

    fytd_turnover = _d(turnover.get("fytd_turnover_inr"))
    fytd_cash = _d(turnover.get("fytd_cash_collected_inr"))
    collection_ratio = (
        (fytd_cash / fytd_turnover * Decimal("100")).quantize(Decimal("0.01"))
        if fytd_turnover > 0
        else None
    )
    receivables = _d(turnover.get("outstanding_receivables_inr"))
    available_cash = _d(treasury["cash"]["available_cash"])
    loan_outstanding = _d(treasury["debt"]["loan_outstanding_principal"])
    od_util_pct = _d(treasury["debt"]["od_utilization_percent"])
    invest_value = _d(treasury["investments"]["current_value"])

    active_emi = sum(
        (
            _d(loan.emi_amount)
            for loan in list_loans(db)
            if loan.status == FinanceLoanStatus.active and loan.emi_amount is not None
        ),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    indicators: list[dict] = []

    # 1) Cash runway
    r_status = runway.get("status") or "missing_cash_position"
    if r_status == "missing_cash_position":
        indicators.append(
            _indicator(
                key="cash_runway",
                label="Cash runway",
                status="watch",
                value="Not set",
                detail=runway.get("message") or "Set a Treasury cash position.",
                accounting_note="Available cash comes from the latest manual bank + cash position.",
            )
        )
    elif r_status == "cash_generative":
        indicators.append(
            _indicator(
                key="cash_runway",
                label="Cash runway",
                status="healthy",
                value="Cash generative",
                detail=runway.get("message") or "Collections cover outflow + loan EMI.",
                accounting_note="Payment-date collections vs operating outflow + EMI (not P&L profit).",
            )
        )
    else:
        months = runway.get("runway_months")
        months_f = float(months) if months is not None else 0.0
        status = "critical" if months_f < 3 else "watch" if months_f < 6 else "healthy"
        indicators.append(
            _indicator(
                key="cash_runway",
                label="Cash runway",
                status=status,
                value=f"{months_f:.1f} mo",
                detail=runway.get("message") or "",
                accounting_note="Runway = available cash ÷ average monthly net cash burn.",
            )
        )

    # 2) Collections vs turnover (P&L vs cash)
    if collection_ratio is None:
        coll_status = "watch"
        coll_value = "—"
        coll_detail = "No FYTD turnover yet — invoice-date turnover drives this ratio."
    elif collection_ratio >= 85:
        coll_status = "healthy"
        coll_value = f"{collection_ratio}%"
        coll_detail = "Cash collected is close to invoice-date turnover for the FY to date."
    elif collection_ratio >= 60:
        coll_status = "watch"
        coll_value = f"{collection_ratio}%"
        coll_detail = "Collections lag turnover — watch receivables timing."
    else:
        coll_status = "critical"
        coll_value = f"{collection_ratio}%"
        coll_detail = "Large gap between invoiced turnover and cash collected."
    indicators.append(
        _indicator(
            key="collections_vs_turnover",
            label="Collections vs turnover",
            status=coll_status,
            value=coll_value,
            detail=coll_detail,
            accounting_note=(
                "Turnover uses invoice date; cash uses payment date. "
                "A gap is timing, not necessarily a P&L loss."
            ),
        )
    )

    # 3) Receivables pressure
    if fytd_turnover <= 0:
        recv_status = "watch"
        recv_value = str(receivables)
        recv_detail = "No FYTD turnover baseline for receivables pressure."
    else:
        recv_ratio = (receivables / fytd_turnover * Decimal("100")).quantize(Decimal("0.01"))
        recv_value = f"{receivables}"
        if recv_ratio <= 25:
            recv_status = "healthy"
            recv_detail = f"Outstanding receivables are {recv_ratio}% of FYTD turnover."
        elif recv_ratio <= 50:
            recv_status = "watch"
            recv_detail = f"Outstanding receivables are {recv_ratio}% of FYTD turnover."
        else:
            recv_status = "critical"
            recv_detail = f"Outstanding receivables are {recv_ratio}% of FYTD turnover."
    indicators.append(
        _indicator(
            key="receivables",
            label="Outstanding receivables",
            status=recv_status,
            value=recv_value,
            detail=recv_detail,
            accounting_note="Balance due on active quotes — not yet collected cash.",
        )
    )

    # 4) Debt / OD
    if loan_outstanding <= 0 and od_util_pct <= 0:
        debt_status = "healthy"
        debt_value = "No active debt"
        debt_detail = "No outstanding loan principal or OD utilization recorded."
    elif od_util_pct >= 85:
        debt_status = "critical"
        debt_value = f"OD {od_util_pct}%"
        debt_detail = (
            f"Loan principal outstanding {loan_outstanding}; OD utilization {od_util_pct}%."
        )
    elif od_util_pct >= 60 or (
        available_cash > 0 and loan_outstanding > available_cash * Decimal("3")
    ):
        debt_status = "watch"
        debt_value = f"Loans {loan_outstanding}"
        debt_detail = (
            f"Loan principal {loan_outstanding}; OD utilization {od_util_pct}%; "
            f"active EMI {active_emi}/mo."
        )
    else:
        debt_status = "healthy"
        debt_value = f"Loans {loan_outstanding}"
        debt_detail = (
            f"Financing position looks manageable. OD utilization {od_util_pct}%; "
            f"EMI {active_emi}/mo."
        )
    indicators.append(
        _indicator(
            key="debt_od",
            label="Debt & OD",
            status=debt_status,
            value=debt_value,
            detail=debt_detail,
            accounting_note=(
                "Loan/OD principal is financing position, not revenue or expense. "
                "Interest is finance cost; EMI is cash outflow."
            ),
        )
    )

    # 5) Liquidity buffer (cash + investments vs short-term burn)
    net_burn = _d(runway.get("average_monthly_net_burn"))
    liquid = available_cash + invest_value
    if r_status == "missing_cash_position":
        liq_status = "watch"
        liq_value = str(invest_value) if invest_value > 0 else "—"
        liq_detail = "Cash position missing; investments alone do not define runway."
    elif net_burn <= 0:
        liq_status = "healthy"
        liq_value = str(liquid)
        liq_detail = "Cash + investments available while net burn is not positive."
    else:
        buffer_months = (liquid / net_burn).quantize(Decimal("0.1"))
        liq_value = f"{buffer_months} mo"
        if buffer_months < 3:
            liq_status = "critical"
        elif buffer_months < 6:
            liq_status = "watch"
        else:
            liq_status = "healthy"
        liq_detail = (
            f"Cash {available_cash} + investments {invest_value} cover ~{buffer_months} months "
            f"of net burn {net_burn}."
        )
    indicators.append(
        _indicator(
            key="liquidity_buffer",
            label="Liquidity buffer",
            status=liq_status,
            value=liq_value,
            detail=liq_detail,
            accounting_note=(
                "Investment purchases are cash + asset, not automatic OpEx. "
                "Income from investments improves cash; principal is not P&L revenue."
            ),
        )
    )

    ranks = {"healthy": 0, "watch": 1, "critical": 2}
    worst = max((ranks.get(i["status"], 1) for i in indicators), default=1)
    overall = {0: "healthy", 1: "watch", 2: "critical"}[worst]
    messages = {
        "healthy": "Live signals look stable across cash, collections, and financing.",
        "watch": "One or more signals need attention — review runway, collections, or debt.",
        "critical": "Critical pressure on cash or financing — prioritize collections and runway.",
    }

    return {
        "as_of": today.isoformat(),
        "overall_status": overall,
        "overall_message": messages[overall],
        "indicators": indicators,
        "runway": runway,
        "fy_turnover_snapshot": {
            "fy_label": turnover.get("fy_label"),
            "fytd_turnover_inr": fytd_turnover,
            "fytd_cash_collected_inr": fytd_cash,
            "average_monthly_billing_inr": turnover.get("average_monthly_billing_inr"),
            "outstanding_receivables_inr": receivables,
            "collection_ratio_percent": collection_ratio,
            "elapsed_months": turnover.get("elapsed_months"),
        },
        "treasury_snapshot": {
            "available_cash": available_cash,
            "loan_outstanding_principal": loan_outstanding,
            "od_utilization_percent": od_util_pct,
            "od_available": treasury["debt"]["od_available"],
            "investments_current_value": invest_value,
            "active_loan_emi_monthly": active_emi,
            "has_manual_cash_position": treasury["cash"]["has_manual_position"],
        },
        "accounting_notes": [
            "Invoice date → P&L turnover; payment date → cash collection.",
            "Loan/OD principal → financing position; interest → P&L finance cost.",
            "Investment/CapEx purchase → cash + asset, not automatic operating expense.",
        ],
        "what_if_seed": {
            "opening_cash": float(available_cash),
            "extra_loan_emi_monthly": float(active_emi),
            "collections_realization_percent": (
                float(collection_ratio) if collection_ratio is not None else 80.0
            ),
        },
    }
