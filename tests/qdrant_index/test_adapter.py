from typing import cast

from qdrant_client import QdrantClient

from rag_app.qdrant_index import IndexFilter, IndexPoint, QdrantIndex


def make_point(
    chunk_id: str,
    product_id: str,
    document_version_id: str,
    index_version_id: str,
    dense: tuple[float, ...],
) -> IndexPoint:
    return IndexPoint(
        id=chunk_id,
        dense=dense,
        sparse={1: 1.0},
        payload={
            "chunk_id": chunk_id,
            "product_id": product_id,
            "document_version_id": document_version_id,
            "index_version_id": index_version_id,
            "content": chunk_id,
        },
    )


def test_dense_search_respects_product_and_index_filter() -> None:
    client = QdrantClient(":memory:")
    index = QdrantIndex(client, collection_name="chunks")
    index.ensure_collection(3)
    index.upsert(
        [
            make_point("p1", "product-a", "v1", "i1", (1.0, 0.0, 0.0)),
            make_point("p2", "product-b", "v1", "i1", (1.0, 0.0, 0.0)),
            make_point("p3", "product-a", "v1", "i2", (1.0, 0.0, 0.0)),
        ]
    )

    hits = index.search_dense(
        (1.0, 0.0, 0.0),
        IndexFilter(
            product_id="product-a",
            document_version_ids=("v1",),
            index_version_id="i1",
        ),
        limit=10,
    )

    assert [hit.id for hit in hits] == ["p1"]


def test_same_point_id_is_idempotent() -> None:
    client = QdrantClient(":memory:")
    index = QdrantIndex(client, collection_name="chunks")
    index.ensure_collection(3)
    point = make_point("p1", "product-a", "v1", "i1", (1.0, 0.0, 0.0))

    index.upsert([point])
    index.upsert([point])

    hits = index.search_dense(
        (1.0, 0.0, 0.0),
        IndexFilter("product-a", ("v1",), "i1"),
        limit=10,
    )

    assert [hit.id for hit in hits] == ["p1"]


def test_delete_document_version_removes_only_matching_points() -> None:
    client = QdrantClient(":memory:")
    index = QdrantIndex(client, collection_name="chunks")
    index.ensure_collection(3)
    index.upsert(
        [
            make_point("p1", "product-a", "v1", "i1", (1.0, 0.0, 0.0)),
            make_point("p2", "product-a", "v2", "i1", (1.0, 0.0, 0.0)),
        ]
    )

    index.delete_document_version("v1", "i1")

    hits = index.search_dense(
        (1.0, 0.0, 0.0),
        IndexFilter("product-a", ("v1", "v2"), "i1"),
        limit=10,
    )
    assert [hit.id for hit in hits] == ["p2"]


def test_replace_document_version_removes_stale_chunk_ids() -> None:
    client = QdrantClient(":memory:")
    index = QdrantIndex(client, collection_name="chunks")
    index.ensure_collection(3)
    old = make_point("old", "product-a", "v1", "i1", (1.0, 0.0, 0.0))
    index.upsert([old])
    replacement = make_point(
        "new",
        "product-a",
        "v1",
        "i1",
        (1.0, 0.0, 0.0),
    )

    index.replace_document_version("v1", "i1", [replacement])

    hits = index.search_dense(
        (1.0, 0.0, 0.0),
        IndexFilter("product-a", ("v1",), "i1"),
        limit=10,
    )
    assert [hit.id for hit in hits] == ["new"]


def test_upsert_splits_large_point_sets_into_batches() -> None:
    class CapturingClient:
        def __init__(self) -> None:
            self.batch_sizes: list[int] = []

        def upsert(self, **kwargs: object) -> None:
            points = kwargs["points"]
            assert isinstance(points, list)
            self.batch_sizes.append(len(points))

    client = CapturingClient()
    index = QdrantIndex(
        cast(QdrantClient, client),
        collection_name="chunks",
        batch_size=2,
    )
    points = [
        make_point(f"p{index}", "product-a", "v1", "i1", (1.0, 0.0, 0.0))
        for index in range(5)
    ]

    index.upsert(points)

    assert client.batch_sizes == [2, 2, 1]
