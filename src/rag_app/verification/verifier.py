import re
from collections.abc import Sequence
from typing import Protocol

from rag_app.answering import AnswerMode, DraftAnswer, Evidence
from rag_app.verification.models import (
    SupportDecision,
    SupportStatus,
    VerificationIssue,
    VerificationResult,
)

_CITATION_PATTERN = re.compile(r"\[(\d+)\]")
_CLAIM_BOUNDARY = re.compile(r"(?<=[。！？!?])|(?<=\n)")
_CJK_PATTERN = re.compile(r"[\u3400-\u9fff]")
_GENERAL_UNSAFE_PATTERN = re.compile(
    r"拆开|拆机|短接|电池保护|维修|更换|进入设置|点击|"
    r"按.{0,8}(?:键|按钮)|连接.{0,12}(?:设备|手机|电脑)|"
    r"兼容|支持.{0,20}(?:型号|接口|协议)|保修|故障原因|"
    r"冒烟|起火|漏液|进水|触电|异味|异常发热|电源线损坏"
)
_DISCOURSE_PREFIXES = {
    "可以",
    "不可以",
    "需要",
    "不需要",
    "能",
    "不能",
    "能够",
    "是",
    "否",
    "有",
    "没有",
    "应当",
    "应该",
    "必须",
    "是的",
    "好的",
    "当然",
}
_NEGATIVE_SHORT_ANSWER_PREFIXES = (
    "不能",
    "不可以",
    "不需要",
    "不会",
    "无需",
)
_INTRO_LEAD_IN_PATTERN = re.compile(
    r"(?:以下|如下).{0,12}(?:方式|方法|步骤)"
)
_NEGATION_PATTERN = re.compile(
    r"请勿|切勿|严禁|禁止|不得|不要|不能|不可|避免|勿"
)


class SemanticSupportChecker(Protocol):
    def supports(
        self,
        *,
        claim: str,
        question: str,
        evidence: tuple[Evidence, ...],
    ) -> bool: ...


class SemanticSupportAssessor(Protocol):
    def assess(
        self,
        *,
        claim: str,
        question: str,
        evidence: tuple[Evidence, ...],
    ) -> SupportDecision: ...


class CitationVerifier:
    def __init__(
        self,
        *,
        semantic_checker: (
            SemanticSupportChecker | SemanticSupportAssessor | None
        ) = None,
    ) -> None:
        self._semantic_checker = semantic_checker

    def check(
        self,
        draft: DraftAnswer,
        evidence: Sequence[Evidence],
        *,
        question: str = "",
        mode: AnswerMode = AnswerMode.MANUAL_GROUNDED,
    ) -> VerificationResult:
        if mode is AnswerMode.GENERAL_EXPLANATION:
            return self._check_general_explanation(
                draft,
                question=question,
            )

        issues: list[VerificationIssue] = []
        if not draft.text.strip():
            issues.append(VerificationIssue.EMPTY_ANSWER)
        if _language_mismatch(question, draft.text):
            issues.append(VerificationIssue.LANGUAGE_MISMATCH)
        if not draft.citations:
            issues.append(VerificationIssue.MISSING_CITATION)

        available = {item.chunk_id for item in evidence}
        if any(citation not in available for citation in draft.citations):
            issues.append(VerificationIssue.UNKNOWN_CITATION)

        cited_indices = tuple(
            int(value) for value in _CITATION_PATTERN.findall(draft.text)
        )
        if not cited_indices:
            issues.append(VerificationIssue.MISSING_CITATION)

        mapped_citation_ids: set[str] = set()
        pending_prefix = ""
        for claim, indices in _claims_with_citations(draft.text):
            if not indices:
                if _is_discourse_prefix(claim):
                    pending_prefix += claim
                    continue
                issues.append(VerificationIssue.UNCITED_CLAIM)
                pending_prefix = ""
                continue
            if any(
                index < 1 or index > len(evidence)
                for index in indices
            ):
                issues.append(VerificationIssue.INVALID_CITATION_INDEX)
                pending_prefix = ""
                continue
            verified_claim = f"{pending_prefix}{claim}".strip()
            pending_prefix = ""

            cited_evidence = tuple(
                dict.fromkeys(
                    evidence[index - 1] for index in indices
                )
            )
            mapped_ids = {
                item.chunk_id for item in cited_evidence
            }
            mapped_citation_ids.update(mapped_ids)

            if _has_exact_evidence_support(
                verified_claim,
                cited_evidence,
            ):
                continue
            if self._semantic_checker is None:
                issues.append(VerificationIssue.SEMANTIC_UNVERIFIED)
                continue
            try:
                assessor = getattr(
                    self._semantic_checker,
                    "assess",
                    None,
                )
                if callable(assessor):
                    decision = assessor(
                        claim=verified_claim,
                        question=question,
                        evidence=cited_evidence,
                    )
                    if decision.status is SupportStatus.SUPPORTED:
                        continue
                    if decision.status is SupportStatus.UNCERTAIN:
                        issues.append(
                            VerificationIssue.SEMANTIC_UNVERIFIED
                        )
                        continue
                    if decision.status is SupportStatus.CHECK_FAILED:
                        issues.append(
                            VerificationIssue.SEMANTIC_CHECK_FAILED
                        )
                        continue
                    issues.append(VerificationIssue.SEMANTIC_UNSUPPORTED)
                    continue
                supports = getattr(
                    self._semantic_checker,
                    "supports",
                    None,
                )
                if not callable(supports):
                    issues.append(VerificationIssue.SEMANTIC_CHECK_FAILED)
                    continue
                supported = supports(
                    claim=verified_claim,
                    question=question,
                    evidence=cited_evidence,
                )
            except Exception:
                issues.append(VerificationIssue.SEMANTIC_CHECK_FAILED)
                continue
            if not supported:
                issues.append(VerificationIssue.SEMANTIC_UNSUPPORTED)

        if pending_prefix:
            issues.append(VerificationIssue.UNCITED_CLAIM)

        if mapped_citation_ids != set(draft.citations):
            issues.append(VerificationIssue.CITATION_MISMATCH)

        return VerificationResult(
            passed=not issues,
            issues=tuple(dict.fromkeys(issues)),
        )

    def verify(
        self,
        draft: DraftAnswer,
        evidence: Sequence[Evidence],
        *,
        question: str = "",
        mode: AnswerMode = AnswerMode.MANUAL_GROUNDED,
    ) -> bool:
        return self.check(
            draft,
            evidence,
            question=question,
            mode=mode,
        ).passed

    def _check_general_explanation(
        self,
        draft: DraftAnswer,
        *,
        question: str,
    ) -> VerificationResult:
        issues: list[VerificationIssue] = []
        if not draft.text.strip():
            issues.append(VerificationIssue.EMPTY_ANSWER)
        if _language_mismatch(question, draft.text):
            issues.append(VerificationIssue.LANGUAGE_MISMATCH)
        if "非手册内容" not in draft.text:
            issues.append(VerificationIssue.NON_MANUAL_MARKER_MISSING)
        if draft.citations or _CITATION_PATTERN.search(draft.text):
            issues.append(VerificationIssue.GENERAL_CITATIONS_FORBIDDEN)
        if _GENERAL_UNSAFE_PATTERN.search(draft.text):
            issues.append(VerificationIssue.GENERAL_UNSAFE_CONTENT)
        return VerificationResult(
            passed=not issues,
            issues=tuple(dict.fromkeys(issues)),
        )


def _claims_with_citations(
    text: str,
) -> tuple[tuple[str, tuple[int, ...]], ...]:
    claims: list[tuple[str, tuple[int, ...]]] = []
    normalized = re.sub(
        r"([。！？!?])((?:\[\d+\])+)",
        r"\2\1",
        text,
    )
    for segment in _CLAIM_BOUNDARY.split(normalized):
        indices = tuple(
            int(value) for value in _CITATION_PATTERN.findall(segment)
        )
        claim = _CITATION_PATTERN.sub("", segment).strip()
        if claim and _normalized_exact_text(claim):
            claims.append((claim, indices))
    return tuple(claims)


def _is_discourse_prefix(claim: str) -> bool:
    normalized = claim.strip().rstrip("。！？!?").strip()
    if (
        len(normalized) <= 80
        and (
            normalized.endswith((":", "："))
            or _INTRO_LEAD_IN_PATTERN.search(normalized)
        )
    ):
        return True
    if normalized in _DISCOURSE_PREFIXES:
        return True
    return (
        len(normalized) <= 12
        and normalized.startswith(_NEGATIVE_SHORT_ANSWER_PREFIXES)
    )


def _has_exact_evidence_support(
    claim: str,
    evidence: tuple[Evidence, ...],
) -> bool:
    normalized_claim = _normalized_exact_text(claim)
    if len(normalized_claim) < 8:
        return False
    claim_has_negation = bool(_NEGATION_PATTERN.search(claim))
    for item in evidence:
        if normalized_claim not in _normalized_exact_text(item.content):
            continue
        evidence_has_negation = bool(
            _NEGATION_PATTERN.search(item.content)
        )
        if claim_has_negation == evidence_has_negation:
            return True
    return False


def _normalized_exact_text(text: str) -> str:
    without_citations = _CITATION_PATTERN.sub("", text)
    return re.sub(
        r"[\W_]+",
        "",
        without_citations.casefold(),
        flags=re.UNICODE,
    )


def _language_mismatch(question: str, answer: str) -> bool:
    return bool(
        _CJK_PATTERN.search(question)
        and answer.strip()
        and not _CJK_PATTERN.search(answer)
    )
