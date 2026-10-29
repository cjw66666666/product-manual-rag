from typing import Protocol

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from rag_app.api.visitor import (
    set_visitor_cookie,
    visitor_from_request,
)
from rag_app.application import ConversationView
from rag_app.conversations import AnswerDetail, UserPreference


class ConversationService(Protocol):
    def create(self, *, visitor_id: str) -> str: ...

    def get(
        self,
        conversation_id: str,
        *,
        visitor_id: str,
    ) -> ConversationView: ...

    def resolve_product(
        self,
        conversation_id: str,
        *,
        product_id: str,
        visitor_id: str,
    ) -> ConversationView: ...

    def get_preferences(self, visitor_id: str) -> UserPreference: ...

    def update_preferences(
        self,
        visitor_id: str,
        *,
        language: str,
        answer_detail: AnswerDetail,
        show_citations: bool,
    ) -> UserPreference: ...

    def add_feedback(
        self,
        conversation_id: str,
        message_id: str,
        *,
        rating: str,
        reason: str | None,
        visitor_id: str,
    ) -> int: ...


class ResolveProductRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=64)


class FeedbackRequest(BaseModel):
    rating: str = Field(pattern=r"^(helpful|not_helpful|report)$")
    reason: str | None = Field(default=None, max_length=2000)


class PreferenceRequest(BaseModel):
    language: str = Field(min_length=2, max_length=16)
    answer_detail: AnswerDetail
    show_citations: bool


def build_conversation_router(
    service: ConversationService | None,
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["conversations"])

    def configured() -> ConversationService:
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="conversation service is not configured",
            )
        return service

    @router.post("/conversations")
    def create_conversation(
        request: Request,
        response: Response,
    ) -> dict[str, str]:
        visitor_id = visitor_from_request(request)
        conversation_id = configured().create(visitor_id=visitor_id)
        set_visitor_cookie(response, request, visitor_id)
        return {"conversation_id": conversation_id}

    @router.get(
        "/conversations/{conversation_id}",
        response_model=ConversationView,
    )
    def get_conversation(
        conversation_id: str,
        request: Request,
        response: Response,
    ) -> ConversationView:
        visitor_id = visitor_from_request(request)
        try:
            view = configured().get(
                conversation_id,
                visitor_id=visitor_id,
            )
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="conversation access denied",
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        set_visitor_cookie(response, request, visitor_id)
        return view

    @router.post(
        "/conversations/{conversation_id}/resolve-product",
        response_model=ConversationView,
    )
    def resolve_product(
        conversation_id: str,
        payload: ResolveProductRequest,
        request: Request,
        response: Response,
    ) -> ConversationView:
        visitor_id = visitor_from_request(request)
        try:
            view = configured().resolve_product(
                conversation_id,
                product_id=payload.product_id,
                visitor_id=visitor_id,
            )
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="conversation access denied",
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        set_visitor_cookie(response, request, visitor_id)
        return view

    @router.post(
        "/conversations/{conversation_id}/messages/{message_id}/feedback"
    )
    def add_feedback(
        conversation_id: str,
        message_id: str,
        payload: FeedbackRequest,
        request: Request,
    ) -> dict[str, int]:
        visitor_id = visitor_from_request(request)
        try:
            feedback_id = configured().add_feedback(
                conversation_id,
                message_id,
                rating=payload.rating,
                reason=payload.reason,
                visitor_id=visitor_id,
            )
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="conversation access denied",
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        return {"feedback_id": feedback_id}

    @router.get("/preferences")
    def get_preferences(
        request: Request,
        response: Response,
    ) -> UserPreference:
        visitor_id = visitor_from_request(request)
        preference = configured().get_preferences(visitor_id)
        set_visitor_cookie(response, request, visitor_id)
        return preference

    @router.patch("/preferences")
    def update_preferences(
        payload: PreferenceRequest,
        request: Request,
        response: Response,
    ) -> UserPreference:
        visitor_id = visitor_from_request(request)
        preference = configured().update_preferences(
            visitor_id,
            language=payload.language,
            answer_detail=payload.answer_detail,
            show_citations=payload.show_citations,
        )
        set_visitor_cookie(response, request, visitor_id)
        return preference

    return router
