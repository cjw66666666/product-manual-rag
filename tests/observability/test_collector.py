from rag_app.answering import AnswerMode
from rag_app.observability import (
    AnswerTraceResult,
    CapturingTraceSink,
)


class RecordingSink:
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


def test_capturing_sink_records_latest_attempt_and_delegates() -> None:
    delegate = RecordingSink()
    sink = CapturingTraceSink(delegate=delegate)
    result = AnswerTraceResult(
        status="succeeded",
        mode=AnswerMode.MANUAL_GROUNDED,
        citation_count=2,
        attempts=1,
        latency_ms=123.0,
    )

    sink.start_answer(trace_id="trace-1", product_id="huawei_c7")
    sink.finish_answer(trace_id="trace-1", result=result)

    assert sink.latest_trace_id == "trace-1"
    assert sink.latest_result is result
    assert delegate.started == [("trace-1", "huawei_c7")]
    assert delegate.finished == [("trace-1", result)]
