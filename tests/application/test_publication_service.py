from dataclasses import dataclass

import pytest

from rag_app.application import VersionPublicationService
from rag_app.persistence.document_index_repository import (
    DocumentIndexRecord,
    DocumentIndexSummary,
)
from rag_app.persistence.repositories import DocumentVersionRecord


@dataclass
class Versions:
    approved: list[tuple[str, str]] | None = None
    activated: list[tuple[str, str, str, str]] | None = None

    def list_versions_for_product(
        self,
        product_id: str,
    ) -> tuple[DocumentVersionRecord, ...]:
        return (
            DocumentVersionRecord(
                id="v1",
                document_id="d1",
                sha256="a" * 64,
                version_key="d1:1",
                version_label="1.0",
                status="validated",
                requires_manual_approval=True,
                approved_at=None,
                approved_by=None,
                document_name="guide.pdf",
            ),
        )

    def list_pending_approval_product_ids(self) -> tuple[str, ...]:
        return ("p1", "p2")

    def list_approved_product_ids(self) -> tuple[str, ...]:
        return ("p3",)

    def approve_version(self, version_id: str, *, approved_by: str) -> None:
        self.approved = [(version_id, approved_by)]

    def activate_version(
        self,
        product_id: str,
        document_id: str,
        version_id: str,
        index_version_id: str,
    ) -> None:
        self.activated = [
            (product_id, document_id, version_id, index_version_id)
        ]

    def document_id_for_version(self, version_id: str) -> str:
        return "d1"

    def active_version_id_for_document(
        self,
        product_id: str,
        document_id: str,
    ) -> str | None:
        return "old-version"

    def active_index_version(self, product_id: str) -> str | None:
        return "old-index"


class Indexes:
    def __init__(self, status: str) -> None:
        self._status = status

    def get(
        self,
        document_version_id: str,
        index_version_id: str,
    ) -> DocumentIndexRecord | None:
        return DocumentIndexRecord(
            status=self._status,
            chunk_count=3,
            error_message=None,
        )

    def list_for_version(
        self,
        document_version_id: str,
    ) -> tuple[DocumentIndexSummary, ...]:
        return (
            DocumentIndexSummary(
                index_version_id="i1",
                status=self._status,
                chunk_count=3,
                error_message=None,
            ),
        )


def test_publication_service_lists_and_approves() -> None:
    versions = Versions(approved=[], activated=[])
    service = VersionPublicationService(
        versions=versions,
        indexes=Indexes("completed"),
    )

    listed = service.list_versions("p1")
    service.approve("v1", approved_by="admin")

    assert listed[0].requires_manual_approval is True
    assert listed[0].approved_at is None
    assert listed[0].document_name == "guide.pdf"
    assert listed[0].indexes[0].index_version_id == "i1"
    assert listed[0].indexes[0].chunk_count == 3
    assert versions.approved == [("v1", "admin")]


def test_publication_service_lists_products_needing_approval() -> None:
    service = VersionPublicationService(
        versions=Versions(approved=[], activated=[]),
        indexes=Indexes("completed"),
    )

    assert service.list_pending_approval_product_ids() == ("p1", "p2")


def test_publication_service_lists_approved_products() -> None:
    service = VersionPublicationService(
        versions=Versions(approved=[], activated=[]),
        indexes=Indexes("completed"),
    )

    assert service.list_approved_product_ids() == ("p3",)


def test_publication_service_requires_completed_index() -> None:
    service = VersionPublicationService(
        versions=Versions(approved=[], activated=[]),
        indexes=Indexes("processing"),
    )

    with pytest.raises(ValueError, match="not completed"):
        service.publish(
            product_id="p1",
            document_version_id="v1",
            index_version_id="i1",
        )


def test_publication_service_activates_completed_index() -> None:
    versions = Versions(approved=[], activated=[])
    service = VersionPublicationService(
        versions=versions,
        indexes=Indexes("completed"),
    )

    service.publish(
        product_id="p1",
        document_version_id="v1",
        index_version_id="i1",
    )

    assert versions.activated == [("p1", "d1", "v1", "i1")]


def test_publication_service_queues_cleanup_before_commit() -> None:
    events: list[str] = []

    class CleanupQueue:
        def enqueue(
            self,
            document_version_id: str,
            index_version_id: str,
        ) -> None:
            events.append(f"queue:{document_version_id}:{index_version_id}")

    versions = Versions(approved=[], activated=[])
    service = VersionPublicationService(
        versions=versions,
        indexes=Indexes("completed"),
        cleanup_queue=CleanupQueue(),
        commit=lambda: events.append("commit"),
    )

    service.publish(
        product_id="p1",
        document_version_id="v1",
        index_version_id="i1",
    )

    assert events == ["queue:old-version:old-index", "commit"]
