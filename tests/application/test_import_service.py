from hashlib import sha256
from pathlib import Path

import pymupdf
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from rag_app.application import (
    PersistentImportService,
    UploadedDocument,
)
from rag_app.catalog import Product, ProductCatalog, ProductCategory
from rag_app.file_store import Sha256FileStore
from rag_app.persistence import ImportRepository, create_schema
from rag_app.persistence.schema import IngestionItem


def test_import_service_stores_blob_and_creates_batch(
    tmp_path: Path,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        service = PersistentImportService(
            repository=ImportRepository(session),
            file_store=Sha256FileStore(tmp_path / "blobs"),
            created_by="admin",
        )

        result = service.enqueue(
            (
                UploadedDocument(
                    filename="manual.pdf",
                    content_type="application/pdf",
                    content=b"%PDF-1.7",
                    sha256="a" * 64,
                    relative_path="tablets/C7/manual.pdf",
                ),
            )
        )
        items = session.scalars(select(IngestionItem)).all()

    assert result.accepted == 1
    assert items[0].sha256 == sha256(b"%PDF-1.7").hexdigest()
    assert items[0].status == "uploaded"
    assert items[0].relative_path == "tablets/C7/manual.pdf"
    assert (tmp_path / "blobs").exists()


def test_import_service_extracts_product_and_version_from_filename(
    tmp_path: Path,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    catalog = ProductCatalog(
        (
            Product(
                "huawei_c7",
                "华为平板 C7",
                ProductCategory.TABLET,
                ("C7",),
            ),
        )
    )
    with Session(engine) as session:
        service = PersistentImportService(
            repository=ImportRepository(session),
            file_store=Sha256FileStore(tmp_path / "blobs"),
            created_by="admin",
            catalog=catalog,
        )
        service.enqueue(
            (
                UploadedDocument(
                    filename="C7_用户指南_V2.1.0.pdf",
                    content_type="application/pdf",
                    content=b"%PDF-1.7",
                    sha256="unused",
                ),
            )
        )
        item = session.scalars(select(IngestionItem)).one()

    assert item.detected_product_ids == ["huawei_c7"]
    assert item.detected_version_label == "2.1.0"
    assert item.confidence == "high"
    assert item.version_source == "filename"


def test_import_service_marks_same_name_conflict(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        service = PersistentImportService(
            repository=ImportRepository(session),
            file_store=Sha256FileStore(tmp_path / "blobs"),
            created_by="admin",
        )
        service.enqueue(
            (
                UploadedDocument(
                    filename="manual.pdf",
                    content_type="application/pdf",
                    content=b"%PDF-old",
                    sha256="unused",
                ),
            )
        )
        service.enqueue(
            (
                UploadedDocument(
                    filename="manual.pdf",
                    content_type="application/pdf",
                    content=b"%PDF-new",
                    sha256="unused",
                ),
            )
        )
        items = session.scalars(
            select(IngestionItem).order_by(IngestionItem.original_filename)
        ).all()
        batch = service.get_batch(items[-1].batch_id)

    assert items[-1].conflict_type == "same_name"
    assert items[-1].status == "conflict"
    assert batch.items[0].conflict_version_label is None


def test_import_service_reads_pdf_cover_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "manual.pdf"
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "HUAWEI C7 User Guide\nVersion: 3.2.1",
    )
    document.save(pdf_path)  # type: ignore[no-untyped-call]
    document.close()  # type: ignore[no-untyped-call]

    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    catalog = ProductCatalog((
        Product(
            "huawei_c7",
            "华为平板 C7",
            ProductCategory.TABLET,
            ("C7",),
        ),
    ))
    with Session(engine) as session:
        service = PersistentImportService(
            repository=ImportRepository(session),
            file_store=Sha256FileStore(tmp_path / "blobs"),
            created_by="admin",
            catalog=catalog,
        )
        service.enqueue((
            UploadedDocument(
                filename="manual.pdf",
                content_type="application/pdf",
                content=pdf_path.read_bytes(),
                sha256="unused",
            ),
        ))
        item = session.scalars(select(IngestionItem)).one()

    assert item.detected_product_ids == ["huawei_c7"]
    assert item.detected_version_label == "3.2.1"
    assert item.version_source == "document_text"


def test_import_service_creates_product_from_manual_name(
    tmp_path: Path,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    class Products:
        def resolve_or_create(self, display_name: str) -> str:
            assert display_name == "HUAWEI MateBook B7-420"
            return "custom_b7"

    with Session(engine) as session:
        service = PersistentImportService(
            repository=ImportRepository(session),
            file_store=Sha256FileStore(tmp_path / "blobs"),
            created_by="admin",
            products=Products(),
        )
        batch = service.enqueue((
            UploadedDocument(
                filename="B7-420-manual.pdf",
                content_type="application/pdf",
                content=b"%PDF-1.7",
                sha256="unused",
            ),
        ))
        item = session.scalars(select(IngestionItem)).one()

        service.update_item_product_name(
            batch.batch_id or "",
            item.id,
            product_name="HUAWEI MateBook B7-420",
            version_label="2.0",
        )

    assert item.selected_product_ids == ["custom_b7"]
    assert item.detected_version_label == "2.0"
    assert item.version_source == "manual"


def test_import_service_prefills_llm_product_without_creating_it(
    tmp_path: Path,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    catalog = ProductCatalog(())

    class FilenameExtractor:
        def extract(self, filename: str) -> str | None:
            assert "B7-420" in filename
            return "HUAWEI MateBook B7-420"

    with Session(engine) as session:
        service = PersistentImportService(
            repository=ImportRepository(session),
            file_store=Sha256FileStore(tmp_path / "blobs"),
            created_by="admin",
            catalog=catalog,
            filename_product_extractor=FilenameExtractor(),
        )
        service.enqueue((
            UploadedDocument(
                filename="B7-420-manual.pdf",
                content_type="application/pdf",
                content=b"%PDF-1.7",
                sha256="unused",
            ),
        ))
        item = session.scalars(select(IngestionItem)).one()

    assert item.detected_product_ids == []
    assert item.selected_product_ids == []
    assert item.detected_product_name == "HUAWEI MateBook B7-420"
    assert item.confidence == "low"
