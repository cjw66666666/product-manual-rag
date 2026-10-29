"""Add conversation ordering and image metadata.

Revision ID: 20261028_0002
Revises: 20261027_0001
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261028_0002"
down_revision: str | None = "20261027_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    message_columns = {
        item["name"] for item in inspector.get_columns("messages")
    }
    summary_columns = {
        item["name"]
        for item in inspector.get_columns("conversation_summaries")
    }
    chunk_columns = {
        item["name"] for item in inspector.get_columns("chunks")
    }
    version_columns = {
        item["name"]
        for item in inspector.get_columns("document_versions")
    }

    if "sequence" not in message_columns:
        op.add_column(
            "messages",
            sa.Column(
                "sequence",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )
    message_indexes = {
        item["name"] for item in inspector.get_indexes("messages")
    }
    if "ix_messages_sequence" not in message_indexes:
        op.create_index(
            "ix_messages_sequence",
            "messages",
            ["sequence"],
            unique=False,
        )

    if "covered_sequence" not in summary_columns:
        op.add_column(
            "conversation_summaries",
            sa.Column(
                "covered_sequence",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )

    if "requires_manual_approval" not in version_columns:
        op.add_column(
            "document_versions",
            sa.Column(
                "requires_manual_approval",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    if "approved_at" not in version_columns:
        op.add_column(
            "document_versions",
            sa.Column(
                "approved_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )
    if "approved_by" not in version_columns:
        op.add_column(
            "document_versions",
            sa.Column("approved_by", sa.String(128), nullable=True),
        )

    if "has_images" not in chunk_columns:
        op.add_column(
            "chunks",
            sa.Column(
                "has_images",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    if "product_index_bindings" not in inspector.get_table_names():
        op.create_table(
            "product_index_bindings",
            sa.Column("product_id", sa.String(64), nullable=False),
            sa.Column("index_version_id", sa.String(64), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
            sa.ForeignKeyConstraint(
                ["index_version_id"],
                ["index_versions.id"],
            ),
            sa.PrimaryKeyConstraint("product_id"),
        )

    if "sparse_index_statistics" not in inspector.get_table_names():
        op.create_table(
            "sparse_index_statistics",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "document_version_id",
                sa.String(64),
                nullable=False,
            ),
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

    rows = bind.execute(
        sa.text(
            "SELECT id, conversation_id FROM messages "
            "ORDER BY conversation_id, created_at, id"
        )
    ).mappings().all()
    sequences: dict[str, int] = {}
    for row in rows:
        conversation_id = str(row["conversation_id"])
        sequence = sequences.get(conversation_id, 0) + 1
        sequences[conversation_id] = sequence
        bind.execute(
            sa.text(
                "UPDATE messages SET sequence = :sequence WHERE id = :id"
            ),
            {"sequence": sequence, "id": row["id"]},
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    message_columns = {
        item["name"] for item in inspector.get_columns("messages")
    }
    summary_columns = {
        item["name"]
        for item in inspector.get_columns("conversation_summaries")
    }
    chunk_columns = {
        item["name"] for item in inspector.get_columns("chunks")
    }
    version_columns = {
        item["name"]
        for item in inspector.get_columns("document_versions")
    }

    if "product_index_bindings" in inspector.get_table_names():
        op.drop_table("product_index_bindings")
    if "sparse_index_statistics" in inspector.get_table_names():
        op.drop_table("sparse_index_statistics")
    if "has_images" in chunk_columns:
        op.drop_column("chunks", "has_images")
    if "approved_by" in version_columns:
        op.drop_column("document_versions", "approved_by")
    if "approved_at" in version_columns:
        op.drop_column("document_versions", "approved_at")
    if "requires_manual_approval" in version_columns:
        op.drop_column("document_versions", "requires_manual_approval")
    if "covered_sequence" in summary_columns:
        op.drop_column("conversation_summaries", "covered_sequence")
    if "sequence" in message_columns:
        op.drop_index("ix_messages_sequence", table_name="messages")
        op.drop_column("messages", "sequence")
