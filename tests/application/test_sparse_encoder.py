from rag_app.application import HashedSparseEncoder
from rag_app.sparse_encoder import Bm25SparseEncoder


def test_sparse_encoder_is_deterministic_and_preserves_model_code() -> None:
    encoder = HashedSparseEncoder()

    first = encoder.encode("C7 无法连接 Wi-Fi")
    second = encoder.encode("C7 无法连接 Wi-Fi")

    assert first == second
    assert first


def test_sparse_encoder_changes_with_text() -> None:
    encoder = HashedSparseEncoder()

    assert encoder.encode("开机") != encoder.encode("关机")


def test_bm25_query_weights_rare_terms_more_than_common_terms() -> None:
    encoder = Bm25SparseEncoder()
    statistics = encoder.fit((
        "开机 电源键",
        "开机 设置",
    ))

    common = encoder.encode_query("开机", statistics)
    rare = encoder.encode_query("电源键", statistics)

    assert next(iter(rare.values())) > next(iter(common.values()))
