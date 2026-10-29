from rag_app.chunking import ChunkDraft
from rag_app.index_builder import build_index_points
from rag_app.remote_models import DenseEmbedding


def test_build_index_points_carries_filters_and_vectors() -> None:
    points = build_index_points(
        document_version_id="v1",
        index_version_id="i1",
        product_id="p1",
        chunk_ids=("db-chunk-1",),
        chunks=(
            ChunkDraft(
                content="请勿拆机。",
                page_start=3,
                page_end=3,
                section_path=("安全",),
                section_types=("safety",),
            ),
        ),
        embeddings=(DenseEmbedding((1.0, 0.0), "model"),),
        sparse_vectors=({1: 1.0},),
        document_sha256="a" * 64,
        document_name="manual.pdf",
        version_label="2.1",
    )

    assert points[0].payload["document_version_id"] == "v1"
    assert points[0].payload["index_version_id"] == "i1"
    assert points[0].payload["product_id"] == "p1"
    assert points[0].id == "db-chunk-1"
    assert points[0].payload["chunk_id"] == "db-chunk-1"
    assert points[0].payload["document_sha256"] == "a" * 64
    assert points[0].payload["document_name"] == "manual.pdf"
    assert points[0].payload["version_label"] == "2.1"
