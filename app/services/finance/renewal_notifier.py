"""In-app notifications for upcoming expense / software renewals."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access_control import MODULE_FINANCIAL_PLANNING, resolve_user_modules
from app.core.module_actions import MODULE_ACTION_EDIT, user_has_module_action
from app.core.permissions import get_role_name
from app.models.enums import EntityType, NotificationType
from app.models.finance import Expense
from app.models.models import Notification, User


def list_upcoming_renewals(db: Session, *, today: date | None = None) -> list[Expense]:
    today = today or date.today()
    expenses = db.scalars(
        select(Expense).where(
            Expense.is_active.is_(True),
            Expense.notify_enabled.is_(True),
            Expense.next_renewal_date.is_not(None),
        )
    ).all()
    due: list[Expense] = []
    for expense in expenses:
        assert expense.next_renewal_date is not None
        window_start = expense.next_renewal_date - timedelta(days=max(0, expense.notify_before_days or 7))
        if window_start <= today <= expense.next_renewal_date:
            due.append(expense)
    return sorted(due, key=lambda row: row.next_renewal_date or today)


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


def notify_upcoming_renewals(db: Session, *, today: date | None = None) -> tuple[int, list[UUID]]:
    """Create in-app notifications for renewals in the notify window (once per renewal date)."""
    today = today or date.today()
    recipients = _finance_edit_recipients(db)
    if not recipients:
        return 0, []

    notified_ids: list[UUID] = []
    for expense in list_upcoming_renewals(db, today=today):
        if expense.renewal_notified_for == expense.next_renewal_date:
            continue
        days_until = (expense.next_renewal_date - today).days  # type: ignore[operator]
        title = f"Renewal in {days_until} day{'s' if days_until != 1 else ''}: {expense.name}"
        vendor = f" ({expense.vendor_name})" if expense.vendor_name else ""
        message = (
            f"{expense.name}{vendor} renews on {expense.next_renewal_date.isoformat()}. "
            f"Amount {expense.amount} {expense.currency_code} · Paid by {expense.paid_by.value}."
        )
        for user in recipients:
            db.add(
                Notification(
                    user_id=user.id,
                    notification_type=NotificationType.expense_renewal,
                    title=title[:200],
                    message=message,
                    entity_type=EntityType.expense,
                    entity_id=expense.id,
                    is_read=False,
                    is_archived=False,
                )
            )
        expense.renewal_notified_for = expense.next_renewal_date
        notified_ids.append(expense.id)

    return len(notified_ids), notified_ids
