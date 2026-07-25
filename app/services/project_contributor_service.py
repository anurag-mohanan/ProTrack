"""Project contributor aggregation for timesheets and reports."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ContributionReason
from app.models.models import Project, Timesheet, TimesheetEntry, User
from app.schemas.timesheet import ContributorReasonHours, ProjectContributorSummary

CONTRIBUTION_REASON_LABELS: dict[ContributionReason, str] = {
    ContributionReason.assisting_designer: "Assisting Designer",
    ContributionReason.peer_review: "Peer Review",
    ContributionReason.design_support: "Design Support",
    ContributionReason.surfacing_support: "Surfacing Support",
    ContributionReason.engineering_change: "Engineering Change",
    ContributionReason.customer_request: "Customer Request",
    ContributionReason.training_mentoring: "Training / Mentoring",
    ContributionReason.rework_quality: "Rework / quality issue (non-billable)",
    ContributionReason.other: "Other",
}

SUPPORT_REASONS = frozenset(
    {
        ContributionReason.assisting_designer,
        ContributionReason.design_support,
        ContributionReason.surfacing_support,
    }
)


def _round_hours(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_percent(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _reason_label(reason: ContributionReason | None, is_owner: bool) -> str:
    if reason is not None:
        return CONTRIBUTION_REASON_LABELS.get(reason, reason.value)
    if is_owner:
        return "Project Owner"
    return "Unspecified"


def get_project_contributors(db: Session, project_id: UUID) -> list[ProjectContributorSummary]:
    project = db.get(Project, project_id)
    if project is None:
        return []

    owner_ids = {uid for uid in (project.designer_id, project.surfacer_id) if uid is not None}

    hour_rows = db.execute(
        select(
            User.id,
            User.first_name,
            User.last_name,
            TimesheetEntry.contribution_reason,
            func.coalesce(func.sum(TimesheetEntry.hours), 0),
        )
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .join(User, Timesheet.user_id == User.id)
        .where(
            TimesheetEntry.project_id == project_id,
            TimesheetEntry.is_deleted.is_(False),
        )
        .group_by(
            User.id,
            User.first_name,
            User.last_name,
            TimesheetEntry.contribution_reason,
        )
    ).all()

    by_user: dict[UUID, dict] = {}
    for user_id, first_name, last_name, reason, hours in hour_rows:
        total = _round_hours(Decimal(str(hours or 0)))
        if total <= 0:
            continue
        bucket = by_user.setdefault(
            user_id,
            {
                "name": f"{first_name} {last_name}".strip(),
                "reason_hours": defaultdict(lambda: Decimal("0")),
                "total": Decimal("0"),
            },
        )
        bucket["total"] += total
        bucket["reason_hours"][reason] += total

    if not by_user:
        return []

    project_total = sum(row["total"] for row in by_user.values())

    contributors: list[ProjectContributorSummary] = []
    for user_id, data in sorted(by_user.items(), key=lambda item: item[1]["total"], reverse=True):
        total = _round_hours(data["total"])
        is_owner = user_id in owner_ids
        role_label = "Contributor"
        if user_id == project.designer_id:
            role_label = "Assigned Designer"
        elif user_id == project.surfacer_id:
            role_label = "Assigned Surfacer"

        reason_breakdown: list[ContributorReasonHours] = []
        for reason, hours in sorted(
            data["reason_hours"].items(),
            key=lambda item: item[1],
            reverse=True,
        ):
            rounded = _round_hours(hours)
            if rounded <= 0:
                continue
            reason_breakdown.append(
                ContributorReasonHours(
                    reason_key=reason,
                    reason_label=_reason_label(reason, is_owner and reason is None),
                    hours=rounded,
                )
            )

        if is_owner:
            primary_label = "Project Owner"
            explicit = [item for item in reason_breakdown if item.reason_key is not None]
            if explicit:
                primary_label = explicit[0].reason_label
        else:
            primary_label = reason_breakdown[0].reason_label if reason_breakdown else "Contributor"

        percent = (
            _round_percent((total / project_total) * Decimal("100"))
            if project_total > 0
            else Decimal("0")
        )

        contributors.append(
            ProjectContributorSummary(
                user_id=user_id,
                user_name=data["name"],
                role_label=role_label,
                is_project_owner=is_owner,
                total_hours=total,
                hours_percent=percent,
                primary_contribution_label=primary_label,
                contribution_reasons=reason_breakdown,
            )
        )
    return contributors


def get_project_contributors_map(
    db: Session, project_ids: list[UUID]
) -> dict[UUID, list[ProjectContributorSummary]]:
    if not project_ids:
        return {}
    return {project_id: get_project_contributors(db, project_id) for project_id in project_ids}


def aggregate_contribution_hours_by_reason(
    db: Session,
    project_id: UUID,
) -> dict[str, Decimal]:
    rows = db.execute(
        select(TimesheetEntry.contribution_reason, func.coalesce(func.sum(TimesheetEntry.hours), 0))
        .where(
            TimesheetEntry.project_id == project_id,
            TimesheetEntry.is_deleted.is_(False),
        )
        .group_by(TimesheetEntry.contribution_reason)
    ).all()

    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for reason, hours in rows:
        label = _reason_label(reason, False)
        totals[label] += _round_hours(Decimal(str(hours or 0)))
    return dict(totals)
