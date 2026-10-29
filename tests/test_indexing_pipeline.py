from dataclasses import dataclass
from pathlib import Path

from rag_app.chunking import ChunkDraft
from rag_app.indexing_pipeline import IndexingPipeline
from rag_app.pdf_parsing import ParsedPage, PdfParseResult
from rag_app.qdrant_index import IndexPoint
from rag_app.remote_models import DenseEmbedding
from rag_app.sparse_encoder import Bm25SparseEncoder, SparseStatistics


class Parser:
    def parse(self, path: Path) -> PdfParseResult:
        return PdfParseResult((ParsedPage(1, "请勿拆机。", 5),))


class Embedder:
    def embed(
        self,
        texts: tuple[str, ...],
        *,
        model: str,
    ) -> tuple[DenseEmbedding, ...]:
        return tuple(DenseEmbedding((1.0,), model) for _ in texts)


@dataclass
class ChunkStore:
    count: int = 0

    def replace_version_chunks(
        self,
        version_id: str,
        chunks: tuple[ChunkDraft, ...],
    ) -> tuple[str, ...]:
        self.count = len(chunks)
        return tuple(
            f"db-chunk-{index}" for index in range(len(chunks))
        )


@dataclass
class Index:
    count: int = 0
    points: tuple[IndexPoint, ...] = ()
    replaced: bool = False

    def replace_document_version(
        self,
        document_version_id: str,
        index_version_id: str,
        points: tuple[IndexPoint, ...],
    ) -> None:
        assert document_version_id == "v1"
        assert index_version_id == "i1"
        self.replaced = True
        self.count = len(points)
        self.points = points


@dataclass
class StatisticsStore:
    stored: SparseStatistics | None = None

    def save(
        self,
        *,
        document_version_id: str,
        index_version_id: str,
        statistics: SparseStatistics,
    ) -> None:
        self.stored = statistics


def test_pipeline_persists_and_indexes_chunks() -> None:
    store = ChunkStore()
    index = Index()
    statistics_store = StatisticsStore()
    result = IndexingPipeline(
        parser=Parser(),
        embedder=Embedder(),
        chunk_store=store,
        index=index,
        sparse_encoder=Bm25SparseEncoder(),
        statistics_store=statistics_store,
        embedding_model="model",
    ).run(
        Path("manual.pdf"),
        document_version_id="v1",
        index_version_id="i1",
        product_id="p1",
        document_sha256="a" * 64,
        document_name="manual.pdf",
        version_label="2.0",
    )

    assert result.chunk_count == 1
    assert store.count == 1
    assert index.count == 1
    assert index.replaced is True
    assert statistics_store.stored is not None
    assert statistics_store.stored.document_count == 1
    assert index.points[0].id == "db-chunk-0"
    assert index.points[0].payload["chunk_id"] == "db-chunk-0"
    assert index.points[0].payload["document_sha256"] == "a" * 64
    assert index.points[0].payload["document_name"] == "manual.pdf"
    assert index.points[0].payload["version_label"] == "2.0"
