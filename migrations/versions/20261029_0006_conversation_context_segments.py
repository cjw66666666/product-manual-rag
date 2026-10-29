"""Add conversation product context segments.

Revision ID: 20261029_0006
Revises: 20261029_0005
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0006"
down_revision: str | None = "20261029_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"]
        for column in inspector.get_columns("conversations")
    }
    if "context_start_sequence" not in columns:
        op.add_column(
            "conversations",
            sa.Column(
                "context_start_sequence",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"]
        for column in inspector.get_columns("conversations")
    }
    if "context_start_sequence" in columns:
        op.drop_column("conversations", "context_start_sequence")
