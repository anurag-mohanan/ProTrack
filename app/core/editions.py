"""Edition catalog and default feature-flag matrices (R10 commercial spine)."""

from __future__ import annotations

from typing import Literal

EditionCode = Literal["trial", "starter", "professional", "business", "enterprise"]

# Stable product flag keys — keep additive; never rename in place.
FLAG_CATALOG: dict[str, str] = {
    "module.projects": "Projects, milestones, templates",
    "module.timesheets": "Timesheets and approvals",
    "module.reports": "Engineering reports",
    "module.finance": "Finance, quotes, P&L",
    "module.hr": "HR, onboarding, exit, past employees",
    "module.performance": "Performance reviews",
    "module.planning_board": "Planning board / capacity wall",
    "module.analytics": "Analytics hub",
    "module.ai": "AI assistants and estimation assist",
    "feature.sso": "SSO / OIDC login",
    "feature.public_api": "Versioned public API",
    "feature.webhooks": "Outbound webhooks",
    "feature.customer_portal": "Customer portal",
    "feature.vendor_portal": "Vendor portal",
    "feature.white_label": "Advanced white-label theming",
}

# Which flags are ON by default for each edition.
_EDITION_DEFAULTS: dict[EditionCode, set[str]] = {
    "trial": {
        "module.projects",
        "module.timesheets",
        "module.reports",
    },
    "starter": {
        "module.projects",
        "module.timesheets",
        "module.reports",
        "feature.white_label",
    },
    "professional": {
        "module.projects",
        "module.timesheets",
        "module.reports",
        "module.planning_board",
        "module.analytics",
        "feature.white_label",
    },
    "business": {
        "module.projects",
        "module.timesheets",
        "module.reports",
        "module.finance",
        "module.hr",
        "module.performance",
        "module.planning_board",
        "module.analytics",
        "feature.public_api",
        "feature.white_label",
    },
    "enterprise": set(FLAG_CATALOG.keys()),
}


def default_flags_for_edition(edition: str) -> dict[str, bool]:
    code: EditionCode = "enterprise"
    if edition in _EDITION_DEFAULTS:
        code = edition  # type: ignore[assignment]
    enabled = _EDITION_DEFAULTS[code]
    return {key: key in enabled for key in FLAG_CATALOG}


def edition_codes() -> list[str]:
    return list(_EDITION_DEFAULTS.keys())
