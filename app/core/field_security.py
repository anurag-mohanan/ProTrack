"""Field-level security: who may see individual sensitive fields.

Endpoint (module/action) authorization decides whether a caller may reach a
resource at all; this layer decides whether specific *fields* within that
resource (salary, cost, budget, profitability) are visible. Rules combine role
membership, financial-planning module access, and explicit special permissions,
so a user who can open a finance page does not automatically see every salary.
"""

from __future__ import annotations

from app.core.access_control import (
    ADMIN,
    ENGINEERING_MANAGER,
    HR,
    MODULE_FINANCIAL_PLANNING,
    OFFICE_ADMINISTRATOR,
    SPECIAL_VIEW_BUDGET,
    SPECIAL_VIEW_FINANCIAL_COST,
    SPECIAL_VIEW_PROFITABILITY,
    SPECIAL_VIEW_SALARY,
    normalize_role_name,
    resolve_user_modules,
    user_has_special,
)
from app.models.models import User

# Field classes.
FIELD_SALARY = "salary"
FIELD_COST = "cost"
FIELD_BUDGET = "budget"
FIELD_PROFITABILITY = "profitability"


def _has_finance_module(user: User, role_name: str) -> bool:
    return MODULE_FINANCIAL_PLANNING in resolve_user_modules(user, role_name)


def can_view_salary(user: User, role_name: str) -> bool:
    """Salary: HR, Engineering Manager, Finance, System Administrator."""
    normalized = normalize_role_name(role_name)
    if normalized in {ADMIN, HR, ENGINEERING_MANAGER, OFFICE_ADMINISTRATOR}:
        return True
    if _has_finance_module(user, role_name):
        return True
    return user_has_special(user, role_name, SPECIAL_VIEW_SALARY)


def can_view_cost(user: User, role_name: str) -> bool:
    """Financial cost (hourly cost, run-rate): Finance, Engineering Manager."""
    normalized = normalize_role_name(role_name)
    if normalized in {ADMIN, ENGINEERING_MANAGER}:
        return True
    if _has_finance_module(user, role_name):
        return True
    return user_has_special(user, role_name, SPECIAL_VIEW_FINANCIAL_COST)


def can_view_budget(user: User, role_name: str) -> bool:
    """Budget: hidden from designers; finance-capable roles only."""
    normalized = normalize_role_name(role_name)
    if normalized in {ADMIN, ENGINEERING_MANAGER}:
        return True
    if _has_finance_module(user, role_name):
        return True
    return user_has_special(user, role_name, SPECIAL_VIEW_BUDGET)


def can_view_profitability(user: User, role_name: str) -> bool:
    """Customer / project profitability: requires financial-planning access."""
    normalized = normalize_role_name(role_name)
    if normalized == ADMIN:
        return True
    if _has_finance_module(user, role_name):
        return True
    return user_has_special(user, role_name, SPECIAL_VIEW_PROFITABILITY)


_CHECKS = {
    FIELD_SALARY: can_view_salary,
    FIELD_COST: can_view_cost,
    FIELD_BUDGET: can_view_budget,
    FIELD_PROFITABILITY: can_view_profitability,
}


def can_view_field(user: User, role_name: str, field_class: str) -> bool:
    check = _CHECKS.get(field_class)
    return True if check is None else check(user, role_name)


def redact(model, field_names: list[str]) -> None:
    """Null out the given attributes on a Pydantic/ORM-like object in place."""
    for name in field_names:
        if hasattr(model, name):
            try:
                setattr(model, name, None)
            except (ValueError, AttributeError):
                pass
