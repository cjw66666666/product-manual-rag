from rag_app.application import IndexScope, RagRetriever
from rag_app.retrieval import EvidenceHit


class ScopeProvider:
    def current(self, product_id: str) -> IndexScope:
        assert product_id == "huawei_c7"
        return IndexScope(("version-1",), "index-1")


class Engine:
    def search(
        self,
        question: str,
        *,
        product_id: str,
        document_version_ids: tuple[str, ...],
        index_version_id: str,
    ) -> tuple[EvidenceHit, ...]:
        assert product_id == "huawei_c7"
        assert document_version_ids == ("version-1",)
        assert index_version_id == "index-1"
        return (
            EvidenceHit(
                "chunk-1",
                "按电源键开机。",
                10,
                0.9,
                product_id="huawei_c7",
                document_version_id="version-1",
                index_version_id="index-1",
                document_sha256="a" * 64,
                document_name="C7 manual.pdf",
                version_label="2.1",
                section_path=("基础使用", "开机"),
            ),
        )


def test_rag_retriever_maps_scope_and_evidence() -> None:
    evidence = RagRetriever(
        scope_provider=ScopeProvider(),
        engine=Engine(),
    ).retrieve("怎么开机？", "huawei_c7")

    assert evidence[0].chunk_id == "chunk-1"
    assert evidence[0].page == 10
    assert evidence[0].document_version_id == "version-1"
    assert evidence[0].document_sha256 == "a" * 64
    assert evidence[0].section_path == ("基础使用", "开机")
