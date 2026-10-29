from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class IngestDocument:
    document_id: str
    product_id: str
    path: Path
    sha256: str
    received_at: datetime
    version_label: str | None
    metadata_confidence: str
    document_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    blocks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ChunkPayload:
    chunk_id: str
    content: str
    page: int


@dataclass(frozen=True, slots=True)
class EmbeddingPayload:
    dense: tuple[float, ...]
    sparse: dict[int, float]


@dataclass(frozen=True, slots=True)
class ExistingVersion:
    version_id: str
    status: str


@dataclass(frozen=True, slots=True)
class IngestionResult:
    version_id: str
    duplicate: bool
    chunk_count: int
