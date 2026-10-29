from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from rag_app.persistence import create_schema
from rag_app.persistence.index_cleanup_repository import (
    IndexCleanupRepository,
)
from rag_app.persistence.schema import (
    Document,
    DocumentVersion,
    FileBlob,
    IndexCleanupJob,
    IndexVersion,
)


def _seed_version(session: Session) -> None:
    session.add(
        IndexVersion(
            id="i1",
            chunker_version="c1",
            dense_provider="provider",
            dense_model="model",
            dense_model_revision="revision",
            dense_dimension=3,
            sparse_method="bm25",
            sparse_tokenizer="jieba",
        )
    )
    session.add(
        Document(
            id="d1",
            canonical_name="guide.pdf",
            manufacturer="HUAWEI",
        )
    )
    session.add(
        FileBlob(
            id=1,
            sha256="a" * 64,
            storage_uri="a/a.pdf",
            size_bytes=10,
            original_filename="guide.pdf",
            content_type="application/pdf",
        )
    )
    session.flush()
    session.add(
        DocumentVersion(
            id="v1",
            document_id="d1",
            file_blob_id=1,
            version_label="1.0",
            version_key="d1:1.0",
            version_source="filename",
            version_confidence="high",
            sha256="a" * 64,
            received_at=datetime(2026, 1, 1, tzinfo=UTC),
            status="active",
            metadata_confidence="high",
            metadata_evidence={},
        )
    )
    session.flush()


def test_cleanup_queue_is_idempotent_and_returns_pending_jobs() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        _seed_version(session)
        repository = IndexCleanupRepository(session)

        repository.enqueue("v1", "i1")
        repository.enqueue("v1", "i1")
        session.commit()

        jobs = repository.list_ready(limit=10)
        rows = session.scalars(select(IndexCleanupJob)).all()

        assert len(rows) == 1
        assert len(jobs) == 1
        assert jobs[0].document_version_id == "v1"
        assert jobs[0].index_version_id == "i1"


def test_cleanup_failure_schedules_retry() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        _seed_version(session)
        repository = IndexCleanupRepository(session)
        repository.enqueue("v1", "i1")
        session.flush()
        job = repository.list_ready(limit=1)[0]

        repository.mark_failed(job.id, "qdrant unavailable")
        session.commit()

        entity = session.get(IndexCleanupJob, job.id)
        assert entity is not None
        assert entity.status == "pending"
        assert entity.attempts == 1
        assert entity.error_message == "qdrant unavailable"
        available_at = entity.available_at
        if available_at.tzinfo is None:
            available_at = available_at.replace(tzinfo=UTC)
        assert available_at > datetime.now(UTC)


def test_cleanup_success_marks_job_completed() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        _seed_version(session)
        repository = IndexCleanupRepository(session)
        repository.enqueue("v1", "i1")
        session.flush()
        job = repository.list_ready(limit=1)[0]

        repository.mark_completed(job.id)
        session.commit()

        entity = session.get(IndexCleanupJob, job.id)
        assert entity is not None
        assert entity.status == "completed"
        assert entity.error_message is None
