from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_app.persistence.schema import (
    DocumentVersion,
    FileBlob,
    ProductDocumentBinding,
    ProductIndexBinding,
)


@dataclass(frozen=True, slots=True)
class DocumentVersionRecord:
    id: str
    document_id: str
    sha256: str
    version_key: str
    version_label: str | None
    status: str
    requires_manual_approval: bool
    approved_at: datetime | None
    approved_by: str | None
    document_name: str | None = None


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_sha256(self, sha256: str) -> DocumentVersionRecord | None:
        result = self._session.scalar(
            select(DocumentVersion).where(DocumentVersion.sha256 == sha256)
        )
        document_name = (
            None
            if result is None
            else self._session.scalar(
                select(FileBlob.original_filename).where(
                    FileBlob.id == result.file_blob_id
                )
            )
        )
        return self._record(result, document_name=document_name)

    def add_document_version(
        self,
        *,
        document_id: str,
        file_blob_id: int,
        version_label: str | None,
        version_key: str,
        version_source: str,
        version_confidence: str,
        sha256: str,
        received_at: datetime,
        status: str,
    ) -> str:
        entity = DocumentVersion(
            id=uuid4().hex,
            document_id=document_id,
            file_blob_id=file_blob_id,
            version_label=version_label,
            version_key=version_key,
            version_source=version_source,
            version_confidence=version_confidence,
            sha256=sha256,
            received_at=received_at,
            status=status,
            metadata_confidence=version_confidence,
            metadata_evidence={},
        )
        self._session.add(entity)
        self._session.flush()
        return entity.id

    def bind_product(self, product_id: str, document_id: str) -> None:
        existing = self._session.scalar(
            select(ProductDocumentBinding).where(
                ProductDocumentBinding.product_id == product_id,
                ProductDocumentBinding.document_id == document_id,
            )
        )
        if existing is None:
            self._session.add(
                ProductDocumentBinding(
                    product_id=product_id,
                    document_id=document_id,
                )
            )
            self._session.flush()

    def activate_version(
        self,
        product_id: str,
        document_id: str,
        version_id: str,
        index_version_id: str | None = None,
    ) -> None:
        binding = self._session.scalar(
            select(ProductDocumentBinding).where(
                ProductDocumentBinding.product_id == product_id,
                ProductDocumentBinding.document_id == document_id,
            )
        )
        if binding is None:
            raise ValueError("product is not bound to document")

        target = self._session.get(DocumentVersion, version_id)
        if target is None:
            raise ValueError("document version not found")
        if target.document_id != document_id:
            raise ValueError("version does not belong to document")
        if target.status not in {"validated", "active"}:
            raise ValueError("document version is not validated")
        if (
            target.requires_manual_approval
            and target.approved_at is None
        ):
            raise ValueError(
                "safety document version requires manual approval"
            )

        if binding.active_version_id and binding.active_version_id != version_id:
            previous = self._session.get(
                DocumentVersion,
                binding.active_version_id,
            )
            if previous is not None:
                previous.status = "superseded"

        target.status = "active"
        binding.active_version_id = version_id
        if index_version_id is not None:
            index_binding = self._session.get(
                ProductIndexBinding,
                product_id,
            )
            if index_binding is None:
                self._session.add(
                    ProductIndexBinding(
                        product_id=product_id,
                        index_version_id=index_version_id,
                    )
                )
            else:
                index_binding.index_version_id = index_version_id
        self._session.flush()

    def requires_manual_approval(self, version_id: str) -> bool:
        version = self._session.get(DocumentVersion, version_id)
        if version is None:
            raise ValueError("document version not found")
        return version.requires_manual_approval

    def approve_version(self, version_id: str, *, approved_by: str) -> None:
        version = self._session.get(DocumentVersion, version_id)
        if version is None:
            raise ValueError("document version not found")
        if version.status not in {"validated", "active"}:
            raise ValueError(
                "only validated or active versions can be approved"
            )
        version.approved_at = datetime.now(UTC)
        version.approved_by = approved_by
        self._session.flush()

    def active_version_ids(self, product_id: str) -> tuple[str, ...]:
        ids = self._session.scalars(
            select(ProductDocumentBinding.active_version_id).where(
                ProductDocumentBinding.product_id == product_id,
                ProductDocumentBinding.active_version_id.is_not(None),
            )
        ).all()
        return tuple(value for value in ids if value is not None)

    def active_index_version(self, product_id: str) -> str | None:
        binding = self._session.get(ProductIndexBinding, product_id)
        return None if binding is None else binding.index_version_id

    def active_version_id_for_document(
        self,
        product_id: str,
        document_id: str,
    ) -> str | None:
        binding = self._session.scalar(
            select(ProductDocumentBinding).where(
                ProductDocumentBinding.product_id == product_id,
                ProductDocumentBinding.document_id == document_id,
            )
        )
        return None if binding is None else binding.active_version_id

    def list_versions_for_product(
        self,
        product_id: str,
    ) -> tuple[DocumentVersionRecord, ...]:
        versions = self._session.execute(
            select(DocumentVersion, FileBlob.original_filename)
            .join(FileBlob, FileBlob.id == DocumentVersion.file_blob_id)
            .join(
                ProductDocumentBinding,
                ProductDocumentBinding.document_id
                == DocumentVersion.document_id,
            )
            .where(ProductDocumentBinding.product_id == product_id)
            .order_by(DocumentVersion.received_at.desc())
        ).all()
        return tuple(
            record
            for version, document_name in versions
            if (
                record := self._record(
                    version,
                    document_name=document_name,
                )
            )
            is not None
        )

    def list_pending_approval_product_ids(self) -> tuple[str, ...]:
        product_ids = self._session.scalars(
            select(ProductDocumentBinding.product_id)
            .join(
                DocumentVersion,
                DocumentVersion.document_id
                == ProductDocumentBinding.document_id,
            )
            .where(
                DocumentVersion.requires_manual_approval.is_(True),
                DocumentVersion.approved_at.is_(None),
            )
            .distinct()
            .order_by(ProductDocumentBinding.product_id)
        ).all()
        return tuple(product_ids)

    def list_approved_product_ids(self) -> tuple[str, ...]:
        product_ids = self._session.scalars(
            select(ProductDocumentBinding.product_id)
            .join(
                DocumentVersion,
                DocumentVersion.document_id
                == ProductDocumentBinding.document_id,
            )
            .where(
                DocumentVersion.approved_at.is_not(None),
                DocumentVersion.status == "validated",
            )
            .distinct()
            .order_by(ProductDocumentBinding.product_id)
        ).all()
        return tuple(product_ids)

    def list_published_product_ids(self) -> tuple[str, ...]:
        product_ids = self._session.scalars(
            select(ProductDocumentBinding.product_id)
            .join(
                DocumentVersion,
                DocumentVersion.document_id
                == ProductDocumentBinding.document_id,
            )
            .where(DocumentVersion.status == "active")
            .distinct()
            .order_by(ProductDocumentBinding.product_id)
        ).all()
        return tuple(product_ids)

    def get_version_status(self, version_id: str) -> str | None:
        version = self._session.get(DocumentVersion, version_id)
        return None if version is None else version.status

    def document_id_for_version(self, version_id: str) -> str:
        version = self._session.get(DocumentVersion, version_id)
        if version is None:
            raise ValueError("document version not found")
        return version.document_id

    def _record(
        self,
        entity: DocumentVersion | None,
        *,
        document_name: str | None = None,
    ) -> DocumentVersionRecord | None:
        if entity is None:
            return None
        return DocumentVersionRecord(
            id=entity.id,
            document_id=entity.document_id,
            sha256=entity.sha256,
            version_key=entity.version_key,
            version_label=entity.version_label,
            status=entity.status,
            requires_manual_approval=entity.requires_manual_approval,
            approved_at=entity.approved_at,
            approved_by=entity.approved_by,
            document_name=document_name,
        )
