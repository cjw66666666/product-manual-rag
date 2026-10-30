from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rag_app.persistence import create_schema
from rag_app.persistence.repositories import DocumentRepository
from rag_app.persistence.schema import (
    Document,
    DocumentVersion,
    FileBlob,
    Product,
)


def test_active_version_is_product_specific() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Product(
                    id="p1",
                    display_name="P1",
                    category="tablet",
                    brand="brand",
                ),
                Document(
                    id="d1",
                    canonical_name="Guide",
                    manufacturer="brand",
                ),
                FileBlob(
                    id=1,
                    sha256="a" * 64,
                    storage_uri="storage/a.pdf",
                    size_bytes=10,
                    original_filename="guide.pdf",
                    content_type="application/pdf",
                ),
            ]
        )
        session.commit()
        repo = DocumentRepository(session)
        version_id = repo.add_document_version(
            document_id="d1",
            file_blob_id=1,
            version_label="2026.1",
            version_key="d1:2026.1",
            version_source="cover",
            version_confidence="high",
            sha256="a" * 64,
            received_at=datetime(2026, 10, 26, tzinfo=UTC),
            status="validated",
        )
        repo.bind_product("p1", "d1")
        repo.activate_version(
            "p1",
            "d1",
            version_id,
            index_version_id="i1",
        )

        assert repo.active_version_ids("p1") == (version_id,)
        assert repo.active_index_version("p1") == "i1"
        assert repo.find_by_sha256("a" * 64) is not None


def test_activating_new_version_supersedes_previous() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Product(
                    id="p1",
                    display_name="P1",
                    category="tablet",
                    brand="brand",
                ),
                Document(
                    id="d1",
                    canonical_name="Guide",
                    manufacturer="brand",
                ),
            ]
        )
        for index in (1, 2):
            session.add(
                FileBlob(
                    id=index,
                    sha256=str(index) * 64,
                    storage_uri=f"storage/{index}.pdf",
                    size_bytes=10,
                    original_filename=f"guide-{index}.pdf",
                    content_type="application/pdf",
                )
            )
        session.commit()
        repo = DocumentRepository(session)
        first = repo.add_document_version(
            document_id="d1",
            file_blob_id=1,
            version_label="2025.1",
            version_key="d1:2025.1",
            version_source="cover",
            version_confidence="high",
            sha256="1" * 64,
            received_at=datetime(2025, 1, 1, tzinfo=UTC),
            status="validated",
        )
        second = repo.add_document_version(
            document_id="d1",
            file_blob_id=2,
            version_label="2026.1",
            version_key="d1:2026.1",
            version_source="cover",
            version_confidence="high",
            sha256="2" * 64,
            received_at=datetime(2026, 1, 1, tzinfo=UTC),
            status="validated",
        )
        repo.bind_product("p1", "d1")
        repo.activate_version("p1", "d1", first)
        repo.activate_version("p1", "d1", second)

        assert repo.active_version_ids("p1") == (second,)
        assert repo.get_version_status(first) == "superseded"
        versions = repo.list_versions_for_product("p1")
        assert {version.document_name for version in versions} == {
            "guide-1.pdf",
            "guide-2.pdf",
        }


def test_safety_version_requires_approval_before_activation() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        session.add_all([
            Product(
                id="p1",
                display_name="P1",
                category="tablet",
                brand="brand",
            ),
            Document(
                id="d1",
                canonical_name="Safety Guide",
                manufacturer="brand",
            ),
            FileBlob(
                id=1,
                sha256="a" * 64,
                storage_uri="storage/a.pdf",
                size_bytes=10,
                original_filename="safety.pdf",
                content_type="application/pdf",
            ),
        ])
        session.flush()
        repo = DocumentRepository(session)
        version_id = repo.add_document_version(
            document_id="d1",
            file_blob_id=1,
            version_label="2026.1",
            version_key="d1:safety",
            version_source="cover",
            version_confidence="high",
            sha256="a" * 64,
            received_at=datetime(2026, 10, 26, tzinfo=UTC),
            status="draft",
        )
        version = session.get(DocumentVersion, version_id)
        assert version is not None
        version.status = "validated"
        version.requires_manual_approval = True
        repo.bind_product("p1", "d1")

        assert repo.list_pending_approval_product_ids() == ("p1",)
        assert repo.list_approved_product_ids() == ()

        with pytest.raises(ValueError, match="approval"):
            repo.activate_version("p1", "d1", version_id)

        repo.approve_version(version_id, approved_by="reviewer")
        assert repo.list_pending_approval_product_ids() == ()
        assert repo.list_approved_product_ids() == ("p1",)
        repo.activate_version("p1", "d1", version_id)

        assert repo.active_version_ids("p1") == (version_id,)


def test_active_version_can_be_reapproved_for_new_index() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        session.add_all([
            Product(
                id="p1",
                display_name="P1",
                category="tablet",
                brand="brand",
            ),
            Document(
                id="d1",
                canonical_name="Safety Guide",
                manufacturer="brand",
            ),
            FileBlob(
                id=1,
                sha256="a" * 64,
                storage_uri="storage/a.pdf",
                size_bytes=10,
                original_filename="safety.pdf",
                content_type="application/pdf",
            ),
        ])
        session.flush()
        repo = DocumentRepository(session)
        version_id = repo.add_document_version(
            document_id="d1",
            file_blob_id=1,
            version_label="2026.1",
            version_key="d1:active",
            version_source="cover",
            version_confidence="high",
            sha256="a" * 64,
            received_at=datetime(2026, 10, 26, tzinfo=UTC),
            status="active",
        )
        version = session.get(DocumentVersion, version_id)
        assert version is not None
        version.requires_manual_approval = True
        version.approved_at = None

        repo.approve_version(version_id, approved_by="reviewer")

        assert version.approved_by == "reviewer"
