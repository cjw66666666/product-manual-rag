import httpx
import pytest

from rag_app.api.app import create_app


@pytest.mark.asyncio
async def test_live_check_is_always_ok() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_check_uses_injected_checker() -> None:
    transport = httpx.ASGITransport(app=create_app(lambda: True))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/health/ready")

        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


@pytest.mark.asyncio
async def test_ready_check_returns_service_unavailable() -> None:
    transport = httpx.ASGITransport(app=create_app(lambda: False))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/health/ready")

        assert response.status_code == 503
        assert response.json() == {"status": "not_ready"}
