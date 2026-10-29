import json
from collections.abc import Callable
from dataclasses import asdict, dataclass

import httpx

from rag_app.remote_models import (
    HttpEmbeddingClient,
    HttpLlmClient,
    HttpRerankerClient,
    ProviderError,
)
from rag_app.settings import Settings


@dataclass(frozen=True, slots=True)
class ProviderProbe:
    name: str
    ok: bool
    detail: str


def _probe(
    name: str,
    operation: Callable[[], object],
) -> ProviderProbe:
    try:
        operation()
    except (ProviderError, httpx.HTTPError, ValueError) as exc:
        return ProviderProbe(name, False, str(exc))
    return ProviderProbe(name, True, "ok")


def probe_providers(
    settings: Settings,
    client: httpx.Client,
) -> tuple[ProviderProbe, ...]:
    embedding = HttpEmbeddingClient(
        client,
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key,
    )
    reranker = HttpRerankerClient(
        client,
        base_url=settings.reranker_base_url,
        api_key=settings.reranker_api_key,
    )
    llm = HttpLlmClient(
        client,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )

    return (
        _probe(
            "embedding",
            lambda: embedding.embed(
                ("ping",),
                model=settings.embedding_model,
            ),
        ),
        _probe(
            "reranker",
            lambda: reranker.rerank(
                "ping",
                ("ping", "pong"),
                model=settings.reranker_model,
            ),
        ),
        _probe(
            "llm",
            lambda: llm.generate("Reply with pong.", model=settings.llm_model),
        ),
    )


def main() -> int:
    settings = Settings()
    with httpx.Client(timeout=30) as client:
        report = probe_providers(settings, client)
    print(
        json.dumps(
            [asdict(item) for item in report],
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if all(item.ok for item in report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
