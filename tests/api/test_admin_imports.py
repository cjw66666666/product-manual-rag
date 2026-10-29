import httpx
import pytest
from argon2 import PasswordHasher

from rag_app.admin_auth import AdminAuth
from rag_app.api.app import create_app
from rag_app.application import (
    ConflictAction,
    ImportBatchResult,
    ImportBatchSummary,
    ImportBatchView,
    ImportItemView,
    UploadedDocument,
)


class FakeImportService:
    def __init__(self) -> None:
        self.relative_paths: list[str | None] = []

    def enqueue(
        self,
        files: tuple[UploadedDocument, ...],
    ) -> ImportBatchResult:
        assert len(files) == 1
        assert files[0].content.startswith(b"%PDF-")
        assert len(files[0].sha256) == 64
        self.relative_paths.append(files[0].relative_path)
        return ImportBatchResult(batch_id="batch-1", accepted=1)

    def get_batch(self, batch_id: str) -> ImportBatchView:
        return ImportBatchView(
            batch_id=batch_id,
            items=(
                ImportItemView(
                    item_id="item-1",
                    filename="manual.pdf",
                    sha256="a" * 64,
                    product_ids=("huawei_c7",),
                    version_label="2.1.0",
                    confidence="high",
                    conflict_type=None,
                    status="pending",
                ),
            ),
        )

    def list_batches(self) -> tuple[ImportBatchSummary, ...]:
        return (
            ImportBatchSummary(
                batch_id="batch-1",
                source_type="files",
                status="queued",
                created_by="admin",
                item_count=1,
            ),
        )

    def resolve_conflict(
        self,
        batch_id: str,
        item_id: str,
        action: ConflictAction,
        new_filename: str | None = None,
    ) -> ImportBatchView:
        return self.get_batch(batch_id)

    def prepare_item(
        self,
        batch_id: str,
        item_id: str,
    ) -> ImportBatchView:
        return self.get_batch(batch_id)

    def update_item_metadata(
        self,
        batch_id: str,
        item_id: str,
        *,
        product_ids: tuple[str, ...],
        version_label: str | None,
    ) -> ImportBatchView:
        return self.get_batch(batch_id)

    def update_item_product_name(
        self,
        batch_id: str,
        item_id: str,
        *,
        product_name: str,
        version_label: str | None,
    ) -> ImportBatchView:
        assert product_name
        return self.get_batch(batch_id)


@pytest.mark.asyncio
async def test_document_import_requires_admin_session() -> None:
    auth = AdminAuth(
        password_hash=PasswordHasher().hash("correct"),
        session_secret="secret",
    )
    app = create_app(
        admin_auth=auth,
        import_service=FakeImportService(),
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
        response = await client.post(
            "/api/admin/imports",
            files={"files": ("manual.pdf", b"%PDF-1.7", "application/pdf")},
        )

    assert response.status_code == 200
    assert response.json()["batch_id"] == "batch-1"


@pytest.mark.asyncio
async def test_import_preview_returns_item_metadata() -> None:
    auth = AdminAuth(
        password_hash=PasswordHasher().hash("correct"),
        session_secret="secret",
    )
    app = create_app(
        admin_auth=auth,
        import_service=FakeImportService(),
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
        response = await client.get("/api/admin/imports/batch-1")
        batches = await client.get("/api/admin/imports")

    assert response.status_code == 200
    assert response.json()["items"][0]["confidence"] == "high"
    assert batches.status_code == 200
    assert batches.json()[0]["item_count"] == 1


@pytest.mark.asyncio
async def test_import_rejects_pdf_extension_without_pdf_signature() -> None:
    auth = AdminAuth(
        password_hash=PasswordHasher().hash("correct"),
        session_secret="secret",
    )
    app = create_app(
        admin_auth=auth,
        import_service=FakeImportService(),
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
        response = await client.post(
            "/api/admin/imports",
            files={
                "files": (
                    "manual.pdf",
                    b"not a pdf",
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 200
    assert response.json()["accepted"] == 0
    assert response.json()["rejected"][0]["reason"] == (
        "file is not a valid PDF"
    )


@pytest.mark.asyncio
async def test_import_rejects_file_above_size_limit() -> None:
    auth = AdminAuth(
        password_hash=PasswordHasher().hash("correct"),
        session_secret="secret",
    )
    app = create_app(
        admin_auth=auth,
        import_service=FakeImportService(),
        max_upload_bytes=8,
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
        response = await client.post(
            "/api/admin/imports",
            files={
                "files": (
                    "manual.pdf",
                    b"%PDF-1.7 too large",
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 200
    assert response.json()["accepted"] == 0
    assert response.json()["rejected"][0]["reason"] == (
        "file exceeds upload size limit"
    )


@pytest.mark.asyncio
async def test_import_preserves_safe_relative_directory_path() -> None:
    auth = AdminAuth(
        password_hash=PasswordHasher().hash("correct"),
        session_secret="secret",
    )
    service = FakeImportService()
    app = create_app(
        admin_auth=auth,
        import_service=service,
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
        response = await client.post(
            "/api/admin/imports",
            files={
                "files": (
                    "manual.pdf",
                    b"%PDF-1.7",
                    "application/pdf",
                )
            },
            data={"relative_paths": "tablets/C7/manual.pdf"},
        )

    assert response.status_code == 200
    assert service.relative_paths == ["tablets/C7/manual.pdf"]


@pytest.mark.asyncio
async def test_admin_can_correct_import_metadata() -> None:
    auth = AdminAuth(
        password_hash=PasswordHasher().hash("correct"),
        session_secret="secret",
    )
    app = create_app(
        admin_auth=auth,
        import_service=FakeImportService(),
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
        response = await client.patch(
            "/api/admin/imports/batch-1/items/item-1/metadata",
            json={
                "product_ids": ["huawei_c7"],
                "version_label": "2.2",
            },
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_can_submit_new_product_name() -> None:
    auth = AdminAuth(
        password_hash=PasswordHasher().hash("correct"),
        session_secret="secret",
    )
    app = create_app(
        admin_auth=auth,
        import_service=FakeImportService(),
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
        response = await client.patch(
            "/api/admin/imports/batch-1/items/item-1/metadata",
            json={
                "product_name": "HUAWEI MateBook B7-420",
                "version_label": "2.0",
            },
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_invalid_file_does_not_abort_remaining_uploads() -> None:
    auth = AdminAuth(
        password_hash=PasswordHasher().hash("correct"),
        session_secret="secret",
    )
    app = create_app(
        admin_auth=auth,
        import_service=FakeImportService(),
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
        response = await client.post(
            "/api/admin/imports",
            files=[
                ("files", ("bad.pdf", b"not-pdf", "application/pdf")),
                ("files", ("good.pdf", b"%PDF-1.7", "application/pdf")),
            ],
        )

    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    assert response.json()["rejected"][0]["filename"] == "bad.pdf"
    assert response.json()["batch_id"] == "batch-1"


@pytest.mark.asyncio
async def test_all_rejected_files_return_no_batch() -> None:
    auth = AdminAuth(
        password_hash=PasswordHasher().hash("correct"),
        session_secret="secret",
    )
    app = create_app(
        admin_auth=auth,
        import_service=FakeImportService(),
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
        response = await client.post(
            "/api/admin/imports",
            files=[
                ("files", ("bad.pdf", b"not-pdf", "application/pdf")),
            ],
        )

    assert response.status_code == 200
    assert response.json()["batch_id"] is None
    assert response.json()["accepted"] == 0
    assert response.json()["rejected"][0]["filename"] == "bad.pdf"
