import json
from collections.abc import Callable, Sequence
from time import sleep
from typing import cast

import httpx

from rag_app.remote_models.cancellation import (
    current_cancellation_check,
)
from rag_app.remote_models.models import (
    DenseEmbedding,
    Generation,
    ProviderError,
    RerankScore,
)


def _post_json(
    client: httpx.Client,
    url: str,
    api_key: str,
    payload: dict[str, object],
    max_attempts: int = 3,
) -> dict[str, object]:
    response: httpx.Response | None = None
    last_error: httpx.HTTPError | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < max_attempts:
                sleep(0.5 * attempt)
                continue
            raise ProviderError(f"provider request failed: {exc}") from exc

        if (
            response.status_code in {429, 500, 502, 503, 504}
            and attempt < max_attempts
        ):
            sleep(0.5 * attempt)
            continue
        break

    if response is None:
        raise ProviderError(f"provider request failed: {last_error}")

    if response.is_error:
        message = f"provider returned HTTP {response.status_code}"
        try:
            body = cast(dict[str, object], response.json())
            error = body.get("error")
            if isinstance(error, dict):
                detail = cast(dict[str, object], error).get("message")
                if isinstance(detail, str):
                    message = detail
            elif isinstance(error, str):
                message = error
            elif isinstance(body.get("message"), str):
                message = str(body["message"])
            else:
                message = response.text[:500] or message
        except ValueError:
            pass
        raise ProviderError(message)

    try:
        return cast(dict[str, object], response.json())
    except ValueError as exc:
        raise ProviderError("provider returned invalid JSON") from exc


class HttpEmbeddingClient:
    def __init__(
        self,
        client: httpx.Client,
        *,
        base_url: str,
        api_key: str,
        batch_size: int = 32,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._batch_size = batch_size

    def embed(
        self,
        texts: Sequence[str],
        *,
        model: str,
    ) -> tuple[DenseEmbedding, ...]:
        result: list[DenseEmbedding] = []
        for offset in range(0, len(texts), self._batch_size):
            batch = texts[offset : offset + self._batch_size]
            body = _post_json(
                self._client,
                f"{self._base_url}/embeddings",
                self._api_key,
                {"model": model, "input": list(batch)},
            )
            data = body.get("data")
            if not isinstance(data, list) or len(data) != len(batch):
                raise ProviderError("embedding response count mismatch")

            for item in data:
                if not isinstance(item, dict):
                    raise ProviderError("invalid embedding response")
                vector = cast(dict[str, object], item).get("embedding")
                if not isinstance(vector, list):
                    raise ProviderError("invalid embedding vector")
                result.append(
                    DenseEmbedding(
                        vector=tuple(float(value) for value in vector),
                        model=model,
                    )
                )
        return tuple(result)


class HttpRerankerClient:
    def __init__(
        self,
        client: httpx.Client,
        *,
        base_url: str,
        api_key: str,
        batch_size: int = 10,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._batch_size = batch_size

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        model: str,
    ) -> tuple[RerankScore, ...]:
        scores: list[RerankScore] = []
        for offset in range(0, len(documents), self._batch_size):
            batch = documents[offset : offset + self._batch_size]
            body = _post_json(
                self._client,
                f"{self._base_url}/rerank",
                self._api_key,
                {
                    "model": model,
                    "query": query,
                    "documents": list(batch),
                },
            )
            results = body.get("results")
            if not isinstance(results, list):
                raise ProviderError("invalid reranker response")

            for item in results:
                if not isinstance(item, dict):
                    raise ProviderError("invalid reranker result")
                record = cast(dict[str, object], item)
                index = record.get("index")
                score = record.get("relevance_score")
                if not isinstance(index, int) or not isinstance(
                    score,
                    int | float,
                ):
                    raise ProviderError("invalid reranker result")
                scores.append(
                    RerankScore(
                        index=offset + index,
                        score=float(score),
                    )
                )
        return tuple(sorted(scores, key=lambda item: item.score, reverse=True))


class HttpLlmClient:
    def __init__(
        self,
        client: httpx.Client,
        *,
        base_url: str,
        api_key: str,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def generate(
        self,
        prompt: str,
        *,
        model: str,
        system_prompt: str | None = None,
    ) -> Generation:
        messages: list[dict[str, str]] = []
        if system_prompt is not None:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        cancellation_check = current_cancellation_check()
        if cancellation_check is not None:
            return self._generate_streaming(
                messages,
                model=model,
                cancellation_check=cancellation_check,
            )
        body = _post_json(
            self._client,
            f"{self._base_url}/chat/completions",
            self._api_key,
            {
                "model": model,
                "temperature": 0,
                "messages": messages,
            },
        )
        choices = body.get("choices")
        usage = body.get("usage")
        if not isinstance(choices, list) or not choices:
            raise ProviderError("invalid LLM response")
        first = choices[0]
        if not isinstance(first, dict):
            raise ProviderError("invalid LLM choice")
        message = cast(dict[str, object], first).get("message")
        if not isinstance(message, dict):
            raise ProviderError("invalid LLM message")
        text = cast(dict[str, object], message).get("content")
        if not isinstance(text, str):
            raise ProviderError("invalid LLM content")

        prompt_tokens = 0
        completion_tokens = 0
        if isinstance(usage, dict):
            usage_record = cast(dict[str, object], usage)
            prompt_value = usage_record.get("prompt_tokens")
            completion_value = usage_record.get("completion_tokens")
            if isinstance(prompt_value, int):
                prompt_tokens = prompt_value
            if isinstance(completion_value, int):
                completion_tokens = completion_value

        return Generation(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def _generate_streaming(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        cancellation_check: Callable[[], None],
    ) -> Generation:
        cancellation_check()
        chunks: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        with self._client.stream(
            "POST",
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "text/event-stream",
            },
            json={
                "model": model,
                "temperature": 0,
                "messages": messages,
                "stream": True,
            },
        ) as response:
            if response.is_error:
                response.read()
                raise ProviderError(
                    f"provider returned HTTP {response.status_code}"
                )
            for line in response.iter_lines():
                cancellation_check()
                if not line.startswith("data:"):
                    continue
                payload_text = line.removeprefix("data:").strip()
                if not payload_text or payload_text == "[DONE]":
                    continue
                try:
                    payload = cast(dict[str, object], json.loads(payload_text))
                except (ValueError, TypeError) as exc:
                    raise ProviderError(
                        "provider returned invalid stream event"
                    ) from exc
                usage = payload.get("usage")
                if isinstance(usage, dict):
                    usage_record = cast(dict[str, object], usage)
                    prompt_value = usage_record.get("prompt_tokens")
                    completion_value = usage_record.get(
                        "completion_tokens"
                    )
                    if isinstance(prompt_value, int):
                        prompt_tokens = prompt_value
                    if isinstance(completion_value, int):
                        completion_tokens = completion_value
                choices = payload.get("choices")
                if not isinstance(choices, list) or not choices:
                    continue
                first = choices[0]
                if not isinstance(first, dict):
                    continue
                delta = cast(dict[str, object], first).get("delta")
                if not isinstance(delta, dict):
                    continue
                content = cast(dict[str, object], delta).get("content")
                if isinstance(content, str):
                    chunks.append(content)
        cancellation_check()
        text = "".join(chunks)
        if not text:
            raise ProviderError("invalid LLM stream content")
        return Generation(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
