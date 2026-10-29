from pathlib import Path

from rag_app.application import CompensatingIndexer, IndexingCommand
from rag_app.indexing_pipeline import IndexingResult


class Pipeline:
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
    ) -> IndexingResult:
        return IndexingResult(2)


class Publisher:
    fail_activation: bool = False
    failed: bool = False

    def publish(
        self,
        *,
        product_id: str,
        document_version_id: str,
        index_version_id: str,
        chunk_count: int,
    ) -> bool:
        if self.fail_activation:
            raise RuntimeError("activation failed")
        return True

    def fail(self, version_id: str, index_id: str, message: str) -> None:
        self.failed = True


class Cleanup:
    called: bool = False

    def delete_document_version(self, version_id: str, index_id: str) -> None:
        self.called = True


def test_compensation_removes_qdrant_points_on_publish_failure() -> None:
    publisher = Publisher()
    publisher.fail_activation = True
    cleanup = Cleanup()
    indexer = CompensatingIndexer(
        pipeline=Pipeline(),
        publisher=publisher,
        cleanup=cleanup,
    )

    try:
        indexer.run(
            Path("manual.pdf"),
            command=IndexingCommand("a" * 64, "v1", "i1", "p1"),
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("publish failure must propagate")

    assert publisher.failed is True
    assert cleanup.called is True
