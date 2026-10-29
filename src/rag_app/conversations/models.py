from dataclasses import dataclass, replace
from enum import StrEnum


class AnswerDetail(StrEnum):
    BRIEF = "brief"
    DETAILED = "detailed"


@dataclass(frozen=True, slots=True)
class UserPreference:
    language: str = "zh-CN"
    answer_detail: AnswerDetail = AnswerDetail.BRIEF
    show_citations: bool = True


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ConversationExchange:
    user_message_id: str
    assistant_message_id: str


@dataclass(frozen=True, slots=True)
class ConversationState:
    conversation_id: str
    product_id: str | None
    messages: tuple[ConversationMessage, ...]
    summary: str = ""

    def with_product(self, product_id: str) -> "ConversationState":
        return replace(self, product_id=product_id)

    def with_messages(
        self,
        messages: tuple[ConversationMessage, ...],
    ) -> "ConversationState":
        return replace(self, messages=messages)
