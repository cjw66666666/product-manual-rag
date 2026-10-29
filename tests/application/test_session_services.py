from typing import cast
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from rag_app.answering import AnswerMode, AnswerObserver, AnswerResult
from rag_app.application import (
    ImportService,
    SessionScopedAnswerService,
    SessionScopedImportService,
)


def answer_result() -> AnswerResult:
    return AnswerResult(
        mode=AnswerMode.REFUSED,
        text="insufficient evidence",
        citations=(),
        attempts=2,
    )


def test_session_scoped_answer_service_uses_a_fresh_session_per_call() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    factory = sessionmaker(bind=engine)
    sessions: list[Session] = []

    class Service:
        def __init__(self, session: Session) -> None:
            self._session = session

        def conversation_product(
            self,
            conversation_id: str,
            *,
            visitor_id: str | None = None,
        ) -> str | None:
            return None

        def answer(
            self,
            question: str,
            product_id: str,
            *,
            conversation_id: str | None = None,
            observer: AnswerObserver | None = None,
            visitor_id: str | None = None,
        ) -> AnswerResult:
            sessions.append(self._session)
            assert self._session.get_bind() is engine
            return answer_result()

    scoped = SessionScopedAnswerService(
        session_factory=factory,
        service_factory=Service,
    )

    scoped.answer("q1", "p1", conversation_id="c1")
    scoped.answer("q2", "p1", conversation_id="c1")

    assert len(sessions) == 2
    assert sessions[0] is not sessions[1]


def test_session_scoped_import_service_uses_a_fresh_session_per_call() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    factory = sessionmaker(bind=engine)
    sessions: list[Session] = []
    batch_id = uuid4().hex

    class Service:
        def __init__(self, session: Session) -> None:
            self._session = session

        def get_batch(self, requested_batch_id: str) -> object:
            sessions.append(self._session)
            assert requested_batch_id == batch_id
            return object()

    scoped = SessionScopedImportService(
        session_factory=factory,
        service_factory=cast(
            type[ImportService],
            Service,
        ),
    )

    scoped.get_batch(batch_id)
    scoped.get_batch(batch_id)

    assert len(sessions) == 2
    assert sessions[0] is not sessions[1]
