"""Soft segregation-of-duties (SoD) checks for special permissions (R1)."""

from __future__ import annotations

from app.core.access_control import (
    SPECIAL_APPROVE_PROJECTS,
    SPECIAL_APPROVE_TIMESHEETS,
    SPECIAL_BUDGET_APPROVAL,
    SPECIAL_DELETE_PROJECTS,
    SPECIAL_FINANCIAL_APPROVAL,
    SPECIAL_IMPORT_TIMESHEETS,
    SPECIAL_MANAGE_PERMISSIONS,
)
from app.core.exceptions import ProTrackValidationError

# Conflicting pairs: holding both specials on one user is rejected (maker-checker).
SOD_CONFLICT_PAIRS: tuple[tuple[str, str, str], ...] = (
    (
        SPECIAL_IMPORT_TIMESHEETS,
        SPECIAL_APPROVE_TIMESHEETS,
        "Cannot both import and approve timesheets (maker-checker).",
    ),
    (
        SPECIAL_DELETE_PROJECTS,
        SPECIAL_APPROVE_PROJECTS,
        "Cannot both delete and approve projects (maker-checker).",
    ),
    (
        SPECIAL_MANAGE_PERMISSIONS,
        SPECIAL_FINANCIAL_APPROVAL,
        "Cannot both manage permissions and hold financial approval.",
    ),
    (
        SPECIAL_MANAGE_PERMISSIONS,
        SPECIAL_BUDGET_APPROVAL,
        "Cannot both manage permissions and hold budget approval.",
    ),
)


def validate_special_permission_sod(
    specials: list[str] | set[str] | None,
    *,
    role_name: str | None = None,
) -> None:
    """Raise ProTrackValidationError when conflicting specials are combined.

    The Admin role is exempt: platform administrators hold both maker and
    checker powers by design. Applying SoD to Admin defaults made it
    impossible to persist delete_projects together with approve_projects.
    """
    if not specials:
        return
    from app.core.access_control import ADMIN, normalize_role_name

    if role_name and normalize_role_name(role_name) == ADMIN:
        return
    held = {str(s).strip() for s in specials if s}
    for left, right, message in SOD_CONFLICT_PAIRS:
        if left in held and right in held:
            raise ProTrackValidationError(
                f"Segregation of duties conflict: {message} "
                f"Remove either '{left}' or '{right}'."
            )
