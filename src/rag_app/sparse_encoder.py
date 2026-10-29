import re
from collections import Counter
from dataclasses import dataclass
from hashlib import blake2b
from math import log

_TOKEN_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]*|[\u4e00-\u9fff]+"
)


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for match in _TOKEN_PATTERN.findall(text):
        if match.isascii():
            tokens.append(match.casefold())
            continue
        if len(match) == 1:
            tokens.append(match)
        else:
            tokens.extend(
                match[index : index + 2]
                for index in range(len(match) - 1)
            )
    return tokens


def _token_id(token: str) -> int:
    digest = blake2b(
        token.encode("utf-8"),
        digest_size=4,
    ).digest()
    return int.from_bytes(digest, "big")


@dataclass(frozen=True, slots=True)
class SparseStatistics:
    document_count: int
    total_length: int
    document_frequency: dict[int, int]


def merge_sparse_statistics(
    values: tuple[SparseStatistics, ...],
) -> SparseStatistics:
    frequencies: dict[int, int] = {}
    for value in values:
        for token, count in value.document_frequency.items():
            frequencies[token] = frequencies.get(token, 0) + count
    return SparseStatistics(
        document_count=sum(value.document_count for value in values),
        total_length=sum(value.total_length for value in values),
        document_frequency=frequencies,
    )


class Bm25SparseEncoder:
    def __init__(
        self,
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("invalid BM25 parameters")
        self._k1 = k1
        self._b = b

    def fit(self, texts: tuple[str, ...]) -> SparseStatistics:
        frequencies: dict[int, int] = {}
        total_length = 0
        for text in texts:
            counts = Counter(_token_id(token) for token in _tokens(text))
            total_length += sum(counts.values())
            for token in counts:
                frequencies[token] = frequencies.get(token, 0) + 1
        return SparseStatistics(
            document_count=len(texts),
            total_length=total_length,
            document_frequency=frequencies,
        )

    def encode_document(
        self,
        text: str,
        statistics: SparseStatistics,
    ) -> dict[int, float]:
        tokens = _tokens(text)
        counts = Counter(_token_id(token) for token in tokens)
        length = max(1, len(tokens))
        average_length = (
            statistics.total_length / statistics.document_count
            if statistics.document_count
            else 1.0
        )
        vector: dict[int, float] = {}
        for token, count in counts.items():
            numerator = count * (self._k1 + 1)
            denominator = count + self._k1 * (
                1 - self._b + self._b * length / average_length
            )
            vector[token] = numerator / denominator
        return vector

    def encode_query(
        self,
        text: str,
        statistics: SparseStatistics,
    ) -> dict[int, float]:
        counts = Counter(_token_id(token) for token in _tokens(text))
        total = max(1, statistics.document_count)
        vector: dict[int, float] = {}
        for token in counts:
            frequency = statistics.document_frequency.get(token, 0)
            idf = log(
                1 + (total - frequency + 0.5) / (frequency + 0.5)
            )
            if idf > 0:
                vector[token] = idf
        return vector


class HashedSparseEncoder:
    def encode(self, text: str) -> dict[int, float]:
        counts = Counter(_tokens(text))
        vector: dict[int, float] = {}
        for token, count in counts.items():
            digest = blake2b(
                token.encode("utf-8"),
                digest_size=4,
            ).digest()
            vector[int.from_bytes(digest, "big")] = float(count)
        return vector
