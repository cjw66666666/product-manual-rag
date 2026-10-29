from collections.abc import Sequence

from rag_app.retrieval.models import FusedCandidate, RankedCandidate


def reciprocal_rank_fusion(
    dense: Sequence[RankedCandidate],
    sparse: Sequence[RankedCandidate],
    limit: int = 20,
    rrf_k: int = 60,
) -> tuple[FusedCandidate, ...]:
    if limit < 1:
        raise ValueError("limit must be positive")
    if rrf_k < 1:
        raise ValueError("rrf_k must be positive")

    scores: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    sequence = 0

    for ranking in (dense, sparse):
        seen: set[str] = set()
        for candidate in ranking:
            if candidate.chunk_id in seen:
                raise ValueError("duplicate chunk id in ranking")
            if candidate.rank < 1:
                raise ValueError("rank must be positive")
            seen.add(candidate.chunk_id)
            scores[candidate.chunk_id] = scores.get(candidate.chunk_id, 0.0) + (
                1.0 / (rrf_k + candidate.rank)
            )
            if candidate.chunk_id not in first_seen:
                first_seen[candidate.chunk_id] = sequence
                sequence += 1

    ordered = sorted(
        scores.items(),
        key=lambda item: (-item[1], first_seen[item[0]]),
    )
    return tuple(
        FusedCandidate(chunk_id=chunk_id, score=score)
        for chunk_id, score in ordered[:limit]
    )
