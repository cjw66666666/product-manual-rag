import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from rag_app.persistence import create_schema
from rag_app.persistence.import_version_binder import ImportVersionBinder
from rag_app.persistence.repositories import DocumentRepository
from rag_app.persistence.schema import (
    Document,
    DocumentVersion,
    IngestionBatch,
    IngestionItem,
    ProductDocumentBinding,
)


def test_binder_creates_version_and_product_binding() -> None:
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
            relative_path="C7_manual.pdf",
            original_filename="C7_manual.pdf",
            sha256="a" * 64,
            detected_product_ids=["huawei_c7"],
            selected_product_ids=["huawei_c7"],
            detected_version_label="2.1.0",
            version_source="filename",
            document_type_codes=[],
            document_version_id=None,
            index_version_id=None,
            confidence="high",
            conflict_type=None,
            status="pending",
        ))
        session.flush()

        version_id = ImportVersionBinder(session).bind(
            item_id="i1",
            index_version_id="i1",
        )
        item = session.get(IngestionItem, "i1")

        assert session.get(DocumentVersion, version_id) is not None
        assert item is not None
        assert item.document_version_id == version_id
        assert item.index_version_id == "i1"
        assert item.status == "queued"
        assert session.query(ProductDocumentBinding).count() == 1


def test_binder_rejects_conflicted_import() -> None:
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
            detected_product_ids=["huawei_c7"],
            selected_product_ids=["huawei_c7"],
            detected_version_label=None,
            version_source="unknown",
            document_type_codes=[],
            document_version_id=None,
            index_version_id=None,
            confidence="medium",
            conflict_type="same_name",
            status="conflict",
        ))
        session.flush()

        with pytest.raises(ValueError, match="conflict"):
            ImportVersionBinder(session).bind(
                item_id="i1",
                index_version_id="i1",
            )


def test_same_name_upgrade_reuses_document_and_replaces_active_version() -> None:
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
                relative_path="C7_manual.pdf",
                original_filename="C7_manual.pdf",
                sha256="a" * 64,
                detected_product_ids=["huawei_c7"],
                selected_product_ids=["huawei_c7"],
                detected_version_label="2.0",
                version_source="filename",
                document_type_codes=[],
                document_version_id=None,
                index_version_id=None,
                confidence="high",
                conflict_type=None,
                status="pending",
            ),
            IngestionItem(
                id="i2",
                batch_id="b1",
                relative_path="C7_manual.pdf",
                original_filename="C7_manual.pdf",
                sha256="b" * 64,
                detected_product_ids=["huawei_c7"],
                selected_product_ids=["huawei_c7"],
                detected_version_label="2.1",
                version_source="filename",
                document_type_codes=[],
                document_version_id=None,
                index_version_id=None,
                confidence="high",
                conflict_type=None,
                status="pending",
            ),
        ])
        session.flush()

        binder = ImportVersionBinder(session)
        first = binder.bind(item_id="i1", index_version_id="i1")
        second = binder.bind(item_id="i2", index_version_id="i1")
        documents = session.scalars(select(Document)).all()
        bindings = session.scalars(select(ProductDocumentBinding)).all()
        versions = session.scalars(select(DocumentVersion)).all()

        assert len(documents) == 1
        assert len(bindings) == 1
        assert {version.document_id for version in versions} == {
            documents[0].id
        }

        repository = DocumentRepository(session)
        for version in versions:
            version.status = "validated"
        repository.activate_version("huawei_c7", documents[0].id, first)
        repository.activate_version("huawei_c7", documents[0].id, second)

        assert repository.active_version_ids("huawei_c7") == (second,)
        assert repository.get_version_status(first) == "superseded"
