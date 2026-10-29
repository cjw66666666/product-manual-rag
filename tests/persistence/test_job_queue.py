from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rag_app.persistence import create_schema
from rag_app.persistence.job_queue import IngestionJobQueue
from rag_app.persistence.schema import IngestionBatch, IngestionItem


def test_queue_claims_only_prepared_items() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        session.add(IngestionBatch(
            id="b1",
            source_type="files",
            status="queued",
            created_by="admin",
        ))
        session.add_all([
            IngestionItem(
                id="i1",
                batch_id="b1",
                relative_path="manual.pdf",
                original_filename="manual.pdf",
                sha256="a" * 64,
                detected_product_ids=[],
                selected_product_ids=[],
                detected_version_label=None,
                version_source="unknown",
                document_type_codes=[],
                confidence="low",
                conflict_type=None,
                status="uploaded",
            ),
            IngestionItem(
                id="i2",
                batch_id="b1",
                relative_path="prepared.pdf",
                original_filename="prepared.pdf",
                sha256="b" * 64,
                detected_product_ids=[],
                selected_product_ids=[],
                detected_version_label=None,
                version_source="unknown",
                document_type_codes=[],
                confidence="low",
                conflict_type=None,
                status="queued",
            ),
        ])
        session.flush()
        queue = IngestionJobQueue(session)

        job = queue.claim()
        assert job is not None
        assert job.id == "i2"
        queue.complete(job.id)

        item = session.get(IngestionItem, "i2")
        uploaded_item = session.get(IngestionItem, "i1")
        assert item is not None
        assert uploaded_item is not None
        assert item.status == "completed"
        assert uploaded_item.status == "uploaded"
