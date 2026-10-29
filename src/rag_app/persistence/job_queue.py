from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_app.persistence.schema import IngestionItem
from rag_app.worker import Job


class IngestionJobQueue:
    def __init__(self, session: Session) -> None:
        self._session = session

    def claim(self) -> Job | None:
        item = self._session.scalar(
            select(IngestionItem)
            .where(IngestionItem.status == "queued")
            .order_by(IngestionItem.id)
            .with_for_update(skip_locked=True)
        )
        if item is None:
            return None
        item.status = "processing"
        self._session.flush()
        return Job(id=item.id, payload=item.sha256)

    def complete(self, job_id: str) -> None:
        item = self._session.get(IngestionItem, job_id)
        if item is None:
            raise ValueError("ingestion item not found")
        item.status = "completed"
        self._session.flush()

    def fail(self, job_id: str, message: str) -> None:
        item = self._session.get(IngestionItem, job_id)
        if item is None:
            raise ValueError("ingestion item not found")
        item.status = "failed"
        item.error_code = "worker_failed"
        item.error_message = message
        self._session.flush()
