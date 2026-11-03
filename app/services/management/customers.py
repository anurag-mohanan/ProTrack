"""Customer performance and customer intelligence profiles.

Built only from existing customer, project, timesheet and Finance records: the Quote-to-Delivery
report for delivery and hours, the Finance ledger for revenue, collections and receivables, Control
Tower and Phase 7 for risk and forecasts. No profitability is calculated: ProTrack has no reliable
cost data per customer, and revenue alone says nothing about profit.

Observed signals (growth, decline, recurring changes, delays, overruns, late payment) state their
evidence and minimum sample; forecasts are listed separately and labelled as forecasts.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ExecutionStatus, PostCompletionWorkType
from app.models.finance import Quote
from app.models.intelligence import EngineeringChange
from app.models.models import Contact, Customer, Project, TimesheetEntry
from app.services.actual_hours import official_entry_clause
from app.services.management.access import ManagementAccess, ManagementForbidden
from app.services.management.business import QuoteLedger, load_ledgers, payment_lead_times
from app.services.management.filters import (
    CockpitFilters,
    Period,
    fy_period,
    project_conditions,
    quote_statement,
)
from app.services.management.metrics import ACTUAL, FORECAST, metric, number, pct
from app.services.management.operations import qtd_reports
from app.services.predictive import read as predictions
from app.services.reporting.periods import financial_year_start

ZERO = Decimal("0")
OPEN = (ExecutionStatus.planning, ExecutionStatus.currently_being_worked_on, ExecutionStatus.on_hold)
TREND_CHANGE = 0.2
MIN_DELAYS = 2
MIN_OVERRUN_SAMPLE = 3
MIN_CHANGES = 2
MIN_LATE_PAYMENTS = 2
HISTORY_YEARS = 5


@dataclass
class DeliveryStats:
    completed: int = 0
    evaluable: int = 0
    on_time: int = 0
    late: int = 0
    variance_days: float = 0.0
    comparable: int = 0
    over: int = 0
    estimate: Decimal = ZERO
    actual: Decimal = ZERO
    quoted: Decimal = ZERO
    quoted_actual: Decimal = ZERO
    quoted_projects: int = 0

    def add(self, row) -> None:
        self.completed += 1
        if row.delivery_variance_days is not None:
            self.evaluable += 1
            self.variance_days += row.delivery_variance_days
            if row.delivery_variance_days <= 0:
                self.on_time += 1
            else:
                self.late += 1
        if row.comparable:
            self.comparable += 1
            self.estimate += row.current_estimate_hours or ZERO
            self.actual += row.actual_hours or ZERO
            if (row.actual_hours or ZERO) > (row.current_estimate_hours or ZERO):
                self.over += 1
        if row.quoted_hours and row.actual_hours is not None:
            self.quoted_projects += 1
            self.quoted += row.quoted_hours
            self.quoted_actual += row.actual_hours

    def read(self) -> dict:
        return {
            "completed_projects": self.completed,
            "delivery_evaluable": self.evaluable,
            "on_time": self.on_time,
            "late": self.late,
            "on_time_rate": pct(self.on_time, self.evaluable),
            "average_variance_days": round(self.variance_days / self.evaluable, 1) if self.evaluable else None,
            "comparable_projects": self.comparable,
            "projects_over_estimate": self.over,
            "approved_estimate_hours": number(self.estimate) if self.comparable else None,
            "actual_hours": number(self.actual) if self.comparable else None,
            "hour_variance_percent": pct(self.actual - self.estimate, self.estimate) if self.comparable else None,
            "quoted_vs_actual": {
                "projects": self.quoted_projects,
                "quoted_hours": number(self.quoted) if self.quoted_projects else None,
                "actual_hours": number(self.quoted_actual) if self.quoted_projects else None,
                "variance_percent": pct(self.quoted_actual - self.quoted, self.quoted) if self.quoted_projects else None,
            },
        }


def _customer_of(db: Session, project_ids: list[UUID]) -> dict[UUID, UUID]:
    if not project_ids:
        return {}
    return dict(db.execute(select(Project.id, Project.customer_id).where(Project.id.in_(project_ids))).all())


def visible_customer_ids(db: Session, access: ManagementAccess, filters: CockpitFilters) -> set[UUID]:
    ids = set(db.scalars(select(Project.customer_id).where(*project_conditions(db, filters, access))).all())
    if access.finance:
        ids |= set(db.scalars(quote_statement(db, filters, access).with_only_columns(Quote.customer_id)).all())
    return ids


def _ledger_totals(ledgers: list[QuoteLedger], period: Period) -> dict[UUID, dict]:
    out: dict[UUID, dict] = defaultdict(lambda: {"invoiced": ZERO, "collected": ZERO, "awarded": ZERO,
                                                "outstanding": ZERO, "previous_invoiced": ZERO})
    previous = period.previous()
    for item in ledgers:
        row = out[item.quote.customer_id]
        row["outstanding"] += item.outstanding
        row["invoiced"] += sum((a for d, a in item.invoices if period.start <= d <= period.end), ZERO)
        row["previous_invoiced"] += sum((a for d, a in item.invoices if previous.start <= d <= previous.end), ZERO)
        row["collected"] += sum((a for d, a in item.payments if period.start <= d <= period.end), ZERO)
        if item.awarded_on and period.start <= item.awarded_on <= period.end:
            row["awarded"] += item.awarded
    return out


def build_customer_table(db: Session, access: ManagementAccess, filters: CockpitFilters, today: date | None = None,
                         reports=None) -> dict:
    today = today or date.today()
    completed, active = reports or qtd_reports(db, access, filters, today)
    owners = _customer_of(db, [r.project_id for r in completed.projects.items + active.projects.items])
    delivery: dict[UUID, DeliveryStats] = defaultdict(DeliveryStats)
    for row in completed.projects.items:
        delivery[owners[row.project_id]].add(row)
    active_count = Counter(owners[r.project_id] for r in active.projects.items)
    totals = dict(
        db.execute(select(Project.customer_id, func.count()).where(*project_conditions(db, filters, access))
                   .group_by(Project.customer_id)).all()
    )
    money = _ledger_totals(load_ledgers(db, quote_statement(db, filters, access)), filters.period) if access.finance else {}
    ids = visible_customer_ids(db, access, filters)
    names = {c.id: c.name for c in db.scalars(select(Customer).where(Customer.id.in_(ids))).all()} if ids else {}
    rows = []
    for cid in ids:
        d = delivery[cid].read()
        row = {
            "customer_id": str(cid), "customer": names.get(cid, "Unknown customer"),
            "projects": int(totals.get(cid, 0)), "active_projects": active_count.get(cid, 0),
            "completed_in_period": d["completed_projects"], "on_time_rate": d["on_time_rate"],
            "delivery_evaluable": d["delivery_evaluable"], "hour_variance_percent": d["hour_variance_percent"],
            "comparable_projects": d["comparable_projects"],
        }
        if access.finance:
            m = money.get(cid)
            row.update({
                "invoiced": number(m["invoiced"]) if m else 0, "awarded": number(m["awarded"]) if m else 0,
                "collected": number(m["collected"]) if m else 0, "outstanding": number(m["outstanding"]) if m else 0,
                "previous_period_invoiced": number(m["previous_invoiced"]) if m else 0,
                "revenue_trend_percent": pct(m["invoiced"] - m["previous_invoiced"], m["previous_invoiced"])
                if m and m["previous_invoiced"] > 0 else None,
            })
        rows.append(row)
    rows.sort(key=lambda r: (-(r.get("invoiced") or 0), -r["projects"], r["customer"].lower()))
    return {
        "rows": rows,
        "finance_visible": access.finance,
        "previous_period": filters.period.previous().as_dict(),
        "notes": [
            "On-time and hour variance cover projects completed in the period with an original baseline or a "
            "comparable approved estimate; blank means there is no reliable sample.",
            "Revenue trend compares invoiced revenue with the period of equal length immediately before.",
            "No customer profitability is shown: ProTrack has no reliable cost data per customer.",
        ],
    }


def _signal(code: str, label: str, evidence: str, sample: int) -> dict:
    return {"code": code, "label": label, "evidence": evidence, "sample": sample, "kind": ACTUAL, "observed": True}


def build_customer_profile(db: Session, access: ManagementAccess, filters: CockpitFilters, customer_id: UUID,
                           today: date | None = None) -> dict:
    today = today or date.today()
    if customer_id not in visible_customer_ids(db, access, CockpitFilters(filters.period)):
        raise ManagementForbidden("Customer not found or outside your scope")
    customer = db.get(Customer, customer_id)
    scoped = CockpitFilters(filters.period, customer_id, filters.classification, filters.manager_id,
                            filters.team_id, filters.business_unit, {**filters.labels, "customer": customer.name})
    fy_month = filters.period.fy_start_month
    current_fy = financial_year_start(today, fy_month).year
    history = Period(fy_period(current_fy - HISTORY_YEARS + 1, fy_month).start, today, "History", fy_month)
    hist_completed, active = qtd_reports(db, access, scoped.with_period(history), today)
    period_rows = [r for r in hist_completed.projects.items
                   if r.actual_completion_date and filters.period.start <= r.actual_completion_date <= filters.period.end]

    period_stats, all_stats = DeliveryStats(), DeliveryStats()
    by_fy: dict[int, DeliveryStats] = defaultdict(DeliveryStats)
    for row in hist_completed.projects.items:
        all_stats.add(row)
        by_fy[financial_year_start(row.actual_completion_date, fy_month).year].add(row)
    for row in period_rows:
        period_stats.add(row)

    projects = list(db.scalars(select(Project).where(*project_conditions(db, scoped, access))).all())
    status_counts = Counter(p.execution_status.value if p.execution_status else "unknown" for p in projects)
    classes = Counter(p.project_classification.value if p.project_classification else "unclassified" for p in projects)
    project_ids = [p.id for p in projects]
    contacts = db.scalars(select(Contact).where(Contact.customer_id == customer_id)
                          .order_by(Contact.is_primary.desc(), Contact.last_name)).all()

    signals, not_assessable = [], []
    late = [r for r in hist_completed.projects.items if r.delivery_variance_days is not None and r.delivery_variance_days > 0]
    if len(late) >= MIN_DELAYS:
        signals.append(_signal("repeated_delays", "Repeated project delays",
                               f"{len(late)} of {all_stats.evaluable} completed projects with an original baseline "
                               "were delivered after it.", all_stats.evaluable))
    elif all_stats.evaluable < MIN_DELAYS:
        not_assessable.append({"code": "repeated_delays", "reason": "Fewer than two completed projects have an original baseline."})
    if all_stats.comparable >= MIN_OVERRUN_SAMPLE and all_stats.over / all_stats.comparable >= 0.5:
        signals.append(_signal("estimate_overruns", "Frequent estimate overruns",
                               f"{all_stats.over} of {all_stats.comparable} comparable completed projects used more "
                               "approved hours than estimated.", all_stats.comparable))
    elif all_stats.comparable < MIN_OVERRUN_SAMPLE:
        not_assessable.append({"code": "estimate_overruns",
                               "reason": f"Fewer than {MIN_OVERRUN_SAMPLE} completed projects have an approved estimate and actual hours."})
    changes = db.scalar(select(func.count()).select_from(EngineeringChange)
                        .where(EngineeringChange.project_id.in_(project_ids))) if project_ids else 0
    change_projects = db.scalar(
        select(func.count(func.distinct(TimesheetEntry.project_id))).where(
            TimesheetEntry.project_id.in_(project_ids), official_entry_clause(),
            TimesheetEntry.post_completion_type == PostCompletionWorkType.customer_change)
    ) if project_ids else 0
    if (changes or 0) >= MIN_CHANGES or (change_projects or 0) >= MIN_CHANGES:
        signals.append(_signal("recurring_changes", "Recurring engineering changes",
                               f"{changes or 0} engineering change record(s); approved customer-change hours on "
                               f"{change_projects or 0} project(s).", len(project_ids)))

    finance = None
    if access.finance:
        ledgers = load_ledgers(db, select(Quote).where(Quote.is_active.is_(True), Quote.customer_id == customer_id))
        p = filters.period
        invoiced = lambda s, e: sum((a for item in ledgers for d, a in item.invoices if s <= d <= e), ZERO)  # noqa: E731
        leads_all = payment_lead_times(ledgers, date.min, today)
        leads_period = [x for x in payment_lead_times(ledgers, p.start, p.end)]
        late_paid = [x for x in leads_all if x[2] is not None and x[2] > 0]
        last12, prev12 = invoiced(today - timedelta(days=365), today), invoiced(today - timedelta(days=730), today - timedelta(days=366))
        finance = {
            "currency": "INR",
            "kpis": [
                metric("awarded_value", sum((i.awarded for i in ledgers if i.awarded_on and p.start <= i.awarded_on <= p.end), ZERO) if ledgers else None),
                metric("invoiced_revenue", invoiced(p.start, p.end) if ledgers else None),
                metric("collections", sum((a for i in ledgers for d, a in i.payments if p.start <= d <= p.end), ZERO) if ledgers else None),
                metric("outstanding_receivables", sum((i.outstanding for i in ledgers), ZERO) if ledgers else None,
                       note=f"As of {today:%d %b %Y}."),
                metric("payment_lead_days", sum(d for _, d, _ in leads_period) / len(leads_period) if leads_period else None,
                       sample=len(leads_period)),
            ],
            "all_time": {
                "awarded": number(sum((i.awarded for i in ledgers), ZERO)),
                "invoiced": number(invoiced(date.min, date.max)),
                "average_payment_lead_days": round(sum(d for _, d, _ in leads_all) / len(leads_all), 1) if leads_all else None,
                "lines_paid": len(leads_all), "lines_paid_late": len(late_paid),
            },
        }
        for item_fy in range(current_fy - HISTORY_YEARS + 1, current_fy + 1):
            window = fy_period(item_fy, fy_month)
            by_fy[item_fy]  # ensure row exists
            finance.setdefault("fy_invoiced", {})[item_fy] = number(invoiced(window.start, min(window.end, today)))
        if len(late_paid) >= MIN_LATE_PAYMENTS:
            signals.append(_signal("delayed_payments", "Delayed payments",
                                   f"{len(late_paid)} of {len(leads_all)} fully paid invoice lines were paid after their due "
                                   f"date (average {round(sum(x[2] for x in late_paid) / len(late_paid), 1)} days late).",
                                   len(leads_all)))
        if prev12 > 0 and last12 >= prev12 * Decimal(str(1 + TREND_CHANGE)):
            signals.append(_signal("growing", "Growing customer",
                                   f"Invoiced revenue in the last 12 months is {pct(last12 - prev12, prev12)}% above the 12 months before.", 2))
        elif prev12 > 0 and last12 <= prev12 * Decimal(str(1 - TREND_CHANGE)):
            signals.append(_signal("declining", "Declining customer activity",
                                   f"Invoiced revenue in the last 12 months is {pct(prev12 - last12, prev12)}% below the 12 months before.", 2))
        elif prev12 <= 0:
            not_assessable.append({"code": "revenue_trend", "reason": "No invoiced revenue in the 12 months before the last 12."})
    else:
        not_assessable.append({"code": "finance_signals", "reason": "Revenue and payment signals need Finance view access."})

    scope = predictions.PredictionScope(visibility_clause=access.visibility_clause, can_view_capacity=access.capacity,
                                        capacity_team_ids=None, finance_visible=access.finance)
    forecasts = [p for pid in project_ids for p in predictions.latest(db, scope, project_id=pid, status="predicted")]
    trend = [
        {"fy_start_year": fy, "label": fy_period(fy, fy_month).label, **by_fy[fy].read(),
         "invoiced": (finance or {}).get("fy_invoiced", {}).get(fy) if finance else None}
        for fy in sorted(set(by_fy) | set(range(current_fy - HISTORY_YEARS + 1, current_fy + 1)))
    ]
    return {
        "customer": {"id": str(customer.id), "name": customer.name, "code": customer.code, "country": customer.country,
                     "city": customer.city, "is_active": customer.is_active},
        "contacts": [{"name": f"{c.first_name or ''} {c.last_name or ''}".strip(), "job_title": c.job_title,
                      "email": c.email, "phone": c.phone, "is_primary": bool(c.is_primary)} for c in contacts],
        "projects": {
            "total": len(projects), "by_status": dict(status_counts), "by_classification": dict(classes),
            "active": [{"project_id": str(r.project_id), "code": r.code, "tool_number": r.tool_number,
                        "part_description": r.part_description, "status": r.execution_status,
                        "current_target_date": r.current_target_date, "actual_hours": r.actual_hours,
                        "current_estimate_hours": r.current_estimate_hours, "delivery_status": r.delivery_status}
                       for r in active.projects.items],
            "completed_in_period": [{"project_id": str(r.project_id), "code": r.code, "tool_number": r.tool_number,
                                     "part_description": r.part_description,
                                     "actual_completion_date": r.actual_completion_date,
                                     "delivery_variance_days": r.delivery_variance_days, "actual_hours": r.actual_hours,
                                     "current_estimate_hours": r.current_estimate_hours, "quoted_hours": r.quoted_hours}
                                    for r in period_rows],
        },
        "delivery": {"period": period_stats.read(), "history": all_stats.read()},
        "finance": finance,
        "finance_visible": access.finance,
        "trend": trend,
        "signals": signals,
        "not_assessable": not_assessable,
        "forecasts": {
            "kind": FORECAST,
            "items": [{"prediction_type": p.prediction_type, "subject": p.subject_label, "project_id": str(p.project_id),
                       "predicted_value": number(p.predicted_value), "predicted_date": p.predicted_date,
                       "unit": p.unit, "baseline_label": p.baseline_label, "baseline_value": number(p.baseline_value),
                       "baseline_date": p.baseline_date, "as_of": p.as_of.isoformat()} for p in forecasts[:20]],
            "note": "Phase 7 forecasts for this customer's projects. Forecasts are not results.",
        },
        "period": filters.period.as_dict(),
        "history_window": history.as_dict(),
        "notes": [
            "Signals are observed history and state their evidence; forecasts are listed separately.",
            "No profitability is shown: revenue without reliable cost data says nothing about profit.",
        ],
    }
