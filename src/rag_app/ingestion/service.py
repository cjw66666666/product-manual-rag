from pathlib import Path
from typing import Protocol

from rag_app.ingestion.models import (
    ChunkPayload,
    EmbeddingPayload,
    ExistingVersion,
    IngestDocument,
    IngestionResult,
    ParsedDocument,
)


class DocumentStore(Protocol):
    def find_by_sha(self, sha256: str) -> ExistingVersion | None: ...

    def link_existing(
        self,
        version_id: str,
        product_id: str,
        document_id: str,
    ) -> None: ...

    def create_version(self, command: IngestDocument) -> str: ...

    def save_chunks(
        self,
        version_id: str,
        chunks: tuple[ChunkPayload, ...],
    ) -> None: ...

    def mark_indexed(self, version_id: str, chunk_count: int) -> None: ...

    def activate(
        self,
        product_id: str,
        document_id: str,
        version_id: str,
    ) -> None: ...

    def mark_failed(self, version_id: str, message: str) -> None: ...


class Parser(Protocol):
    def parse(self, path: Path) -> ParsedDocument: ...


class Chunker(Protocol):
    def chunk(self, document: ParsedDocument) -> tuple[ChunkPayload, ...]: ...


class Embedder(Protocol):
    def embed(
        self,
        texts: tuple[str, ...],
    ) -> tuple[EmbeddingPayload, ...]: ...


class IndexWriter(Protocol):
    def write(
        self,
        version_id: str,
        chunks: tuple[ChunkPayload, ...],
        embeddings: tuple[EmbeddingPayload, ...],
    ) -> int: ...


class IngestionService:
    def __init__(
        self,
        *,
        store: DocumentStore,
        parser: Parser,
        chunker: Chunker,
        embedder: Embedder,
        writer: IndexWriter,
    ) -> None:
        self._store = store
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._writer = writer

    def ingest(self, command: IngestDocument) -> IngestionResult:
        existing = self._store.find_by_sha(command.sha256)
        if existing is not None:
            self._store.link_existing(
                existing.version_id,
                command.product_id,
                command.document_id,
            )
            return IngestionResult(
                version_id=existing.version_id,
                duplicate=True,
                chunk_count=0,
            )

        version_id = self._store.create_version(command)
        try:
            parsed = self._parser.parse(command.path)
            chunks = self._chunker.chunk(parsed)
            if not chunks:
                raise ValueError("document produced no chunks")

            embeddings = self._embedder.embed(
                tuple(chunk.content for chunk in chunks)
            )
            if len(embeddings) != len(chunks):
                raise ValueError("embedding count does not match chunk count")

            self._store.save_chunks(version_id, chunks)
            indexed_count = self._writer.write(
                version_id,
                chunks,
                embeddings,
            )
            if indexed_count != len(chunks):
                raise ValueError("indexed count does not match chunk count")

            self._store.mark_indexed(version_id, indexed_count)
            self._store.activate(
                command.product_id,
                command.document_id,
                version_id,
            )
        except Exception as exc:
            self._store.mark_failed(version_id, str(exc))
            raise

        return IngestionResult(
            version_id=version_id,
            duplicate=False,
            chunk_count=len(chunks),
        )
