from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from rag_app.indexing_pipeline import IndexingResult
from rag_app.worker import Job


@dataclass(frozen=True, slots=True)
class IndexingCommand:
    sha256: str
    document_version_id: str
    index_version_id: str
    product_id: str
    document_name: str | None = None
    version_label: str | None = None


class ContextProvider(Protocol):
    def get(self, job_id: str) -> IndexingCommand: ...


class FileLocator(Protocol):
    def path_for_sha256(self, digest: str) -> Path: ...


class Indexer(Protocol):
    def run(
        self,
        path: Path,
        *,
        command: IndexingCommand,
    ) -> IndexingResult: ...

    def recover(
        self,
        command: IndexingCommand,
        message: str,
    ) -> None: ...


class IndexingJobHandler:
    def __init__(
        self,
        *,
        contexts: ContextProvider,
        file_store: FileLocator,
        indexer: Indexer,
    ) -> None:
        self._contexts = contexts
        self._file_store = file_store
        self._indexer = indexer

    def handle(self, job: Job) -> None:
        context = self._contexts.get(job.id)
        self._indexer.run(
            self._file_store.path_for_sha256(context.sha256),
            command=context,
        )

    def recover(self, job: Job, message: str) -> None:
        context = self._contexts.get(job.id)
        self._indexer.recover(context, message)
