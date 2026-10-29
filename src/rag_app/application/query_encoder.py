from typing import Protocol

from rag_app.remote_models import DenseEmbedding
from rag_app.retrieval import EncodedQuery
from rag_app.sparse_encoder import (
    Bm25SparseEncoder,
    SparseStatistics,
)


class DenseEmbedder(Protocol):
    def embed(
        self,
        texts: tuple[str, ...],
        *,
        model: str,
    ) -> tuple[DenseEmbedding, ...]: ...


class SparseEncoder(Protocol):
    def encode(self, text: str) -> dict[int, float]: ...


class RemoteQueryEncoder:
    def __init__(
        self,
        *,
        embedder: DenseEmbedder,
        sparse_encoder: SparseEncoder,
        model: str,
    ) -> None:
        self._embedder = embedder
        self._sparse_encoder = sparse_encoder
        self._model = model

    def encode(
        self,
        question: str,
        *,
        document_version_ids: tuple[str, ...] = (),
        index_version_id: str = "",
    ) -> EncodedQuery:
        del document_version_ids, index_version_id
        embeddings = self._embedder.embed((question,), model=self._model)
        if len(embeddings) != 1:
            raise ValueError("expected one query embedding")
        return EncodedQuery(
            dense=embeddings[0].vector,
            sparse=self._sparse_encoder.encode(question),
        )


class SparseStatisticsProvider(Protocol):
    def aggregate(
        self,
        *,
        document_version_ids: tuple[str, ...],
        index_version_id: str,
    ) -> SparseStatistics: ...


class Bm25QueryEncoder:
    def __init__(
        self,
        *,
        embedder: DenseEmbedder,
        statistics: SparseStatisticsProvider,
        model: str,
    ) -> None:
        self._embedder = embedder
        self._statistics = statistics
        self._model = model
        self._encoder = Bm25SparseEncoder()

    def encode(
        self,
        question: str,
        *,
        document_version_ids: tuple[str, ...],
        index_version_id: str,
    ) -> EncodedQuery:
        embeddings = self._embedder.embed((question,), model=self._model)
        if len(embeddings) != 1:
            raise ValueError("expected one query embedding")
        statistics = self._statistics.aggregate(
            document_version_ids=document_version_ids,
            index_version_id=index_version_id,
        )
        sparse = (
            self._encoder.encode_query(question, statistics)
            if statistics.document_count > 0
            else {}
        )
        return EncodedQuery(
            dense=embeddings[0].vector,
            sparse=sparse,
        )
