from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from rag_app.chunking import ChunkDraft
from rag_app.index_builder import build_index_points
from rag_app.pdf_chunking import build_page_chunks
from rag_app.pdf_parsing import PdfParseResult
from rag_app.qdrant_index import IndexPoint
from rag_app.remote_models import DenseEmbedding
from rag_app.sparse_encoder import (
    Bm25SparseEncoder,
    SparseStatistics,
)


class Parser(Protocol):
    def parse(self, path: Path) -> PdfParseResult: ...


class Embedder(Protocol):
    def embed(
        self,
        texts: tuple[str, ...],
        *,
        model: str,
    ) -> tuple[DenseEmbedding, ...]: ...


class ChunkStore(Protocol):
    def replace_version_chunks(
        self,
        version_id: str,
        chunks: tuple[ChunkDraft, ...],
    ) -> tuple[str, ...]: ...


class Index(Protocol):
    def replace_document_version(
        self,
        document_version_id: str,
        index_version_id: str,
        points: tuple[IndexPoint, ...],
    ) -> None: ...


class SparseStatisticsStore(Protocol):
    def save(
        self,
        *,
        document_version_id: str,
        index_version_id: str,
        statistics: SparseStatistics,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class IndexingResult:
    chunk_count: int


class IndexingPipeline:
    def __init__(
        self,
        *,
        parser: Parser,
        embedder: Embedder,
        chunk_store: ChunkStore,
        index: Index,
        sparse_encoder: Bm25SparseEncoder,
        statistics_store: SparseStatisticsStore,
        embedding_model: str,
    ) -> None:
        self._parser = parser
        self._embedder = embedder
        self._chunk_store = chunk_store
        self._index = index
        self._sparse_encoder = sparse_encoder
        self._statistics_store = statistics_store
        self._embedding_model = embedding_model

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
        parsed = self._parser.parse(path)
        chunks = build_page_chunks(parsed)
        if not chunks:
            raise ValueError("document produced no chunks")
        embeddings = self._embedder.embed(
            tuple(chunk.content for chunk in chunks),
            model=self._embedding_model,
        )
        if len(embeddings) != len(chunks):
            raise ValueError("embedding count does not match chunk count")
        chunk_ids = self._chunk_store.replace_version_chunks(
            document_version_id,
            chunks,
        )
        if len(chunk_ids) != len(chunks):
            raise ValueError("stored chunk count mismatch")
        statistics = self._sparse_encoder.fit(
            tuple(chunk.content for chunk in chunks)
        )
        sparse_vectors = tuple(
            self._sparse_encoder.encode_document(chunk.content, statistics)
            for chunk in chunks
        )
        self._statistics_store.save(
            document_version_id=document_version_id,
            index_version_id=index_version_id,
            statistics=statistics,
        )
        points = build_index_points(
            document_version_id=document_version_id,
            index_version_id=index_version_id,
            product_id=product_id,
            chunk_ids=chunk_ids,
            chunks=chunks,
            embeddings=embeddings,
            sparse_vectors=sparse_vectors,
            document_sha256=document_sha256,
            document_name=document_name,
            version_label=version_label,
        )
        self._index.replace_document_version(
            document_version_id,
            index_version_id,
            points,
        )
        return IndexingResult(chunk_count=len(chunks))
