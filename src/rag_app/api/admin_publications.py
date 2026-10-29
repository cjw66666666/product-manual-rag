from typing import Protocol

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from rag_app.admin_auth import AdminAuth
from rag_app.api.admin import ensure_admin
from rag_app.application import VersionView


class PublicationService(Protocol):
    def list_versions(self, product_id: str) -> tuple[VersionView, ...]: ...

    def approve(self, version_id: str, *, approved_by: str) -> None: ...

    def publish(
        self,
        *,
        product_id: str,
        document_version_id: str,
        index_version_id: str,
    ) -> None: ...


class PublishRequest(BaseModel):
    product_id: str
    index_version_id: str


def build_publication_router(
    auth: AdminAuth | None,
    service: PublicationService | None,
) -> APIRouter:
    router = APIRouter(prefix="/api/admin", tags=["admin-publications"])

    @router.get(
        "/products/{product_id}/versions",
        response_model=tuple[VersionView, ...],
    )
    def list_versions(
        product_id: str,
        request: Request,
    ) -> tuple[VersionView, ...]:
        ensure_admin(auth, request)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="publication service is not configured",
            )
        return service.list_versions(product_id)

    @router.post("/versions/{version_id}/approve")
    def approve_version(
        version_id: str,
        request: Request,
    ) -> dict[str, str]:
        ensure_admin(auth, request)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="publication service is not configured",
            )
        try:
            service.approve(version_id, approved_by="admin")
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        return {"status": "approved"}

    @router.post("/versions/{version_id}/publish")
    def publish_version(
        version_id: str,
        payload: PublishRequest,
        request: Request,
    ) -> dict[str, str]:
        ensure_admin(auth, request)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="publication service is not configured",
            )
        try:
            service.publish(
                product_id=payload.product_id,
                document_version_id=version_id,
                index_version_id=payload.index_version_id,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        return {"status": "active"}

    return router
