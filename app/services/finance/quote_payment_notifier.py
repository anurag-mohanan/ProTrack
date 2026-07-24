"""Payment follow-up reminders for invoiced quotes with outstanding balance."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access_control import MODULE_FINANCIAL_PLANNING, resolve_user_modules
from app.core.module_actions import MODULE_ACTION_EDIT, user_has_module_action
from app.core.permissions import get_role_name
from app.models.enums import EntityType, NotificationType
from app.models.finance import Quote
from app.models.models import Customer, Notification, Team, User
from app.services.finance.quote_cash_ledger_service import summarize_quote_cash

# First follow-up 30 days after earliest invoice; then weekly while balance_due > 0.
INITIAL_DELAY_DAYS = 30
REMINDER_INTERVAL_DAYS = 7


def payment_follow_up_anchor(db: Session, quote: Quote) -> date | None:
    summary = summarize_quote_cash(db, quote)
    if summary["balance_due"] > 0:
        return summary["invoiced_date"] or quote.invoiced_date
    # Legacy unpaid with no ledger lines yet
    if (
        quote.is_invoiced
        and not quote.is_paid
        and not summary["invoice_lines"]
        and quote.invoiced_date is not None
    ):
        return quote.invoiced_date
    return None


def next_payment_follow_up_date(
    db: Session,
    quote: Quote,
    *,
    today: date | None = None,
) -> date | None:
    """Next calendar day a payment follow-up is due (None if balance cleared)."""
    today = today or date.today()
    anchor = payment_follow_up_anchor(db, quote)
    if anchor is None:
        return None
    first = anchor + timedelta(days=INITIAL_DELAY_DAYS)
    if today < first:
        return first
    days_since = (today - anchor).days
    offset = (days_since - INITIAL_DELAY_DAYS) % REMINDER_INTERVAL_DAYS
    if offset == 0:
        return today
    return today + timedelta(days=REMINDER_INTERVAL_DAYS - offset)


def payment_follow_up_due(
    db: Session,
    quote: Quote,
    *,
    today: date | None = None,
) -> bool:
    """True when finance should actively chase payment (day 30+ with balance)."""
    today = today or date.today()
    anchor = payment_follow_up_anchor(db, quote)
    if anchor is None:
        return False
    return (today - anchor).days >= INITIAL_DELAY_DAYS


def _should_notify_today(db: Session, quote: Quote, today: date) -> bool:
    anchor = payment_follow_up_anchor(db, quote)
    if anchor is None:
        return False
    days_since = (today - anchor).days
    if days_since < INITIAL_DELAY_DAYS:
        return False
    if (days_since - INITIAL_DELAY_DAYS) % REMINDER_INTERVAL_DAYS != 0:
        return False
    if quote.last_payment_reminder_at == today:
        return False
    return True


def list_quotes_due_for_payment_reminder(
    db: Session,
    *,
    today: date | None = None,
    team_id: UUID | None = None,
) -> list[Quote]:
    today = today or date.today()
    stmt = select(Quote).where(Quote.is_active.is_(True), Quote.is_invoiced.is_(True))
    if team_id is not None:
        stmt = stmt.where(Quote.team_id == team_id)
    due: list[Quote] = []
    for quote in db.scalars(stmt).all():
        if _should_notify_today(db, quote, today):
            due.append(quote)
    return sorted(due, key=lambda row: (row.tool_number or "", str(row.id)))


def _finance_edit_recipients(db: Session) -> list[User]:
    users = db.scalars(select(User).where(User.is_active.is_(True))).all()
    recipients: list[User] = []
    for user in users:
        role = get_role_name(db, user)
        if MODULE_FINANCIAL_PLANNING not in resolve_user_modules(user, role):
            continue
        if user_has_module_action(user, role, MODULE_FINANCIAL_PLANNING, MODULE_ACTION_EDIT):
            recipients.append(user)
    return recipients


def notify_unpaid_quotes(
    db: Session,
    *,
    today: date | None = None,
    team_id: UUID | None = None,
) -> tuple[int, list[UUID]]:
    """Notify finance editors: 30 days after invoice, then weekly while balance due."""
    today = today or date.today()
    recipients = _finance_edit_recipients(db)
    if not recipients:
        return 0, []

    notified_ids: list[UUID] = []
    for quote in list_quotes_due_for_payment_reminder(db, today=today, team_id=team_id):
        summary = summarize_quote_cash(db, quote)
        customer = db.get(Customer, quote.customer_id)
        customer_label = customer.name if customer is not None else "Unknown customer"
        team_label = ""
        if quote.team_id:
            team = db.get(Team, quote.team_id)
            if team:
                team_label = f" [{team.name}]"
        anchor = summary["invoiced_date"] or quote.invoiced_date
        days_since = (today - anchor).days if anchor else 0
        quote_ref = quote.external_quote_number or quote.tool_number
        po = f" PO {quote.customer_po_number}" if quote.customer_po_number else ""
        title = f"Payment follow-up: {quote_ref}{team_label}"[:200]
        message = (
            f"{quote_ref}{po} ({customer_label}){team_label} has balance due "
            f"{summary['balance_due']} (invoiced {summary['total_invoiced']}, "
            f"paid {summary['total_paid']}) — {days_since} days since first invoice. "
            f"Record partial payments in Finance → Revenue / quotes."
        )
        for user in recipients:
            db.add(
                Notification(
                    user_id=user.id,
                    notification_type=NotificationType.quote_payment_follow_up,
                    title=title,
                    message=message,
                    entity_type=EntityType.quote,
                    entity_id=quote.id,
                    is_read=False,
                    is_archived=False,
                )
            )
        quote.last_payment_reminder_at = today
        notified_ids.append(quote.id)

    return len(notified_ids), notified_ids
