from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class AnswerMode(StrEnum):
    MANUAL_GROUNDED = "manual_grounded"
    GENERAL_EXPLANATION = "general_explanation"
    CLARIFICATION = "clarification"
    REFUSED = "refused"


class RiskLevel(StrEnum):
    NORMAL = "normal"
    SAFETY_CRITICAL = "safety_critical"


@dataclass(frozen=True, slots=True)
class Evidence:
    chunk_id: str
    content: str
    page: int
    product_id: str | None = None
    document_version_id: str | None = None
    index_version_id: str | None = None
    document_sha256: str | None = None
    document_name: str | None = None
    version_label: str | None = None
    section_path: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DraftAnswer:
    text: str
    citations: tuple[str, ...]
    refused: bool = False


@dataclass(frozen=True, slots=True)
class AnswerResult:
    mode: AnswerMode
    text: str
    citations: tuple[str, ...]
    attempts: int
    evidence: tuple[Evidence, ...] = ()
    assistant_message_id: str | None = None


class Retriever(Protocol):
    def retrieve(self, question: str) -> tuple[Evidence, ...]: ...


class Generator(Protocol):
    def generate(
        self,
        question: str,
        evidence: tuple[Evidence, ...],
        mode: AnswerMode,
        *,
        feedback: str | None = None,
    ) -> DraftAnswer: ...


class AnswerObserver(Protocol):
    def stage(self, stage: str) -> None: ...

    def check_cancelled(self) -> None: ...


class AnswerCancelled(RuntimeError):
    pass


class AnswerVerifier(Protocol):
    def verify(
        self,
        draft: DraftAnswer,
        evidence: tuple[Evidence, ...],
        *,
        question: str,
        mode: AnswerMode,
    ) -> bool: ...
