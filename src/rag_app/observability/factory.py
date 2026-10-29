from collections.abc import Callable
from typing import cast

from langfuse import Langfuse

from rag_app.observability.langfuse_sink import (
    LangfuseClient,
    LangfuseTraceSink,
)
from rag_app.observability.traced_service import (
    NullAnswerTraceSink,
    TraceSink,
)


def build_langfuse_sink(
    *,
    public_key: str | None,
    secret_key: str | None,
    host: str,
    client_factory: Callable[..., LangfuseClient] | None = None,
) -> TraceSink:
    if not public_key or not secret_key:
        return NullAnswerTraceSink()

    factory = (
        client_factory
        if client_factory is not None
        else cast(Callable[..., LangfuseClient], Langfuse)
    )
    client = factory(
        public_key=public_key,
        secret_key=secret_key,
        host=host,
    )
    return LangfuseTraceSink(client=client)
