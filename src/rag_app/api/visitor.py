import secrets

from fastapi import Request, Response


def visitor_from_request(request: Request) -> str:
    return (
        request.cookies.get("rag_visitor_id")
        or request.headers.get("X-Visitor-ID")
        or secrets.token_urlsafe(32)
    )


def set_visitor_cookie(
    response: Response,
    request: Request,
    visitor_id: str,
) -> None:
    response.set_cookie(
        "rag_visitor_id",
        visitor_id,
        max_age=365 * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
