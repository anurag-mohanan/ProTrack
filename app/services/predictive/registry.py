"""Prediction types, their model versions and the per-type settings rows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.prediction import (
    MODEL_ACTIVE,
    MODEL_CANDIDATE,
    PredictionModelVersion,
    PredictionSetting,
)


@dataclass(frozen=True)
class ModelSpec:
    version: str
    description: str


@dataclass(frozen=True)
class TypeSpec:
    key: str
    label: str
    # projects | resources | finance: decides which permission guards the output
    module: str
    unit: str
    description: str
    versions: tuple[ModelSpec, ...]


TYPES: dict[str, TypeSpec] = {
    spec.key: spec
    for spec in (
        TypeSpec(
            key="project_delivery",
            label="Project completion date",
            module="projects",
            unit="days",
            description="Expected completion date of an open project and its variance against the current target.",
            versions=(
                ModelSpec(
                    "delivery-1",
                    "Comparable completed projects of the same type: calendar days per approved original estimate hour, "
                    "conditioned on the project not having finished yet; a capacity check on the designer can only move "
                    "the date later.",
                ),
            ),
        ),
        TypeSpec(
            key="project_final_hours",
            label="Final engineering hours",
            module="projects",
            unit="hours",
            description="Expected final actual hours of an open project against its approved estimate.",
            versions=(
                ModelSpec(
                    "hours-1",
                    "Comparable completed projects of the same type: actual ÷ approved original estimate, applied to "
                    "this project's original estimate and conditioned on the hours already recorded.",
                ),
            ),
        ),
        TypeSpec(
            key="milestone_delay",
            label="Milestone finish date",
            module="projects",
            unit="days",
            description="Expected finish of open milestones with a plan, respecting recorded dependencies only.",
            versions=(
                ModelSpec(
                    "milestone-1",
                    "Comparable completed milestones of the same template milestone (else stage): actual ÷ planned "
                    "duration, conditioned on elapsed time; a start waits for predecessors predicted to finish later.",
                ),
            ),
        ),
        TypeSpec(
            key="resource_demand",
            label="Engineering workload",
            module="resources",
            unit="hours",
            description="Expected project workload against allocatable capacity per team over 2, 4, 8 and 12 weeks.",
            versions=(
                ModelSpec(
                    "demand-1",
                    "Remaining hours (predicted final − actual, else approved remaining) spread evenly over the assigned "
                    "designer's working days until the project's end date; capacity from the Phase 3 daily rule minus "
                    "the historical non-project share.",
                ),
            ),
        ),
        TypeSpec(
            key="finance_billing",
            label="Billing per month",
            module="finance",
            unit="amount",
            description="Expected invoicing per month and currency.",
            versions=(
                ModelSpec(
                    "billing-1",
                    "Phase 3 billing items; completion-triggered items dated by actual or predicted completion plus the "
                    "historical invoicing lag when there is enough history.",
                ),
            ),
        ),
        TypeSpec(
            key="finance_collections",
            label="Collections per month",
            module="finance",
            unit="amount",
            description="Expected cash collected per month and currency.",
            versions=(
                ModelSpec(
                    "collections-1",
                    "Phase 3 outstanding invoice lines, moved from the contractual due date by the customer's (else the "
                    "company's) median payment delay when there is enough paid history.",
                ),
            ),
        ),
    )
}

# Extra versions registered at runtime (tests, or a new method being trialled in shadow).
_EXTRA_VERSIONS: dict[str, list[ModelSpec]] = {}


def register_version(prediction_type: str, spec: ModelSpec) -> None:
    _EXTRA_VERSIONS.setdefault(prediction_type, []).append(spec)


def unregister_versions() -> None:
    _EXTRA_VERSIONS.clear()


def versions(prediction_type: str) -> list[ModelSpec]:
    return [*TYPES[prediction_type].versions, *_EXTRA_VERSIONS.get(prediction_type, [])]


def sync(db: Session) -> dict[str, PredictionSetting]:
    """Make sure every type has a settings row and every code version a lifecycle row.

    The first version of a type becomes active; any later version starts as a candidate and only
    runs in shadow until an administrator activates it.
    """
    now = datetime.utcnow()
    settings = {s.prediction_type: s for s in db.scalars(select(PredictionSetting)).all()}
    known = {(v.prediction_type, v.version): v for v in db.scalars(select(PredictionModelVersion)).all()}
    for key in TYPES:
        setting = settings.get(key)
        if setting is None:
            setting = PredictionSetting(prediction_type=key, is_enabled=True)
            db.add(setting)
            settings[key] = setting
        for spec in versions(key):
            if (key, spec.version) in known:
                continue
            first = setting.active_version is None
            row = PredictionModelVersion(
                prediction_type=key,
                version=spec.version,
                status=MODEL_ACTIVE if first else MODEL_CANDIDATE,
                description=spec.description,
                registered_at=now,
                activated_at=now if first else None,
                activation_note="First version of this prediction type." if first else None,
            )
            db.add(row)
            known[(key, spec.version)] = row
            if first:
                setting.active_version = spec.version
    db.flush()
    return settings
