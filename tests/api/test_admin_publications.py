import httpx
import pytest
from argon2 import PasswordHasher

from rag_app.admin_auth import AdminAuth
from rag_app.api.app import create_app
from rag_app.application import VersionIndexView, VersionView


class FakePublicationService:
    def __init__(self) -> None:
        self.approved: list[str] = []
        self.published: list[tuple[str, str, str]] = []

    def list_versions(self, product_id: str) -> tuple[VersionView, ...]:
        return (
            VersionView(
                id="v1",
                document_id="d1",
                version_label="1.0",
                status="validated",
                requires_manual_approval=True,
                approved_at=None,
                approved_by=None,
                document_name="guide.pdf",
                indexes=(
                    VersionIndexView(
                        index_version_id="i4",
                        status="completed",
                        chunk_count=56,
                        error_message=None,
                    ),
                ),
            ),
        )

    def list_pending_approval_product_ids(self) -> tuple[str, ...]:
        return ("p1",)

    def approve(self, version_id: str, *, approved_by: str) -> None:
        self.approved.append(version_id)

    def publish(
        self,
        *,
        product_id: str,
        document_version_id: str,
        index_version_id: str,
    ) -> None:
        self.published.append(
            (product_id, document_version_id, index_version_id)
        )


@pytest.mark.asyncio
async def test_admin_can_list_approve_and_publish_safety_version() -> None:
    auth = AdminAuth(
        password_hash=PasswordHasher().hash("correct"),
        session_secret="secret",
    )
    service = FakePublicationService()
    app = create_app(
        admin_auth=auth,
        publication_service=service,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        await client.post(
            "/api/admin/login",
            json={"password": "correct"},
        )
        pending_products = await client.get(
            "/api/admin/products/pending-approval"
        )
        listed = await client.get("/api/admin/products/p1/versions")
        approved = await client.post(
            "/api/admin/versions/v1/approve",
        )
        published = await client.post(
            "/api/admin/versions/v1/publish",
            json={
                "product_id": "p1",
                "index_version_id": "i1",
            },
        )

    assert pending_products.status_code == 200
    assert pending_products.json() == ["p1"]
    assert listed.status_code == 200
    assert listed.json()[0]["requires_manual_approval"] is True
    assert listed.json()[0]["document_name"] == "guide.pdf"
    assert listed.json()[0]["indexes"][0]["chunk_count"] == 56
    assert approved.status_code == 200
    assert published.status_code == 200
    assert service.approved == ["v1"]
    assert service.published == [("p1", "v1", "i1")]
