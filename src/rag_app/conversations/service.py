from collections.abc import Sequence

from rag_app.conversations.models import (
    ConversationMessage,
    ConversationState,
)


def summarize_old_messages(
    messages: Sequence[ConversationMessage],
    keep_recent: int = 6,
) -> tuple[str, tuple[ConversationMessage, ...]]:
    if keep_recent < 1:
        raise ValueError("keep_recent must be positive")
    if len(messages) <= keep_recent:
        return "", tuple(messages)

    old = messages[:-keep_recent]
    recent = tuple(messages[-keep_recent:])
    summary = "\n".join(f"{item.role}: {item.content}" for item in old)
    return summary, recent


class ConversationService:
    def start(self, conversation_id: str) -> ConversationState:
        return ConversationState(
            conversation_id=conversation_id,
            product_id=None,
            messages=(),
        )

    def select_product(
        self,
        state: ConversationState,
        product_id: str,
    ) -> ConversationState:
        return state.with_product(product_id)

    def change_product(
        self,
        state: ConversationState,
        product_id: str,
    ) -> ConversationState:
        return ConversationState(
            conversation_id=state.conversation_id,
            product_id=product_id,
            messages=(),
        )

    def append_exchange(
        self,
        state: ConversationState,
        question: str,
        answer: str,
    ) -> ConversationState:
        messages = (
            *state.messages,
            ConversationMessage("user", question),
            ConversationMessage("assistant", answer),
        )
        return state.with_messages(messages)
