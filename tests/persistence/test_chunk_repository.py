from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from rag_app.chunking import ChunkDraft
from rag_app.persistence import create_schema
from rag_app.persistence.chunk_repository import ChunkRepository
from rag_app.persistence.schema import Chunk, Document, DocumentVersion, FileBlob


def test_repository_replaces_chunks_for_version() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(
        dbapi_connection: Any,
        connection_record: Any,
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    create_schema(engine)
    with Session(engine) as session:
        session.add_all([
            Document(id="d1", canonical_name="Guide", manufacturer="brand"),
            FileBlob(
                id=1,
                sha256="a" * 64,
                storage_uri="aa/aa/file.pdf",
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
        repo = ChunkRepository(session)
        chunk = ChunkDraft(
            content="安全\n请勿拆机。",
            page_start=3,
            page_end=3,
            section_path=("安全",),
            section_types=("safety",),
        )

        chunk_ids = repo.replace_version_chunks("v1", (chunk, chunk))
        stored_ids = session.scalars(select(Chunk.id)).all()

        assert len(chunk_ids) == 2
        assert set(chunk_ids) == set(stored_ids)
        assert chunk_ids[0] != chunk_ids[1]
        assert len(session.scalars(select(Chunk)).all()) == 2
        version = session.get(DocumentVersion, "v1")
        assert version is not None
        assert version.requires_manual_approval is True
