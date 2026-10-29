from dataclasses import dataclass

from rag_app.worker import Job, WorkerLoop


@dataclass
class Queue:
    jobs: list[Job]
    completed: list[str]
    failed: list[tuple[str, str]]

    def claim(self) -> Job | None:
        return self.jobs.pop(0) if self.jobs else None

    def complete(self, job_id: str) -> None:
        self.completed.append(job_id)

    def fail(self, job_id: str, message: str) -> None:
        self.failed.append((job_id, message))


class Handler:
    def handle(self, job: Job) -> None:
        if job.payload == "bad":
            raise RuntimeError("boom")


class Transaction:
    def __init__(self) -> None:
        self.events: list[str] = []

    def commit(self) -> None:
        self.events.append("commit")

    def rollback(self) -> None:
        self.events.append("rollback")


class CommitFailureTransaction(Transaction):
    def __init__(self) -> None:
        super().__init__()
        self.commit_calls = 0

    def commit(self) -> None:
        self.commit_calls += 1
        if self.commit_calls == 1:
            raise RuntimeError("database unavailable")
        super().commit()


class RecoveringHandler(Handler):
    def __init__(self) -> None:
        self.recovered: list[tuple[str, str]] = []

    def recover(self, job: Job, message: str) -> None:
        self.recovered.append((job.id, message))


def test_worker_completes_and_fails_jobs() -> None:
    queue = Queue(
        jobs=[Job("1", "good"), Job("2", "bad")],
        completed=[],
        failed=[],
    )
    worker = WorkerLoop(queue=queue, handler=Handler())

    processed = worker.run(max_jobs=2)

    assert processed == 2
    assert queue.completed == ["1"]
    assert queue.failed == [("2", "boom")]


def test_worker_uses_one_transaction_per_job() -> None:
    queue = Queue(
        jobs=[Job("1", "good"), Job("2", "bad")],
        completed=[],
        failed=[],
    )
    transaction = Transaction()

    WorkerLoop(
        queue=queue,
        handler=Handler(),
        transaction=transaction,
    ).run(max_jobs=2)

    assert transaction.events == ["commit", "rollback", "commit"]


def test_worker_rolls_back_handler_failure_before_marking_job_failed() -> None:
    queue = Queue(
        jobs=[Job("1", "bad")],
        completed=[],
        failed=[],
    )
    transaction = Transaction()

    WorkerLoop(
        queue=queue,
        handler=Handler(),
        transaction=transaction,
    ).run(max_jobs=1)

    assert transaction.events == ["rollback", "commit"]
    assert queue.failed == [("1", "boom")]


def test_worker_recovers_external_effects_when_commit_fails() -> None:
    queue = Queue(
        jobs=[Job("1", "good")],
        completed=[],
        failed=[],
    )
    transaction = CommitFailureTransaction()
    handler = RecoveringHandler()

    WorkerLoop(
        queue=queue,
        handler=handler,
        transaction=transaction,
    ).run(max_jobs=1)

    assert transaction.events == ["rollback", "commit"]
    assert handler.recovered == [
        ("1", "transaction commit failed: database unavailable")
    ]
    assert queue.failed == [
        ("1", "transaction commit failed: database unavailable")
    ]


def test_worker_ends_transaction_when_queue_is_empty() -> None:
    queue = Queue(jobs=[], completed=[], failed=[])
    transaction = Transaction()

    processed = WorkerLoop(
        queue=queue,
        handler=Handler(),
        transaction=transaction,
    ).run(max_jobs=3)

    assert processed == 0
    assert transaction.events == ["commit"]
