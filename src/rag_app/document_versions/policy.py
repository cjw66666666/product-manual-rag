from collections.abc import Sequence
from datetime import datetime

from rag_app.document_versions.models import (
    ExistingUpload,
    MetadataConfidence,
    UploadDecision,
    UploadProbe,
    VersionStatus,
)

_ALLOWED_TRANSITIONS: dict[VersionStatus, frozenset[VersionStatus]] = {
    VersionStatus.DRAFT: frozenset({VersionStatus.PROCESSING}),
    VersionStatus.PROCESSING: frozenset(
        {VersionStatus.VALIDATED, VersionStatus.FAILED}
    ),
    VersionStatus.VALIDATED: frozenset({VersionStatus.ACTIVE}),
    VersionStatus.ACTIVE: frozenset({VersionStatus.SUPERSEDED}),
    VersionStatus.SUPERSEDED: frozenset(),
    VersionStatus.FAILED: frozenset({VersionStatus.PROCESSING}),
}


def classify_upload(
    probe: UploadProbe,
    existing: Sequence[ExistingUpload],
) -> UploadDecision:
    if any(item.sha256 == probe.sha256 for item in existing):
        return UploadDecision.DUPLICATE_CONTENT
    if any(
        item.normalized_name == probe.normalized_name for item in existing
    ):
        return UploadDecision.SAME_NAME_CONFLICT
    return UploadDecision.NEW_DOCUMENT


def classify_metadata_confidence(
    has_product: bool,
    has_version: bool,
) -> MetadataConfidence:
    if has_product and has_version:
        return MetadataConfidence.HIGH
    if has_product:
        return MetadataConfidence.MEDIUM
    return MetadataConfidence.LOW


def next_status(
    current: VersionStatus,
    target: VersionStatus,
) -> VersionStatus:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(
            f"invalid version transition: {current.value} -> {target.value}"
        )
    return target


def provisional_version_key(received_at: datetime, sequence: int) -> str:
    if sequence < 1:
        raise ValueError("sequence must be positive")
    return f"received-{received_at:%Y%m%dT%H%M%SZ}-{sequence:03d}"
