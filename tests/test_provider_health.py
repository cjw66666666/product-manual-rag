import httpx

from rag_app.provider_health import probe_providers
from rag_app.settings import Settings


def test_probe_providers_checks_all_three_services() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(200, json={"data": [{"embedding": [1.0]}]})
        if request.url.path.endswith("/rerank"):
            return httpx.Response(
                200,
                json={"results": [{"index": 0, "relevance_score": 0.9}]},
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "pong"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    report = probe_providers(Settings(), client)

    assert [item.name for item in report] == [
        "embedding",
        "reranker",
        "llm",
    ]
    assert all(item.ok for item in report)
