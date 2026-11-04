"""Repair contaminated product aliases and document bindings.

Revision ID: 20261104_0007
Revises: 20261029_0006
Create Date: 2026-11-04
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20261104_0007"
down_revision: str | None = "20261029_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    product_aliases = sa.table(
        "product_aliases",
        sa.column("product_id", sa.String()),
        sa.column("normalized_alias", sa.String()),
    )
    connection.execute(
        sa.delete(product_aliases).where(
            product_aliases.c.product_id == "huawei_c5e_gen4",
            product_aliases.c.normalized_alias == "c5e",
        )
    )

    documents = sa.table(
        "documents",
        sa.column("id", sa.String()),
        sa.column("canonical_name", sa.String()),
    )
    bindings = sa.table(
        "product_document_bindings",
        sa.column("id", sa.Integer()),
        sa.column("product_id", sa.String()),
        sa.column("document_id", sa.String()),
        sa.column("active_version_id", sa.String()),
    )
    versions = sa.table(
        "document_versions",
        sa.column("id", sa.String()),
        sa.column("status", sa.String()),
        sa.column("superseded_at", sa.DateTime(timezone=True)),
    )

    stale_document_ids = set(
        connection.execute(
            sa.select(documents.c.id).where(
                sa.or_(
                    sa.and_(
                        documents.c.canonical_name.like(
                            "%华为平板 C5e%"
                        ),
                        documents.c.canonical_name.like("%BZI-W00%"),
                    ),
                    documents.c.canonical_name.like("Aolynk CB304n%"),
                )
            )
        ).scalars()
    )
    if not stale_document_ids:
        return

    stale_bindings = connection.execute(
        sa.select(
            bindings.c.id,
            bindings.c.active_version_id,
        ).where(
            bindings.c.document_id.in_(stale_document_ids),
            sa.or_(
                sa.and_(
                    bindings.c.product_id == "huawei_c5e_gen4",
                    bindings.c.document_id.in_(stale_document_ids),
                ),
                sa.and_(
                    bindings.c.product_id == "huawei_c7",
                    bindings.c.document_id.in_(stale_document_ids),
                ),
            ),
        )
    ).all()
    for binding in stale_bindings:
        if binding.active_version_id is not None:
            connection.execute(
                sa.update(versions)
                .where(versions.c.id == binding.active_version_id)
                .values(
                    status="superseded",
                    superseded_at=datetime.now(UTC),
                )
            )
        connection.execute(
            sa.update(bindings)
            .where(bindings.c.id == binding.id)
            .values(active_version_id=None)
        )


def downgrade() -> None:
    # This migration removes known-bad scope data and is intentionally
    # irreversible.
    pass
