from typing import Protocol


class VersionLookup(Protocol):
    def document_id_for_version(self, version_id: str) -> str: ...

    def requires_manual_approval(self, version_id: str) -> bool: ...

    def active_version_id_for_document(
        self,
        product_id: str,
        document_id: str,
    ) -> str | None: ...

    def active_index_version(self, product_id: str) -> str | None: ...


class VersionActivator(Protocol):
    def activate_version(
        self,
        product_id: str,
        document_id: str,
        version_id: str,
        index_version_id: str,
    ) -> None: ...


class IndexStatus(Protocol):
    def mark_success(
        self,
        document_version_id: str,
        index_version_id: str,
        chunk_count: int,
    ) -> None: ...

    def mark_failure(
        self,
        document_version_id: str,
        index_version_id: str,
        message: str,
    ) -> None: ...


class CleanupQueue(Protocol):
    def enqueue(
        self,
        document_version_id: str,
        index_version_id: str,
    ) -> None: ...


class IndexPublicationService:
    def __init__(
        self,
        *,
        versions: VersionLookup,
        activator: VersionActivator,
        index_status: IndexStatus,
        cleanup_queue: CleanupQueue | None = None,
    ) -> None:
        self._versions = versions
        self._activator = activator
        self._index_status = index_status
        self._cleanup_queue = cleanup_queue

    def publish(
        self,
        *,
        product_id: str,
        document_version_id: str,
        index_version_id: str,
        chunk_count: int,
    ) -> bool:
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
        self._index_status.mark_success(
            document_version_id,
            index_version_id,
            chunk_count,
        )
        if self._versions.requires_manual_approval(document_version_id):
            return False
        self._activator.activate_version(
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
        return True

    def fail(
        self,
        document_version_id: str,
        index_version_id: str,
        message: str,
    ) -> None:
        self._index_status.mark_failure(
            document_version_id,
            index_version_id,
            message,
        )
