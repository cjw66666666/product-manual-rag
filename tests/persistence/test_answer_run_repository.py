from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from rag_app.answering import AnswerMode, AnswerResult, Evidence
from rag_app.conversations import SqlConversationContextStore
from rag_app.persistence import create_schema
from rag_app.persistence.answer_run_repository import AnswerRunRepository
from rag_app.persistence.schema import AnswerRun, Product


def test_answer_run_persists_versions_and_citation_snapshot() -> None:
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
        evidence = Evidence(
            "chunk-1",
            "按电源键开机。",
            10,
            product_id="p1",
            document_version_id="v1",
            index_version_id="i1",
            document_sha256="a" * 64,
            document_name="manual.pdf",
            version_label="1.0",
            section_path=("基础使用", "开机"),
        )
        run_id = AnswerRunRepository(session).record(
            conversation_id="c1",
            exchange=exchange,
            result=AnswerResult(
                mode=AnswerMode.MANUAL_GROUNDED,
                text="按电源键。[1]",
                citations=("chunk-1",),
                attempts=1,
                evidence=(evidence,),
            ),
            latency_ms=12.5,
        )

        run = session.scalar(
            select(AnswerRun).where(AnswerRun.id == run_id)
        )

        assert run is not None
        assert run.user_message_id == exchange.user_message_id
        assert run.assistant_message_id == exchange.assistant_message_id
        assert run.retrieved_document_version_ids == ["v1"]
        assert run.index_version_id == "i1"
        assert run.citations_snapshot[0]["document_sha256"] == "a" * 64
        assert run.citations_snapshot[0]["section_path"] == [
            "基础使用",
            "开机",
        ]
        assert run.status == "completed"


def test_failed_answer_keeps_user_message_without_fake_assistant() -> None:
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
        user_message_id = contexts.begin_exchange(
            "c1",
            "p1",
            "怎么开机？",
            visitor_id="visitor-1",
        )

        run_id = AnswerRunRepository(session).record_failure(
            conversation_id="c1",
            user_message_id=user_message_id,
            status="failed",
            error_type="ProviderError",
            latency_ms=20.0,
        )
        run = session.scalar(
            select(AnswerRun).where(AnswerRun.id == run_id)
        )

        assert run is not None
        assert run.user_message_id == user_message_id
        assert run.assistant_message_id is None
        assert run.status == "failed"
        assert run.verification_result == {
            "error_type": "ProviderError"
        }
