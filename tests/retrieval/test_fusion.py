import pytest

from rag_app.retrieval import RankedCandidate, reciprocal_rank_fusion


def test_rrf_combines_rankings() -> None:
    result = reciprocal_rank_fusion(
        (RankedCandidate("a", 1), RankedCandidate("b", 2)),
        (RankedCandidate("b", 1), RankedCandidate("c", 2)),
        limit=3,
    )

    assert [item.chunk_id for item in result] == ["b", "a", "c"]


def test_rrf_is_deterministic_for_ties() -> None:
    result = reciprocal_rank_fusion(
        (RankedCandidate("z", 1), RankedCandidate("a", 2)),
        (),
        limit=2,
    )

    assert [item.chunk_id for item in result] == ["z", "a"]


def test_rrf_rejects_duplicate_chunk_in_one_ranking() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        reciprocal_rank_fusion(
            (RankedCandidate("a", 1), RankedCandidate("a", 2)),
            (),
        )


def test_rrf_rejects_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="limit"):
        reciprocal_rank_fusion((), (), limit=0)
