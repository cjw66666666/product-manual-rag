"""Add LLM-derived product name to ingestion items.

Revision ID: 20261029_0004
Revises: 20261028_0003
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0004"
down_revision: str | None = "20261028_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"]
        for column in inspector.get_columns("ingestion_items")
    }
    if "detected_product_name" not in columns:
        op.add_column(
            "ingestion_items",
            sa.Column("detected_product_name", sa.String(255), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"]
        for column in inspector.get_columns("ingestion_items")
    }
    if "detected_product_name" in columns:
        op.drop_column("ingestion_items", "detected_product_name")
