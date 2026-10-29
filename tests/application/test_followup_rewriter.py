from rag_app.application import LlmFollowUpRewriter
from rag_app.conversations import ConversationMessage, ConversationState
from rag_app.remote_models import Generation


class RecordingLlm:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0
        self.system_prompt: str | None = None

    def generate(
        self,
        prompt: str,
        *,
        model: str,
        system_prompt: str | None = None,
    ) -> Generation:
        self.calls += 1
        self.system_prompt = system_prompt
        assert "上一轮如何连接蓝牙" in prompt
        return Generation(self.text, 10, 3)


def test_followup_rewriter_uses_bounded_conversation_context() -> None:
    llm = RecordingLlm("华为平板 C7 如何连接蓝牙设备？")
    context = ConversationState(
        conversation_id="conversation-1",
        product_id="huawei_c7",
        messages=(
            ConversationMessage("user", "C7 支持蓝牙吗？"),
            ConversationMessage("assistant", "上一轮如何连接蓝牙？"),
        ),
    )

    rewritten = LlmFollowUpRewriter(
        llm=llm,
        model="chat",
    ).rewrite("那怎么连接？", context=context)

    assert rewritten == "华为平板 C7 如何连接蓝牙设备？"
    assert llm.calls == 1
    assert llm.system_prompt is not None
    assert "do not add" in llm.system_prompt.casefold()


def test_followup_rewriter_skips_llm_without_history() -> None:
    llm = RecordingLlm("unused")
    context = ConversationState(
        conversation_id="conversation-1",
        product_id="huawei_c7",
        messages=(),
    )

    rewritten = LlmFollowUpRewriter(
        llm=llm,
        model="chat",
    ).rewrite("那怎么连接？", context=context)

    assert rewritten == "那怎么连接？"
    assert llm.calls == 0
