from collections.abc import Callable

from fastapi import APIRouter, Response, status


def build_health_router(
    readiness_check: Callable[[], bool],
) -> APIRouter:
    router = APIRouter(prefix="/health", tags=["health"])

    @router.get("/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/ready")
    def ready(response: Response) -> dict[str, str]:
        if not readiness_check():
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "not_ready"}
        return {"status": "ready"}

    return router
