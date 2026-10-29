from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_app.persistence.schema import (
    Document,
    DocumentVersion,
    FileBlob,
    IngestionItem,
    ProductDocumentBinding,
)


class ImportVersionBinder:
    def __init__(self, session: Session) -> None:
        self._session = session

    def bind(self, *, item_id: str, index_version_id: str) -> str:
        item = self._session.get(IngestionItem, item_id)
        if item is None:
            raise ValueError("ingestion item not found")
        if item.document_version_id is not None:
            item.index_version_id = index_version_id
            item.status = "queued"
            self._session.flush()
            return item.document_version_id
        if item.conflict_type is not None or item.status == "conflict":
            raise ValueError("import item has an unresolved conflict")
        if len(item.selected_product_ids) != 1:
            raise ValueError("exactly one product must be selected")
        product_id = item.selected_product_ids[0]

        blob = self._session.scalar(
            select(FileBlob).where(FileBlob.sha256 == item.sha256)
        )
        if blob is None:
            blob = FileBlob(
                sha256=item.sha256,
                storage_uri=(
                    f"{item.sha256[:2]}/{item.sha256[2:4]}/"
                    f"{item.sha256}.pdf"
                ),
                size_bytes=0,
                original_filename=item.original_filename,
                content_type="application/pdf",
            )
            self._session.add(blob)
            self._session.flush()

        normalized_name = item.original_filename.casefold()
        bound_documents = self._session.scalars(
            select(Document)
            .join(
                ProductDocumentBinding,
                ProductDocumentBinding.document_id == Document.id,
            )
            .where(ProductDocumentBinding.product_id == product_id)
        ).all()
        document = next(
            (
                candidate
                for candidate in bound_documents
                if candidate.canonical_name.casefold() == normalized_name
            ),
            None,
        )
        if document is None:
            document = Document(
                id=uuid4().hex,
                canonical_name=item.original_filename,
                manufacturer="HUAWEI",
                status="active",
            )
            self._session.add(document)
            self._session.flush()
            self._session.add(
                ProductDocumentBinding(
                    product_id=product_id,
                    document_id=document.id,
                )
            )

        version = DocumentVersion(
            id=uuid4().hex,
            document_id=document.id,
            file_blob_id=blob.id,
            version_label=item.detected_version_label,
            version_key=f"item:{item.id}",
            version_source=item.version_source,
            version_confidence=item.confidence,
            sha256=item.sha256,
            received_at=datetime.now(UTC),
            status="draft",
            metadata_confidence=item.confidence,
            metadata_evidence={},
        )
        self._session.add(version)
        self._session.flush()
        item.document_version_id = version.id
        item.index_version_id = index_version_id
        item.status = "queued"
        self._session.flush()
        return version.id
