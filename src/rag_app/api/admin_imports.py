from hashlib import sha256
from pathlib import PurePosixPath
from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field

from rag_app.admin_auth import AdminAuth
from rag_app.api.admin import ensure_admin
from rag_app.application import (
    ConflictAction,
    ImportBatchResult,
    ImportBatchSummary,
    ImportBatchView,
    ImportRejection,
    ImportService,
    UploadedDocument,
)


class ConflictResolutionRequest(BaseModel):
    action: ConflictAction
    new_filename: str | None = None


class ImportMetadataRequest(BaseModel):
    product_ids: list[str] = Field(default_factory=list)
    product_name: str | None = None
    version_label: str | None = None


async def _read_pdf_limited(
    file: UploadFile,
    *,
    max_bytes: int,
) -> bytes:
    content_type = (file.content_type or "").casefold()
    if content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported content type",
        )

    content = bytearray()
    while chunk := await file.read(1024 * 1024):
        if len(content) + len(chunk) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file exceeds upload size limit",
            )
        content.extend(chunk)
    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file is not a valid PDF",
        )
    return bytes(content)


def _safe_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid relative path",
        )
    return path.as_posix()


def build_import_router(
    auth: AdminAuth | None,
    service: ImportService | None,
    *,
    max_upload_bytes: int = 50 * 1024 * 1024,
    max_batch_upload_bytes: int = 200 * 1024 * 1024,
) -> APIRouter:
    if max_upload_bytes < 1 or max_batch_upload_bytes < 1:
        raise ValueError("upload limits must be positive")
    router = APIRouter(prefix="/api/admin", tags=["admin-imports"])

    @router.post("/imports", response_model=ImportBatchResult)
    async def create_import(
        request: Request,
        files: Annotated[list[UploadFile], File()],
        relative_paths: Annotated[list[str] | None, Form()] = None,
    ) -> ImportBatchResult:
        ensure_admin(auth, request)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="import service is not configured",
            )

        uploaded: list[UploadedDocument] = []
        rejected: list[ImportRejection] = []
        total_bytes = 0
        for index, file in enumerate(files):
            filename = file.filename or ""
            try:
                if not filename.casefold().endswith(".pdf"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="only PDF files are supported",
                    )
                content = await _read_pdf_limited(
                    file,
                    max_bytes=max_upload_bytes,
                )
                if total_bytes + len(content) > max_batch_upload_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="batch exceeds upload size limit",
                    )
                total_bytes += len(content)
                uploaded.append(
                    UploadedDocument(
                        filename=filename,
                        content_type=(
                            file.content_type or "application/pdf"
                        ),
                        content=content,
                        sha256=sha256(content).hexdigest(),
                        relative_path=(
                            _safe_relative_path(relative_paths[index])
                            if relative_paths is not None
                            and index < len(relative_paths)
                            else filename
                        ),
                    )
                )
            except HTTPException as exc:
                rejected.append(
                    ImportRejection(
                        filename=filename,
                        reason=str(exc.detail),
                    )
                )
        if not uploaded:
            return ImportBatchResult(
                batch_id=None,
                accepted=0,
                rejected=tuple(rejected),
            )
        result = service.enqueue(tuple(uploaded))
        return ImportBatchResult(
            batch_id=result.batch_id,
            accepted=result.accepted,
            rejected=tuple(rejected),
        )

    @router.get("/imports/{batch_id}", response_model=ImportBatchView)
    def get_import(
        batch_id: str,
        request: Request,
    ) -> ImportBatchView:
        ensure_admin(auth, request)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="import service is not configured",
            )
        return service.get_batch(batch_id)

    @router.get(
        "/imports",
        response_model=tuple[ImportBatchSummary, ...],
    )
    def list_imports(
        request: Request,
    ) -> tuple[ImportBatchSummary, ...]:
        ensure_admin(auth, request)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="import service is not configured",
            )
        return service.list_batches()

    @router.post(
        "/imports/{batch_id}/conflicts/{item_id}/resolve",
        response_model=ImportBatchView,
    )
    def resolve_import_conflict(
        batch_id: str,
        item_id: str,
        request: Request,
        payload: ConflictResolutionRequest,
    ) -> ImportBatchView:
        ensure_admin(auth, request)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="import service is not configured",
            )
        try:
            return service.resolve_conflict(
                batch_id,
                item_id,
                payload.action,
                payload.new_filename,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    @router.patch(
        "/imports/{batch_id}/items/{item_id}/metadata",
        response_model=ImportBatchView,
    )
    def update_import_metadata(
        batch_id: str,
        item_id: str,
        payload: ImportMetadataRequest,
        request: Request,
    ) -> ImportBatchView:
        ensure_admin(auth, request)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="import service is not configured",
            )
        try:
            if payload.product_name is not None:
                return service.update_item_product_name(
                    batch_id,
                    item_id,
                    product_name=payload.product_name,
                    version_label=payload.version_label,
                )
            return service.update_item_metadata(
                batch_id,
                item_id,
                product_ids=tuple(payload.product_ids),
                version_label=payload.version_label,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    @router.post(
        "/imports/{batch_id}/items/{item_id}/prepare",
        response_model=ImportBatchView,
    )
    def prepare_import_item(
        batch_id: str,
        item_id: str,
        request: Request,
    ) -> ImportBatchView:
        ensure_admin(auth, request)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="import service is not configured",
            )
        try:
            return service.prepare_item(batch_id, item_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    return router
