import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rag_app.application import ConversationApplicationService
from rag_app.conversations import AnswerDetail, SqlConversationContextStore
from rag_app.persistence import create_schema
from rag_app.persistence.conversation_repository import (
    SqlConversationRepository,
)
from rag_app.persistence.schema import Product


def test_conversation_service_creates_reads_and_resolves_product() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        session.add(Product(
            id="p1",
            display_name="P1",
            category="tablet",
            brand="brand",
        ))
        session.flush()
        service = ConversationApplicationService(
            conversations=SqlConversationRepository(session),
            commit=session.commit,
        )

        conversation_id = service.create(visitor_id="visitor-1")
        resolved = service.resolve_product(
            conversation_id,
            product_id="p1",
            visitor_id="visitor-1",
        )
        loaded = service.get(
            conversation_id,
            visitor_id="visitor-1",
        )

        assert resolved.product_id == "p1"
        assert loaded.conversation_id == conversation_id
        with pytest.raises(PermissionError, match="visitor"):
            service.get(conversation_id, visitor_id="visitor-2")


def test_conversation_service_updates_preferences() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        service = ConversationApplicationService(
            conversations=SqlConversationRepository(session),
            commit=session.commit,
        )

        initial = service.get_preferences("visitor-1")
        updated = service.update_preferences(
            "visitor-1",
            language="en-US",
            answer_detail=AnswerDetail.DETAILED,
            show_citations=False,
        )

        assert initial.language == "zh-CN"
        assert updated.language == "en-US"
        assert updated.answer_detail is AnswerDetail.DETAILED
        assert updated.show_citations is False


def test_conversation_service_records_feedback_for_owned_answer() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        session.add(Product(
            id="p1",
            display_name="P1",
            category="tablet",
            brand="brand",
        ))
        session.flush()
        contexts = SqlConversationContextStore(session)
        contexts.open("c1", "p1", visitor_id="visitor-1")
        exchange = contexts.append_exchange(
            "c1",
            "p1",
            "怎么开机？",
            "按电源键。[1]",
            visitor_id="visitor-1",
        )
        from rag_app.answering import AnswerMode, AnswerResult
        from rag_app.persistence.answer_run_repository import (
            AnswerRunRepository,
        )

        AnswerRunRepository(session).record(
            conversation_id="c1",
            exchange=exchange,
            result=AnswerResult(
                mode=AnswerMode.MANUAL_GROUNDED,
                text="按电源键。[1]",
                citations=(),
                attempts=1,
            ),
            latency_ms=10,
        )
        service = ConversationApplicationService(
            conversations=SqlConversationRepository(session),
            commit=session.commit,
        )

        feedback_id = service.add_feedback(
            "c1",
            exchange.assistant_message_id,
            rating="helpful",
            reason=None,
            visitor_id="visitor-1",
        )

        assert feedback_id > 0
        with pytest.raises(PermissionError, match="visitor"):
            service.add_feedback(
                "c1",
                exchange.assistant_message_id,
                rating="helpful",
                reason=None,
                visitor_id="visitor-2",
            )
