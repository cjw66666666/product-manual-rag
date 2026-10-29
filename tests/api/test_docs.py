import httpx
import pytest

from rag_app.api.app import create_app


@pytest.mark.asyncio
async def test_local_docs_page_does_not_require_cdn() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/docs")

    assert response.status_code == 200
    assert "/openapi.json" in response.text
    assert "cdn.jsdelivr.net" not in response.text
