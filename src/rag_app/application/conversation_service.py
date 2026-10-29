from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from rag_app.conversations import AnswerDetail, UserPreference
from rag_app.persistence.conversation_repository import (
    ConversationRecord,
)


class ConversationRepository(Protocol):
    def create(self, *, visitor_id: str) -> str: ...

    def get(
        self,
        conversation_id: str,
        *,
        visitor_id: str,
    ) -> ConversationRecord: ...

    def resolve_product(
        self,
        conversation_id: str,
        *,
        product_id: str,
        visitor_id: str,
    ) -> ConversationRecord: ...

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


@dataclass(frozen=True, slots=True)
class ConversationMessageView:
    id: str
    role: str
    content: str
    mode: str | None


@dataclass(frozen=True, slots=True)
class ConversationView:
    conversation_id: str
    product_id: str | None
    messages: tuple[ConversationMessageView, ...]


class ConversationApplicationService:
    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        commit: Callable[[], None] = lambda: None,
    ) -> None:
        self._conversations = conversations
        self._commit = commit

    def create(self, *, visitor_id: str) -> str:
        conversation_id = self._conversations.create(
            visitor_id=visitor_id
        )
        self._commit()
        return conversation_id

    def get(
        self,
        conversation_id: str,
        *,
        visitor_id: str,
    ) -> ConversationView:
        return self._view(
            self._conversations.get(
                conversation_id,
                visitor_id=visitor_id,
            )
        )

    def resolve_product(
        self,
        conversation_id: str,
        *,
        product_id: str,
        visitor_id: str,
    ) -> ConversationView:
        record = self._conversations.resolve_product(
            conversation_id,
            product_id=product_id,
            visitor_id=visitor_id,
        )
        self._commit()
        return self._view(record)

    def get_preferences(self, visitor_id: str) -> UserPreference:
        return self._conversations.get_preferences(visitor_id)

    def update_preferences(
        self,
        visitor_id: str,
        *,
        language: str,
        answer_detail: AnswerDetail,
        show_citations: bool,
    ) -> UserPreference:
        preference = self._conversations.update_preferences(
            visitor_id,
            language=language,
            answer_detail=answer_detail,
            show_citations=show_citations,
        )
        self._commit()
        return preference

    def add_feedback(
        self,
        conversation_id: str,
        message_id: str,
        *,
        rating: str,
        reason: str | None,
        visitor_id: str,
    ) -> int:
        feedback_id = self._conversations.add_feedback(
            conversation_id,
            message_id,
            rating=rating,
            reason=reason,
            visitor_id=visitor_id,
        )
        self._commit()
        return feedback_id

    @staticmethod
    def _view(record: ConversationRecord) -> ConversationView:
        return ConversationView(
            conversation_id=record.conversation_id,
            product_id=record.product_id,
            messages=tuple(
                ConversationMessageView(
                    id=item.id,
                    role=item.role,
                    content=item.content,
                    mode=item.mode,
                )
                for item in record.messages
            ),
        )
