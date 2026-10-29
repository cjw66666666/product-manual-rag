from pathlib import Path
from typing import Protocol

from rag_app.indexing_pipeline import IndexingResult
from rag_app.indexing_worker import IndexingCommand


class Pipeline(Protocol):
    def run(
        self,
        path: Path,
        *,
        document_version_id: str,
        index_version_id: str,
        product_id: str,
        document_sha256: str | None = None,
        document_name: str | None = None,
        version_label: str | None = None,
    ) -> IndexingResult: ...


class Publisher(Protocol):
    def publish(
        self,
        *,
        product_id: str,
        document_version_id: str,
        index_version_id: str,
        chunk_count: int,
    ) -> bool: ...

    def fail(
        self,
        document_version_id: str,
        index_version_id: str,
        message: str,
    ) -> None: ...


class Cleanup(Protocol):
    def delete_document_version(
        self,
        document_version_id: str,
        index_version_id: str,
    ) -> None: ...


class CompensatingIndexer:
    def __init__(
        self,
        *,
        pipeline: Pipeline,
        publisher: Publisher,
        cleanup: Cleanup,
    ) -> None:
        self._pipeline = pipeline
        self._publisher = publisher
        self._cleanup = cleanup

    def run(
        self,
        path: Path,
        *,
        command: IndexingCommand,
    ) -> IndexingResult:
        try:
            result = self._pipeline.run(
                path,
                document_version_id=command.document_version_id,
                index_version_id=command.index_version_id,
                product_id=command.product_id,
                document_sha256=command.sha256,
                document_name=command.document_name,
                version_label=command.version_label,
            )
            self._publisher.publish(
                product_id=command.product_id,
                document_version_id=command.document_version_id,
                index_version_id=command.index_version_id,
                chunk_count=result.chunk_count,
            )
            return result
        except Exception as exc:
            self._cleanup.delete_document_version(
                command.document_version_id,
                command.index_version_id,
            )
            self._publisher.fail(
                command.document_version_id,
                command.index_version_id,
                str(exc),
            )
            raise

    def recover(
        self,
        command: IndexingCommand,
        message: str,
    ) -> None:
        self._cleanup.delete_document_version(
            command.document_version_id,
            command.index_version_id,
        )
        self._publisher.fail(
            command.document_version_id,
            command.index_version_id,
            message,
        )
