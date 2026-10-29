"""Add transactional index cleanup jobs.

Revision ID: 20261029_0005
Revises: 20261029_0004
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0005"
down_revision: str | None = "20261029_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "index_cleanup_jobs" in inspector.get_table_names():
        return
    op.create_table(
        "index_cleanup_jobs",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("document_version_id", sa.String(64), nullable=False),
        sa.Column("index_version_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
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
            name="uq_index_cleanup_version",
        ),
    )
    op.create_index(
        "ix_index_cleanup_jobs_document_version_id",
        "index_cleanup_jobs",
        ["document_version_id"],
    )
    op.create_index(
        "ix_index_cleanup_jobs_status",
        "index_cleanup_jobs",
        ["status"],
    )
    op.create_index(
        "ix_index_cleanup_jobs_available_at",
        "index_cleanup_jobs",
        ["available_at"],
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "index_cleanup_jobs" in inspector.get_table_names():
        op.drop_table("index_cleanup_jobs")
