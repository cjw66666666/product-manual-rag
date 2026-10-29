from rag_app.catalog import Product, ProductCatalog, ProductCategory
from rag_app.metadata_extraction import extract_metadata

CATALOG = ProductCatalog(
    (
        Product(
            "huawei_c7",
            "华为平板 C7",
            ProductCategory.TABLET,
            ("C7", "DBY-W09"),
        ),
    )
)


def test_extracts_product_and_explicit_version() -> None:
    result = extract_metadata("华为平板 C7 用户指南\n版本号：V2.1.0", CATALOG)

    assert result.product_ids == ("huawei_c7",)
    assert result.version_label == "2.1.0"
    assert result.confidence == "high"


def test_product_only_is_medium_confidence() -> None:
    result = extract_metadata("DBY-W09 用户指南", CATALOG)

    assert result.product_ids == ("huawei_c7",)
    assert result.version_label is None
    assert result.confidence == "medium"


def test_unknown_product_and_version_is_low_confidence() -> None:
    result = extract_metadata("通用设备说明", CATALOG)

    assert result.product_ids == ()
    assert result.confidence == "low"
