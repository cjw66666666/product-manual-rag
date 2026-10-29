from dataclasses import dataclass
from enum import StrEnum


class VerificationIssue(StrEnum):
    MISSING_CITATION = "missing_citation"
    UNKNOWN_CITATION = "unknown_citation"
    EMPTY_ANSWER = "empty_answer"
    INVALID_CITATION_INDEX = "invalid_citation_index"
    UNCITED_CLAIM = "uncited_claim"
    CITATION_MISMATCH = "citation_mismatch"
    SEMANTIC_UNVERIFIED = "semantic_unverified"
    SEMANTIC_UNSUPPORTED = "semantic_unsupported"
    SEMANTIC_CHECK_FAILED = "semantic_check_failed"
    NON_MANUAL_MARKER_MISSING = "non_manual_marker_missing"
    GENERAL_CITATIONS_FORBIDDEN = "general_citations_forbidden"
    GENERAL_UNSAFE_CONTENT = "general_unsafe_content"
    LANGUAGE_MISMATCH = "language_mismatch"


class SupportStatus(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNCERTAIN = "uncertain"
    CHECK_FAILED = "check_failed"


@dataclass(frozen=True, slots=True)
class SupportDecision:
    status: SupportStatus
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class VerificationResult:
    passed: bool
    issues: tuple[VerificationIssue, ...]
