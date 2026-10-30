from dataclasses import dataclass, field

import pytest

from rag_app.answering import (
    AnswerCancelled,
    AnswerLoop,
    AnswerMode,
    AnswerObserver,
    DraftAnswer,
    Evidence,
    RiskLevel,
    classify_risk,
    is_general_concept_question,
)
from rag_app.verification import VerificationIssue, VerificationResult


@dataclass
class FakeRetriever:
    responses: tuple[tuple[Evidence, ...], ...]
    attempts: int = 0

    def retrieve(self, question: str) -> tuple[Evidence, ...]:
        self.attempts += 1
        index = min(self.attempts - 1, len(self.responses) - 1)
        return self.responses[index]


@dataclass
class FakeGenerator:
    calls: int = 0

    def generate(
        self,
        question: str,
        evidence: tuple[Evidence, ...],
        mode: AnswerMode,
        *,
        feedback: str | None = None,
    ) -> DraftAnswer:
        self.calls += 1
        if mode is AnswerMode.GENERAL_EXPLANATION:
            return DraftAnswer("非手册内容：蓝牙是一种短距离通信技术。", ())
        return DraftAnswer("不要拆机。[1]", ("chunk-1",))


@dataclass
class FakeVerifier:
    results: list[bool] = field(default_factory=list)

    def verify(
        self,
        draft: DraftAnswer,
        evidence: tuple[Evidence, ...],
        *,
        question: str,
        mode: AnswerMode,
    ) -> bool:
        return self.results.pop(0)


class RefusingGenerator:
    def generate(
        self,
        question: str,
        evidence: tuple[Evidence, ...],
        mode: AnswerMode,
        *,
        feedback: str | None = None,
    ) -> DraftAnswer:
        return DraftAnswer("证据不足，无法回答。", (), refused=True)


class UnexpectedVerifier:
    def verify(
        self,
        draft: DraftAnswer,
        evidence: tuple[Evidence, ...],
        *,
        question: str,
        mode: AnswerMode,
    ) -> bool:
        raise AssertionError("refused drafts must not be verified")


@dataclass
class RecordingVerifier:
    question: str | None = None

    def verify(
        self,
        draft: DraftAnswer,
        evidence: tuple[Evidence, ...],
        *,
        question: str,
        mode: AnswerMode,
    ) -> bool:
        self.question = question
        return True


def test_safety_question_retries_once_then_answers() -> None:
    evidence = (Evidence("chunk-1", "请勿拆机。", 3),)
    retriever = FakeRetriever((evidence, evidence))
    generator = FakeGenerator()

    result = AnswerLoop(
        retriever=retriever,
        generator=generator,
        verifier=FakeVerifier([False, True]),
    ).run("设备冒烟了怎么办？")

    assert result.mode is AnswerMode.MANUAL_GROUNDED
    assert result.attempts == 2
    assert retriever.attempts == 2
    assert generator.calls == 2
    assert result.evidence[0].chunk_id == "chunk-1"


def test_generator_refusal_is_returned_without_retry_or_citations() -> None:
    evidence = (Evidence("chunk-1", "该手册未给出完整操作步骤。", 3),)

    result = AnswerLoop(
        retriever=FakeRetriever((evidence,)),
        generator=RefusingGenerator(),
        verifier=UnexpectedVerifier(),
    ).run("这个型号如何连接蓝牙？")

    assert result.mode is AnswerMode.REFUSED
    assert result.attempts == 1
    assert result.citations == ()
    assert result.evidence == ()


def test_safety_question_without_evidence_refuses() -> None:
    result = AnswerLoop(
        retriever=FakeRetriever(((),)),
        generator=FakeGenerator(),
        verifier=FakeVerifier([True]),
    ).run("设备漏液了怎么办？")

    assert result.mode is AnswerMode.REFUSED
    assert result.attempts == 2


def test_non_safety_question_can_fall_back_to_general() -> None:
    result = AnswerLoop(
        retriever=FakeRetriever(((),)),
        generator=FakeGenerator(),
        verifier=FakeVerifier([True]),
        allow_general_fallback=True,
    ).run("什么是蓝牙？")

    assert result.mode is AnswerMode.GENERAL_EXPLANATION
    assert result.text.startswith("非手册内容")
    assert result.citations == ()


def test_general_concept_uses_general_mode_even_with_evidence() -> None:
    result = AnswerLoop(
        retriever=FakeRetriever((
            (Evidence("chunk-1", "无关的手册片段。", 3),),
        )),
        generator=FakeGenerator(),
        verifier=FakeVerifier([True]),
        allow_general_fallback=True,
    ).run("什么是蓝牙？")

    assert result.mode is AnswerMode.GENERAL_EXPLANATION
    assert result.text.startswith("非手册内容")
    assert result.citations == ()


def test_general_follow_up_uses_original_question_context() -> None:
    result = AnswerLoop(
        retriever=FakeRetriever((
            (Evidence("chunk-1", "无关的手册片段。", 3),),
        )),
        generator=FakeGenerator(),
        verifier=FakeVerifier([True]),
        allow_general_fallback=True,
    ).run(
        "蓝牙与 WiFi 的主要差异",
        risk_question="它和 Wi-Fi 有什么区别？",
    )

    assert result.mode is AnswerMode.GENERAL_EXPLANATION


def test_verification_feedback_is_passed_to_second_generation() -> None:
    @dataclass
    class VerificationResult:
        passed: bool
        issues: tuple[str, ...]

    class CheckingVerifier:
        calls: int = 0

        def verify(
            self,
            draft: DraftAnswer,
            evidence: tuple[Evidence, ...],
            *,
            question: str,
            mode: AnswerMode,
        ) -> bool:
            raise AssertionError("check should be used when available")

        def check(
            self,
            draft: DraftAnswer,
            evidence: tuple[Evidence, ...],
            *,
            question: str,
            mode: AnswerMode,
        ) -> VerificationResult:
            self.calls += 1
            if self.calls == 1:
                return VerificationResult(False, ("uncited_claim",))
            return VerificationResult(True, ())

    class FeedbackGenerator:
        feedbacks: list[str | None]

        def __init__(self) -> None:
            self.feedbacks = []

        def generate(
            self,
            question: str,
            evidence: tuple[Evidence, ...],
            mode: AnswerMode,
            *,
            feedback: str | None = None,
        ) -> DraftAnswer:
            self.feedbacks.append(feedback)
            return DraftAnswer("不要拆机。[1]", ("chunk-1",))

    generator = FeedbackGenerator()
    result = AnswerLoop(
        retriever=FakeRetriever((
            (Evidence("chunk-1", "请勿拆机。", 3),),
        )),
        generator=generator,
        verifier=CheckingVerifier(),
    ).run("设备可以拆机吗？")

    assert result.mode is AnswerMode.MANUAL_GROUNDED
    assert generator.feedbacks[0] is None
    assert generator.feedbacks[1] is not None
    assert "cite" in generator.feedbacks[1].casefold()


def test_transient_verification_failure_retries_without_regeneration() -> None:
    class FlakyCheckingVerifier:
        calls: int = 0

        def verify(
            self,
            draft: DraftAnswer,
            evidence: tuple[Evidence, ...],
            *,
            question: str,
            mode: AnswerMode,
        ) -> bool:
            raise AssertionError("check should be used when available")

        def check(
            self,
            draft: DraftAnswer,
            evidence: tuple[Evidence, ...],
            *,
            question: str,
            mode: AnswerMode,
        ) -> VerificationResult:
            self.calls += 1
            if self.calls == 1:
                return VerificationResult(
                    False,
                    (VerificationIssue.SEMANTIC_CHECK_FAILED,),
                )
            return VerificationResult(True, ())

    retriever = FakeRetriever((
        (Evidence("chunk-1", "请勿拆机。", 3),),
    ))
    generator = FakeGenerator()
    verifier = FlakyCheckingVerifier()

    result = AnswerLoop(
        retriever=retriever,
        generator=generator,
        verifier=verifier,
    ).run("设备可以拆机吗？")

    assert result.mode is AnswerMode.MANUAL_GROUNDED
    assert result.attempts == 1
    assert retriever.attempts == 1
    assert generator.calls == 1
    assert verifier.calls == 2


def test_general_concept_classifier_keeps_safety_and_steps_out() -> None:
    assert is_general_concept_question("什么是蓝牙？")
    assert is_general_concept_question(
        "IP 防护等级中第一个数字和第二个数字分别代表什么？"
    )
    assert is_general_concept_question("蓝牙和 Wi-Fi 有何差异？")
    assert not is_general_concept_question("拆机是什么意思？")
    assert not is_general_concept_question(
        "华为平板 C7 如何连接蓝牙？"
    )


def test_risk_classifier_detects_fire_smoke_and_battery_swelling() -> None:
    assert classify_risk("设备冒烟了") is RiskLevel.SAFETY_CRITICAL
    assert classify_risk("电池鼓包") is RiskLevel.SAFETY_CRITICAL
    assert classify_risk("怎么打开蓝牙") is RiskLevel.NORMAL


def test_risk_classifier_detects_documented_safety_categories() -> None:
    safety_questions = (
        "平板进水了怎么办？",
        "充电时有异味",
        "设备异常发热",
        "电源线损坏还能用吗？",
        "电池保护电路可以短接吗？",
        "这个故障怎么维修？",
    )

    assert all(
        classify_risk(question) is RiskLevel.SAFETY_CRITICAL
        for question in safety_questions
    )


def test_verifier_receives_the_original_question() -> None:
    verifier = RecordingVerifier()

    AnswerLoop(
        retriever=FakeRetriever((
            (Evidence("chunk-1", "请勿拆机。", 3),),
        )),
        generator=FakeGenerator(),
        verifier=verifier,
    ).run("设备可以拆机吗？")

    assert verifier.question == "设备可以拆机吗？"


def test_rewritten_safety_question_is_included_in_verification_context() -> None:
    verifier = RecordingVerifier()

    AnswerLoop(
        retriever=FakeRetriever((
            (Evidence("chunk-1", "请勿拆机。", 3),),
        )),
        generator=FakeGenerator(),
        verifier=verifier,
    ).run(
        "设备冒烟了怎么办？",
        risk_question="那怎么办？",
    )

    assert verifier.question is not None
    assert "设备冒烟了怎么办" in verifier.question
    assert "那怎么办" in verifier.question


@dataclass
class RecordingObserver(AnswerObserver):
    stages: list[str]
    cancelled: bool = False

    def stage(self, stage: str) -> None:
        self.stages.append(stage)

    def check_cancelled(self) -> None:
        if self.cancelled:
            raise RuntimeError("cancelled")


def test_answer_loop_reports_pipeline_stages() -> None:
    observer = RecordingObserver([])

    AnswerLoop(
        retriever=FakeRetriever((
            (Evidence("chunk-1", "请勿拆机。", 3),),
        )),
        generator=FakeGenerator(),
        verifier=FakeVerifier([True]),
    ).run("设备可以拆机吗？", observer=observer)

    assert observer.stages == [
        "retrieving",
        "reranking",
        "generating",
        "verifying",
    ]


def test_cancelled_observer_stops_before_retrieval_and_generation() -> None:
    retriever = FakeRetriever((
        (Evidence("chunk-1", "请勿拆机。", 3),),
    ))
    generator = FakeGenerator()

    class CancelledObserver(RecordingObserver):
        def check_cancelled(self) -> None:
            raise AnswerCancelled("client disconnected")

    with pytest.raises(AnswerCancelled):
        AnswerLoop(
            retriever=retriever,
            generator=generator,
            verifier=FakeVerifier([True]),
        ).run("设备可以拆机吗？", observer=CancelledObserver([]))

    assert retriever.attempts == 0
    assert generator.calls == 0


def test_general_fallback_does_not_add_a_third_model_call() -> None:
    class CountingGenerator:
        calls: int = 0

        def generate(
            self,
            question: str,
            evidence: tuple[Evidence, ...],
            mode: AnswerMode,
            *,
            feedback: str | None = None,
        ) -> DraftAnswer:
            self.calls += 1
            return DraftAnswer("非手册内容：通用说明。", ())

    generator = CountingGenerator()

    result = AnswerLoop(
        retriever=FakeRetriever(((),)),
        generator=generator,
        verifier=FakeVerifier([False, False]),
        allow_general_fallback=True,
    ).run("什么是蓝牙？")

    assert result.mode is AnswerMode.REFUSED
    assert result.attempts == 2
    assert generator.calls == 2
