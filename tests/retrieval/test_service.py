from dataclasses import dataclass

from rag_app.retrieval import (
    EncodedQuery,
    EvidenceHit,
    HybridRetrievalService,
    RetrievalTrace,
    SearchHit,
)


@dataclass
class FakeEncoder:
    def encode(
        self,
        question: str,
        *,
        document_version_ids: tuple[str, ...],
        index_version_id: str,
    ) -> EncodedQuery:
        assert document_version_ids
        assert index_version_id
        return EncodedQuery(dense=(1.0, 0.0), sparse={1: 1.0})


@dataclass
class FakeDenseSearch:
    hits: tuple[SearchHit, ...]
    received_limit: int = 0

    def search(
        self,
        vector: tuple[float, ...],
        *,
        product_id: str,
        document_version_ids: tuple[str, ...],
        index_version_id: str,
        limit: int,
    ) -> tuple[SearchHit, ...]:
        self.received_limit = limit
        return self.hits


@dataclass
class FakeSparseSearch:
    hits: tuple[SearchHit, ...]
    received_limit: int = 0

    def search(
        self,
        vector: dict[int, float],
        *,
        product_id: str,
        document_version_ids: tuple[str, ...],
        index_version_id: str,
        limit: int,
    ) -> tuple[SearchHit, ...]:
        self.received_limit = limit
        return self.hits


@dataclass
class FakeReranker:
    received_count: int = 0

    def rerank(
        self,
        question: str,
        hits: tuple[SearchHit, ...],
    ) -> tuple[EvidenceHit, ...]:
        self.received_count = len(hits)
        return tuple(
            EvidenceHit(
                chunk_id=hit.chunk_id,
                content=hit.content,
                page=hit.page,
                score=1.0 - index / 10,
            )
            for index, hit in enumerate(reversed(hits))
        )


class TraceRecorder:
    def __init__(self) -> None:
        self.traces: list[RetrievalTrace] = []

    def record(self, trace: RetrievalTrace) -> None:
        self.traces.append(trace)


def hit(chunk_id: str) -> SearchHit:
    return SearchHit(
        chunk_id=chunk_id,
        content=f"content-{chunk_id}",
        page=1,
    )


def test_hybrid_service_fuses_reranks_and_limits() -> None:
    dense = FakeDenseSearch((hit("a"), hit("b")))
    sparse = FakeSparseSearch((hit("b"), hit("c")))
    reranker = FakeReranker()

    result = HybridRetrievalService(
        encoder=FakeEncoder(),
        dense_search=dense,
        sparse_search=sparse,
        reranker=reranker,
    ).search(
        "question",
        product_id="p1",
        document_version_ids=("v1",),
        index_version_id="i1",
    )

    assert [item.chunk_id for item in result] == ["c", "a", "b"]
    assert dense.received_limit == 30
    assert sparse.received_limit == 30
    assert reranker.received_count == 3


def test_hybrid_service_records_each_retrieval_stage() -> None:
    recorder = TraceRecorder()
    service = HybridRetrievalService(
        encoder=FakeEncoder(),
        dense_search=FakeDenseSearch((hit("a"), hit("b"))),
        sparse_search=FakeSparseSearch((hit("b"), hit("c"))),
        reranker=FakeReranker(),
        observer=recorder,
    )

    service.search(
        "question",
        product_id="p1",
        document_version_ids=("v1",),
        index_version_id="i1",
    )

    assert len(recorder.traces) == 1
    trace = recorder.traces[0]
    assert [item.chunk_id for item in trace.dense] == ["a", "b"]
    assert [item.chunk_id for item in trace.sparse] == ["b", "c"]
    assert [item.chunk_id for item in trace.rrf] == ["b", "a", "c"]
    assert [item.chunk_id for item in trace.reranked] == ["c", "a", "b"]
    assert [item.chunk_id for item in trace.final] == ["c", "a", "b"]


def test_final_context_balances_rerank_and_rrf_ranks() -> None:
    hits = tuple(hit(chunk_id) for chunk_id in "abcdefghijkl")

    class OrderedReranker:
        def rerank(
            self,
            question: str,
            candidates: tuple[SearchHit, ...],
        ) -> tuple[EvidenceHit, ...]:
            order = ("a", "b", "c", "k", "d", "l", "h", "i", "j", "e", "g", "f")
            by_id = {item.chunk_id: item for item in candidates}
            return tuple(
                EvidenceHit(
                    chunk_id=chunk_id,
                    content=by_id[chunk_id].content,
                    page=by_id[chunk_id].page,
                    score=1.0 - index / 20,
                )
                for index, chunk_id in enumerate(order)
            )

    result = HybridRetrievalService(
        encoder=FakeEncoder(),
        dense_search=FakeDenseSearch(hits),
        sparse_search=FakeSparseSearch(hits),
        reranker=OrderedReranker(),
    ).search(
        "question",
        product_id="p1",
        document_version_ids=("v1",),
        index_version_id="i1",
    )

    assert [item.chunk_id for item in result] == [
        "a",
        "b",
        "c",
        "d",
        "k",
        "e",
    ]
