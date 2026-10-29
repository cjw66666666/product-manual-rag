import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from math import ceil
from time import perf_counter
from typing import Protocol
from uuid import uuid4

from rag_app.answering import AnswerResult, Evidence
from rag_app.retrieval import EvidenceHit, RetrievalTrace, SearchHit


class LatestRetrievalTrace:
    def __init__(self) -> None:
        self._latest: RetrievalTrace | None = None

    @property
    def latest(self) -> RetrievalTrace | None:
        return self._latest

    def record(self, trace: RetrievalTrace) -> None:
        self._latest = trace

    def clear(self) -> None:
        self._latest = None


class AnswerFunction(Protocol):
    def __call__(
        self,
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
    ) -> AnswerResult: ...


@dataclass(frozen=True, slots=True)
class CaseResult:
    case_id: str
    expected_mode: str
    mode_match: bool
    required_facts_hit: bool
    citation_count: int
    invalid_citation_count: int
    latency_ms: float
    passed: bool
    answer: str
    expected_pages: tuple[int, ...]
    cited_pages: tuple[int, ...]
    citation_hit: bool
    recall_at_20: float | None = None
    recall_at_30: float | None = None
    rrf_best_rank: int | None = None
    rerank_best_rank: int | None = None
    final_top_k_hit: bool | None = None
    error: str | None = None
    forbidden_claim_hit: bool = False


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    total: int
    answerable_total: int
    refused_total: int
    passed: int
    pass_rate: float
    mode_match_rate: float
    citation_hit_rate: float
    required_facts_hit_rate: float
    recall_at_20_mean: float | None
    recall_at_30_mean: float | None
    final_top_k_hit_rate: float | None
    average_latency_ms: float
    p95_latency_ms: float
    invalid_citations: int
    errors: int
    forbidden_claim_cases: int


def _expected_pages(case: dict[str, object]) -> tuple[int, ...]:
    must_cite = case.get("must_cite")
    if not isinstance(must_cite, list):
        return ()
    return tuple(
        page
        for item in must_cite
        if isinstance(item, dict)
        and isinstance((page := item.get("page")), int)
    )


def _expected_citations(
    case: dict[str, object],
) -> tuple[dict[str, object], ...]:
    citations = case.get("must_cite")
    if not isinstance(citations, list):
        return ()
    return tuple(item for item in citations if isinstance(item, dict))


def _normalized(text: str) -> str:
    return "".join(text.casefold().split())


def _normalized_fact(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = normalized.replace("×", "x").replace("✕", "x")
    return re.sub(
        r"[\W_]+",
        "",
        normalized,
        flags=re.UNICODE,
    )


def _contains_fact(text: str, fact: str) -> bool:
    normalized_fact = _normalized_fact(fact)
    return bool(normalized_fact) and (
        normalized_fact in _normalized_fact(text)
    )


def _quote_matches(expected: str, actual: str) -> bool:
    left = _normalized(expected)
    right = _normalized(actual)
    if not left or not right:
        return False
    if left in right or right in left:
        return True
    match = SequenceMatcher(
        None,
        left,
        right,
        autojunk=False,
    ).find_longest_match()
    return match.size >= min(40, max(12, len(left) // 3))


def _matches_expected(
    expected: dict[str, object],
    *,
    page: int,
    content: str,
    document_sha256: str | None = None,
    section_path: tuple[str, ...] = (),
) -> bool:
    expected_page = expected.get("page")
    if not isinstance(expected_page, int):
        return False
    allowed_pages = {expected_page}
    alternate_pages = expected.get("alternate_pages")
    if isinstance(alternate_pages, list):
        allowed_pages.update(
            item for item in alternate_pages if isinstance(item, int)
        )
    if page not in allowed_pages:
        return False
    expected_sha = expected.get("document_sha256")
    if (
        isinstance(expected_sha, str)
        and document_sha256 != expected_sha
    ):
        return False
    expected_section = expected.get("section_path")
    if isinstance(expected_section, list):
        expected_path = tuple(
            item for item in expected_section if isinstance(item, str)
        )
        if expected_path and not any(
            expected in actual or actual in expected
            for expected in expected_path
            for actual in section_path
        ):
            return False
    expected_quote = expected.get("evidence_quote")
    if isinstance(expected_quote, str) and expected_quote.strip():
        return _quote_matches(expected_quote, content)
    return True


def _recall_at(
    expected: tuple[dict[str, object], ...],
    hits: tuple[SearchHit | EvidenceHit, ...],
    limit: int,
) -> float | None:
    if not expected:
        return None
    matched = sum(
        any(
            _matches_expected(
                item,
                page=hit.page,
                content=hit.content,
                document_sha256=hit.document_sha256,
                section_path=hit.section_path,
            )
            for hit in hits[:limit]
        )
        for item in expected
    )
    return matched / len(expected)


def _best_rank(
    expected: tuple[dict[str, object], ...],
    hits: tuple[SearchHit | EvidenceHit, ...],
) -> int | None:
    for rank, hit in enumerate(hits, start=1):
        if any(
            _matches_expected(
                item,
                page=hit.page,
                content=hit.content,
                document_sha256=hit.document_sha256,
                section_path=hit.section_path,
            )
            for item in expected
        ):
            return rank
    return None


def _contains_expected(
    expected: tuple[dict[str, object], ...],
    hits: tuple[SearchHit | EvidenceHit, ...],
) -> bool | None:
    if not expected:
        return None
    return _best_rank(expected, hits) is not None


def _evidence_hit(
    expected: tuple[dict[str, object], ...],
    evidence_by_id: dict[str, Evidence],
    cited_ids: tuple[str, ...],
) -> bool:
    if not expected:
        return False
    evidence = tuple(
        evidence_by_id[chunk_id]
        for chunk_id in cited_ids
        if chunk_id in evidence_by_id
    )
    return all(
        any(
            _matches_expected(
                item,
                page=hit.page,
                content=hit.content,
                document_sha256=hit.document_sha256,
                section_path=hit.section_path,
            )
            for hit in evidence
        )
        for item in expected
    )


def evaluate_case(
    case: dict[str, object],
    answer_fn: AnswerFunction,
    *,
    trace: RetrievalTrace | None = None,
    trace_fn: Callable[[], RetrievalTrace | None] | None = None,
) -> CaseResult:
    case_id = str(case["case_id"])
    messages = case.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("evaluation case requires at least one message")
    product_id = str(case["product_id"])
    expected_pages = _expected_pages(case)
    expected_citations = _expected_citations(case)
    expected_mode = str(case["expected_mode"])
    required_values = case.get("required_facts")
    if not isinstance(required_values, list):
        required_values = []
    required_facts = tuple(
        str(value)
        for value in required_values
        if isinstance(value, str)
    )
    forbidden_values = case.get("forbidden_claims")
    if not isinstance(forbidden_values, list):
        forbidden_values = []
    forbidden_claims = tuple(
        str(value)
        for value in forbidden_values
        if isinstance(value, str)
    )
    started = perf_counter()
    try:
        conversation_id = (
            f"eval-{case_id[:48]}-{uuid4().hex[:8]}"
        )
        result: AnswerResult | None = None
        for message in messages:
            result = answer_fn(
                str(message),
                product_id,
                conversation_id=conversation_id,
            )
        if result is None:
            raise ValueError("evaluation case produced no answer")
        resolved_trace = (
            trace
            if trace is not None
            else trace_fn()
            if trace_fn is not None
            else None
        )
    except Exception as exc:
        return CaseResult(
            case_id=case_id,
            expected_mode=expected_mode,
            mode_match=False,
            required_facts_hit=False,
            citation_count=0,
            invalid_citation_count=0,
            latency_ms=(perf_counter() - started) * 1000,
            passed=False,
            answer="",
            expected_pages=expected_pages,
            cited_pages=(),
            citation_hit=False,
            error=str(exc),
            forbidden_claim_hit=False,
        )

    evidence_by_id: dict[str, Evidence] = {
        item.chunk_id: item for item in result.evidence
    }
    cited_pages = tuple(
        evidence_by_id[chunk_id].page
        for chunk_id in result.citations
        if chunk_id in evidence_by_id
    )
    mode_match = result.mode.value == expected_mode
    invalid_citation_count = sum(
        chunk_id not in evidence_by_id for chunk_id in result.citations
    )
    citation_hit = (
        _evidence_hit(
            expected_citations,
            evidence_by_id,
            result.citations,
        )
        if expected_citations
        else not result.citations
    )
    required_facts_hit = all(
        _contains_fact(result.text, fact)
        for fact in required_facts
    )
    forbidden_claim_hit = any(
        _contains_fact(result.text, claim)
        for claim in forbidden_claims
    )
    if expected_mode == "manual_grounded":
        passed = (
            mode_match
            and citation_hit
            and required_facts_hit
            and not forbidden_claim_hit
            and invalid_citation_count == 0
        )
    else:
        passed = (
            mode_match
            and required_facts_hit
            and not forbidden_claim_hit
            and not result.citations
            and invalid_citation_count == 0
        )

    recall_at_20: float | None = None
    recall_at_30: float | None = None
    rrf_best_rank: int | None = None
    rerank_best_rank: int | None = None
    final_top_k_hit: bool | None = None
    if resolved_trace is not None and expected_citations:
        recall_at_20 = _recall_at(
            expected_citations,
            resolved_trace.rrf,
            20,
        )
        recall_at_30 = _recall_at(
            expected_citations,
            resolved_trace.rrf,
            30,
        )
        rrf_best_rank = _best_rank(
            expected_citations,
            resolved_trace.rrf,
        )
        rerank_best_rank = _best_rank(
            expected_citations,
            resolved_trace.reranked,
        )
        final_top_k_hit = _contains_expected(
            expected_citations,
            resolved_trace.final,
        )

    return CaseResult(
        case_id=case_id,
        expected_mode=expected_mode,
        mode_match=mode_match,
        required_facts_hit=required_facts_hit,
        citation_count=len(result.citations),
        invalid_citation_count=invalid_citation_count,
        latency_ms=(perf_counter() - started) * 1000,
        passed=passed,
        answer=result.text,
        expected_pages=expected_pages,
        cited_pages=cited_pages,
        citation_hit=citation_hit,
        recall_at_20=recall_at_20,
        recall_at_30=recall_at_30,
        rrf_best_rank=rrf_best_rank,
        rerank_best_rank=rerank_best_rank,
        final_top_k_hit=final_top_k_hit,
        forbidden_claim_hit=forbidden_claim_hit,
    )


def summarize(results: tuple[CaseResult, ...]) -> EvaluationSummary:
    total = len(results)
    if total == 0:
        raise ValueError("at least one result is required")

    def rate(values: list[bool]) -> float:
        return sum(values) / total

    def optional_rate(values: list[bool]) -> float | None:
        return sum(values) / len(values) if values else None

    def optional_mean(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    ordered_latencies = sorted(result.latency_ms for result in results)
    p95_index = max(0, ceil(len(ordered_latencies) * 0.95) - 1)
    answerable = [
        result for result in results if result.recall_at_20 is not None
    ]
    manual_results = [
        result for result in results if result.expected_pages
    ]

    return EvaluationSummary(
        total=total,
        answerable_total=len(manual_results),
        refused_total=sum(
            result.expected_mode == "refused"
            for result in results
        ),
        passed=sum(result.passed for result in results),
        pass_rate=rate([result.passed for result in results]),
        mode_match_rate=rate([result.mode_match for result in results]),
        citation_hit_rate=(
            sum(result.citation_hit for result in manual_results)
            / len(manual_results)
            if manual_results
            else 0.0
        ),
        required_facts_hit_rate=(
            sum(result.required_facts_hit for result in manual_results)
            / len(manual_results)
            if manual_results
            else 0.0
        ),
        recall_at_20_mean=optional_mean(
            [
                result.recall_at_20
                for result in answerable
                if result.recall_at_20 is not None
            ]
        ),
        recall_at_30_mean=optional_mean(
            [
                result.recall_at_30
                for result in answerable
                if result.recall_at_30 is not None
            ]
        ),
        final_top_k_hit_rate=optional_rate(
            [
                result.final_top_k_hit
                for result in answerable
                if result.final_top_k_hit is not None
            ]
        ),
        average_latency_ms=sum(
            result.latency_ms for result in results
        )
        / total,
        p95_latency_ms=ordered_latencies[p95_index],
        invalid_citations=sum(
            result.invalid_citation_count for result in results
        ),
        errors=sum(result.error is not None for result in results),
        forbidden_claim_cases=sum(
            result.forbidden_claim_hit for result in results
        ),
    )
