from uuid import uuid4

from sqlalchemy.orm import Session

from rag_app.answering import AnswerResult
from rag_app.conversations import ConversationExchange
from rag_app.persistence.schema import AnswerRun


class AnswerRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        conversation_id: str,
        exchange: ConversationExchange,
        result: AnswerResult,
        latency_ms: float,
    ) -> str:
        evidence_by_id = {
            item.chunk_id: item for item in result.evidence
        }
        citations_snapshot = [
            {
                "chunk_id": item.chunk_id,
                "page": item.page,
                "content": item.content,
                "product_id": item.product_id,
                "document_version_id": item.document_version_id,
                "index_version_id": item.index_version_id,
                "document_sha256": item.document_sha256,
                "document_name": item.document_name,
                "version_label": item.version_label,
                "section_path": list(item.section_path),
            }
            for chunk_id in result.citations
            if (item := evidence_by_id.get(chunk_id)) is not None
        ]
        document_versions = tuple(
            dict.fromkeys(
                item.document_version_id
                for item in result.evidence
                if item.document_version_id is not None
            )
        )
        index_version_id = next(
            (
                item.index_version_id
                for item in result.evidence
                if item.index_version_id is not None
            ),
            None,
        )
        entity = AnswerRun(
            id=uuid4().hex,
            conversation_id=conversation_id,
            user_message_id=exchange.user_message_id,
            assistant_message_id=exchange.assistant_message_id,
            mode=result.mode.value,
            trace_id=None,
            index_version_id=index_version_id,
            retrieved_document_version_ids=list(document_versions),
            citations_snapshot=citations_snapshot,
            verification_result={
                "mode": result.mode.value,
                "attempts": result.attempts,
            },
            retry_count=max(0, result.attempts - 1),
            latency_ms=latency_ms,
            token_usage={},
            estimated_cost=0,
            status=(
                "refused"
                if result.mode.value == "refused"
                else "completed"
            ),
        )
        self._session.add(entity)
        self._session.flush()
        return entity.id

    def record_failure(
        self,
        *,
        conversation_id: str,
        user_message_id: str,
        status: str,
        error_type: str,
        latency_ms: float,
    ) -> str:
        entity = AnswerRun(
            id=uuid4().hex,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=None,
            mode="failed",
            trace_id=None,
            index_version_id=None,
            retrieved_document_version_ids=[],
            citations_snapshot=[],
            verification_result={"error_type": error_type},
            retry_count=0,
            latency_ms=latency_ms,
            token_usage={},
            estimated_cost=0,
            status=status,
        )
        self._session.add(entity)
        self._session.flush()
        return entity.id
