from rag_app.answering import AnswerMode, DraftAnswer, Evidence
from rag_app.core import build_core_answer_loop


class EmptyRetriever:
    def retrieve(self, question: str) -> tuple[Evidence, ...]:
        return ()


class UnusedGenerator:
    def generate(
        self,
        question: str,
        evidence: tuple[Evidence, ...],
        mode: AnswerMode,
        *,
        feedback: str | None = None,
    ) -> DraftAnswer:
        raise AssertionError("generator should not be called")


def test_core_composition_returns_a_refusal_without_evidence() -> None:
    result = build_core_answer_loop(
        retriever=EmptyRetriever(),
        generator=UnusedGenerator(),
    ).run("怎么开机？")

    assert result.mode is AnswerMode.REFUSED
    assert result.attempts == 2
