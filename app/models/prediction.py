"""Predictive engineering intelligence (phase 112): predictions, model versions, settings, scenarios.

Additive tables only. Predictions are never edited after they are written except to
record the actual outcome; each run adds new rows and marks the previous row for the
same subject as superseded, so the history of what was predicted, when and by which
model version is preserved. No table here owns business data.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Index

from app.db.base import (
    Base,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Mapped,
    Numeric,
    String,
    Text,
    Uuid,
    mapped_column,
)
from app.models.mixins import TenantMixin, TimestampMixin

PREDICTED = "predicted"
INSUFFICIENT = "insufficient_data"
PREDICTION_STATUSES = (PREDICTED, INSUFFICIENT)

OUTCOME_PENDING = "pending"
OUTCOME_EVALUATED = "evaluated"
OUTCOME_NOT_EVALUABLE = "not_evaluable"

MODEL_ACTIVE = "active"
MODEL_CANDIDATE = "candidate"
MODEL_RETIRED = "retired"

RUN_RUNNING = "running"
RUN_SUCCEEDED = "succeeded"
RUN_FAILED = "failed"


class PredictionSetting(Base, TimestampMixin, TenantMixin):
    """Per prediction type: enabled flag and the active model version."""

    __tablename__ = "prediction_settings"
    __table_args__ = (Index("uq_prediction_settings_type", "tenant_id", "prediction_type", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prediction_type: Mapped[str] = mapped_column(String(40), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active_version: Mapped[Optional[str]] = mapped_column(String(30))
    disabled_reason: Mapped[Optional[str]] = mapped_column(String(500))
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))


class PredictionModelVersion(Base, TimestampMixin, TenantMixin):
    """Version history of each prediction method. Code defines methods; this records their lifecycle."""

    __tablename__ = "prediction_model_versions"
    __table_args__ = (
        Index("uq_prediction_model_versions_type_version", "tenant_id", "prediction_type", "version", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prediction_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    # active | candidate | retired
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=MODEL_CANDIDATE)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    activated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    activation_note: Mapped[Optional[str]] = mapped_column(Text)
    retired_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class PredictionRun(Base, TimestampMixin, TenantMixin):
    __tablename__ = "prediction_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # manual | job
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    triggered_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RUN_RUNNING, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # JSON {type: {"predicted": n, "insufficient_data": n, "evaluated": n}}
    counts_json: Mapped[Optional[str]] = mapped_column(Text)
    error: Mapped[Optional[str]] = mapped_column(Text)


class Prediction(Base, TimestampMixin, TenantMixin):
    """One prediction for one subject at one as-of date by one model version."""

    __tablename__ = "predictions"
    __table_args__ = (
        Index("ix_predictions_latest", "prediction_type", "subject_key", "is_latest"),
        Index("ix_predictions_outcome", "prediction_type", "outcome_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("prediction_runs.id", ondelete="SET NULL"), index=True
    )
    prediction_type: Mapped[str] = mapped_column(String(40), nullable=False)
    model_version: Mapped[str] = mapped_column(String(30), nullable=False)
    # Candidate versions run in shadow: stored and evaluated, never shown or alerted on.
    is_shadow: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # project | milestone | team | person | currency_period
    subject_type: Mapped[str] = mapped_column(String(30), nullable=False)
    subject_key: Mapped[str] = mapped_column(String(200), nullable=False)
    subject_label: Mapped[str] = mapped_column(String(300), nullable=False)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    milestone_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("milestones.id", ondelete="SET NULL")
    )
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL"))
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL")
    )
    currency: Mapped[Optional[str]] = mapped_column(String(10))
    as_of: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    horizon_start: Mapped[Optional[date]] = mapped_column(Date)
    horizon_end: Mapped[Optional[date]] = mapped_column(Date)
    # predicted | insufficient_data
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    # hours | days | amount
    unit: Mapped[Optional[str]] = mapped_column(String(20))
    predicted_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    predicted_date: Mapped[Optional[date]] = mapped_column(Date)
    lower_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    upper_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    lower_date: Mapped[Optional[date]] = mapped_column(Date)
    upper_date: Mapped[Optional[date]] = mapped_column(Date)
    range_basis: Mapped[Optional[str]] = mapped_column(String(200))
    # Only set when the model's probabilities have been shown to be calibrated.
    probability: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4))
    # Share of comparable history with the event; always available when computed, never called a probability.
    observed_frequency: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4))
    # The value the prediction is compared with (committed date, approved hours, contractual amount).
    baseline_label: Mapped[Optional[str]] = mapped_column(String(100))
    baseline_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    baseline_date: Mapped[Optional[date]] = mapped_column(Date)
    variance_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comparison_group: Mapped[Optional[str]] = mapped_column(String(300))
    factors_json: Mapped[Optional[str]] = mapped_column(Text)
    data_used_json: Mapped[Optional[str]] = mapped_column(Text)
    warnings_json: Mapped[Optional[str]] = mapped_column(Text)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    superseded_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # False for an earlier prediction replaced by a rerun on the same as-of date.
    counts_for_accuracy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # pending | evaluated | not_evaluable
    outcome_status: Mapped[str] = mapped_column(String(20), nullable=False, default=OUTCOME_PENDING)
    actual_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    actual_date: Mapped[Optional[date]] = mapped_column(Date)
    error_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    abs_error: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    pct_error: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    naive_abs_error: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    event_occurred: Mapped[Optional[bool]] = mapped_column(Boolean)
    horizon_days: Mapped[Optional[int]] = mapped_column(Integer)
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    outcome_note: Mapped[Optional[str]] = mapped_column(String(500))


class PredictionScenario(Base, TimestampMixin, TenantMixin):
    """A hypothetical what-if. Stored for comparison only; never applied to project records."""

    __tablename__ = "prediction_scenarios"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    assumptions_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    model_versions_json: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
