from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_app.persistence.schema import IndexCleanupJob


@dataclass(frozen=True, slots=True)
class CleanupJobRecord:
    id: str
    document_version_id: str
    index_version_id: str


class IndexCleanupRepository:
    def __init__(
        self,
        session: Session,
        *,
        max_attempts: int = 5,
    ) -> None:
        self._session = session
        self._max_attempts = max_attempts

    def enqueue(
        self,
        document_version_id: str,
        index_version_id: str,
    ) -> None:
        existing = self._session.scalar(
            select(IndexCleanupJob).where(
                IndexCleanupJob.document_version_id
                == document_version_id,
                IndexCleanupJob.index_version_id == index_version_id,
            )
        )
        if existing is not None:
            return
        self._session.add(
            IndexCleanupJob(
                id=uuid4().hex,
                document_version_id=document_version_id,
                index_version_id=index_version_id,
                status="pending",
                attempts=0,
                available_at=datetime.now(UTC),
            )
        )
        self._session.flush()

    def list_ready(self, *, limit: int) -> tuple[CleanupJobRecord, ...]:
        if limit < 1:
            raise ValueError("limit must be positive")
        entities = self._session.scalars(
            select(IndexCleanupJob)
            .where(
                IndexCleanupJob.status == "pending",
                IndexCleanupJob.available_at <= datetime.now(UTC),
            )
            .order_by(
                IndexCleanupJob.available_at,
                IndexCleanupJob.created_at,
                IndexCleanupJob.id,
            )
            .limit(limit)
        ).all()
        return tuple(
            CleanupJobRecord(
                id=entity.id,
                document_version_id=entity.document_version_id,
                index_version_id=entity.index_version_id,
            )
            for entity in entities
        )

    def mark_completed(self, job_id: str) -> None:
        entity = self._session.get(IndexCleanupJob, job_id)
        if entity is None:
            raise ValueError("cleanup job not found")
        entity.status = "completed"
        entity.error_message = None
        self._session.flush()

    def mark_failed(self, job_id: str, message: str) -> None:
        entity = self._session.get(IndexCleanupJob, job_id)
        if entity is None:
            raise ValueError("cleanup job not found")
        entity.attempts += 1
        entity.error_message = message
        if entity.attempts >= self._max_attempts:
            entity.status = "failed"
        else:
            entity.status = "pending"
            entity.available_at = datetime.now(UTC) + timedelta(
                seconds=min(300, 2**entity.attempts),
            )
        self._session.flush()
