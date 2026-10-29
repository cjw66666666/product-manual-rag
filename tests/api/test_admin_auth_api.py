import httpx
import pytest
from argon2 import PasswordHasher

from rag_app.admin_auth import AdminAuth
from rag_app.api.app import create_app


@pytest.mark.asyncio
async def test_admin_login_sets_http_only_cookie() -> None:
    auth = AdminAuth(
        password_hash=PasswordHasher().hash("correct"),
        session_secret="secret",
    )
    transport = httpx.ASGITransport(app=create_app(admin_auth=auth))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/admin/login",
            json={"password": "correct"},
        )

    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].casefold()


@pytest.mark.asyncio
async def test_admin_login_rejects_wrong_password() -> None:
    auth = AdminAuth(
        password_hash=PasswordHasher().hash("correct"),
        session_secret="secret",
    )
    transport = httpx.ASGITransport(app=create_app(admin_auth=auth))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/admin/login",
            json={"password": "wrong"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_session_cookie_protects_admin_route() -> None:
    auth = AdminAuth(
        password_hash=PasswordHasher().hash("correct"),
        session_secret="secret",
    )
    transport = httpx.ASGITransport(app=create_app(admin_auth=auth))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        unauthorized = await client.get("/api/admin/session")
        await client.post(
            "/api/admin/login",
            json={"password": "correct"},
        )
        authorized = await client.get("/api/admin/session")

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json() == {"role": "admin"}
