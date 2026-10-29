from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    HasIdCondition,
    MatchAny,
    MatchValue,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from rag_app.qdrant_index.models import IndexFilter, IndexHit, IndexPoint


class QdrantIndex:
    def __init__(
        self,
        client: QdrantClient,
        *,
        collection_name: str = "chunks",
        batch_size: int = 128,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self._client = client
        self._collection_name = collection_name
        self._batch_size = batch_size

    def ensure_collection(self, dimension: int) -> None:
        if dimension < 1:
            raise ValueError("dimension must be positive")
        if self._client.collection_exists(self._collection_name):
            return
        self._client.create_collection(
            collection_name=self._collection_name,
            vectors_config={
                "dense": VectorParams(
                    size=dimension,
                    distance=Distance.COSINE,
                )
            },
            sparse_vectors_config={"sparse": SparseVectorParams()},
        )

    def upsert(self, points: Sequence[IndexPoint]) -> None:
        for offset in range(0, len(points), self._batch_size):
            batch = points[offset : offset + self._batch_size]
            self._client.upsert(
                collection_name=self._collection_name,
                points=[
                PointStruct(
                    id=str(uuid5(NAMESPACE_URL, point.id)),
                    vector={
                        "dense": list(point.dense),
                        "sparse": SparseVector(
                            indices=sorted(point.sparse),
                            values=[
                                point.sparse[index]
                                for index in sorted(point.sparse)
                            ],
                        ),
                    },
                    payload=point.payload,
                )
                for point in batch
                ],
                wait=True,
            )

    def replace_document_version(
        self,
        document_version_id: str,
        index_version_id: str,
        points: Sequence[IndexPoint],
    ) -> None:
        self.upsert(points)
        kept_ids: list[int | str | UUID] = [
            str(uuid5(NAMESPACE_URL, point.id)) for point in points
        ]
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_version_id",
                            match=MatchValue(value=document_version_id),
                        ),
                        FieldCondition(
                            key="index_version_id",
                            match=MatchValue(value=index_version_id),
                        ),
                    ],
                    must_not=[
                        HasIdCondition(has_id=kept_ids),
                    ],
                )
            ),
            wait=True,
        )

    def search_dense(
        self,
        vector: tuple[float, ...],
        filters: IndexFilter,
        limit: int,
    ) -> tuple[IndexHit, ...]:
        response = self._client.query_points(
            collection_name=self._collection_name,
            query=list(vector),
            using="dense",
            query_filter=self._filter(filters),
            limit=limit,
            with_payload=True,
        )
        return self._hits(response.points)

    def search_sparse(
        self,
        vector: dict[int, float],
        filters: IndexFilter,
        limit: int,
    ) -> tuple[IndexHit, ...]:
        response = self._client.query_points(
            collection_name=self._collection_name,
            query=SparseVector(
                indices=sorted(vector),
                values=[vector[index] for index in sorted(vector)],
            ),
            using="sparse",
            query_filter=self._filter(filters),
            limit=limit,
            with_payload=True,
        )
        return self._hits(response.points)

    def delete_document_version(
        self,
        document_version_id: str,
        index_version_id: str,
    ) -> None:
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_version_id",
                            match=MatchValue(value=document_version_id),
                        ),
                        FieldCondition(
                            key="index_version_id",
                            match=MatchValue(value=index_version_id),
                        ),
                    ]
                )
            ),
            wait=True,
        )

    def _filter(self, filters: IndexFilter) -> Filter:
        return Filter(
            must=[
                FieldCondition(
                    key="product_id",
                    match=MatchValue(value=filters.product_id),
                ),
                FieldCondition(
                    key="index_version_id",
                    match=MatchValue(value=filters.index_version_id),
                ),
                FieldCondition(
                    key="document_version_id",
                    match=MatchAny(
                        any=list(filters.document_version_ids)
                    ),
                ),
            ]
        )

    def _hits(self, points: Sequence[object]) -> tuple[IndexHit, ...]:
        hits: list[IndexHit] = []
        for point in points:
            payload = getattr(point, "payload", None) or {}
            chunk_id = payload.get("chunk_id")
            if not isinstance(chunk_id, str):
                continue
            hits.append(
                IndexHit(
                    id=chunk_id,
                    score=float(getattr(point, "score", 0.0)),
                    payload=payload,
                )
            )
        return tuple(hits)
