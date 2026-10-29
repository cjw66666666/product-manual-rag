from dataclasses import dataclass

from rag_app.answering import AnswerMode, AnswerResult, DraftAnswer, Evidence
from rag_app.application import ChatAnswerService, ConversationalAnswerService
from rag_app.conversations import (
    ConversationExchange,
    ConversationMessage,
    ConversationService,
    ConversationState,
)


class ScopedRetriever:
    def retrieve(
        self,
        question: str,
        product_id: str,
    ) -> tuple[Evidence, ...]:
        assert product_id == "huawei_c7"
        return (Evidence("chunk-1", "按电源键开机。", 10),)


class Generator:
    def generate(
        self,
        question: str,
        evidence: tuple[Evidence, ...],
        mode: AnswerMode,
        *,
        feedback: str | None = None,
    ) -> DraftAnswer:
        return DraftAnswer("按电源键开机。[1]", ("chunk-1",))


class Verifier:
    def verify(
        self,
        draft: DraftAnswer,
        evidence: tuple[Evidence, ...],
        *,
        question: str,
        mode: AnswerMode,
    ) -> bool:
        return True


def test_chat_service_scopes_retrieval_to_product() -> None:
    result: AnswerResult = ChatAnswerService(
        retriever=ScopedRetriever(),
        generator=Generator(),
        verifier=Verifier(),
    ).answer("怎么开机？", "huawei_c7")

    assert result.mode is AnswerMode.MANUAL_GROUNDED
    assert result.citations == ("chunk-1",)


@dataclass
class MemoryContexts:
    states: dict[str, ConversationState]

    def product_id(
        self,
        conversation_id: str,
        *,
        visitor_id: str | None = None,
    ) -> str | None:
        state = self.states.get(conversation_id)
        return None if state is None else state.product_id

    def open(
        self,
        conversation_id: str,
        product_id: str,
        *,
        visitor_id: str | None = None,
    ) -> ConversationState:
        state = self.states.get(conversation_id)
        if state is None or state.product_id != product_id:
            state = ConversationState(
                conversation_id=conversation_id,
                product_id=product_id,
                messages=(),
            )
            self.states[conversation_id] = state
        return state

    def append_exchange(
        self,
        conversation_id: str,
        product_id: str,
        question: str,
        answer: str,
        *,
        visitor_id: str | None = None,
    ) -> ConversationExchange:
        state = self.open(
            conversation_id,
            product_id,
            visitor_id=visitor_id,
        )
        self.states[conversation_id] = state.with_messages(
            (
                *state.messages,
                *ConversationService().append_exchange(
                    state,
                    question,
                    answer,
                ).messages[len(state.messages):],
            )
        )
        return ConversationExchange(
            user_message_id=f"{conversation_id}-user-{len(state.messages)}",
            assistant_message_id=(
                f"{conversation_id}-assistant-{len(state.messages) + 1}"
            ),
        )

    def begin_exchange(
        self,
        conversation_id: str,
        product_id: str,
        question: str,
        *,
        visitor_id: str | None = None,
    ) -> str:
        state = self.open(
            conversation_id,
            product_id,
            visitor_id=visitor_id,
        )
        self.states[conversation_id] = state.with_messages(
            (*state.messages, ConversationMessage("user", question))
        )
        return f"{conversation_id}-user-{len(state.messages)}"

    def complete_exchange(
        self,
        conversation_id: str,
        product_id: str,
        user_message_id: str,
        answer: str,
        *,
        visitor_id: str | None = None,
    ) -> ConversationExchange:
        state = self.open(
            conversation_id,
            product_id,
            visitor_id=visitor_id,
        )
        self.states[conversation_id] = state.with_messages(
            (*state.messages, ConversationMessage("assistant", answer))
        )
        return ConversationExchange(
            user_message_id=user_message_id,
            assistant_message_id=(
                f"{conversation_id}-assistant-{len(state.messages)}"
            ),
        )


class RecordingRewriter:
    def __init__(self) -> None:
        self.questions: list[tuple[str, ConversationState]] = []

    def rewrite(
        self,
        question: str,
        *,
        context: ConversationState,
    ) -> str:
        self.questions.append((question, context))
        if question == "那蓝牙怎么连接耳机？":
            return "华为平板 C7 如何连接蓝牙耳机？"
        return question


class ContextAwareRetriever:
    def __init__(self) -> None:
        self.questions: list[str] = []

    def retrieve(
        self,
        question: str,
        product_id: str,
    ) -> tuple[Evidence, ...]:
        self.questions.append(question)
        return (Evidence("chunk-1", "打开设置并连接蓝牙设备。", 10),)


class EmptyRetriever:
    def retrieve(
        self,
        question: str,
        product_id: str,
    ) -> tuple[Evidence, ...]:
        return ()


class ContextGenerator:
    modes: list[AnswerMode]

    def __init__(self) -> None:
        self.modes = []

    def generate(
        self,
        question: str,
        evidence: tuple[Evidence, ...],
        mode: AnswerMode,
        *,
        feedback: str | None = None,
    ) -> DraftAnswer:
        self.modes.append(mode)
        if mode is AnswerMode.GENERAL_EXPLANATION:
            return DraftAnswer("非手册内容：这是通用说明。", ())
        return DraftAnswer("打开设置并连接蓝牙设备。[1]", ("chunk-1",))


def test_follow_up_uses_conversation_history_before_retrieval() -> None:
    contexts = MemoryContexts(states={})
    rewriter = RecordingRewriter()
    retriever = ContextAwareRetriever()
    service = ConversationalAnswerService(
        service=ChatAnswerService(
            retriever=retriever,
            generator=ContextGenerator(),
            verifier=Verifier(),
        ),
        contexts=contexts,
        rewriter=rewriter,
    )

    service.answer(
        "C7 支持蓝牙吗？",
        "huawei_c7",
        conversation_id="conversation-1",
    )
    service.answer(
        "那蓝牙怎么连接耳机？",
        "huawei_c7",
        conversation_id="conversation-1",
    )

    assert retriever.questions == [
        "C7 支持蓝牙吗？",
        "华为平板 C7 如何连接蓝牙耳机？",
    ]
    assert len(contexts.states["conversation-1"].messages) == 4


def test_ambiguous_follow_up_returns_clarification_without_retrieval() -> None:
    class Observer:
        def __init__(self) -> None:
            self.stages: list[str] = []

        def stage(self, stage: str) -> None:
            self.stages.append(stage)

        def check_cancelled(self) -> None:
            return

    contexts = MemoryContexts(states={})
    rewriter = RecordingRewriter()
    retriever = ContextAwareRetriever()
    observer = Observer()
    service = ConversationalAnswerService(
        service=ChatAnswerService(
            retriever=retriever,
            generator=ContextGenerator(),
            verifier=Verifier(),
        ),
        contexts=contexts,
        rewriter=rewriter,
    )
    service.answer(
        "C7 支持蓝牙吗？",
        "huawei_c7",
        conversation_id="conversation-1",
    )

    result = service.answer(
        "那怎么连接？",
        "huawei_c7",
        conversation_id="conversation-1",
        observer=observer,
    )

    assert result.mode is AnswerMode.CLARIFICATION
    assert "具体设备" in result.text
    assert result.citations == ()
    assert retriever.questions == ["C7 支持蓝牙吗？"]
    assert len(rewriter.questions) == 1
    assert len(contexts.states["conversation-1"].messages) == 4
    assert observer.stages == ["clarifying"]


def test_product_switch_clears_previous_conversation_context() -> None:
    contexts = MemoryContexts(states={})
    rewriter = RecordingRewriter()
    service = ConversationalAnswerService(
        service=ChatAnswerService(
            retriever=ContextAwareRetriever(),
            generator=ContextGenerator(),
            verifier=Verifier(),
        ),
        contexts=contexts,
        rewriter=rewriter,
    )
    service.answer(
        "C7 支持蓝牙吗？",
        "huawei_c7",
        conversation_id="conversation-1",
    )

    service.answer(
        "MateBook 怎么开机？",
        "huawei_b5_440",
        conversation_id="conversation-1",
    )

    switched_context = rewriter.questions[-1][1]
    assert switched_context.product_id == "huawei_b5_440"
    assert switched_context.messages == ()


def test_original_safety_risk_survives_followup_rewrite() -> None:
    contexts = MemoryContexts(states={})
    generator = ContextGenerator()

    class RiskDroppingRewriter:
        def rewrite(
            self,
            question: str,
            *,
            context: ConversationState,
        ) -> str:
            return "设备怎么办？"

    service = ConversationalAnswerService(
        service=ChatAnswerService(
            retriever=EmptyRetriever(),
            generator=generator,
            verifier=Verifier(),
            allow_general_fallback=True,
        ),
        contexts=contexts,
        rewriter=RiskDroppingRewriter(),
    )

    result = service.answer(
        "设备冒烟了怎么办？",
        "huawei_c7",
        conversation_id="conversation-1",
    )

    assert result.mode is AnswerMode.REFUSED
    assert generator.modes == []
