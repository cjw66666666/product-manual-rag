"""Add persisted sparse statistics.

Revision ID: 20261028_0003
Revises: 20261028_0002
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261028_0003"
down_revision: str | None = "20261028_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "sparse_index_statistics" in inspector.get_table_names():
        return
    op.create_table(
        "sparse_index_statistics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_version_id", sa.String(64), nullable=False),
        sa.Column("index_version_id", sa.String(64), nullable=False),
        sa.Column("statistics", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["index_version_id"],
            ["index_versions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_version_id",
            "index_version_id",
            name="uq_sparse_statistics_version",
        ),
    )
    op.create_index(
        "ix_sparse_index_statistics_document_version_id",
        "sparse_index_statistics",
        ["document_version_id"],
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "sparse_index_statistics" in inspector.get_table_names():
        op.drop_table("sparse_index_statistics")
