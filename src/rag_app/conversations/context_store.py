from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from rag_app.conversations.models import (
    ConversationExchange,
    ConversationMessage,
    ConversationState,
)
from rag_app.persistence.schema import (
    Conversation,
    ConversationSummary,
    Message,
)


class SqlConversationContextStore:
    def __init__(
        self,
        session: Session,
        *,
        visitor_id: str = "anonymous",
        keep_recent: int = 6,
    ) -> None:
        if keep_recent < 1:
            raise ValueError("keep_recent must be positive")
        self._session = session
        self._default_visitor_id = visitor_id
        self._keep_recent = keep_recent

    def product_id(
        self,
        conversation_id: str,
        *,
        visitor_id: str | None = None,
    ) -> str | None:
        conversation = self._session.get(Conversation, conversation_id)
        if conversation is None:
            return None
        self._verify_visitor(conversation, visitor_id)
        return conversation.product_id

    def open(
        self,
        conversation_id: str,
        product_id: str,
        *,
        visitor_id: str | None = None,
    ) -> ConversationState:
        resolved_visitor_id = visitor_id or self._default_visitor_id
        conversation = self._session.get(Conversation, conversation_id)
        if conversation is None:
            conversation = Conversation(
                id=conversation_id,
                visitor_id=resolved_visitor_id,
                product_id=product_id,
                status="active",
            )
            self._session.add(conversation)
            self._session.flush()
        else:
            self._verify_visitor(conversation, resolved_visitor_id)
            if conversation.product_id != product_id:
                self._clear_topic(conversation)
                conversation.product_id = product_id
                conversation.status = "active"
                self._session.flush()

        summary_entity = self._session.scalar(
            select(ConversationSummary)
            .where(
                ConversationSummary.conversation_id == conversation_id
            )
            .order_by(
                ConversationSummary.covered_sequence.desc(),
                ConversationSummary.id.desc(),
            )
        )
        recent = self._session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.sequence >= conversation.context_start_sequence,
            )
            .order_by(Message.sequence.desc())
            .limit(self._keep_recent)
        ).all()
        return ConversationState(
            conversation_id=conversation_id,
            product_id=product_id,
            messages=tuple(
                ConversationMessage(role=item.role, content=item.content)
                for item in reversed(recent)
            ),
            summary=(
                summary_entity.summary if summary_entity is not None else ""
            ),
        )

    def append_exchange(
        self,
        conversation_id: str,
        product_id: str,
        question: str,
        answer: str,
        *,
        visitor_id: str | None = None,
    ) -> ConversationExchange:
        user_message_id = self.begin_exchange(
            conversation_id,
            product_id,
            question,
            visitor_id=visitor_id,
        )
        return self.complete_exchange(
            conversation_id,
            product_id,
            user_message_id,
            answer,
            visitor_id=visitor_id,
        )

    def begin_exchange(
        self,
        conversation_id: str,
        product_id: str,
        question: str,
        *,
        visitor_id: str | None = None,
    ) -> str:
        self.open(
            conversation_id,
            product_id,
            visitor_id=visitor_id,
        )
        current_sequence = self._session.scalar(
            select(func.max(Message.sequence)).where(
                Message.conversation_id == conversation_id
            )
        ) or 0
        user_message = Message(
            id=uuid4().hex,
            conversation_id=conversation_id,
            role="user",
            content=question,
            rewritten_query=None,
            sequence=current_sequence + 1,
        )
        self._session.add(user_message)
        self._session.flush()
        return user_message.id

    def complete_exchange(
        self,
        conversation_id: str,
        product_id: str,
        user_message_id: str,
        answer: str,
        *,
        visitor_id: str | None = None,
    ) -> ConversationExchange:
        self.open(
            conversation_id,
            product_id,
            visitor_id=visitor_id,
        )
        current_sequence = self._session.scalar(
            select(func.max(Message.sequence)).where(
                Message.conversation_id == conversation_id
            )
        ) or 0
        assistant_message = Message(
            id=uuid4().hex,
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            rewritten_query=None,
            sequence=current_sequence + 1,
        )
        self._session.add(assistant_message)
        self._session.flush()
        self._refresh_summary(conversation_id)
        return ConversationExchange(
            user_message_id=user_message_id,
            assistant_message_id=assistant_message.id,
        )

    def _refresh_summary(self, conversation_id: str) -> None:
        conversation = self._session.get(Conversation, conversation_id)
        if conversation is None:
            raise ValueError("conversation not found")
        messages = self._session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.sequence >= conversation.context_start_sequence,
            )
            .order_by(Message.sequence)
        ).all()
        if len(messages) <= self._keep_recent:
            return
        old = messages[: -self._keep_recent]
        summary = "\n".join(
            f"{item.role}: {item.content}" for item in old
        )
        entity = self._session.scalar(
            select(ConversationSummary)
            .where(
                ConversationSummary.conversation_id == conversation_id
            )
            .order_by(
                ConversationSummary.covered_sequence.desc(),
                ConversationSummary.id.desc(),
            )
        )
        if entity is None:
            entity = ConversationSummary(
                conversation_id=conversation_id,
                summary=summary,
                covered_message_id=old[-1].id,
                covered_sequence=old[-1].sequence,
                token_estimate=len(summary),
            )
            self._session.add(entity)
        else:
            entity.summary = summary
            entity.covered_message_id = old[-1].id
            entity.covered_sequence = old[-1].sequence
            entity.token_estimate = len(summary)
        self._session.flush()

    def _clear_topic(self, conversation: Conversation) -> None:
        self._session.execute(
            delete(ConversationSummary).where(
                ConversationSummary.conversation_id == conversation.id
            )
        )
        current_sequence = self._session.scalar(
            select(func.max(Message.sequence)).where(
                Message.conversation_id == conversation.id
            )
        ) or 0
        conversation.context_start_sequence = current_sequence + 1

    @staticmethod
    def _verify_visitor(
        conversation: Conversation,
        visitor_id: str | None,
    ) -> None:
        if visitor_id is not None and conversation.visitor_id != visitor_id:
            raise PermissionError(
                "conversation visitor does not match"
            )
