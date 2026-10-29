from dataclasses import dataclass

from rag_app.application.index_cleanup import IndexCleanupProcessor
from rag_app.persistence.index_cleanup_repository import CleanupJobRecord


@dataclass
class Repository:
    jobs: list[CleanupJobRecord]
    completed: list[str]
    failed: list[tuple[str, str]]

    def list_ready(self, *, limit: int) -> tuple[CleanupJobRecord, ...]:
        return tuple(self.jobs[:limit])

    def mark_completed(self, job_id: str) -> None:
        self.completed.append(job_id)

    def mark_failed(self, job_id: str, message: str) -> None:
        self.failed.append((job_id, message))


class Transaction:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class Cleanup:
    def __init__(self) -> None:
        self.deleted: list[tuple[str, str]] = []

    def delete_document_version(
        self,
        document_version_id: str,
        index_version_id: str,
    ) -> None:
        self.deleted.append((document_version_id, index_version_id))


class FailingCleanup(Cleanup):
    def delete_document_version(
        self,
        document_version_id: str,
        index_version_id: str,
    ) -> None:
        raise RuntimeError("qdrant unavailable")


def test_processor_completes_cleanup_after_qdrant_delete() -> None:
    repository = Repository(
        jobs=[CleanupJobRecord("j1", "old-version", "i1")],
        completed=[],
        failed=[],
    )
    transaction = Transaction()
    cleanup = Cleanup()

    processed = IndexCleanupProcessor(
        repository=repository,
        cleanup=cleanup,
        transaction=transaction,
    ).run(max_jobs=10)

    assert processed == 1
    assert cleanup.deleted == [("old-version", "i1")]
    assert repository.completed == ["j1"]
    assert repository.failed == []
    assert transaction.commits == 1


def test_processor_records_failure_without_stopping_next_job() -> None:
    repository = Repository(
        jobs=[
            CleanupJobRecord("j1", "old-version-1", "i1"),
            CleanupJobRecord("j2", "old-version-2", "i1"),
        ],
        completed=[],
        failed=[],
    )
    transaction = Transaction()

    processed = IndexCleanupProcessor(
        repository=repository,
        cleanup=FailingCleanup(),
        transaction=transaction,
    ).run(max_jobs=10)

    assert processed == 2
    assert repository.failed == [
        ("j1", "qdrant unavailable"),
        ("j2", "qdrant unavailable"),
    ]
    assert transaction.rollbacks == 2
    assert transaction.commits == 2
