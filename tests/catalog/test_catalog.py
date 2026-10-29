import pytest

from rag_app.catalog import (
    MatchStatus,
    Product,
    ProductCatalog,
    ProductCategory,
)


def make_catalog() -> ProductCatalog:
    return ProductCatalog(
        (
            Product(
                id="huawei_c7",
                display_name="华为平板 C7",
                category=ProductCategory.TABLET,
                aliases=("C7", "DBY-W09", "华为平板C7"),
            ),
            Product(
                id="huawei_c5e",
                display_name="华为擎云 C5e",
                category=ProductCategory.TABLET,
                aliases=("C5e", "BZI-W00"),
            ),
        )
    )


def test_resolve_unique_product_alias() -> None:
    match = make_catalog().resolve("我的 DBY-W09 屏幕怎么清洁？")

    assert match.status is MatchStatus.RESOLVED
    assert [product.id for product in match.products] == ["huawei_c7"]


def test_resolve_is_case_insensitive_and_collapses_spaces() -> None:
    match = make_catalog().resolve("c7  支持蓝牙吗")

    assert match.status is MatchStatus.RESOLVED
    assert match.products[0].id == "huawei_c7"


def test_resolve_does_not_treat_c5e_as_c5() -> None:
    match = make_catalog().resolve("C5e 怎么连接键盘")

    assert match.status is MatchStatus.RESOLVED
    assert match.products[0].id == "huawei_c5e"


def test_resolve_returns_not_found_without_alias() -> None:
    match = make_catalog().resolve("这台设备怎么开机？")

    assert match.status is MatchStatus.NOT_FOUND
    assert match.products == ()


def test_duplicate_normalized_alias_is_rejected() -> None:
    with pytest.raises(ValueError, match="alias"):
        ProductCatalog(
            (
                Product("one", "One", ProductCategory.TABLET, ("Same",)),
                Product("two", "Two", ProductCategory.TABLET, ("same",)),
            )
        )
