from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from rag_app.ingestion import (
    ChunkPayload,
    EmbeddingPayload,
    ExistingVersion,
    IngestDocument,
    IngestionService,
    ParsedDocument,
)


@dataclass
class FakeStore:
    existing: ExistingVersion | None = None
    linked: list[tuple[str, str, str]] = field(default_factory=list)
    created: int = 0
    activated: bool = False
    failed: bool = False

    def find_by_sha(self, sha256: str) -> ExistingVersion | None:
        return self.existing

    def link_existing(
        self,
        version_id: str,
        product_id: str,
        document_id: str,
    ) -> None:
        self.linked.append((version_id, product_id, document_id))

    def create_version(self, command: IngestDocument) -> str:
        self.created += 1
        return "version-new"

    def save_chunks(
        self,
        version_id: str,
        chunks: tuple[ChunkPayload, ...],
    ) -> None:
        pass

    def mark_indexed(self, version_id: str, chunk_count: int) -> None:
        pass

    def activate(
        self,
        product_id: str,
        document_id: str,
        version_id: str,
    ) -> None:
        self.activated = True

    def mark_failed(self, version_id: str, message: str) -> None:
        self.failed = True


@dataclass
class FakeParser:
    calls: int = 0

    def parse(self, path: Path) -> ParsedDocument:
        self.calls += 1
        return ParsedDocument(blocks=("安全说明",))


@dataclass
class FakeChunker:
    calls: int = 0

    def chunk(self, document: ParsedDocument) -> tuple[ChunkPayload, ...]:
        self.calls += 1
        return (
            ChunkPayload(
                chunk_id="chunk-1",
                content="请勿拆机。",
                page=1,
            ),
        )


@dataclass
class FakeEmbedder:
    calls: int = 0

    def embed(self, texts: tuple[str, ...]) -> tuple[EmbeddingPayload, ...]:
        self.calls += 1
        return tuple(
            EmbeddingPayload(dense=(1.0, 0.0), sparse={1: 1.0})
            for _ in texts
        )


@dataclass
class FakeIndexWriter:
    calls: int = 0
    fail: bool = False

    def write(
        self,
        version_id: str,
        chunks: tuple[ChunkPayload, ...],
        embeddings: tuple[EmbeddingPayload, ...],
    ) -> int:
        self.calls += 1
        if self.fail:
            raise RuntimeError("index failed")
        return len(chunks)


def command() -> IngestDocument:
    return IngestDocument(
        document_id="doc-1",
        product_id="product-1",
        path=Path("manual.pdf"),
        sha256="a" * 64,
        received_at=datetime(2026, 10, 26, tzinfo=UTC),
        version_label="2026.1",
        metadata_confidence="high",
        document_types=("user_guide",),
    )


def service(
    store: FakeStore,
    parser: FakeParser,
    chunker: FakeChunker,
    embedder: FakeEmbedder,
    writer: FakeIndexWriter,
) -> IngestionService:
    return IngestionService(
        store=store,
        parser=parser,
        chunker=chunker,
        embedder=embedder,
        writer=writer,
    )


def test_duplicate_sha_links_existing_without_reprocessing() -> None:
    store = FakeStore(ExistingVersion("version-old", "active"))
    parser = FakeParser()
    chunker = FakeChunker()
    embedder = FakeEmbedder()
    writer = FakeIndexWriter()

    result = service(store, parser, chunker, embedder, writer).ingest(command())

    assert result.duplicate is True
    assert result.version_id == "version-old"
    assert store.linked == [("version-old", "product-1", "doc-1")]
    assert parser.calls == chunker.calls == embedder.calls == writer.calls == 0


def test_new_version_is_indexed_before_activation() -> None:
    store = FakeStore()
    parser = FakeParser()
    chunker = FakeChunker()
    embedder = FakeEmbedder()
    writer = FakeIndexWriter()

    result = service(store, parser, chunker, embedder, writer).ingest(command())

    assert result.duplicate is False
    assert result.version_id == "version-new"
    assert store.activated is True
    assert parser.calls == chunker.calls == embedder.calls == writer.calls == 1


def test_index_failure_marks_version_failed_without_activation() -> None:
    store = FakeStore()
    writer = FakeIndexWriter(fail=True)

    with pytest.raises(RuntimeError, match="index failed"):
        service(
            store,
            FakeParser(),
            FakeChunker(),
            FakeEmbedder(),
            writer,
        ).ingest(command())

    assert store.failed is True
    assert store.activated is False
