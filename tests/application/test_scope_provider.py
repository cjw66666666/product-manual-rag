from rag_app.application import ProductIndexScopeProvider


class Versions:
    def active_version_ids(self, product_id: str) -> tuple[str, ...]:
        assert product_id == "huawei_c7"
        return ("v1", "v2")

    def active_index_version(self, product_id: str) -> str | None:
        assert product_id == "huawei_c7"
        return "product-index"


def test_scope_provider_combines_versions_and_index_version() -> None:
    scope = ProductIndexScopeProvider(
        versions=Versions(),
        index_version_id="index-1",
    ).current("huawei_c7")

    assert scope.document_version_ids == ("v1", "v2")
    assert scope.index_version_id == "product-index"


def test_scope_provider_uses_fallback_when_product_has_no_pointer() -> None:
    class NoPointerVersions(Versions):
        def active_index_version(self, product_id: str) -> str | None:
            return None

    scope = ProductIndexScopeProvider(
        versions=NoPointerVersions(),
        index_version_id="index-1",
    ).current("huawei_c7")

    assert scope.index_version_id == "index-1"
