"""R10 M1c — ORM query-time tenant isolation.

Applies SELECT loader criteria for TenantMixin (+ FeatureFlag). Opt out via
``without_tenant_filter()`` or ``execution_options(skip_tenant_filter=True)``.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator
from uuid import UUID

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session, with_loader_criteria

from app.core.request_context import get_tenant_id
from app.models.commercial import PROSOHM_TENANT_ID

_skip_tenant_filter: ContextVar[bool] = ContextVar(
    "protrack_skip_tenant_filter", default=False
)
_registered = False

SKIP_TENANT_FILTER = "skip_tenant_filter"


def resolve_effective_tenant_id() -> UUID:
    """Request tenant, or Prosohm when unbound (jobs / startup / tests)."""
    return get_tenant_id() or PROSOHM_TENANT_ID


@contextmanager
def without_tenant_filter() -> Iterator[None]:
    """Disable automatic tenant filtering in this context (seeds, rare admin)."""
    token = _skip_tenant_filter.set(True)
    try:
        yield
    finally:
        _skip_tenant_filter.reset(token)


def tenant_filter_skipped() -> bool:
    return bool(_skip_tenant_filter.get())


def _should_apply(execute_state) -> bool:
    if tenant_filter_skipped():
        return False
    if execute_state.execution_options.get(SKIP_TENANT_FILTER, False):
        return False
    if not execute_state.is_select:
        return False
    if execute_state.is_column_load:
        return False
    if execute_state.is_relationship_load:
        return False
    return True


def _apply_loader_criteria(execute_state, tenant_id: UUID) -> None:
    from app.models.commercial import FeatureFlag
    from app.models.mixins import TenantMixin

    # Closure variable (not a default-arg) so AnalyzedCode rebinds per execute.
    # Do not call functions inside the lambda — SQLAlchemy extracts bound values
    # from closure cells; a default-arg bake-in gets cached as Prosohm forever.
    tid = tenant_id

    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantMixin,
            lambda cls: cls.tenant_id == tid,
            include_aliases=True,
        ),
        with_loader_criteria(
            FeatureFlag,
            lambda cls: cls.tenant_id == tid,
            include_aliases=True,
        ),
    )


def _on_do_orm_execute(execute_state) -> None:
    if not _should_apply(execute_state):
        return
    _apply_loader_criteria(execute_state, resolve_effective_tenant_id())


def _on_before_flush(session: Session, _flush_context, _instances) -> None:
    if tenant_filter_skipped():
        return
    tid = resolve_effective_tenant_id()
    for obj in list(session.new) + list(session.dirty):
        state = inspect(obj)
        if state.transient or state.deleted:
            continue
        mapper = state.mapper
        if mapper is None or "tenant_id" not in mapper.columns:
            continue
        # Tenant registry rows are global.
        if mapper.class_.__name__ == "Tenant":
            continue
        obj_tid = getattr(obj, "tenant_id", None)
        if obj_tid is None:
            continue
        if obj_tid != tid:
            raise ValueError(
                f"{mapper.class_.__name__}.tenant_id={obj_tid} does not match "
                f"effective tenant {tid} (use without_tenant_filter() to opt out)"
            )


def register_tenant_filter() -> None:
    """Idempotent Session event registration."""
    global _registered
    if _registered:
        return
    event.listen(Session, "do_orm_execute", _on_do_orm_execute)
    event.listen(Session, "before_flush", _on_before_flush)
    _registered = True
