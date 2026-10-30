from collections.abc import Callable
from typing import Protocol

from sqlalchemy.orm import Session

from rag_app.answering import AnswerObserver, AnswerResult
from rag_app.application.conversation_service import (
    ConversationApplicationService,
    ConversationView,
)
from rag_app.application.import_service import (
    ConflictAction,
    ImportBatchResult,
    ImportBatchSummary,
    ImportBatchView,
    UploadedDocument,
)
from rag_app.application.publication_service import (
    VersionPublicationService,
    VersionView,
)
from rag_app.conversations import AnswerDetail, UserPreference


class AnswerService(Protocol):
    def conversation_product(
        self,
        conversation_id: str,
        *,
        visitor_id: str | None = None,
    ) -> str | None: ...

    def answer(
        self,
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
        observer: AnswerObserver | None = None,
        visitor_id: str | None = None,
    ) -> AnswerResult: ...


class SessionScopedAnswerService:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        service_factory: Callable[[Session], AnswerService],
    ) -> None:
        self._session_factory = session_factory
        self._service_factory = service_factory

    def conversation_product(
        self,
        conversation_id: str,
        *,
        visitor_id: str | None = None,
    ) -> str | None:
        with self._session_factory() as session:
            return self._service_factory(
                session
            ).conversation_product(
                conversation_id,
                visitor_id=visitor_id,
            )

    def answer(
        self,
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
        observer: AnswerObserver | None = None,
        visitor_id: str | None = None,
    ) -> AnswerResult:
        with self._session_factory() as session:
            service = self._service_factory(session)
            return service.answer(
                question,
                product_id,
                conversation_id=conversation_id,
                observer=observer,
                visitor_id=visitor_id,
            )


class ImportService(Protocol):
    def enqueue(
        self,
        files: tuple[UploadedDocument, ...],
    ) -> ImportBatchResult: ...

    def get_batch(self, batch_id: str) -> ImportBatchView: ...

    def list_batches(self) -> tuple[ImportBatchSummary, ...]: ...

    def resolve_conflict(
        self,
        batch_id: str,
        item_id: str,
        action: ConflictAction,
        new_filename: str | None = None,
    ) -> ImportBatchView: ...

    def prepare_item(
        self,
        batch_id: str,
        item_id: str,
    ) -> ImportBatchView: ...

    def update_item_metadata(
        self,
        batch_id: str,
        item_id: str,
        *,
        product_ids: tuple[str, ...],
        version_label: str | None,
    ) -> ImportBatchView: ...

    def update_item_product_name(
        self,
        batch_id: str,
        item_id: str,
        *,
        product_name: str,
        version_label: str | None,
    ) -> ImportBatchView: ...


class SessionScopedImportService:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        service_factory: Callable[[Session], ImportService],
    ) -> None:
        self._session_factory = session_factory
        self._service_factory = service_factory

    def enqueue(
        self,
        files: tuple[UploadedDocument, ...],
    ) -> ImportBatchResult:
        with self._session_factory() as session:
            return self._service_factory(session).enqueue(files)

    def get_batch(self, batch_id: str) -> ImportBatchView:
        with self._session_factory() as session:
            return self._service_factory(session).get_batch(batch_id)

    def list_batches(self) -> tuple[ImportBatchSummary, ...]:
        with self._session_factory() as session:
            return self._service_factory(session).list_batches()

    def resolve_conflict(
        self,
        batch_id: str,
        item_id: str,
        action: ConflictAction,
        new_filename: str | None = None,
    ) -> ImportBatchView:
        with self._session_factory() as session:
            return self._service_factory(session).resolve_conflict(
                batch_id,
                item_id,
                action,
                new_filename,
            )

    def prepare_item(
        self,
        batch_id: str,
        item_id: str,
    ) -> ImportBatchView:
        with self._session_factory() as session:
            return self._service_factory(session).prepare_item(
                batch_id,
                item_id,
            )

    def update_item_metadata(
        self,
        batch_id: str,
        item_id: str,
        *,
        product_ids: tuple[str, ...],
        version_label: str | None,
    ) -> ImportBatchView:
        with self._session_factory() as session:
            return self._service_factory(session).update_item_metadata(
                batch_id,
                item_id,
                product_ids=product_ids,
                version_label=version_label,
            )

    def update_item_product_name(
        self,
        batch_id: str,
        item_id: str,
        *,
        product_name: str,
        version_label: str | None,
    ) -> ImportBatchView:
        with self._session_factory() as session:
            return self._service_factory(
                session
            ).update_item_product_name(
                batch_id,
                item_id,
                product_name=product_name,
                version_label=version_label,
            )


class SessionScopedPublicationService:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        service_factory: Callable[
            [Session],
            VersionPublicationService,
        ],
    ) -> None:
        self._session_factory = session_factory
        self._service_factory = service_factory

    def list_versions(
        self,
        product_id: str,
    ) -> tuple[VersionView, ...]:
        with self._session_factory() as session:
            return self._service_factory(session).list_versions(product_id)

    def list_pending_approval_product_ids(self) -> tuple[str, ...]:
        with self._session_factory() as session:
            return self._service_factory(
                session
            ).list_pending_approval_product_ids()

    def approve(self, version_id: str, *, approved_by: str) -> None:
        with self._session_factory() as session:
            self._service_factory(session).approve(
                version_id,
                approved_by=approved_by,
            )

    def publish(
        self,
        *,
        product_id: str,
        document_version_id: str,
        index_version_id: str,
    ) -> None:
        with self._session_factory() as session:
            self._service_factory(session).publish(
                product_id=product_id,
                document_version_id=document_version_id,
                index_version_id=index_version_id,
            )


class SessionScopedConversationService:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        service_factory: Callable[
            [Session],
            ConversationApplicationService,
        ],
    ) -> None:
        self._session_factory = session_factory
        self._service_factory = service_factory

    def create(self, *, visitor_id: str) -> str:
        with self._session_factory() as session:
            return self._service_factory(session).create(
                visitor_id=visitor_id
            )

    def get(
        self,
        conversation_id: str,
        *,
        visitor_id: str,
    ) -> ConversationView:
        with self._session_factory() as session:
            return self._service_factory(session).get(
                conversation_id,
                visitor_id=visitor_id,
            )

    def resolve_product(
        self,
        conversation_id: str,
        *,
        product_id: str,
        visitor_id: str,
    ) -> ConversationView:
        with self._session_factory() as session:
            return self._service_factory(session).resolve_product(
                conversation_id,
                product_id=product_id,
                visitor_id=visitor_id,
            )

    def get_preferences(self, visitor_id: str) -> UserPreference:
        with self._session_factory() as session:
            return self._service_factory(session).get_preferences(
                visitor_id
            )

    def update_preferences(
        self,
        visitor_id: str,
        *,
        language: str,
        answer_detail: AnswerDetail,
        show_citations: bool,
    ) -> UserPreference:
        with self._session_factory() as session:
            return self._service_factory(session).update_preferences(
                visitor_id,
                language=language,
                answer_detail=answer_detail,
                show_citations=show_citations,
            )

    def add_feedback(
        self,
        conversation_id: str,
        message_id: str,
        *,
        rating: str,
        reason: str | None,
        visitor_id: str,
    ) -> int:
        with self._session_factory() as session:
            return self._service_factory(session).add_feedback(
                conversation_id,
                message_id,
                rating=rating,
                reason=reason,
                visitor_id=visitor_id,
            )
