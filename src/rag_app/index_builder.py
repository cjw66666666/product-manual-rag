from collections.abc import Sequence

from rag_app.chunking import ChunkDraft
from rag_app.qdrant_index import IndexPoint
from rag_app.remote_models import DenseEmbedding


def build_index_points(
    *,
    document_version_id: str,
    index_version_id: str,
    product_id: str,
    chunk_ids: Sequence[str],
    chunks: Sequence[ChunkDraft],
    embeddings: Sequence[DenseEmbedding],
    sparse_vectors: Sequence[dict[int, float]],
    document_sha256: str | None = None,
    document_name: str | None = None,
    version_label: str | None = None,
) -> tuple[IndexPoint, ...]:
    if not (
        len(chunk_ids)
        == len(chunks)
        == len(embeddings)
        == len(sparse_vectors)
    ):
        raise ValueError("chunk id, chunk, embedding, and sparse counts differ")
    points: list[IndexPoint] = []
    for chunk_id, chunk, embedding, sparse in zip(
        chunk_ids,
        chunks,
        embeddings,
        sparse_vectors,
        strict=True,
    ):
        points.append(
            IndexPoint(
                id=chunk_id,
                dense=embedding.vector,
                sparse=sparse,
                payload={
                    "chunk_id": chunk_id,
                    "document_version_id": document_version_id,
                    "index_version_id": index_version_id,
                    "product_id": product_id,
                    "document_sha256": document_sha256,
                    "document_name": document_name,
                    "version_label": version_label,
                    "content": chunk.content,
                    "page": chunk.page_start,
                    "section_path": list(chunk.section_path),
                    "section_types": list(chunk.section_types),
                    "has_images": chunk.has_images,
                },
            )
        )
    return tuple(points)
