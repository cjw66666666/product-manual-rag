import logging
from dataclasses import dataclass

import pytest

from rag_app.answering import AnswerMode, AnswerObserver, AnswerResult
from rag_app.observability import (
    AnswerTraceResult,
    TracedAnswerService,
)


@dataclass
class StubAnswerService:
    result: AnswerResult | None = None
    error: Exception | None = None

    def conversation_product(
        self,
        conversation_id: str,
        *,
        visitor_id: str | None = None,
    ) -> str | None:
        return None

    def answer(
        self,
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
        observer: AnswerObserver | None = None,
        visitor_id: str | None = None,
    ) -> AnswerResult:
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise AssertionError("result is required")
        return self.result


class RecordingTraceSink:
    def __init__(self) -> None:
        self.started: list[tuple[str, str]] = []
        self.finished: list[tuple[str, AnswerTraceResult]] = []

    def start_answer(self, *, trace_id: str, product_id: str) -> None:
        self.started.append((trace_id, product_id))

    def finish_answer(
        self,
        *,
        trace_id: str,
        result: AnswerTraceResult,
    ) -> None:
        self.finished.append((trace_id, result))


def answer_result() -> AnswerResult:
    return AnswerResult(
        mode=AnswerMode.MANUAL_GROUNDED,
        text="按电源键开机。[1]",
        citations=("chunk-1",),
        attempts=1,
    )


def test_traced_service_records_success_without_question_or_answer_text() -> None:
    sink = RecordingTraceSink()
    result = answer_result()
    service = TracedAnswerService(
        service=StubAnswerService(result=result),
        sink=sink,
        trace_id_factory=lambda: "trace-1",
    )

    actual = service.answer("怎么开机？", "huawei_c7")

    assert actual is result
    assert sink.started == [("trace-1", "huawei_c7")]
    assert len(sink.finished) == 1
    trace_id, trace_result = sink.finished[0]
    assert trace_id == "trace-1"
    assert trace_result.status == "succeeded"
    assert trace_result.mode is AnswerMode.MANUAL_GROUNDED
    assert trace_result.citation_count == 1
    assert trace_result.attempts == 1
    assert trace_result.latency_ms >= 0
    assert trace_result.error_type is None


def test_traced_service_records_failure_and_reraises() -> None:
    sink = RecordingTraceSink()
    service = TracedAnswerService(
        service=StubAnswerService(error=RuntimeError("provider failed")),
        sink=sink,
        trace_id_factory=lambda: "trace-2",
    )

    with pytest.raises(RuntimeError, match="provider failed"):
        service.answer("怎么开机？", "huawei_c7")

    assert sink.started == [("trace-2", "huawei_c7")]
    trace_id, trace_result = sink.finished[0]
    assert trace_id == "trace-2"
    assert trace_result.status == "failed"
    assert trace_result.error_type == "RuntimeError"
    assert trace_result.mode is None


def test_trace_sink_failure_does_not_break_answer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailingSink:
        def start_answer(self, *, trace_id: str, product_id: str) -> None:
            raise ConnectionError("trace unavailable")

        def finish_answer(
            self,
            *,
            trace_id: str,
            result: AnswerTraceResult,
        ) -> None:
            raise ConnectionError("trace unavailable")

    result = answer_result()
    service = TracedAnswerService(
        service=StubAnswerService(result=result),
        sink=FailingSink(),
        trace_id_factory=lambda: "trace-3",
    )

    with caplog.at_level(logging.WARNING):
        actual = service.answer("怎么开机？", "huawei_c7")

    assert actual is result
    assert "failed to start answer trace" in caplog.text
    assert "failed to finish answer trace" in caplog.text
