from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from rag_app.admin_auth import AdminAuth


class LoginRequest(BaseModel):
    password: str


def ensure_admin(auth: AdminAuth | None, request: Request) -> None:
    if auth is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin authentication is not configured",
        )
    token = request.cookies.get("admin_session", "")
    if not auth.verify(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="admin session required",
        )


def build_admin_router(auth: AdminAuth | None) -> APIRouter:
    router = APIRouter(prefix="/api/admin", tags=["admin"])

    @router.post("/login")
    def login(request: LoginRequest, response: Response) -> dict[str, str]:
        if auth is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="admin authentication is not configured",
            )
        token = auth.authenticate(request.password)
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid credentials",
            )
        response.set_cookie(
            "admin_session",
            token,
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=3600,
        )
        return {"status": "ok"}

    @router.post("/logout")
    def logout(response: Response) -> dict[str, str]:
        response.delete_cookie("admin_session")
        return {"status": "ok"}

    @router.get("/session")
    def session(request: Request) -> dict[str, str]:
        ensure_admin(auth, request)
        return {"role": "admin"}

    return router
