"""Alembic script template."""
from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str
down_revision: str | None
branch_labels: str | tuple[str, ...] | None
depends_on: str | tuple[str, ...] | None
