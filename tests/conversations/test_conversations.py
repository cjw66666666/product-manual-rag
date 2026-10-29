import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from rag_app.answering import AnswerMode, AnswerResult
from rag_app.conversations import (
    AnswerDetail,
    ConversationMessage,
    ConversationService,
    SqlConversationContextStore,
    UserPreference,
    summarize_old_messages,
)
from rag_app.persistence import create_schema
from rag_app.persistence.answer_run_repository import AnswerRunRepository
from rag_app.persistence.schema import Message, Product


def test_new_conversation_has_no_product() -> None:
    state = ConversationService().start("conversation-1")

    assert state.product_id is None
    assert state.messages == ()


def test_select_product_sets_current_product() -> None:
    service = ConversationService()
    state = service.start("conversation-1")

    state = service.select_product(state, "huawei_c7")

    assert state.product_id == "huawei_c7"


def test_changing_product_clears_old_messages() -> None:
    service = ConversationService()
    state = service.start("conversation-1")
    state = service.select_product(state, "huawei_c7")
    state = service.append_exchange(state, "怎么开机？", "按电源键。[1]")

    state = service.change_product(state, "huawei_b5_440")

    assert state.product_id == "huawei_b5_440"
    assert state.messages == ()


def test_summary_preserves_recent_messages() -> None:
    messages = tuple(
        ConversationMessage("user", f"question-{index}") for index in range(8)
    )

    summary, recent = summarize_old_messages(messages, keep_recent=6)

    assert summary == "user: question-0\nuser: question-1"
    assert len(recent) == 6
    assert recent[-1].content == "question-7"


def test_default_preference_keeps_citations_brief() -> None:
    preference = UserPreference()

    assert preference.language == "zh-CN"
    assert preference.answer_detail is AnswerDetail.BRIEF
    assert preference.show_citations is True


def test_sql_context_store_persists_history_and_switches_topic() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        session.add_all([
            Product(
                id="p1",
                display_name="P1",
                category="tablet",
                brand="brand",
            ),
            Product(
                id="p2",
                display_name="P2",
                category="laptop",
                brand="brand",
            ),
        ])
        session.flush()
        store = SqlConversationContextStore(
            session,
        )
        store.open("conversation-1", "p1", visitor_id="visitor-1")
        exchange = store.append_exchange(
            "conversation-1",
            "p1",
            "C7 支持蓝牙吗？",
            "支持。[1]",
            visitor_id="visitor-1",
        )
        AnswerRunRepository(session).record(
            conversation_id="conversation-1",
            exchange=exchange,
            result=AnswerResult(
                mode=AnswerMode.MANUAL_GROUNDED,
                text="支持。[1]",
                citations=(),
                attempts=1,
            ),
            latency_ms=10,
        )
        session.flush()

        same_product = store.open(
            "conversation-1",
            "p1",
            visitor_id="visitor-1",
        )
        switched = store.open(
            "conversation-1",
            "p2",
            visitor_id="visitor-1",
        )

        assert [message.content for message in same_product.messages] == [
            "C7 支持蓝牙吗？",
            "支持。[1]",
        ]
        assert switched.product_id == "p2"
        assert switched.messages == ()
        assert session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == "conversation-1")
        ) == 2


def test_sql_context_store_rolls_old_messages_into_summary() -> None:
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
        store = SqlConversationContextStore(
            session,
        )
        store.open("conversation-1", "p1", visitor_id="visitor-1")
        for index in range(4):
            store.append_exchange(
                "conversation-1",
                "p1",
                f"question-{index}",
                f"answer-{index}",
                visitor_id="visitor-1",
            )

        context = store.open(
            "conversation-1",
            "p1",
            visitor_id="visitor-1",
        )

        assert "question-0" in context.summary
        assert len(context.messages) == 6
        assert context.messages[-1].content == "answer-3"


def test_sql_context_store_rejects_a_different_visitor() -> None:
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
        store = SqlConversationContextStore(session)
        store.open("conversation-1", "p1", visitor_id="visitor-1")

        with pytest.raises(PermissionError, match="visitor"):
            store.open("conversation-1", "p1", visitor_id="visitor-2")
