from rag_app.application import QdrantDenseSearch, QdrantSparseSearch
from rag_app.qdrant_index import IndexFilter, IndexHit


class FakeIndex:
    def __init__(self, mode: str) -> None:
        self.mode = mode

    def search_dense(
        self,
        vector: tuple[float, ...],
        filters: IndexFilter,
        limit: int,
    ) -> tuple[IndexHit, ...]:
        assert self.mode == "dense"
        assert vector == (1.0, 0.0)
        assert filters.index_version_id == "i1"
        return (IndexHit("chunk-1", 0.9, {
            "content": "x",
            "page": 3,
            "product_id": "p1",
            "document_version_id": "v1",
            "index_version_id": "i1",
            "document_sha256": "a" * 64,
            "document_name": "manual.pdf",
            "version_label": "2.1",
            "section_path": ["安全", "充电"],
        }),)

    def search_sparse(
        self,
        vector: dict[int, float],
        filters: IndexFilter,
        limit: int,
    ) -> tuple[IndexHit, ...]:
        assert self.mode == "sparse"
        assert vector == {1: 0.5}
        return (IndexHit("chunk-1", 0.8, {"content": "x", "page": 3}),)


def test_dense_adapter_maps_search_hit() -> None:
    hit = QdrantDenseSearch(FakeIndex("dense")).search(
        (1.0, 0.0),
        product_id="p1",
        document_version_ids=("v1",),
        index_version_id="i1",
        limit=10,
    )[0]

    assert hit.chunk_id == "chunk-1"
    assert hit.content == "x"
    assert hit.page == 3
    assert hit.product_id == "p1"
    assert hit.document_version_id == "v1"
    assert hit.document_sha256 == "a" * 64
    assert hit.document_name == "manual.pdf"
    assert hit.version_label == "2.1"
    assert hit.section_path == ("安全", "充电")


def test_sparse_adapter_maps_search_hit() -> None:
    hit = QdrantSparseSearch(FakeIndex("sparse")).search(
        {1: 0.5},
        product_id="p1",
        document_version_ids=("v1",),
        index_version_id="i1",
        limit=10,
    )[0]

    assert hit.chunk_id == "chunk-1"
