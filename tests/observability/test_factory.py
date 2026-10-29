from dataclasses import dataclass, field
from typing import Any

from rag_app.observability import (
    LangfuseTraceSink,
    NullAnswerTraceSink,
    build_langfuse_sink,
)


@dataclass
class FakeLangfuseClient:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def start_observation(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        raise AssertionError("factory tests do not start observations")

    def flush(self) -> None:
        pass

    def create_score(self, **kwargs: Any) -> None:
        pass


def test_langfuse_factory_returns_null_without_both_keys() -> None:
    sink = build_langfuse_sink(
        public_key="pk-only",
        secret_key=None,
        host="http://127.0.0.1:3001",
    )

    assert isinstance(sink, NullAnswerTraceSink)


def test_langfuse_factory_builds_sink_with_configuration() -> None:
    client = FakeLangfuseClient()
    calls: list[dict[str, str]] = []

    def factory(**kwargs: str) -> FakeLangfuseClient:
        calls.append(kwargs)
        return client

    sink = build_langfuse_sink(
        public_key="pk-test",
        secret_key="sk-test",
        host="http://127.0.0.1:3001",
        client_factory=factory,
    )

    assert isinstance(sink, LangfuseTraceSink)
    assert calls == [
        {
            "public_key": "pk-test",
            "secret_key": "sk-test",
            "host": "http://127.0.0.1:3001",
        }
    ]
