import httpx
import pytest

from rag_app.api.app import create_app
from rag_app.application import ConversationView
from rag_app.conversations import AnswerDetail, UserPreference


class FakeConversationService:
    def __init__(self) -> None:
        self.preference = UserPreference()
        self.resolved_product: str | None = None

    def create(self, *, visitor_id: str) -> str:
        return "conversation-1"

    def get(
        self,
        conversation_id: str,
        *,
        visitor_id: str,
    ) -> ConversationView:
        return ConversationView(
            conversation_id=conversation_id,
            product_id=self.resolved_product,
            messages=(),
        )

    def resolve_product(
        self,
        conversation_id: str,
        *,
        product_id: str,
        visitor_id: str,
    ) -> ConversationView:
        self.resolved_product = product_id
        return self.get(conversation_id, visitor_id=visitor_id)

    def get_preferences(self, visitor_id: str) -> UserPreference:
        return self.preference

    def update_preferences(
        self,
        visitor_id: str,
        *,
        language: str,
        answer_detail: AnswerDetail,
        show_citations: bool,
    ) -> UserPreference:
        self.preference = UserPreference(
            language=language,
            answer_detail=answer_detail,
            show_citations=show_citations,
        )
        return self.preference

    def add_feedback(
        self,
        conversation_id: str,
        message_id: str,
        *,
        rating: str,
        reason: str | None,
        visitor_id: str,
    ) -> int:
        return 1


@pytest.mark.asyncio
async def test_public_conversation_api_closes_core_workflow() -> None:
    service = FakeConversationService()
    transport = httpx.ASGITransport(
        app=create_app(conversation_service=service)
    )
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        created = await client.post("/api/conversations")
        resolved = await client.post(
            "/api/conversations/conversation-1/resolve-product",
            json={"product_id": "p1"},
        )
        loaded = await client.get(
            "/api/conversations/conversation-1"
        )
        preferences = await client.patch(
            "/api/preferences",
            json={
                "language": "en-US",
                "answer_detail": "detailed",
                "show_citations": False,
            },
        )
        feedback = await client.post(
            "/api/conversations/conversation-1/messages/m1/feedback",
            json={"rating": "helpful", "reason": None},
        )

    assert created.status_code == 200
    assert created.json()["conversation_id"] == "conversation-1"
    assert resolved.status_code == 200
    assert resolved.json()["product_id"] == "p1"
    assert loaded.status_code == 200
    assert preferences.json()["answer_detail"] == "detailed"
    assert feedback.json()["feedback_id"] == 1
