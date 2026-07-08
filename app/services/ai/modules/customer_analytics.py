"""Customer intelligence analytics."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.models.enums import ExecutionStatus
from app.models.intelligence import EngineeringChange
from app.models.models import Customer, Project
from app.schemas.ai import CustomerIntelligence
from app.services.ai.base import AiContext, AiModule, round_hours
from app.services.ai.scoring import scorer


class CustomerAnalyticsModule(AiModule):
    name = "customer_analytics"

    def run(self, ctx: AiContext, **kwargs: Any) -> list[CustomerIntelligence] | CustomerIntelligence:
        customer_id = kwargs.get("customer_id")
        customers = (
            [ctx.db.get(Customer, UUID(str(customer_id)))]
            if customer_id
            else list(ctx.db.scalars(select(Customer).where(Customer.is_active.is_(True))).all())
        )

        results: list[CustomerIntelligence] = []
        for customer in customers:
            if customer is None:
                continue
            projects = list(
                ctx.db.scalars(
                    select(Project).where(
                        Project.customer_id == customer.id,
                        Project.is_deleted.is_(False),
                    )
                ).all()
            )
            completed = [p for p in projects if p.execution_status == ExecutionStatus.completed]
            active = [
                p
                for p in projects
                if p.execution_status
                in (
                    ExecutionStatus.planning,
                    ExecutionStatus.currently_being_worked_on,
                    ExecutionStatus.on_hold,
                )
            ]

            avg_hours = (
                sum(float(p.actual_hours or 0) for p in completed) / len(completed)
                if completed
                else 0
            )
            variances = []
            on_time = 0
            for p in completed:
                if p.due_date and p.completed_at:
                    completed_date = p.completed_at.date()
                    delta = (completed_date - p.due_date).days
                    variances.append(delta)
                    if delta <= 0:
                        on_time += 1
            avg_variance = sum(variances) / len(variances) if variances else 0
            on_time_pct = (on_time / len(completed) * 100) if completed else 80

            ec_count = int(
                ctx.db.scalar(
                    select(func.count())
                    .select_from(EngineeringChange)
                    .join(Project, EngineeringChange.project_id == Project.id)
                    .where(Project.customer_id == customer.id)
                )
                or 0
            )

            workload = sum(float(p.actual_hours or 0) for p in active)
            score = scorer.customer_score(
                on_time_percent=on_time_pct,
                change_count=ec_count,
                schedule_variance=avg_variance,
                workload_hours=workload,
            )

            results.append(
                CustomerIntelligence(
                    customer_id=customer.id,
                    customer_name=customer.name,
                    average_project_hours=round_hours(avg_hours),
                    average_schedule_variance_days=round(avg_variance, 1),
                    engineering_change_count=ec_count,
                    on_time_delivery_percent=round(on_time_pct, 1),
                    active_workload_hours=round_hours(workload),
                    active_project_count=len(active),
                    customer_score=score,
                    trend="improving" if on_time_pct >= 85 else "stable" if on_time_pct >= 70 else "declining",
                )
            )

        if customer_id:
            return results[0] if results else CustomerIntelligence(
                customer_id=UUID(str(customer_id)),
                customer_name="Unknown",
            )
        return sorted(results, key=lambda r: r.active_workload_hours, reverse=True)
