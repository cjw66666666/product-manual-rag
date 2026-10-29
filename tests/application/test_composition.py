import httpx
from qdrant_client import QdrantClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rag_app.application import ConversationalAnswerService
from rag_app.bootstrap import build_answer_service
from rag_app.evaluation import LatestRetrievalTrace
from rag_app.persistence import create_schema
from rag_app.settings import Settings


def test_build_answer_service_wires_public_adapters() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    service = build_answer_service(
        settings=Settings(),
        session=Session(engine),
        qdrant=QdrantClient(":memory:"),
        http_client=httpx.Client(),
        index_version_id="index-1",
    )

    assert isinstance(service, ConversationalAnswerService)


def test_build_answer_service_accepts_a_retrieval_observer() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    observer = LatestRetrievalTrace()

    service = build_answer_service(
        settings=Settings(),
        session=Session(engine),
        qdrant=QdrantClient(":memory:"),
        http_client=httpx.Client(),
        index_version_id="index-1",
        retrieval_observer=observer,
    )

    assert isinstance(service, ConversationalAnswerService)
