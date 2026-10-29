from typing import Protocol

from rag_app.qdrant_index import IndexFilter, IndexHit
from rag_app.retrieval import SearchHit


class IndexSearcher(Protocol):
    def search_dense(
        self,
        vector: tuple[float, ...],
        filters: IndexFilter,
        limit: int,
    ) -> tuple[IndexHit, ...]: ...

    def search_sparse(
        self,
        vector: dict[int, float],
        filters: IndexFilter,
        limit: int,
    ) -> tuple[IndexHit, ...]: ...


def _to_hit(hit: IndexHit) -> SearchHit:
    content = hit.payload.get("content")
    page = hit.payload.get("page")
    if not isinstance(content, str) or not isinstance(page, int):
        raise ValueError("Qdrant payload is missing content or page")
    section_path = hit.payload.get("section_path")
    return SearchHit(
        chunk_id=hit.id,
        content=content,
        page=page,
        product_id=_optional_str(hit.payload, "product_id"),
        document_version_id=_optional_str(
            hit.payload,
            "document_version_id",
        ),
        index_version_id=_optional_str(hit.payload, "index_version_id"),
        document_sha256=_optional_str(hit.payload, "document_sha256"),
        document_name=_optional_str(hit.payload, "document_name"),
        version_label=_optional_str(hit.payload, "version_label"),
        section_path=tuple(
            item for item in section_path if isinstance(item, str)
        )
        if isinstance(section_path, list)
        else (),
    )


def _optional_str(
    payload: dict[str, object],
    key: str,
) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


class QdrantDenseSearch:
    def __init__(self, index: IndexSearcher) -> None:
        self._index = index

    def search(
        self,
        vector: tuple[float, ...],
        *,
        product_id: str,
        document_version_ids: tuple[str, ...],
        index_version_id: str,
        limit: int,
    ) -> tuple[SearchHit, ...]:
        hits = self._index.search_dense(
            vector,
            IndexFilter(
                product_id,
                document_version_ids,
                index_version_id,
            ),
            limit,
        )
        return tuple(_to_hit(hit) for hit in hits)


class QdrantSparseSearch:
    def __init__(self, index: IndexSearcher) -> None:
        self._index = index

    def search(
        self,
        vector: dict[int, float],
        *,
        product_id: str,
        document_version_ids: tuple[str, ...],
        index_version_id: str,
        limit: int,
    ) -> tuple[SearchHit, ...]:
        hits = self._index.search_sparse(
            vector,
            IndexFilter(
                product_id,
                document_version_ids,
                index_version_id,
            ),
            limit,
        )
        return tuple(_to_hit(hit) for hit in hits)
