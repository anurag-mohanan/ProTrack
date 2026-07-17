"""Module × action permission helpers for EBMP modules."""

from __future__ import annotations

import json

from app.models.models import User

MODULE_ACTION_VIEW = "view"
MODULE_ACTION_CREATE = "create"
MODULE_ACTION_EDIT = "edit"
MODULE_ACTION_DELETE = "delete"
MODULE_ACTION_APPROVE = "approve"
MODULE_ACTION_EXPORT = "export"
MODULE_ACTION_CONFIGURE = "configure"
MODULE_ACTION_EDIT_REVIEWS = "edit_reviews"
MODULE_ACTION_MANAGE_TEMPLATES = "manage_templates"
MODULE_ACTION_CALIBRATE = "calibrate"
MODULE_ACTION_OPEN_CYCLES = "open_cycles"

ALL_MODULE_ACTIONS: tuple[str, ...] = (
    MODULE_ACTION_VIEW,
    MODULE_ACTION_CREATE,
    MODULE_ACTION_EDIT,
    MODULE_ACTION_DELETE,
    MODULE_ACTION_APPROVE,
    MODULE_ACTION_EXPORT,
    MODULE_ACTION_CONFIGURE,
    MODULE_ACTION_EDIT_REVIEWS,
    MODULE_ACTION_MANAGE_TEMPLATES,
    MODULE_ACTION_CALIBRATE,
    MODULE_ACTION_OPEN_CYCLES,
)


def _parse_actions_map(raw: str | None) -> dict[str, list[str]] | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    result: dict[str, list[str]] = {}
    for module, actions in parsed.items():
        if not isinstance(module, str) or not isinstance(actions, list):
            continue
        cleaned = [
            action
            for action in actions
            if isinstance(action, str) and action in ALL_MODULE_ACTIONS
        ]
        if cleaned:
            result[module] = sorted(set(cleaned))
    return result


def serialize_module_actions(values: dict[str, list[str]] | None) -> str | None:
    if values is None:
        return None
    cleaned: dict[str, list[str]] = {}
    for module, actions in values.items():
        valid = sorted({a for a in actions if a in ALL_MODULE_ACTIONS})
        if valid:
            cleaned[module] = valid
    return json.dumps(cleaned, sort_keys=True) if cleaned else None


def default_module_actions_for_role(role_name: str, modules: list[str]) -> dict[str, list[str]]:
    """Full action set for Admin; CRUD+approve+export for EM finance; view elsewhere."""
    from app.core.access_control import (
        ADMIN,
        DESIGN_LEADER,
        ENGINEERING_MANAGER,
        HR,
        MODULE_FINANCIAL_PLANNING,
        MODULE_HUMAN_RESOURCES,
        MODULE_PERFORMANCE,
        MODULE_REPORTS_ANALYTICS,
        MODULE_SYSTEM_ADMINISTRATION,
        OFFICE_ADMINISTRATOR,
        normalize_role_name,
    )

    normalized = normalize_role_name(role_name)
    full = list(ALL_MODULE_ACTIONS)
    performance_manager = [
        MODULE_ACTION_VIEW,
        MODULE_ACTION_EDIT_REVIEWS,
        MODULE_ACTION_CALIBRATE,
        MODULE_ACTION_OPEN_CYCLES,
    ]
    performance_hr = [
        *performance_manager,
        MODULE_ACTION_MANAGE_TEMPLATES,
        MODULE_ACTION_CONFIGURE,
    ]
    result: dict[str, list[str]] = {}
    for module in modules:
        if normalized == ADMIN:
            result[module] = full
        elif module == MODULE_PERFORMANCE:
            if normalized in {ADMIN, HR, OFFICE_ADMINISTRATOR}:
                result[module] = performance_hr
            elif normalized in {ENGINEERING_MANAGER, DESIGN_LEADER}:
                result[module] = performance_manager
            else:
                result[module] = [MODULE_ACTION_VIEW]
        elif normalized == ENGINEERING_MANAGER and module == MODULE_FINANCIAL_PLANNING:
            result[module] = full
        elif module == MODULE_SYSTEM_ADMINISTRATION and normalized == ADMIN:
            result[module] = full
        elif module in {MODULE_HUMAN_RESOURCES, MODULE_REPORTS_ANALYTICS}:
            if normalized in {ADMIN, HR, OFFICE_ADMINISTRATOR, ENGINEERING_MANAGER}:
                result[module] = [MODULE_ACTION_VIEW, MODULE_ACTION_EXPORT]
            else:
                result[module] = [MODULE_ACTION_VIEW]
        else:
            result[module] = [MODULE_ACTION_VIEW]
    return result


def resolve_user_module_actions(user: User, role_name: str, modules: list[str]) -> dict[str, list[str]]:
    stored = _parse_actions_map(getattr(user, "module_actions", None))
    if stored is not None:
        return {
            module: sorted(set(actions) | {MODULE_ACTION_VIEW})
            for module, actions in stored.items()
            if module in modules
        }
    return default_module_actions_for_role(role_name, modules)


def user_has_module_action(
    user: User,
    role_name: str,
    module: str,
    action: str,
    *,
    modules: list[str] | None = None,
) -> bool:
    from app.core.access_control import resolve_user_modules

    resolved_modules = modules if modules is not None else resolve_user_modules(user, role_name)
    if module not in resolved_modules:
        return False
    if action == MODULE_ACTION_VIEW:
        return True
    actions_map = resolve_user_module_actions(user, role_name, resolved_modules)
    return action in actions_map.get(module, [MODULE_ACTION_VIEW])
