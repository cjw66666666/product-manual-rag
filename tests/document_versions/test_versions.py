from datetime import UTC, datetime

import pytest

from rag_app.document_versions import (
    ExistingUpload,
    MetadataConfidence,
    UploadDecision,
    UploadProbe,
    VersionStatus,
    classify_metadata_confidence,
    classify_upload,
    next_status,
    provisional_version_key,
)


def test_exact_hash_is_duplicate_even_when_name_differs() -> None:
    decision = classify_upload(
        UploadProbe("abc", "new-name.pdf"),
        (ExistingUpload("abc", "old-name.pdf"),),
    )

    assert decision is UploadDecision.DUPLICATE_CONTENT


def test_same_name_different_hash_is_conflict() -> None:
    decision = classify_upload(
        UploadProbe("new", "guide.pdf"),
        (ExistingUpload("old", "guide.pdf"),),
    )

    assert decision is UploadDecision.SAME_NAME_CONFLICT


def test_new_hash_and_name_is_new_document() -> None:
    decision = classify_upload(
        UploadProbe("new", "new.pdf"),
        (ExistingUpload("old", "old.pdf"),),
    )

    assert decision is UploadDecision.NEW_DOCUMENT


@pytest.mark.parametrize(
    ("has_product", "has_version", "expected"),
    [
        (True, True, MetadataConfidence.HIGH),
        (True, False, MetadataConfidence.MEDIUM),
        (False, True, MetadataConfidence.LOW),
        (False, False, MetadataConfidence.LOW),
    ],
)
def test_metadata_confidence(
    has_product: bool,
    has_version: bool,
    expected: MetadataConfidence,
) -> None:
    assert classify_metadata_confidence(has_product, has_version) is expected


def test_version_state_machine_allows_validation_and_activation() -> None:
    processed = next_status(VersionStatus.DRAFT, VersionStatus.PROCESSING)
    validated = next_status(processed, VersionStatus.VALIDATED)
    active = next_status(validated, VersionStatus.ACTIVE)

    assert active is VersionStatus.ACTIVE


def test_version_state_machine_rejects_skipping_validation() -> None:
    with pytest.raises(ValueError, match="invalid version transition"):
        next_status(VersionStatus.DRAFT, VersionStatus.ACTIVE)


def test_provisional_version_key_uses_received_time() -> None:
    key = provisional_version_key(
        datetime(2026, 10, 26, 9, 30, tzinfo=UTC),
        3,
    )

    assert key == "received-20261026T093000Z-003"
