from collections.abc import Callable, Sequence

from fastapi import APIRouter
from pydantic import BaseModel

from rag_app.catalog import Product, ProductCategory


class ProductResponse(BaseModel):
    id: str
    display_name: str
    category: ProductCategory
    aliases: list[str]


def build_products_router(
    products: Sequence[Product],
    product_loader: Callable[[], Sequence[Product]] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["products"])

    @router.get("/products", response_model=list[ProductResponse])
    def list_products() -> list[ProductResponse]:
        available = product_loader() if product_loader is not None else products
        return [
            ProductResponse(
                id=product.id,
                display_name=product.display_name,
                category=product.category,
                aliases=list(product.aliases),
            )
            for product in available
        ]

    return router
