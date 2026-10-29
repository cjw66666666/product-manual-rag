from dataclasses import dataclass
from typing import Protocol

from rag_app.retrieval.fusion import reciprocal_rank_fusion
from rag_app.retrieval.models import RankedCandidate


@dataclass(frozen=True, slots=True)
class EncodedQuery:
    dense: tuple[float, ...]
    sparse: dict[int, float]


@dataclass(frozen=True, slots=True)
class SearchHit:
    chunk_id: str
    content: str
    page: int
    product_id: str | None = None
    document_version_id: str | None = None
    index_version_id: str | None = None
    document_sha256: str | None = None
    document_name: str | None = None
    version_label: str | None = None
    section_path: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvidenceHit:
    chunk_id: str
    content: str
    page: int
    score: float
    product_id: str | None = None
    document_version_id: str | None = None
    index_version_id: str | None = None
    document_sha256: str | None = None
    document_name: str | None = None
    version_label: str | None = None
    section_path: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RetrievalTrace:
    dense: tuple[SearchHit, ...]
    sparse: tuple[SearchHit, ...]
    rrf: tuple[SearchHit, ...]
    reranked: tuple[EvidenceHit, ...]
    final: tuple[EvidenceHit, ...]


class QueryEncoder(Protocol):
    def encode(
        self,
        question: str,
        *,
        document_version_ids: tuple[str, ...],
        index_version_id: str,
    ) -> EncodedQuery: ...


class DenseSearch(Protocol):
    def search(
        self,
        vector: tuple[float, ...],
        *,
        product_id: str,
        document_version_ids: tuple[str, ...],
        index_version_id: str,
        limit: int,
    ) -> tuple[SearchHit, ...]: ...


class SparseSearch(Protocol):
    def search(
        self,
        vector: dict[int, float],
        *,
        product_id: str,
        document_version_ids: tuple[str, ...],
        index_version_id: str,
        limit: int,
    ) -> tuple[SearchHit, ...]: ...


class Reranker(Protocol):
    def rerank(
        self,
        question: str,
        hits: tuple[SearchHit, ...],
    ) -> tuple[EvidenceHit, ...]: ...


class RetrievalObserver(Protocol):
    def record(self, trace: RetrievalTrace) -> None: ...


class HybridRetrievalService:
    def __init__(
        self,
        *,
        encoder: QueryEncoder,
        dense_search: DenseSearch,
        sparse_search: SparseSearch,
        reranker: Reranker,
        coarse_limit: int = 30,
        rerank_limit: int = 20,
        final_limit: int = 6,
        observer: RetrievalObserver | None = None,
    ) -> None:
        self._encoder = encoder
        self._dense_search = dense_search
        self._sparse_search = sparse_search
        self._reranker = reranker
        self._coarse_limit = coarse_limit
        self._rerank_limit = rerank_limit
        self._final_limit = final_limit
        self._observer = observer

    def search(
        self,
        question: str,
        *,
        product_id: str,
        document_version_ids: tuple[str, ...],
        index_version_id: str,
    ) -> tuple[EvidenceHit, ...]:
        encoded = self._encoder.encode(
            question,
            document_version_ids=document_version_ids,
            index_version_id=index_version_id,
        )
        dense = self._dense_search.search(
            encoded.dense,
            product_id=product_id,
            document_version_ids=document_version_ids,
            index_version_id=index_version_id,
            limit=self._coarse_limit,
        )
        sparse = self._sparse_search.search(
            encoded.sparse,
            product_id=product_id,
            document_version_ids=document_version_ids,
            index_version_id=index_version_id,
            limit=self._coarse_limit,
        )

        by_id = {
            item.chunk_id: item
            for item in (*dense, *sparse)
        }
        fused = reciprocal_rank_fusion(
            tuple(
                RankedCandidate(item.chunk_id, rank)
                for rank, item in enumerate(dense, start=1)
            ),
            tuple(
                RankedCandidate(item.chunk_id, rank)
                for rank, item in enumerate(sparse, start=1)
            ),
            limit=self._coarse_limit,
        )
        rrf_hits = tuple(by_id[item.chunk_id] for item in fused)
        candidates = rrf_hits[: self._rerank_limit]
        reranked = self._reranker.rerank(question, candidates)
        final = reranked[: self._final_limit]
        if self._observer is not None:
            self._observer.record(
                RetrievalTrace(
                    dense=dense,
                    sparse=sparse,
                    rrf=rrf_hits,
                    reranked=reranked,
                    final=final,
                )
            )
        return final
