from rag_app.answering.models import (
    AnswerMode,
    AnswerObserver,
    AnswerResult,
    AnswerVerifier,
    DraftAnswer,
    Evidence,
    Generator,
    Retriever,
    RiskLevel,
)
from rag_app.answering.policy import (
    classify_risk,
    is_general_concept_question,
)

_FEEDBACK_INSTRUCTIONS = {
    "missing_citation": (
        "Cite every factual sentence and introductory lead-in."
    ),
    "uncited_claim": (
        "Cite every factual sentence, bullet, and introductory lead-in."
    ),
    "citation_mismatch": (
        "Use only the provided citation indices and cover every factual claim."
    ),
    "invalid_citation_index": (
        "Use only evidence indices from 1 to the number of supplied items."
    ),
    "unknown_citation": (
        "Cite only evidence items supplied in this request."
    ),
    "semantic_unsupported": (
        "Remove claims that are not directly supported by the cited evidence."
    ),
    "semantic_unverified": (
        "Only state claims that the cited evidence can directly verify."
    ),
    "semantic_check_failed": (
        "Keep the answer strictly within directly stated evidence."
    ),
    "language_mismatch": (
        "Write the answer in the same language as the user question."
    ),
    "non_manual_marker_missing": (
        'Start the answer with the exact marker "非手册内容：".'
    ),
    "general_citations_forbidden": (
        "Do not include citations in a general explanation."
    ),
    "general_unsafe_content": (
        "Remove device-specific steps, compatibility claims, repair, or "
        "safety handling."
    ),
}


class AnswerLoop:
    def __init__(
        self,
        retriever: Retriever,
        generator: Generator,
        verifier: AnswerVerifier,
        allow_general_fallback: bool = False,
        max_attempts: int = 2,
    ) -> None:
        if max_attempts < 1 or max_attempts > 2:
            raise ValueError("max_attempts must be between 1 and 2")
        self._retriever = retriever
        self._generator = generator
        self._verifier = verifier
        self._allow_general_fallback = allow_general_fallback
        self._max_attempts = max_attempts

    def run(
        self,
        question: str,
        *,
        observer: AnswerObserver | None = None,
        risk_question: str | None = None,
    ) -> AnswerResult:
        risk = classify_risk(risk_question or question)
        verification_question = risk_question or question
        general_concept = (
            risk is RiskLevel.NORMAL
            and self._allow_general_fallback
            and (
                is_general_concept_question(question)
                or is_general_concept_question(risk_question or question)
            )
        )

        verification_feedback: str | None = None
        for attempt in range(1, self._max_attempts + 1):
            if attempt > 1:
                self._stage(observer, "retrying")
            self._stage(observer, "retrieving")
            evidence = self._retriever.retrieve(question)
            self._stage(observer, "reranking")
            if general_concept:
                mode = AnswerMode.GENERAL_EXPLANATION
            elif evidence:
                mode = AnswerMode.MANUAL_GROUNDED
            else:
                continue

            self._stage(observer, "generating")
            draft = self._generator.generate(
                question,
                evidence,
                mode,
                feedback=verification_feedback,
            )
            if draft.refused:
                return AnswerResult(
                    mode=AnswerMode.REFUSED,
                    text=(
                        "当前手册没有足够依据回答这个问题，"
                        "请联系官方支持。"
                    ),
                    citations=(),
                    attempts=attempt,
                )
            self._stage(observer, "verifying")
            passed, verification_feedback = self._check_answer(
                draft,
                evidence,
                question=verification_question,
                mode=mode,
                observer=observer,
            )
            if passed:
                return AnswerResult(
                    mode=mode,
                    text=draft.text,
                    citations=draft.citations,
                    attempts=attempt,
                    evidence=(evidence if mode is AnswerMode.MANUAL_GROUNDED else ()),
                )

        return AnswerResult(
            mode=AnswerMode.REFUSED,
            text="当前手册没有足够依据回答这个问题，请联系官方支持。",
            citations=(),
            attempts=self._max_attempts,
        )

    def _check_answer(
        self,
        draft: DraftAnswer,
        evidence: tuple[Evidence, ...],
        *,
        question: str,
        mode: AnswerMode,
        observer: AnswerObserver | None,
    ) -> tuple[bool, str | None]:
        checker = getattr(self._verifier, "check", None)
        if callable(checker):
            for verification_attempt in range(2):
                result = checker(
                    draft,
                    evidence,
                    question=question,
                    mode=mode,
                )
                passed = bool(getattr(result, "passed", False))
                issues = getattr(result, "issues", ())
                if (
                    passed
                    or verification_attempt == 1
                    or not self._has_retryable_verification_issue(issues)
                ):
                    return passed, self._feedback(issues)
                self._stage(observer, "verifying")
            return False, None
        passed = self._verifier.verify(
            draft,
            evidence,
            question=question,
            mode=mode,
        )
        return passed, None

    @staticmethod
    def _has_retryable_verification_issue(issues: object) -> bool:
        if not isinstance(issues, tuple | list):
            return False
        retryable = {"semantic_check_failed", "semantic_unverified"}
        return any(
            getattr(issue, "value", issue) in retryable
            for issue in issues
        )

    @staticmethod
    def _feedback(issues: object) -> str | None:
        if not isinstance(issues, tuple | list):
            return None
        hints: list[str] = []
        for issue in issues:
            value = getattr(issue, "value", issue)
            if isinstance(value, str):
                hint = _FEEDBACK_INSTRUCTIONS.get(value)
                if hint is not None:
                    hints.append(hint)
        if not hints:
            return None
        return "Previous answer failed verification. " + " ".join(
            dict.fromkeys(hints)
        )

    @staticmethod
    def _stage(
        observer: AnswerObserver | None,
        name: str,
    ) -> None:
        if observer is not None:
            observer.stage(name)
            observer.check_cancelled()
