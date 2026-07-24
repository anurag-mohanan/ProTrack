"""Customer CRUD with optional name/code search."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, or_, select

from app.crud.base import CRUDBase
from app.models.models import Customer
from app.schemas.organization import CustomerCreate, CustomerUpdate


class CRUDCustomer(CRUDBase[Customer, CustomerCreate, CustomerUpdate]):
    def _apply_filters(
        self,
        stmt: Select[tuple[Customer]],
        filters: dict[str, Any] | None = None,
    ) -> Select[tuple[Customer]]:
        if not filters:
            return stmt
        search = filters.get("search")
        remaining = {k: v for k, v in filters.items() if k != "search" and v is not None}
        for field, value in remaining.items():
            if hasattr(self.model, field):
                stmt = stmt.where(getattr(self.model, field) == value)
        if isinstance(search, str) and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Customer.name.ilike(term),
                    Customer.code.ilike(term),
                )
            )
        return stmt

    def count_multi(
        self,
        db,
        *,
        filters: dict[str, Any] | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(self.model)
        stmt = self._apply_filters(stmt, filters)
        return int(db.scalar(stmt) or 0)


customer = CRUDCustomer(Customer)
