from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_app.persistence.schema import DocumentIndex, DocumentVersion


@dataclass(frozen=True, slots=True)
class DocumentIndexRecord:
    status: str
    chunk_count: int
    error_message: str | None


@dataclass(frozen=True, slots=True)
class DocumentIndexSummary:
    index_version_id: str
    status: str
    chunk_count: int
    error_message: str | None


class DocumentIndexRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def mark_success(
        self,
        document_version_id: str,
        index_version_id: str,
        chunk_count: int,
    ) -> None:
        entity = self._get_or_create(document_version_id, index_version_id)
        entity.status = "completed"
        entity.chunk_count = chunk_count
        entity.indexed_at = datetime.now(UTC)
        entity.error_code = None
        entity.error_message = None
        version = self._session.get(DocumentVersion, document_version_id)
        if version is None:
            raise ValueError("document version not found")
        if version.status in {"draft", "processing", "failed"}:
            version.status = "validated"
        self._session.flush()

    def mark_failure(
        self,
        document_version_id: str,
        index_version_id: str,
        message: str,
    ) -> None:
        entity = self._get_or_create(document_version_id, index_version_id)
        entity.status = "failed"
        entity.error_code = "indexing_failed"
        entity.error_message = message
        self._session.flush()

    def get(
        self,
        document_version_id: str,
        index_version_id: str,
    ) -> DocumentIndexRecord | None:
        entity = self._session.scalar(
            select(DocumentIndex).where(
                DocumentIndex.document_version_id == document_version_id,
                DocumentIndex.index_version_id == index_version_id,
            )
        )
        if entity is None:
            return None
        return DocumentIndexRecord(
            status=entity.status,
            chunk_count=entity.chunk_count,
            error_message=entity.error_message,
        )

    def list_for_version(
        self,
        document_version_id: str,
    ) -> tuple[DocumentIndexSummary, ...]:
        entities = self._session.scalars(
            select(DocumentIndex)
            .where(
                DocumentIndex.document_version_id == document_version_id
            )
            .order_by(DocumentIndex.index_version_id)
        ).all()
        return tuple(
            DocumentIndexSummary(
                index_version_id=entity.index_version_id,
                status=entity.status,
                chunk_count=entity.chunk_count,
                error_message=entity.error_message,
            )
            for entity in entities
        )

    def _get_or_create(
        self,
        document_version_id: str,
        index_version_id: str,
    ) -> DocumentIndex:
        entity = self._session.scalar(
            select(DocumentIndex).where(
                DocumentIndex.document_version_id == document_version_id,
                DocumentIndex.index_version_id == index_version_id,
            )
        )
        if entity is None:
            entity = DocumentIndex(
                document_version_id=document_version_id,
                index_version_id=index_version_id,
                status="processing",
                chunk_count=0,
            )
            self._session.add(entity)
            self._session.flush()
        return entity
