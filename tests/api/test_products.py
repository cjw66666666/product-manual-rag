import httpx
import pytest

from rag_app.api.app import create_app
from rag_app.catalog import Product, ProductCategory


@pytest.mark.asyncio
async def test_products_endpoint_returns_public_catalog() -> None:
    product = Product(
        id="huawei_c7",
        display_name="华为平板 C7",
        category=ProductCategory.TABLET,
        aliases=("C7", "DBY-W09"),
    )
    transport = httpx.ASGITransport(app=create_app(products=(product,)))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/api/products")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "huawei_c7",
            "display_name": "华为平板 C7",
            "category": "tablet",
            "aliases": ["C7", "DBY-W09"],
        }
    ]


@pytest.mark.asyncio
async def test_products_endpoint_can_load_dynamic_catalog() -> None:
    dynamic = Product(
        id="custom_b7",
        display_name="HUAWEI MateBook B7-420",
        category=ProductCategory.OTHER,
        aliases=("HUAWEI MateBook B7-420",),
    )
    transport = httpx.ASGITransport(
        app=create_app(product_loader=lambda: (dynamic,))
    )
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/api/products")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "custom_b7"
    assert response.json()[0]["category"] == "other"
