import json

import httpx
import pytest

from rag_app.answering import AnswerCancelled
from rag_app.remote_models import (
    HttpEmbeddingClient,
    HttpLlmClient,
    HttpRerankerClient,
    ProviderError,
    cancellation_scope,
)


def test_embedding_client_sends_model_and_input() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings"
        assert request.headers["Authorization"] == "Bearer secret"
        body = json.loads(request.content)
        assert body == {"model": "embedding-model", "input": ["a", "b"]}
        return httpx.Response(
            200,
            json={
                "data": [
                    {"embedding": [1.0, 0.0]},
                    {"embedding": [0.0, 1.0]},
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    embedding = HttpEmbeddingClient(
        client,
        base_url="https://models.test/v1",
        api_key="secret",
    ).embed(("a", "b"), model="embedding-model")

    assert [item.vector for item in embedding] == [(1.0, 0.0), (0.0, 1.0)]


def test_embedding_client_batches_large_input_sets() -> None:
    batch_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        batch_sizes.append(len(body["input"]))
        return httpx.Response(
            200,
            json={
                "data": [
                    {"embedding": [float(index), 1.0]}
                    for index in range(len(body["input"]))
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    embeddings = HttpEmbeddingClient(
        client,
        base_url="https://models.test/v1",
        api_key="secret",
    ).embed(
        tuple(f"text-{index}" for index in range(40)),
        model="embedding-model",
    )

    assert batch_sizes == [32, 8]
    assert len(embeddings) == 40


def test_provider_retries_transient_connection_failure() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ConnectError("temporary", request=request)
        return httpx.Response(200, json={"data": [{"embedding": [1.0]}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    embeddings = HttpEmbeddingClient(
        client,
        base_url="https://models.test/v1",
        api_key="secret",
    ).embed(("text",), model="embedding-model")

    assert attempts == 3
    assert embeddings[0].vector == (1.0,)


def test_reranker_client_sorts_scores_descending() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/rerank"
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 0, "relevance_score": 0.1},
                    {"index": 1, "relevance_score": 0.9},
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    scores = HttpRerankerClient(
        client,
        base_url="https://models.test/v1",
        api_key="secret",
    ).rerank("question", ("a", "b"), model="reranker")

    assert [item.index for item in scores] == [1, 0]


def test_reranker_client_batches_large_candidate_sets() -> None:
    batch_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        batch_sizes.append(len(body["documents"]))
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": index, "relevance_score": 1.0 - index / 100}
                    for index in range(len(body["documents"]))
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    scores = HttpRerankerClient(
        client,
        base_url="https://models.test/v1",
        api_key="secret",
    ).rerank(
        "question",
        tuple(f"document-{index}" for index in range(12)),
        model="reranker",
    )

    assert batch_sizes == [10, 2]
    assert len(scores) == 12


def test_llm_client_parses_usage_and_maps_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            429,
            json={"error": {"message": "rate limited"}},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = HttpLlmClient(
        client,
        base_url="https://models.test/v1",
        api_key="secret",
    )

    with pytest.raises(ProviderError, match="rate limited"):
        llm.generate("hello", model="chat")


def test_llm_client_sends_optional_system_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["temperature"] == 0
        assert body["messages"] == [
            {"role": "system", "content": "trusted policy"},
            {"role": "user", "content": "untrusted data"},
        ]
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = HttpLlmClient(
        client,
        base_url="https://models.test/v1",
        api_key="secret",
    ).generate(
        "untrusted data",
        model="chat",
        system_prompt="trusted policy",
    )

    assert result.text == "ok"


def test_llm_client_aggregates_cancellable_streaming_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["stream"] is True
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                b'data: {"choices":[{"delta":{"content":"ANSWER\\n"}}]}\n\n'
                b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
                b"data: [DONE]\n\n"
            ),
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = HttpLlmClient(
        client,
        base_url="https://models.test/v1",
        api_key="secret",
    )

    with cancellation_scope(lambda: None):
        result = llm.generate("hello", model="chat")

    assert result.text == "ANSWER\nok"


def test_llm_client_stops_streaming_when_cancelled() -> None:
    checks = 0

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                b'data: {"choices":[{"delta":{"content":"first"}}]}\n\n'
                b'data: {"choices":[{"delta":{"content":"second"}}]}\n\n'
                b"data: [DONE]\n\n"
            ),
        )

    def check_cancelled() -> None:
        nonlocal checks
        checks += 1
        if checks >= 3:
            raise AnswerCancelled("client disconnected")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = HttpLlmClient(
        client,
        base_url="https://models.test/v1",
        api_key="secret",
    )

    with (
        cancellation_scope(check_cancelled),
        pytest.raises(AnswerCancelled, match="disconnected"),
    ):
        llm.generate("hello", model="chat")

    assert checks >= 3
