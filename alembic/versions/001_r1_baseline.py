"""R1 baseline — create ORM tables for greenfield installs.

Revision ID: 001_r1_baseline
Revises:
Create Date: 2026-07-24

Existing deployments should continue using phase sync. For greenfield Postgres:
  alembic upgrade head
then start the API so phase sync fills columns/indexes.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

import app.models  # noqa: F401
import app.models.finance  # noqa: F401
from app.db.base import Base

revision: str = "001_r1_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
