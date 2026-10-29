from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_app.conversations import (
    AnswerDetail,
    SqlConversationContextStore,
    UserPreference,
)
from rag_app.persistence.schema import (
    AnswerRun,
    Conversation,
    Feedback,
    Message,
    VisitorPreference,
)


@dataclass(frozen=True, slots=True)
class ConversationMessageRecord:
    id: str
    role: str
    content: str
    mode: str | None


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    conversation_id: str
    product_id: str | None
    messages: tuple[ConversationMessageRecord, ...]


class SqlConversationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, visitor_id: str) -> str:
        conversation_id = uuid4().hex
        self._session.add(Conversation(
            id=conversation_id,
            visitor_id=visitor_id,
            product_id=None,
            status="active",
        ))
        self._session.flush()
        return conversation_id

    def get(
        self,
        conversation_id: str,
        *,
        visitor_id: str,
    ) -> ConversationRecord:
        conversation = self._owned_conversation(
            conversation_id,
            visitor_id=visitor_id,
        )
        messages = self._session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.sequence >= conversation.context_start_sequence,
            )
            .order_by(Message.sequence)
        ).all()
        runs = self._session.scalars(
            select(AnswerRun).where(
                AnswerRun.conversation_id == conversation_id
            )
        ).all()
        modes = {
            run.assistant_message_id: run.mode
            for run in runs
            if run.assistant_message_id is not None
        }
        return ConversationRecord(
            conversation_id=conversation_id,
            product_id=conversation.product_id,
            messages=tuple(
                ConversationMessageRecord(
                    id=message.id,
                    role=message.role,
                    content=message.content,
                    mode=modes.get(message.id),
                )
                for message in messages
            ),
        )

    def resolve_product(
        self,
        conversation_id: str,
        *,
        product_id: str,
        visitor_id: str,
    ) -> ConversationRecord:
        self._owned_conversation(
            conversation_id,
            visitor_id=visitor_id,
        )
        SqlConversationContextStore(self._session).open(
            conversation_id,
            product_id,
            visitor_id=visitor_id,
        )
        return self.get(
            conversation_id,
            visitor_id=visitor_id,
        )

    def get_preferences(self, visitor_id: str) -> UserPreference:
        entity = self._session.get(VisitorPreference, visitor_id)
        if entity is None:
            return UserPreference()
        return UserPreference(
            language=entity.language,
            answer_detail=AnswerDetail(entity.answer_detail),
            show_citations=entity.show_citations,
        )

    def update_preferences(
        self,
        visitor_id: str,
        *,
        language: str,
        answer_detail: AnswerDetail,
        show_citations: bool,
    ) -> UserPreference:
        entity = self._session.get(VisitorPreference, visitor_id)
        if entity is None:
            entity = VisitorPreference(visitor_id=visitor_id)
            self._session.add(entity)
        entity.language = language
        entity.answer_detail = answer_detail.value
        entity.show_citations = show_citations
        self._session.flush()
        return UserPreference(
            language=language,
            answer_detail=answer_detail,
            show_citations=show_citations,
        )

    def add_feedback(
        self,
        conversation_id: str,
        message_id: str,
        *,
        rating: str,
        reason: str | None,
        visitor_id: str,
    ) -> int:
        self._owned_conversation(
            conversation_id,
            visitor_id=visitor_id,
        )
        run = self._session.scalar(
            select(AnswerRun).where(
                AnswerRun.conversation_id == conversation_id,
                AnswerRun.assistant_message_id == message_id,
            )
        )
        if run is None:
            raise ValueError("answer message not found")
        feedback = Feedback(
            answer_run_id=run.id,
            rating=rating,
            reason=reason,
        )
        self._session.add(feedback)
        self._session.flush()
        return feedback.id

    def _owned_conversation(
        self,
        conversation_id: str,
        *,
        visitor_id: str,
    ) -> Conversation:
        conversation = self._session.get(Conversation, conversation_id)
        if conversation is None:
            raise ValueError("conversation not found")
        if conversation.visitor_id != visitor_id:
            raise PermissionError(
                "conversation visitor does not match"
            )
        return conversation
