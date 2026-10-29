"""Initial source-of-truth schema.

Revision ID: 20261027_0001
Revises:
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from alembic import op

from rag_app.persistence.schema import Base

revision: str = "20261027_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
