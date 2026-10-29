from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_app.catalog import Product, ProductCatalog, ProductCategory
from rag_app.persistence.schema import (
    IndexVersion,
    ProductAlias,
)
from rag_app.persistence.schema import (
    Product as ProductRow,
)


@dataclass(frozen=True, slots=True)
class SeedProduct:
    id: str
    name: str
    category: ProductCategory
    aliases: tuple[str, ...]


PRODUCTS = (
    SeedProduct(
        "huawei_c7",
        "华为平板 C7",
        ProductCategory.TABLET,
        ("C7", "DBY-W09"),
    ),
    SeedProduct(
        "huawei_c5e_gen4",
        "华为擎云 C5 第4代",
        ProductCategory.TABLET,
        ("C5e", "C5 第4代", "BYD5-W10", "BYD5-AL10"),
    ),
    SeedProduct(
        "huawei_b5_440",
        "HUAWEI MateBook B5-440",
        ProductCategory.LAPTOP,
        ("B5-440", "KLVFZ"),
    ),
    SeedProduct(
        "huawei_hm740",
        "华为擎云 HM740",
        ProductCategory.LAPTOP,
        ("HM740", "HM740-001", "HM740-031"),
    ),
    SeedProduct(
        "huawei_b5_341w",
        "华为显示器 B5-341W",
        ProductCategory.MONITOR,
        ("B5-341W", "ZQE-CBA"),
    ),
    SeedProduct(
        "huawei_m272q",
        "华为擎云 M272Q",
        ProductCategory.MONITOR,
        ("M272Q", "XSN-27QBZ"),
    ),
)


def seed_initial_data(
    session: Session,
    *,
    index_version_id: str,
) -> ProductCatalog:
    for item in PRODUCTS:
        row = session.get(ProductRow, item.id)
        if row is None:
            session.add(
                ProductRow(
                    id=item.id,
                    display_name=item.name,
                    category=item.category.value,
                    brand="HUAWEI",
                    status="active",
                )
            )
        for alias in (item.name, *item.aliases):
            normalized = alias.casefold()
            exists = session.scalar(
                select(ProductAlias).where(
                    ProductAlias.normalized_alias == normalized
                )
            )
            if exists is None:
                session.add(
                    ProductAlias(
                        product_id=item.id,
                        alias=alias,
                        normalized_alias=normalized,
                        alias_type="model",
                    )
                )

    if session.get(IndexVersion, index_version_id) is None:
        session.add(
            IndexVersion(
                id=index_version_id,
                chunker_version="v1",
                dense_provider="siliconflow",
                dense_model="BAAI/bge-m3",
                dense_model_revision="provider-managed",
                dense_dimension=1024,
                sparse_method="hashed",
                sparse_tokenizer="cjk-bigram",
            )
        )
    session.flush()
    return ProductCatalog(
        tuple(
            Product(
                item.id,
                item.name,
                item.category,
                (item.id, *item.aliases),
            )
            for item in PRODUCTS
        )
    )
