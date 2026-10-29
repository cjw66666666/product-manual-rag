from dataclasses import dataclass
from enum import StrEnum


class VersionStatus(StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    VALIDATED = "validated"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class MetadataConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class UploadDecision(StrEnum):
    DUPLICATE_CONTENT = "duplicate_content"
    SAME_NAME_CONFLICT = "same_name"
    NEW_DOCUMENT = "new_document"


@dataclass(frozen=True, slots=True)
class ExistingUpload:
    sha256: str
    normalized_name: str


@dataclass(frozen=True, slots=True)
class UploadProbe:
    sha256: str
    normalized_name: str
