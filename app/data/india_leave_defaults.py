"""India leave-type defaults for a future Leave module.

Prosohm currently runs leave on GreytHR / another platform, so the full Leave
workflow is deferred. These defaults are ready to seed when Leave is built:

- Flexible approval: single approver *or* multi-level (configurable per type /
  company policy).
- Day counts follow common Indian private-sector practice and can be overridden
  per employee / year when the module ships.
"""

from __future__ import annotations

from typing import TypedDict


class IndiaLeaveTypeDefault(TypedDict):
    code: str
    name: str
    description: str
    default_annual_days: float
    is_paid: bool
    requires_approval: bool
    allows_half_day: bool
    carry_forward_max_days: float | None
    colour: str
    sort_order: int


# Typical India private-sector entitlements (calendar year). Adjust at go-live.
INDIA_LEAVE_TYPE_DEFAULTS: tuple[IndiaLeaveTypeDefault, ...] = (
    {
        "code": "el",
        "name": "Earned Leave / Privilege Leave",
        "description": "Annual earned leave. Often accrues monthly; unused days may carry forward up to a cap.",
        "default_annual_days": 18.0,
        "is_paid": True,
        "requires_approval": True,
        "allows_half_day": True,
        "carry_forward_max_days": 30.0,
        "colour": "#1565c0",
        "sort_order": 10,
    },
    {
        "code": "cl",
        "name": "Casual Leave",
        "description": "Short-notice personal leave. Usually does not carry forward.",
        "default_annual_days": 12.0,
        "is_paid": True,
        "requires_approval": True,
        "allows_half_day": True,
        "carry_forward_max_days": 0.0,
        "colour": "#00897b",
        "sort_order": 20,
    },
    {
        "code": "sl",
        "name": "Sick Leave",
        "description": "Medical leave. Medical certificate may be required beyond a threshold.",
        "default_annual_days": 12.0,
        "is_paid": True,
        "requires_approval": True,
        "allows_half_day": True,
        "carry_forward_max_days": 0.0,
        "colour": "#c62828",
        "sort_order": 30,
    },
    {
        "code": "comp_off",
        "name": "Compensatory Off",
        "description": "Time off in lieu of weekend / holiday work. Granted per worked day.",
        "default_annual_days": 0.0,
        "is_paid": True,
        "requires_approval": True,
        "allows_half_day": True,
        "carry_forward_max_days": None,
        "colour": "#6a1b9a",
        "sort_order": 40,
    },
    {
        "code": "wfh",
        "name": "Work From Home",
        "description": "Remote work day (tracked separately from leave balance when enabled).",
        "default_annual_days": 0.0,
        "is_paid": True,
        "requires_approval": True,
        "allows_half_day": True,
        "carry_forward_max_days": None,
        "colour": "#455a64",
        "sort_order": 50,
    },
    {
        "code": "unpaid",
        "name": "Leave Without Pay (LWP)",
        "description": "Unpaid absence when paid balances are exhausted or not applicable.",
        "default_annual_days": 0.0,
        "is_paid": False,
        "requires_approval": True,
        "allows_half_day": True,
        "carry_forward_max_days": None,
        "colour": "#757575",
        "sort_order": 60,
    },
    {
        "code": "maternity",
        "name": "Maternity Leave",
        "description": "Statutory maternity leave (India Maternity Benefit Act — typically 26 weeks for eligible employees).",
        "default_annual_days": 182.0,
        "is_paid": True,
        "requires_approval": True,
        "allows_half_day": False,
        "carry_forward_max_days": None,
        "colour": "#ad1457",
        "sort_order": 70,
    },
    {
        "code": "paternity",
        "name": "Paternity Leave",
        "description": "Company paternity leave (policy-driven; common range 5–15 days).",
        "default_annual_days": 7.0,
        "is_paid": True,
        "requires_approval": True,
        "allows_half_day": False,
        "carry_forward_max_days": None,
        "colour": "#0277bd",
        "sort_order": 80,
    },
    {
        "code": "bereavement",
        "name": "Bereavement / Compassionate Leave",
        "description": "Leave for death in the immediate family.",
        "default_annual_days": 3.0,
        "is_paid": True,
        "requires_approval": True,
        "allows_half_day": False,
        "carry_forward_max_days": None,
        "colour": "#37474f",
        "sort_order": 90,
    },
    {
        "code": "marriage",
        "name": "Marriage Leave",
        "description": "Leave for the employee's own wedding (company policy).",
        "default_annual_days": 5.0,
        "is_paid": True,
        "requires_approval": True,
        "allows_half_day": False,
        "carry_forward_max_days": None,
        "colour": "#ef6c00",
        "sort_order": 100,
    },
)

# When Leave ships: company setting approval_levels = 1 | 2 (default 1).
# Multi-level: Level 1 = reporting manager; Level 2 = HR / department head.
LEAVE_APPROVAL_MODES = ("single", "multi_level")
DEFAULT_LEAVE_APPROVAL_MODE = "single"
