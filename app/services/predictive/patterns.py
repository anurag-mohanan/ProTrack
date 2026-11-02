"""Portfolio patterns: group differences in completed work, with sample sizes and significance.

Computed on request from the same inputs as the predictions; nothing is stored. A difference is
only reported as a pattern when both sides are large enough and a rank test finds it unlikely to
be chance. Smaller groups are listed with their size only, never with a label.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.services.predictive.inputs import ProjectFacts
from app.services.predictive.stats import MIN_PATTERN_GROUP, MIN_SAMPLE, SIGNIFICANCE, central, mann_whitney_p

LIMITATIONS = [
    "Patterns describe completed work only; they are associations, not causes.",
    "Several groups are tested at once, so roughly 1 in 20 tested differences can look significant by chance.",
    f"A group needs at least {MIN_PATTERN_GROUP} projects and the comparison group at least {MIN_SAMPLE}.",
    "Customer differences in effort and delivery are compared only within the same project type and complexity, "
    "so a customer is never used as a stand-in for project complexity.",
]


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    unit: str
    value: Callable[[ProjectFacts], float | None]
    rule: str


def _effort(f: ProjectFacts) -> float | None:
    if not f.estimate_approved or not f.original_estimate or f.original_estimate <= 0:
        return None
    if f.actual_status != "recorded" or not f.actual_hours or f.actual_hours <= 0:
        return None
    return float(f.actual_hours / f.original_estimate)


def _slip(f: ProjectFacts) -> float | None:
    if f.completed_on is None or f.committed_date is None:
        return None
    return float((f.completed_on - f.committed_date).days)


METRICS = (
    Metric("effort_ratio", "Actual ÷ original approved estimate", "ratio", _effort,
           "Completed projects with an approved original estimate and recorded actual hours."),
    Metric("delivery_slip_days", "Completion − committed date (days)", "days", _slip,
           "Completed projects with a committed (baseline) date."),
)

DIMENSIONS: dict[str, tuple[str, Callable[[ProjectFacts], tuple[object, str] | None]]] = {
    "project_type": ("Project type", lambda f: (f.project_type_id, f.project_type_name or "No project type")),
    "complexity": ("Complexity", lambda f: (f.complexity, (f.complexity or "unset").title())),
    "team": ("Team", lambda f: (f.team_id, None) if f.team_id else None),
    "customer": ("Customer", lambda f: (f.customer_id, f.customer_name or "Unknown customer") if f.customer_id else None),
}


def _row(metric_key: str, metric_label: str, unit: str, dimension: str, label: str, group: list[float], rest: list[float],
         comparison: str, period: tuple[date | None, date | None], stratum: str | None = None) -> dict:
    p = mann_whitney_p(group, rest)
    g, r = central(group), central(rest)
    significant = p is not None and p < SIGNIFICANCE
    unit_text = "" if unit == "ratio" else f" {unit}"
    return {
        "metric": metric_key,
        "metric_label": metric_label,
        "dimension": dimension,
        "group_label": label,
        "stratum": stratum,
        "n": len(group),
        "comparison_n": len(rest),
        "comparison_group": comparison,
        "group_median": round(g, 3),
        "comparison_median": round(r, 3),
        "difference": round(g - r, 3),
        "p_value": round(p, 4) if p is not None else None,
        "significant": significant,
        "finding": (
            f"{label}: median {round(g, 2)}{unit_text} against {round(r, 2)}{unit_text} for {comparison} "
            f"(n={len(group)} vs {len(rest)}, p={round(p, 3)})." if significant else None
        ),
        "period_start": period[0].isoformat() if period[0] else None,
        "period_end": period[1].isoformat() if period[1] else None,
    }


def project_patterns(history: list[ProjectFacts], team_names: dict[UUID, str]) -> dict:
    rows: list[dict] = []
    too_small: list[dict] = []
    for metric in METRICS:
        points = [(f, v) for f in history if (v := metric.value(f)) is not None]
        dates = [f.completed_on for f, _ in points if f.completed_on]
        period = (min(dates) if dates else None, max(dates) if dates else None)
        for dimension, (dim_label, key_of) in DIMENSIONS.items():
            if dimension == "customer":
                strata: dict[tuple, list] = defaultdict(list)
                for f, v in points:
                    strata[(f.project_type_id, f.complexity)].append((f, v))
                for (type_id, complexity), cell in strata.items():
                    stratum = f"{cell[0][0].project_type_name or 'No project type'}, {(complexity or 'unset')} complexity"
                    _compare(metric, dimension, key_of, cell, rows, too_small, period, team_names, stratum)
            else:
                _compare(metric, dimension, key_of, points, rows, too_small, period, team_names, None)
    return {
        "patterns": [r for r in rows if r["significant"]],
        "no_reliable_difference": [r for r in rows if not r["significant"]],
        "too_small": too_small,
        "metrics": [{"key": m.key, "label": m.label, "rule": m.rule,
                     "projects": sum(1 for f in history if m.value(f) is not None)} for m in METRICS],
        "limitations": LIMITATIONS,
    }


def _compare(metric: Metric, dimension: str, key_of, points: list, rows: list, too_small: list, period, team_names,
             stratum: str | None) -> None:
    groups: dict[object, list] = defaultdict(list)
    labels: dict[object, str] = {}
    for f, v in points:
        keyed = key_of(f)
        if keyed is None:
            continue
        key, label = keyed
        groups[key].append(v)
        labels[key] = label or team_names.get(key, "Unknown team")
    if len(groups) < 2:
        return
    for key, values in groups.items():
        rest = [v for other, vs in groups.items() if other != key for v in vs]
        label = labels[key]
        if len(values) < MIN_PATTERN_GROUP or len(rest) < MIN_SAMPLE:
            too_small.append({"metric": metric.key, "dimension": dimension, "group_label": label, "stratum": stratum,
                              "n": len(values), "comparison_n": len(rest)})
            continue
        comparison = f"other {DIMENSIONS[dimension][0].lower()}s" + (f" ({stratum})" if stratum else "")
        rows.append(_row(metric.key, metric.label, metric.unit, dimension, label, values, rest, comparison, period, stratum))


def portfolio_project_patterns(db, as_of: date) -> dict:
    """Project patterns over every completed project up to ``as_of`` (organisation-wide)."""
    from sqlalchemy import select

    from app.models.models import Team
    from app.services.predictive.inputs import completed_projects, load_facts

    history = list(load_facts(db, completed_projects(db, as_of), as_of).values())
    return project_patterns(history, {t.id: t.name for t in db.scalars(select(Team))})


def portfolio_finance_patterns(db, as_of: date) -> dict:
    """Customer payment and invoicing patterns from the Phase 3 ledgers (Finance viewers only)."""
    from sqlalchemy import select

    from app.models.models import Customer
    from app.services.predictive import finance

    ledgers = finance.load_ledgers(db)
    names = {c.id: c.name for c in db.scalars(select(Customer))}
    return finance_patterns(finance.payment_delays(ledgers, as_of), finance.invoice_lags(ledgers, as_of), names)


def finance_patterns(delays: list[tuple[UUID | None, int]], lags: list[tuple[UUID | None, int]],
                     customer_names: dict[UUID, str]) -> dict:
    """Customer payment and invoicing behaviour. Customer identity is the subject here, not a proxy."""
    rows, too_small = [], []
    for key, label, samples in (("payment_delay_days", "Days from due date to full payment", delays),
                                ("invoice_lag_days", "Days from completion to invoice", lags)):
        by_customer: dict[UUID | None, list[float]] = defaultdict(list)
        for customer, value in samples:
            by_customer[customer].append(float(value))
        for customer, values in by_customer.items():
            rest = [v for c, vs in by_customer.items() if c != customer for v in vs]
            name = customer_names.get(customer, "Unknown customer") if customer else "Unknown customer"
            if len(values) < MIN_PATTERN_GROUP or len(rest) < MIN_SAMPLE:
                too_small.append({"metric": key, "dimension": "customer", "group_label": name, "n": len(values),
                                  "comparison_n": len(rest)})
                continue
            rows.append(_row(key, label, "days", "customer", name, values, rest, "other customers", (None, None)))
    return {
        "patterns": [r for r in rows if r["significant"]],
        "no_reliable_difference": [r for r in rows if not r["significant"]],
        "too_small": too_small,
        "limitations": [LIMITATIONS[0], LIMITATIONS[1], LIMITATIONS[2]],
    }
