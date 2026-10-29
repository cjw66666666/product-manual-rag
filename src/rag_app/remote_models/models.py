from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DenseEmbedding:
    vector: tuple[float, ...]
    model: str


@dataclass(frozen=True, slots=True)
class RerankScore:
    index: int
    score: float


@dataclass(frozen=True, slots=True)
class Generation:
    text: str
    prompt_tokens: int
    completion_tokens: int


class ProviderError(RuntimeError):
    pass
