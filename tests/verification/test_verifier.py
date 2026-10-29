from rag_app.answering import AnswerMode, DraftAnswer, Evidence
from rag_app.remote_models import Generation
from rag_app.verification import (
    CitationVerifier,
    RemoteSemanticSupportChecker,
    SupportDecision,
    SupportStatus,
    VerificationIssue,
)


class AcceptingSemanticChecker:
    def supports(
        self,
        *,
        claim: str,
        question: str,
        evidence: tuple[Evidence, ...],
    ) -> bool:
        return True


class RejectingSemanticChecker:
    def supports(
        self,
        *,
        claim: str,
        question: str,
        evidence: tuple[Evidence, ...],
    ) -> bool:
        return False


class JsonLlm:
    def __init__(self, text: str) -> None:
        self.text = text
        self.system_prompt: str | None = None

    def generate(
        self,
        prompt: str,
        *,
        model: str,
        system_prompt: str | None = None,
    ) -> Generation:
        self.system_prompt = system_prompt
        assert "<manual_evidence>" in prompt
        assert "<claim>" in prompt
        return Generation(self.text, 10, 2)


def test_valid_citations_pass() -> None:
    verifier = CitationVerifier(
        semantic_checker=AcceptingSemanticChecker()
    )
    draft = DraftAnswer("不要拆机。[1]", ("chunk-1",))
    evidence = (Evidence("chunk-1", "请勿拆机。", 3),)

    result = verifier.check(draft, evidence)

    assert result.passed is True
    assert result.issues == ()
    assert verifier.verify(draft, evidence) is True


def test_empty_answer_fails() -> None:
    result = CitationVerifier().check(
        DraftAnswer("", ()),
        (Evidence("chunk-1", "请勿拆机。", 3),),
    )

    assert result.passed is False
    assert VerificationIssue.EMPTY_ANSWER in result.issues


def test_missing_citation_fails() -> None:
    result = CitationVerifier().check(
        DraftAnswer("不要拆机。", ()),
        (Evidence("chunk-1", "请勿拆机。", 3),),
    )

    assert result.passed is False
    assert VerificationIssue.MISSING_CITATION in result.issues


def test_unknown_citation_fails() -> None:
    result = CitationVerifier().check(
        DraftAnswer("不要拆机。[1]", ("chunk-missing",)),
        (Evidence("chunk-1", "请勿拆机。", 3),),
    )

    assert result.passed is False
    assert VerificationIssue.UNKNOWN_CITATION in result.issues


def test_inline_citation_outside_evidence_fails() -> None:
    result = CitationVerifier(
        semantic_checker=AcceptingSemanticChecker()
    ).check(
        DraftAnswer(
            "按电源键开机[1]，保修三年[9]。",
            ("chunk-1",),
        ),
        (Evidence("chunk-1", "按电源键开机。", 3),),
    )

    assert result.passed is False
    assert VerificationIssue.INVALID_CITATION_INDEX in result.issues


def test_semantically_contradicted_answer_fails() -> None:
    result = CitationVerifier(
        semantic_checker=RejectingSemanticChecker()
    ).check(
        DraftAnswer(
            "请立即短接并继续使用[1]。",
            ("chunk-1",),
        ),
        (Evidence("chunk-1", "请勿短接电池保护电路。", 3),),
    )

    assert result.passed is False
    assert VerificationIssue.SEMANTIC_UNSUPPORTED in result.issues


def test_exact_cited_evidence_short_circuits_semantic_failure() -> None:
    result = CitationVerifier(
        semantic_checker=RejectingSemanticChecker()
    ).check(
        DraftAnswer(
            "按 F10 键保存并退出，即可恢复 BIOS 默认设置。[1]",
            ("chunk-1",),
        ),
        (
            Evidence(
                "chunk-1",
                "按 F9 键调出恢复出厂设置窗口，选择是，"
                "按 F10 键保存并退出，即可恢复 BIOS 默认设置。",
                9,
            ),
        ),
    )

    assert result.passed is True
    assert result.issues == ()


def test_exact_evidence_does_not_allow_removing_a_prohibition() -> None:
    result = CitationVerifier().check(
        DraftAnswer("短接电池保护电路。[1]", ("chunk-1",)),
        (Evidence("chunk-1", "请勿短接电池保护电路。", 3),),
    )

    assert result.passed is False
    assert result.issues


def test_remote_semantic_checker_requires_json_support_decision() -> None:
    llm = JsonLlm('{"supported": true}')
    checker = RemoteSemanticSupportChecker(
        llm=llm,
        model="verifier",
    )

    supported = checker.supports(
        claim="请勿拆机。",
        question="可以拆机吗？",
        evidence=(Evidence("chunk-1", "请勿拆机。", 3),),
    )

    assert supported is True
    assert llm.system_prompt is not None
    assert "untrusted data" in llm.system_prompt


def test_remote_semantic_checker_fails_closed_on_invalid_output() -> None:
    checker = RemoteSemanticSupportChecker(
        llm=JsonLlm("supported"),
        model="verifier",
    )

    supported = checker.supports(
        claim="请勿拆机。",
        question="可以拆机吗？",
        evidence=(Evidence("chunk-1", "请勿拆机。", 3),),
    )

    assert supported is False


def test_remote_semantic_checker_exposes_invalid_output_status() -> None:
    checker = RemoteSemanticSupportChecker(
        llm=JsonLlm("supported"),
        model="verifier",
    )

    decision = checker.assess(
        claim="请勿拆机。",
        question="可以拆机吗？",
        evidence=(Evidence("chunk-1", "请勿拆机。", 3),),
    )

    assert decision.status is SupportStatus.CHECK_FAILED


def test_uncertain_semantic_decision_is_not_a_contradiction() -> None:
    class UncertainSemanticChecker:
        def assess(
            self,
            *,
            claim: str,
            question: str,
            evidence: tuple[Evidence, ...],
        ) -> SupportDecision:
            return SupportDecision(SupportStatus.UNCERTAIN)

    result = CitationVerifier(
        semantic_checker=UncertainSemanticChecker()
    ).check(
        DraftAnswer("按电源键开机。[1]", ("chunk-1",)),
        (Evidence("chunk-1", "按电源键可开机。", 3),),
    )

    assert result.passed is False
    assert result.issues == (VerificationIssue.SEMANTIC_UNVERIFIED,)


def test_general_explanation_requires_non_manual_marker() -> None:
    result = CitationVerifier().check(
        DraftAnswer("蓝牙是一种短距离通信技术。", ()),
        (),
        mode=AnswerMode.GENERAL_EXPLANATION,
    )

    assert result.passed is False
    assert VerificationIssue.NON_MANUAL_MARKER_MISSING in result.issues


def test_marked_general_explanation_passes_without_citations() -> None:
    result = CitationVerifier().check(
        DraftAnswer("非手册内容：蓝牙是一种短距离通信技术。", ()),
        (),
        mode=AnswerMode.GENERAL_EXPLANATION,
    )

    assert result.passed is True
    assert result.issues == ()


def test_general_explanation_rejects_safety_and_repair_instructions() -> None:
    result = CitationVerifier().check(
        DraftAnswer(
            "非手册内容：请拆开后盖并短接电池保护电路。",
            (),
        ),
        (),
        mode=AnswerMode.GENERAL_EXPLANATION,
    )

    assert result.passed is False
    assert VerificationIssue.GENERAL_UNSAFE_CONTENT in result.issues


def test_separate_claims_can_cite_different_chunks() -> None:
    result = CitationVerifier(
        semantic_checker=AcceptingSemanticChecker()
    ).check(
        DraftAnswer(
            "先按电源键[1]。再选择语言[2]。",
            ("chunk-1", "chunk-2"),
        ),
        (
            Evidence("chunk-1", "按电源键。", 1),
            Evidence("chunk-2", "选择语言。", 2),
        ),
    )

    assert result.passed is True
    assert result.issues == ()


def test_zero_citation_index_is_rejected() -> None:
    result = CitationVerifier(
        semantic_checker=AcceptingSemanticChecker()
    ).check(
        DraftAnswer("按电源键[0]。", ("chunk-1",)),
        (Evidence("chunk-1", "按电源键。", 1),),
    )

    assert result.passed is False
    assert VerificationIssue.INVALID_CITATION_INDEX in result.issues


def test_semicolon_does_not_split_a_cited_sentence() -> None:
    result = CitationVerifier(
        semantic_checker=AcceptingSemanticChecker()
    ).check(
        DraftAnswer(
            "先连接充电器；再检查充电图标。[1]",
            ("chunk-1",),
        ),
        (Evidence("chunk-1", "连接充电器并检查充电图标。", 1),),
    )

    assert result.passed is True


def test_short_discourse_prefix_is_verified_with_next_cited_claim() -> None:
    class PrefixAwareChecker:
        def supports(
            self,
            *,
            claim: str,
            question: str,
            evidence: tuple[Evidence, ...],
        ) -> bool:
            return claim == "可以。根据用户指南，显示器高度可以调整。"

    result = CitationVerifier(
        semantic_checker=PrefixAwareChecker()
    ).check(
        DraftAnswer(
            "可以。根据用户指南，显示器高度可以调整。[1]",
            ("chunk-1",),
        ),
        (Evidence("chunk-1", "显示器高度可以调整。", 3),),
    )

    assert result.passed is True
    assert result.issues == ()


def test_short_factual_answer_is_verified_with_next_cited_claim() -> None:
    class PrefixAwareChecker:
        def supports(
            self,
            *,
            claim: str,
            question: str,
            evidence: tuple[Evidence, ...],
        ) -> bool:
            return claim == (
                "需要。首次开机时，必须连接电源适配器，"
                "计算机会自动开机。"
            )

    result = CitationVerifier(
        semantic_checker=PrefixAwareChecker()
    ).check(
        DraftAnswer(
            "需要。首次开机时，必须连接电源适配器，"
            "计算机会自动开机。[1]",
            ("chunk-1",),
        ),
        (
            Evidence(
                "chunk-1",
                "首次开机时，必须连接电源适配器，计算机会自动开机。",
                11,
            ),
        ),
    )

    assert result.passed is True
    assert result.issues == ()


def test_negative_short_answer_is_verified_with_next_cited_claim() -> None:
    class PrefixAwareChecker:
        def supports(
            self,
            *,
            claim: str,
            question: str,
            evidence: tuple[Evidence, ...],
        ) -> bool:
            return claim.startswith("不能继续使用。")

    result = CitationVerifier(
        semantic_checker=PrefixAwareChecker()
    ).check(
        DraftAnswer(
            "不能继续使用。电源线损坏时继续使用可能导致触电。[1]",
            ("chunk-1",),
        ),
        (
            Evidence(
                "chunk-1",
                "电源线已损坏时请勿继续使用，以免发生触电或火灾。",
                21,
            ),
        ),
    )

    assert result.passed is True
    assert result.issues == ()


def test_citation_before_spaced_punctuation_has_no_empty_claim() -> None:
    result = CitationVerifier(
        semantic_checker=AcceptingSemanticChecker()
    ).check(
        DraftAnswer(
            "若电源线损坏，请勿继续使用，以免发生触电或火灾[1]\n。",
            ("chunk-1",),
        ),
        (
            Evidence(
                "chunk-1",
                "若电源线损坏，请勿继续使用，以免发生触电或火灾。",
                21,
            ),
        ),
    )

    assert result.passed is True
    assert result.issues == ()


def test_introductory_lead_in_uses_next_cited_bullet() -> None:
    class IntroAwareChecker:
        def supports(
            self,
            *,
            claim: str,
            question: str,
            evidence: tuple[Evidence, ...],
        ) -> bool:
            return claim.startswith("若要切换为功能键模式，可通过以下方式：")

    result = CitationVerifier(
        semantic_checker=IntroAwareChecker()
    ).check(
        DraftAnswer(
            "若要切换为功能键模式，可通过以下方式：\n"
            "- 按下 Fn 键；当指示灯亮起时，表示已锁定为功能键模式。[1]",
            ("chunk-1",),
        ),
        (
            Evidence(
                "chunk-1",
                "按下 Fn 键，当指示灯亮起时，表示已将 F1、F2 "
                "等键锁定为功能键模式。",
                6,
            ),
        ),
    )

    assert result.passed is True
    assert result.issues == ()


def test_chinese_question_rejects_english_answer() -> None:
    result = CitationVerifier(
        semantic_checker=AcceptingSemanticChecker()
    ).check(
        DraftAnswer(
            "Press the power button to start the device.[1]",
            ("chunk-1",),
        ),
        (Evidence("chunk-1", "按电源键开机。", 3),),
        question="如何开机？",
    )

    assert result.passed is False
    assert VerificationIssue.LANGUAGE_MISMATCH in result.issues
