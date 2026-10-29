from rag_app.application import Bm25QueryEncoder, RemoteQueryEncoder
from rag_app.remote_models import DenseEmbedding
from rag_app.sparse_encoder import SparseStatistics


class Embedder:
    def embed(
        self,
        texts: tuple[str, ...],
        *,
        model: str,
    ) -> tuple[DenseEmbedding, ...]:
        assert texts == ("怎么开机？",)
        assert model == "bge-m3"
        return (DenseEmbedding((1.0, 0.0), model),)


class Sparse:
    def encode(self, text: str) -> dict[int, float]:
        return {7: 1.0}


def test_remote_query_encoder_combines_dense_and_sparse() -> None:
    encoded = RemoteQueryEncoder(
        embedder=Embedder(),
        sparse_encoder=Sparse(),
        model="bge-m3",
    ).encode("怎么开机？")

    assert encoded.dense == (1.0, 0.0)
    assert encoded.sparse == {7: 1.0}


def test_bm25_query_encoder_uses_active_document_statistics() -> None:
    class Statistics:
        def aggregate(
            self,
            *,
            document_version_ids: tuple[str, ...],
            index_version_id: str,
        ) -> SparseStatistics:
            from rag_app.sparse_encoder import Bm25SparseEncoder

            assert document_version_ids == ("v1",)
            assert index_version_id == "i1"
            return Bm25SparseEncoder().fit(("开机 电源键",))

    encoded = Bm25QueryEncoder(
        embedder=Embedder(),
        statistics=Statistics(),
        model="bge-m3",
    ).encode(
        "怎么开机？",
        document_version_ids=("v1",),
        index_version_id="i1",
    )

    assert encoded.dense == (1.0, 0.0)
    assert encoded.sparse
