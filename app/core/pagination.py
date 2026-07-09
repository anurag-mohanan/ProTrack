"""Shared pagination helpers for list APIs."""

from __future__ import annotations

from math import ceil
from typing import Any, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field, computed_field

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 500
PAGE_SIZE_OPTIONS = (25, 50, 100)

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    pages: int = Field(ge=1)

    @classmethod
    def build(
        cls,
        *,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> PaginatedResponse[T]:
        pages = max(1, ceil(total / page_size)) if page_size else 1
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_records(self) -> int:
        return self.total

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_pages(self) -> int:
        return self.pages

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_previous(self) -> bool:
        return self.page > 1


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    sort: str | None = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)

    @classmethod
    def from_query(
        cls,
        *,
        page: int = 1,
        page_size: int | None = None,
        skip: int | None = None,
        limit: int | None = None,
        sort: str | None = None,
    ) -> PaginationParams:
        """Resolve page/page_size with backward-compatible skip/limit."""
        if skip is not None or limit is not None:
            resolved_skip = skip if skip is not None else 0
            resolved_limit = limit if limit is not None else DEFAULT_PAGE_SIZE
            resolved_page = (resolved_skip // resolved_limit) + 1 if resolved_limit else 1
            return cls(
                page=resolved_page,
                page_size=resolved_limit,
                sort=sort,
                skip=resolved_skip,
                limit=resolved_limit,
            )
        resolved_page_size = page_size if page_size is not None else DEFAULT_PAGE_SIZE
        resolved_skip = (page - 1) * resolved_page_size
        return cls(
            page=page,
            page_size=resolved_page_size,
            sort=sort,
            skip=resolved_skip,
            limit=resolved_page_size,
        )


def pagination_query(
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1, le=MAX_PAGE_SIZE),
    skip: int | None = Query(None, ge=0),
    limit: int | None = Query(None, ge=1, le=MAX_PAGE_SIZE),
    sort: str | None = Query(None),
) -> PaginationParams:
    return PaginationParams.from_query(
        page=page,
        page_size=page_size,
        skip=skip,
        limit=limit,
        sort=sort,
    )


def apply_sort(stmt: Any, model: type, sort: str | None) -> Any:
    """Apply optional sort field (prefix '-' for descending)."""
    if not sort:
        return stmt
    descending = sort.startswith("-")
    field_name = sort[1:] if descending else sort
    if not hasattr(model, field_name):
        return stmt
    column = getattr(model, field_name)
    return stmt.order_by(column.desc() if descending else column.asc())
