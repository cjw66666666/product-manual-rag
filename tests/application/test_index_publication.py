from rag_app.application import IndexPublicationService


class Versions:
    def document_id_for_version(self, version_id: str) -> str:
        return "doc-1"

    def requires_manual_approval(self, version_id: str) -> bool:
        return False

    def active_version_id_for_document(
        self,
        product_id: str,
        document_id: str,
    ) -> str | None:
        return "old-version"

    def active_index_version(self, product_id: str) -> str | None:
        return "old-index"


class Activator:
    def activate_version(
        self,
        product_id: str,
        document_id: str,
        version_id: str,
        index_version_id: str,
    ) -> None:
        assert document_id == "doc-1"


class Status:
    called: bool = False

    def mark_success(self, version_id: str, index_id: str, count: int) -> None:
        self.called = True

    def mark_failure(
        self,
        version_id: str,
        index_id: str,
        message: str,
    ) -> None:
        pass


class OrderedActivator(Activator):
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def activate_version(
        self,
        product_id: str,
        document_id: str,
        version_id: str,
        index_version_id: str,
    ) -> None:
        self._events.append("activate")


class OrderedStatus(Status):
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def mark_success(self, version_id: str, index_id: str, count: int) -> None:
        self._events.append("mark_success")


class OrderedCleanupQueue:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def enqueue(
        self,
        document_version_id: str,
        index_version_id: str,
    ) -> None:
        self._events.append(
            f"queue:{document_version_id}:{index_version_id}"
        )


def test_publication_activates_then_marks_index_complete() -> None:
    status = Status()
    IndexPublicationService(
        versions=Versions(),
        activator=Activator(),
        index_status=status,
    ).publish(
        product_id="p1",
        document_version_id="v1",
        index_version_id="i1",
        chunk_count=3,
    )

    assert status.called is True


def test_publication_confirms_index_before_activation() -> None:
    events: list[str] = []

    IndexPublicationService(
        versions=Versions(),
        activator=OrderedActivator(events),
        index_status=OrderedStatus(events),
    ).publish(
        product_id="p1",
        document_version_id="v1",
        index_version_id="i1",
        chunk_count=3,
    )

    assert events == ["mark_success", "activate"]


def test_publication_queues_previous_vectors_after_activation() -> None:
    events: list[str] = []

    IndexPublicationService(
        versions=Versions(),
        activator=OrderedActivator(events),
        index_status=OrderedStatus(events),
        cleanup_queue=OrderedCleanupQueue(events),
    ).publish(
        product_id="p1",
        document_version_id="v1",
        index_version_id="i1",
        chunk_count=3,
    )

    assert events == [
        "mark_success",
        "activate",
        "queue:old-version:old-index",
    ]


def test_safety_version_waits_for_manual_approval() -> None:
    events: list[str] = []

    class SafetyVersions(Versions):
        def requires_manual_approval(self, version_id: str) -> bool:
            return True

    activated = IndexPublicationService(
        versions=SafetyVersions(),
        activator=OrderedActivator(events),
        index_status=OrderedStatus(events),
    ).publish(
        product_id="p1",
        document_version_id="v1",
        index_version_id="i1",
        chunk_count=3,
    )

    assert activated is False
    assert events == ["mark_success"]
