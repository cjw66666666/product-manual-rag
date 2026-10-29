from dataclasses import dataclass, field
from typing import Any

from rag_app.answering import AnswerMode
from rag_app.observability import AnswerTraceResult, LangfuseTraceSink


@dataclass
class FakeObservation:
    updates: list[dict[str, Any]] = field(default_factory=list)
    ended: int = 0

    def update(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)

    def end(self) -> None:
        self.ended += 1


@dataclass
class FakeLangfuseClient:
    started: list[dict[str, Any]] = field(default_factory=list)
    observations: list[FakeObservation] = field(default_factory=list)
    scores: list[dict[str, Any]] = field(default_factory=list)
    flushed: int = 0

    def start_observation(self, **kwargs: Any) -> FakeObservation:
        self.started.append(kwargs)
        observation = FakeObservation()
        self.observations.append(observation)
        return observation

    def flush(self) -> None:
        self.flushed += 1

    def create_score(self, **kwargs: Any) -> None:
        self.scores.append(kwargs)


def test_langfuse_sink_starts_span_without_user_content() -> None:
    client = FakeLangfuseClient()
    sink = LangfuseTraceSink(client=client)

    sink.start_answer(trace_id="a" * 32, product_id="huawei_c7")

    assert client.started == [
        {
            "name": "rag.answer",
            "as_type": "span",
            "trace_context": {"trace_id": "a" * 32},
            "metadata": {"product_id": "huawei_c7"},
        }
    ]


def test_langfuse_sink_ends_successful_span_with_metrics_only() -> None:
    client = FakeLangfuseClient()
    sink = LangfuseTraceSink(client=client)
    sink.start_answer(trace_id="b" * 32, product_id="huawei_c7")

    sink.finish_answer(
        trace_id="b" * 32,
        result=AnswerTraceResult(
            status="succeeded",
            mode=AnswerMode.MANUAL_GROUNDED,
            citation_count=2,
            attempts=1,
            latency_ms=123.456,
        ),
    )

    observation = client.observations[0]
    assert observation.updates == [
        {
            "output": {
                "status": "succeeded",
                "mode": "manual_grounded",
                "citation_count": 2,
                "attempts": 1,
            },
            "metadata": {"latency_ms": 123.456},
            "level": "DEFAULT",
            "status_message": "succeeded",
        }
    ]
    assert observation.ended == 1


def test_langfuse_sink_marks_failed_span_as_error() -> None:
    client = FakeLangfuseClient()
    sink = LangfuseTraceSink(client=client)
    sink.start_answer(trace_id="c" * 32, product_id="huawei_c7")

    sink.finish_answer(
        trace_id="c" * 32,
        result=AnswerTraceResult(
            status="failed",
            mode=None,
            citation_count=0,
            attempts=0,
            latency_ms=50.0,
            error_type="ProviderError",
        ),
    )

    update = client.observations[0].updates[0]
    assert update["level"] == "ERROR"
    assert update["status_message"] == "failed"
    assert update["output"]["error_type"] == "ProviderError"
    assert client.observations[0].ended == 1


def test_langfuse_sink_ignores_unknown_trace_and_can_flush() -> None:
    client = FakeLangfuseClient()
    sink = LangfuseTraceSink(client=client)

    sink.finish_answer(
        trace_id="d" * 32,
        result=AnswerTraceResult(
            status="succeeded",
            mode=AnswerMode.REFUSED,
            citation_count=0,
            attempts=2,
            latency_ms=10.0,
        ),
    )
    sink.flush()

    assert client.started == []
    assert client.flushed == 1


def test_langfuse_sink_records_numeric_and_boolean_scores_by_trace_id() -> None:
    client = FakeLangfuseClient()
    sink = LangfuseTraceSink(client=client)

    sink.score_trace(
        trace_id="e" * 32,
        name="recall_at_20",
        value=0.75,
    )
    sink.score_trace(
        trace_id="e" * 32,
        name="case_passed",
        value=True,
    )

    assert client.scores == [
        {
            "name": "recall_at_20",
            "value": 0.75,
            "trace_id": "e" * 32,
            "data_type": "NUMERIC",
        },
        {
            "name": "case_passed",
            "value": True,
            "trace_id": "e" * 32,
            "data_type": "BOOLEAN",
        },
    ]
