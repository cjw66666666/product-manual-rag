from dataclasses import dataclass, field
from pathlib import Path

from rag_app.indexing_pipeline import IndexingResult
from rag_app.indexing_worker import (
    IndexingCommand,
    IndexingJobHandler,
)
from rag_app.worker import Job


class Contexts:
    def get(self, job_id: str) -> IndexingCommand:
        return IndexingCommand(
            sha256="a" * 64,
            document_version_id="v1",
            index_version_id="i1",
            product_id="p1",
        )


class Store:
    def path_for_sha256(self, digest: str) -> Path:
        return Path("manual.pdf")


@dataclass
class Indexer:
    calls: int = 0
    recovered: list[tuple[str, str]] = field(default_factory=list)

    def run(
        self,
        path: Path,
        *,
        command: IndexingCommand,
    ) -> IndexingResult:
        self.calls += 1
        return IndexingResult(chunk_count=3)

    def recover(
        self,
        command: IndexingCommand,
        message: str,
    ) -> None:
        self.recovered.append((command.document_version_id, message))


def test_indexing_handler_runs_pipeline_and_marks_success() -> None:
    indexer = Indexer()
    handler = IndexingJobHandler(
        contexts=Contexts(),
        file_store=Store(),
        indexer=indexer,
    )

    handler.handle(Job("job-1", "ignored"))

    assert indexer.calls == 1


def test_indexing_handler_recovers_failed_job() -> None:
    indexer = Indexer()
    handler = IndexingJobHandler(
        contexts=Contexts(),
        file_store=Store(),
        indexer=indexer,
    )

    handler.recover(Job("job-1", "ignored"), "commit failed")

    assert indexer.recovered == [("v1", "commit failed")]
