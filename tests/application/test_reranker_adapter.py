from rag_app.application import RemoteReranker
from rag_app.remote_models import RerankScore
from rag_app.retrieval import SearchHit


class Client:
    def rerank(
        self,
        query: str,
        documents: tuple[str, ...],
        *,
        model: str,
    ) -> tuple[RerankScore, ...]:
        assert documents == ("first", "second")
        return (RerankScore(1, 0.9), RerankScore(0, 0.2))


def test_remote_reranker_maps_sorted_scores() -> None:
    hits = (
        SearchHit("a", "first", 1),
        SearchHit("b", "second", 2),
    )

    result = RemoteReranker(
        client=Client(),
        model="reranker",
    ).rerank("question", hits)

    assert [item.chunk_id for item in result] == ["b", "a"]
    assert result[0].page == 2


def test_remote_reranker_falls_back_to_rrf_order_on_empty_response() -> None:
    class EmptyClient:
        def rerank(
            self,
            query: str,
            documents: tuple[str, ...],
            *,
            model: str,
        ) -> tuple[RerankScore, ...]:
            return ()

    hits = (
        SearchHit("a", "first", 1),
        SearchHit("b", "second", 2),
    )

    result = RemoteReranker(
        client=EmptyClient(),
        model="reranker",
    ).rerank("question", hits)

    assert [item.chunk_id for item in result] == ["a", "b"]
