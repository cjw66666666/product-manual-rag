from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_app.catalog import Product, ProductCategory
from rag_app.catalog.resolver import normalize_alias
from rag_app.persistence.schema import Product as ProductRow
from rag_app.persistence.schema import ProductAlias


class ProductDirectoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve_or_create(self, display_name: str) -> str:
        cleaned = " ".join(display_name.split())
        if not cleaned:
            raise ValueError("product name cannot be blank")
        normalized = normalize_alias(cleaned)
        plain_normalized = cleaned.casefold()

        aliases = self._session.scalars(select(ProductAlias)).all()
        existing = next(
            (
                alias
                for alias in aliases
                if normalize_alias(alias.alias) == normalized
                or alias.normalized_alias == plain_normalized
            ),
            None,
        )
        if existing is not None:
            return existing.product_id

        product_id = f"custom_{sha256(normalized.encode()).hexdigest()[:24]}"
        self._session.add(
            ProductRow(
                id=product_id,
                display_name=cleaned,
                category=ProductCategory.OTHER.value,
                brand=(
                    "HUAWEI"
                    if "huawei" in normalized or "华为" in normalized
                    else "UNKNOWN"
                ),
                status="active",
            )
        )
        self._session.add(
            ProductAlias(
                product_id=product_id,
                alias=cleaned,
                normalized_alias=plain_normalized,
                alias_type="manual",
            )
        )
        self._session.flush()
        return product_id

    def list_catalog_products(self) -> tuple[Product, ...]:
        rows = self._session.scalars(
            select(ProductRow).order_by(ProductRow.display_name)
        ).all()
        aliases = self._session.scalars(select(ProductAlias)).all()
        aliases_by_product: dict[str, list[str]] = {}
        for alias in aliases:
            aliases_by_product.setdefault(alias.product_id, []).append(
                alias.alias
            )
        products: list[Product] = []
        for row in rows:
            try:
                category = ProductCategory(row.category)
            except ValueError:
                category = ProductCategory.OTHER
            products.append(
                Product(
                    id=row.id,
                    display_name=row.display_name,
                    category=category,
                    aliases=tuple(
                        aliases_by_product.get(row.id, [row.display_name])
                    ),
                )
            )
        return tuple(products)
