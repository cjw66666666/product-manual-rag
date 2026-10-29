from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    chunk_id: str
    rank: int


@dataclass(frozen=True, slots=True)
class FusedCandidate:
    chunk_id: str
    score: float
