from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rag_app.persistence import create_schema
from rag_app.persistence.schema import (
    Document,
    DocumentVersion,
    FileBlob,
    IndexVersion,
)
from rag_app.persistence.sparse_statistics_repository import (
    SparseStatisticsRepository,
)
from rag_app.sparse_encoder import Bm25SparseEncoder


def _seed(session: Session, version_id: str, key: str) -> None:
    session.add(Document(
        id=f"d-{version_id}",
        canonical_name=f"{version_id}.pdf",
        manufacturer="brand",
    ))
    blob_id = 1 if version_id == "v1" else 2
    session.add(FileBlob(
        id=blob_id,
        sha256=key * 64,
        storage_uri=f"{key}/{key}.pdf",
        size_bytes=10,
        original_filename=f"{version_id}.pdf",
        content_type="application/pdf",
    ))
    session.flush()
    session.add(DocumentVersion(
        id=version_id,
        document_id=f"d-{version_id}",
        file_blob_id=blob_id,
        version_label="1.0",
        version_key=f"{version_id}:1.0",
        version_source="filename",
        version_confidence="high",
        sha256=key * 64,
        received_at=datetime(2026, 1, 1, tzinfo=UTC),
        status="validated",
        metadata_confidence="high",
        metadata_evidence={},
    ))


def test_sparse_statistics_round_trip_and_aggregate() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        session.add(IndexVersion(
            id="i1",
            chunker_version="c1",
            dense_provider="test",
            dense_model="model",
            dense_model_revision="1",
            dense_dimension=2,
            sparse_method="bm25",
            sparse_tokenizer="test",
        ))
        _seed(session, "v1", "a")
        _seed(session, "v2", "b")
        session.flush()
        repo = SparseStatisticsRepository(session)
        encoder = Bm25SparseEncoder()
        repo.save(
            document_version_id="v1",
            index_version_id="i1",
            statistics=encoder.fit(("开机 电源键",)),
        )
        repo.save(
            document_version_id="v2",
            index_version_id="i1",
            statistics=encoder.fit(("开机 设置",)),
        )

        merged = repo.aggregate(
            document_version_ids=("v1", "v2"),
            index_version_id="i1",
        )

        assert merged.document_count == 2
        assert sorted(merged.document_frequency.values()) == [1, 1, 1, 2]
