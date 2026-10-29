import logging
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Literal, Protocol
from uuid import uuid4

from rag_app.answering import AnswerMode, AnswerObserver, AnswerResult

logger = logging.getLogger(__name__)


class AnswerService(Protocol):
    def conversation_product(
        self,
        conversation_id: str,
        *,
        visitor_id: str | None = None,
    ) -> str | None: ...

    def answer(
        self,
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
        observer: AnswerObserver | None = None,
        visitor_id: str | None = None,
    ) -> AnswerResult: ...


@dataclass(frozen=True, slots=True)
class AnswerTraceResult:
    status: Literal["succeeded", "failed"]
    mode: AnswerMode | None
    citation_count: int
    attempts: int
    latency_ms: float
    error_type: str | None = None


class AnswerTraceSink(Protocol):
    def start_answer(self, *, trace_id: str, product_id: str) -> None: ...

    def finish_answer(
        self,
        *,
        trace_id: str,
        result: AnswerTraceResult,
    ) -> None: ...


class TraceScoreSink(Protocol):
    def score_trace(
        self,
        *,
        trace_id: str,
        name: str,
        value: float | bool,
    ) -> None: ...


class TraceSink(AnswerTraceSink, TraceScoreSink, Protocol):
    pass


class NullAnswerTraceSink:
    def start_answer(self, *, trace_id: str, product_id: str) -> None:
        pass

    def finish_answer(
        self,
        *,
        trace_id: str,
        result: AnswerTraceResult,
    ) -> None:
        pass

    def score_trace(
        self,
        *,
        trace_id: str,
        name: str,
        value: float | bool,
    ) -> None:
        pass


class CapturingTraceSink:
    def __init__(self, *, delegate: AnswerTraceSink) -> None:
        self._delegate = delegate
        self.latest_trace_id: str | None = None
        self.latest_result: AnswerTraceResult | None = None

    def start_answer(self, *, trace_id: str, product_id: str) -> None:
        self.latest_trace_id = trace_id
        self.latest_result = None
        self._delegate.start_answer(
            trace_id=trace_id,
            product_id=product_id,
        )

    def finish_answer(
        self,
        *,
        trace_id: str,
        result: AnswerTraceResult,
    ) -> None:
        self.latest_trace_id = trace_id
        self.latest_result = result
        self._delegate.finish_answer(
            trace_id=trace_id,
            result=result,
        )


class TracedAnswerService:
    def __init__(
        self,
        *,
        service: AnswerService,
        sink: AnswerTraceSink,
        trace_id_factory: Callable[[], str] = lambda: uuid4().hex,
    ) -> None:
        self._service = service
        self._sink = sink
        self._trace_id_factory = trace_id_factory

    def conversation_product(
        self,
        conversation_id: str,
        *,
        visitor_id: str | None = None,
    ) -> str | None:
        return self._service.conversation_product(
            conversation_id,
            visitor_id=visitor_id,
        )

    def answer(
        self,
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
        observer: AnswerObserver | None = None,
        visitor_id: str | None = None,
    ) -> AnswerResult:
        trace_id = self._trace_id_factory()
        try:
            self._sink.start_answer(
                trace_id=trace_id,
                product_id=product_id,
            )
        except Exception:
            logger.warning(
                "failed to start answer trace",
                exc_info=True,
            )

        started = perf_counter()
        try:
            result = self._service.answer(
                question,
                product_id,
                conversation_id=conversation_id,
                observer=observer,
                visitor_id=visitor_id,
            )
        except Exception as exc:
            self._finish(
                trace_id,
                AnswerTraceResult(
                    status="failed",
                    mode=None,
                    citation_count=0,
                    attempts=0,
                    latency_ms=(perf_counter() - started) * 1000,
                    error_type=type(exc).__name__,
                ),
            )
            raise

        self._finish(
            trace_id,
            AnswerTraceResult(
                status="succeeded",
                mode=result.mode,
                citation_count=len(result.citations),
                attempts=result.attempts,
                latency_ms=(perf_counter() - started) * 1000,
            ),
        )
        return result

    def _finish(
        self,
        trace_id: str,
        result: AnswerTraceResult,
    ) -> None:
        try:
            self._sink.finish_answer(
                trace_id=trace_id,
                result=result,
            )
        except Exception:
            logger.warning(
                "failed to finish answer trace",
                exc_info=True,
            )
