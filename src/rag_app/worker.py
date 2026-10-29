import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    payload: str


class JobQueue(Protocol):
    def claim(self) -> Job | None: ...

    def complete(self, job_id: str) -> None: ...

    def fail(self, job_id: str, message: str) -> None: ...


class JobHandler(Protocol):
    def handle(self, job: Job) -> None: ...


class Transaction(Protocol):
    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class WorkerLoop:
    def __init__(
        self,
        *,
        queue: JobQueue,
        handler: JobHandler,
        transaction: Transaction | None = None,
    ) -> None:
        self._queue = queue
        self._handler = handler
        self._transaction = transaction

    def run(self, *, max_jobs: int) -> int:
        if max_jobs < 1:
            raise ValueError("max_jobs must be positive")
        processed = 0
        while processed < max_jobs:
            job = self._queue.claim()
            if job is None:
                self._commit()
                break
            try:
                self._handler.handle(job)
                self._queue.complete(job.id)
            except Exception as exc:
                self._fail_after_rollback(job, str(exc))
            else:
                try:
                    self._commit()
                except Exception as exc:
                    self._fail_after_rollback(
                        job,
                        f"transaction commit failed: {exc}",
                    )
            processed += 1
        return processed

    def _fail_after_rollback(self, job: Job, message: str) -> None:
        self._rollback()
        recover = getattr(self._handler, "recover", None)
        if recover is not None:
            try:
                recover(job, message)
            except Exception:
                logger.exception(
                    "job recovery failed for %s",
                    job.id,
                )
        self._queue.fail(job.id, message)
        self._commit()

    def _commit(self) -> None:
        if self._transaction is not None:
            self._transaction.commit()

    def _rollback(self) -> None:
        if self._transaction is not None:
            self._transaction.rollback()
