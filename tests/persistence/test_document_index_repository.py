from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rag_app.persistence import create_schema
from rag_app.persistence.document_index_repository import (
    DocumentIndexRepository,
)
from rag_app.persistence.schema import Document, DocumentVersion, FileBlob


def test_repository_upserts_index_success() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        repo = DocumentIndexRepository(session)
        session.add_all([
            Document(
                id="d1",
                canonical_name="Guide",
                manufacturer="brand",
            ),
            FileBlob(
                id=1,
                sha256="a" * 64,
                storage_uri="a/a.pdf",
                size_bytes=10,
                original_filename="guide.pdf",
                content_type="application/pdf",
            ),
        ])
        session.flush()
        session.add(DocumentVersion(
            id="v1",
            document_id="d1",
            file_blob_id=1,
            version_label="1.0",
            version_key="d1:1.0",
            version_source="filename",
            version_confidence="high",
            sha256="a" * 64,
            received_at=datetime(2026, 1, 1, tzinfo=UTC),
            status="processing",
            metadata_confidence="high",
            metadata_evidence={},
        ))
        session.flush()

        repo.mark_success("v1", "i1", 3)
        record = repo.get("v1", "i1")
        version = session.get(DocumentVersion, "v1")

        assert record is not None
        assert record.status == "completed"
        assert record.chunk_count == 3
        assert version is not None
        assert version.status == "validated"
        summaries = repo.list_for_version("v1")
        assert len(summaries) == 1
        assert summaries[0].index_version_id == "i1"
        assert summaries[0].chunk_count == 3


def test_repository_records_failure() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        repo = DocumentIndexRepository(session)

        repo.mark_failure("v1", "i1", "bad pdf")
        record = repo.get("v1", "i1")

        assert record is not None
        assert record.status == "failed"
        assert record.error_message == "bad pdf"
