"""In-app notifications for quotes not yet invoiced."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access_control import MODULE_FINANCIAL_PLANNING, resolve_user_modules
from app.core.module_actions import MODULE_ACTION_EDIT, user_has_module_action
from app.core.permissions import get_role_name
from app.models.enums import EntityType, NotificationType
from app.models.finance import Quote
from app.models.models import Customer, Notification, Team, User

INITIAL_DELAY_DAYS = 15
REMINDER_INTERVAL_DAYS = 5


def _quote_anchor_date(quote: Quote) -> date:
    if quote.created_at is not None:
        return quote.created_at.date()
    return quote.quoted_date or date.today()


def _should_notify_today(quote: Quote, today: date) -> bool:
    if quote.is_invoiced:
        return False
    days_since = (today - _quote_anchor_date(quote)).days
    if days_since < INITIAL_DELAY_DAYS:
        return False
    if (days_since - INITIAL_DELAY_DAYS) % REMINDER_INTERVAL_DAYS != 0:
        return False
    if quote.last_invoicing_reminder_at == today:
        return False
    return True


def list_quotes_due_for_invoicing_reminder(
    db: Session,
    *,
    today: date | None = None,
    team_id: UUID | None = None,
) -> list[Quote]:
    today = today or date.today()
    stmt = select(Quote).where(Quote.is_active.is_(True), Quote.is_invoiced.is_(False))
    if team_id is not None:
        stmt = stmt.where(Quote.team_id == team_id)
    due: list[Quote] = []
    for quote in db.scalars(stmt).all():
        if _should_notify_today(quote, today):
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


def notify_uninvoiced_quotes(
    db: Session,
    *,
    today: date | None = None,
    team_id: UUID | None = None,
) -> tuple[int, list[UUID]]:
    """Notify finance editors when a quote is still not invoiced (day 15, then every 5 days)."""
    today = today or date.today()
    recipients = _finance_edit_recipients(db)
    if not recipients:
        return 0, []

    notified_ids: list[UUID] = []
    for quote in list_quotes_due_for_invoicing_reminder(db, today=today, team_id=team_id):
        customer = db.get(Customer, quote.customer_id)
        customer_label = customer.name if customer is not None else "Unknown customer"
        team_label = ""
        if quote.team_id:
            team = db.get(Team, quote.team_id)
            if team:
                team_label = f" [{team.name}]"
        days_since = (today - _quote_anchor_date(quote)).days
        quote_ref = quote.external_quote_number or quote.tool_number
        title = f"Quote not invoiced: {quote_ref}{team_label}"[:200]
        message = (
            f"{quote_ref} ({customer_label}){team_label} was added {days_since} days ago "
            f"and is still not invoiced. Mark invoiced and set the invoiced date in Finance → Quotes."
        )
        for user in recipients:
            db.add(
                Notification(
                    user_id=user.id,
                    notification_type=NotificationType.quote_not_invoiced,
                    title=title,
                    message=message,
                    entity_type=EntityType.quote,
                    entity_id=quote.id,
                    is_read=False,
                    is_archived=False,
                )
            )
        quote.last_invoicing_reminder_at = today
        notified_ids.append(quote.id)

    return len(notified_ids), notified_ids
