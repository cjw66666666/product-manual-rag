from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IndexPoint:
    id: str
    dense: tuple[float, ...]
    sparse: dict[int, float]
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class IndexFilter:
    product_id: str
    document_version_ids: tuple[str, ...]
    index_version_id: str


@dataclass(frozen=True, slots=True)
class IndexHit:
    id: str
    score: float
    payload: dict[str, object]
