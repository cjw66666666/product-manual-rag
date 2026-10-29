from threading import Lock
from typing import Any, Protocol

from rag_app.observability.traced_service import AnswerTraceResult


class LangfuseObservation(Protocol):
    def update(self, **kwargs: Any) -> None: ...

    def end(self) -> None: ...


class LangfuseClient(Protocol):
    def start_observation(self, **kwargs: Any) -> LangfuseObservation: ...

    def flush(self) -> None: ...

    def create_score(self, **kwargs: Any) -> None: ...


class LangfuseTraceSink:
    def __init__(self, *, client: LangfuseClient) -> None:
        self._client = client
        self._observations: dict[str, LangfuseObservation] = {}
        self._lock = Lock()

    def start_answer(self, *, trace_id: str, product_id: str) -> None:
        observation = self._client.start_observation(
            name="rag.answer",
            as_type="span",
            trace_context={"trace_id": trace_id},
            metadata={"product_id": product_id},
        )
        with self._lock:
            self._observations[trace_id] = observation

    def finish_answer(
        self,
        *,
        trace_id: str,
        result: AnswerTraceResult,
    ) -> None:
        with self._lock:
            observation = self._observations.pop(trace_id, None)
        if observation is None:
            return

        output: dict[str, object] = {
            "status": result.status,
            "mode": result.mode.value if result.mode is not None else None,
            "citation_count": result.citation_count,
            "attempts": result.attempts,
        }
        metadata: dict[str, object] = {"latency_ms": result.latency_ms}
        if result.error_type is not None:
            output["error_type"] = result.error_type
            metadata["error_type"] = result.error_type

        try:
            observation.update(
                output=output,
                metadata=metadata,
                level=(
                    "ERROR"
                    if result.status == "failed"
                    else "DEFAULT"
                ),
                status_message=result.status,
            )
        finally:
            observation.end()

    def flush(self) -> None:
        self._client.flush()

    def score_trace(
        self,
        *,
        trace_id: str,
        name: str,
        value: float | bool,
    ) -> None:
        self._client.create_score(
            name=name,
            value=value,
            trace_id=trace_id,
            data_type="BOOLEAN" if isinstance(value, bool) else "NUMERIC",
        )
