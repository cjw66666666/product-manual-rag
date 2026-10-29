from typing import Protocol

from rag_app.persistence.index_cleanup_repository import CleanupJobRecord


class CleanupRepository(Protocol):
    def list_ready(self, *, limit: int) -> tuple[CleanupJobRecord, ...]: ...

    def mark_completed(self, job_id: str) -> None: ...

    def mark_failed(self, job_id: str, message: str) -> None: ...


class VersionCleanup(Protocol):
    def delete_document_version(
        self,
        document_version_id: str,
        index_version_id: str,
    ) -> None: ...


class Transaction(Protocol):
    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class IndexCleanupProcessor:
    def __init__(
        self,
        *,
        repository: CleanupRepository,
        cleanup: VersionCleanup,
        transaction: Transaction,
    ) -> None:
        self._repository = repository
        self._cleanup = cleanup
        self._transaction = transaction

    def run(self, *, max_jobs: int) -> int:
        if max_jobs < 1:
            raise ValueError("max_jobs must be positive")
        jobs = self._repository.list_ready(limit=max_jobs)
        for job in jobs:
            try:
                self._cleanup.delete_document_version(
                    job.document_version_id,
                    job.index_version_id,
                )
            except Exception as exc:
                self._transaction.rollback()
                self._repository.mark_failed(job.id, str(exc))
                self._transaction.commit()
                continue
            self._repository.mark_completed(job.id)
            self._transaction.commit()
        return len(jobs)
