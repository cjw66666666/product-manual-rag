from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rag_app.persistence import create_schema
from rag_app.persistence.indexing_context import IndexingContextProvider
from rag_app.persistence.schema import IngestionBatch, IngestionItem


def test_context_provider_requires_version_and_product() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        session.add(IngestionBatch(
            id="b1",
            source_type="files",
            status="queued",
            created_by="admin",
        ))
        session.add(IngestionItem(
            id="i1",
            batch_id="b1",
            relative_path="manual.pdf",
            original_filename="manual.pdf",
            sha256="a" * 64,
            detected_product_ids=["p1"],
            selected_product_ids=["p1"],
            detected_version_label="1.0",
            version_source="filename",
            document_type_codes=[],
            document_version_id=None,
            index_version_id=None,
            confidence="high",
            conflict_type=None,
            status="processing",
        ))
        session.flush()

        provider = IndexingContextProvider(session)

        try:
            provider.get("i1")
        except ValueError as exc:
            assert "document version" in str(exc)
        else:
            raise AssertionError("missing version must fail")
