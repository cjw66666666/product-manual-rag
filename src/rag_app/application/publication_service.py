from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from rag_app.persistence.document_index_repository import (
    DocumentIndexRecord,
    DocumentIndexRepository,
    DocumentIndexSummary,
)
from rag_app.persistence.repositories import (
    DocumentRepository,
    DocumentVersionRecord,
)


class VersionRepository(Protocol):
    def list_versions_for_product(
        self,
        product_id: str,
    ) -> tuple[DocumentVersionRecord, ...]: ...

    def list_pending_approval_product_ids(self) -> tuple[str, ...]: ...

    def approve_version(self, version_id: str, *, approved_by: str) -> None: ...

    def activate_version(
        self,
        product_id: str,
        document_id: str,
        version_id: str,
        index_version_id: str,
    ) -> None: ...

    def document_id_for_version(self, version_id: str) -> str: ...

    def active_version_id_for_document(
        self,
        product_id: str,
        document_id: str,
    ) -> str | None: ...

    def active_index_version(self, product_id: str) -> str | None: ...


class IndexRepository(Protocol):
    def get(
        self,
        document_version_id: str,
        index_version_id: str,
    ) -> DocumentIndexRecord | None: ...

    def list_for_version(
        self,
        document_version_id: str,
    ) -> tuple[DocumentIndexSummary, ...]: ...


class CleanupQueue(Protocol):
    def enqueue(
        self,
        document_version_id: str,
        index_version_id: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class VersionIndexView:
    index_version_id: str
    status: str
    chunk_count: int
    error_message: str | None


@dataclass(frozen=True, slots=True)
class VersionView:
    id: str
    document_id: str
    version_label: str | None
    status: str
    requires_manual_approval: bool
    approved_at: datetime | None
    approved_by: str | None
    document_name: str | None = None
    indexes: tuple[VersionIndexView, ...] = ()


class VersionPublicationService:
    def __init__(
        self,
        *,
        versions: VersionRepository,
        indexes: IndexRepository,
        cleanup_queue: CleanupQueue | None = None,
        commit: Callable[[], None] = lambda: None,
    ) -> None:
        self._versions = versions
        self._indexes = indexes
        self._cleanup_queue = cleanup_queue
        self._commit = commit

    def list_versions(self, product_id: str) -> tuple[VersionView, ...]:
        return tuple(
            VersionView(
                id=item.id,
                document_id=item.document_id,
                version_label=item.version_label,
                status=item.status,
                requires_manual_approval=item.requires_manual_approval,
                approved_at=item.approved_at,
                approved_by=item.approved_by,
                document_name=item.document_name,
                indexes=tuple(
                    VersionIndexView(
                        index_version_id=index.index_version_id,
                        status=index.status,
                        chunk_count=index.chunk_count,
                        error_message=index.error_message,
                    )
                    for index in self._indexes.list_for_version(item.id)
                ),
            )
            for item in self._versions.list_versions_for_product(product_id)
        )

    def list_pending_approval_product_ids(self) -> tuple[str, ...]:
        return self._versions.list_pending_approval_product_ids()

    def approve(self, version_id: str, *, approved_by: str) -> None:
        self._versions.approve_version(
            version_id,
            approved_by=approved_by,
        )
        self._commit()

    def publish(
        self,
        *,
        product_id: str,
        document_version_id: str,
        index_version_id: str,
    ) -> None:
        index = self._indexes.get(
            document_version_id,
            index_version_id,
        )
        if index is None or index.status != "completed":
            raise ValueError("document index is not completed")
        document_id = self._versions.document_id_for_version(
            document_version_id
        )
        previous_version_id = (
            self._versions.active_version_id_for_document(
                product_id,
                document_id,
            )
            if self._cleanup_queue is not None
            else None
        )
        previous_index_version_id = (
            self._versions.active_index_version(product_id)
            or index_version_id
        )
        self._versions.activate_version(
            product_id,
            document_id,
            document_version_id,
            index_version_id,
        )
        if (
            self._cleanup_queue is not None
            and previous_version_id is not None
            and previous_version_id != document_version_id
        ):
            self._cleanup_queue.enqueue(
                previous_version_id,
                previous_index_version_id,
            )
        self._commit()


def build_publication_service(
    *,
    versions: DocumentRepository,
    indexes: DocumentIndexRepository,
    commit: Callable[[], None],
    cleanup_queue: CleanupQueue | None = None,
) -> VersionPublicationService:
    return VersionPublicationService(
        versions=versions,
        indexes=indexes,
        cleanup_queue=cleanup_queue,
        commit=commit,
    )
