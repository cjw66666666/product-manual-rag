from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_app.persistence.schema import SparseIndexStatistics
from rag_app.sparse_encoder import (
    SparseStatistics,
    merge_sparse_statistics,
)


class SparseStatisticsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        *,
        document_version_id: str,
        index_version_id: str,
        statistics: SparseStatistics,
    ) -> None:
        entity = self._session.scalar(
            select(SparseIndexStatistics).where(
                SparseIndexStatistics.document_version_id
                == document_version_id,
                SparseIndexStatistics.index_version_id == index_version_id,
            )
        )
        payload = {
            "document_count": statistics.document_count,
            "total_length": statistics.total_length,
            "document_frequency": {
                str(key): value
                for key, value in statistics.document_frequency.items()
            },
        }
        if entity is None:
            entity = SparseIndexStatistics(
                document_version_id=document_version_id,
                index_version_id=index_version_id,
                statistics=payload,
            )
            self._session.add(entity)
        else:
            entity.statistics = payload
        self._session.flush()

    def aggregate(
        self,
        *,
        document_version_ids: tuple[str, ...],
        index_version_id: str,
    ) -> SparseStatistics:
        entities = self._session.scalars(
            select(SparseIndexStatistics).where(
                SparseIndexStatistics.document_version_id.in_(
                    document_version_ids
                ),
                SparseIndexStatistics.index_version_id == index_version_id,
            )
        ).all()
        values = tuple(_statistics(entity.statistics) for entity in entities)
        return merge_sparse_statistics(values)


def _statistics(payload: dict[str, object]) -> SparseStatistics:
    document_count = payload.get("document_count")
    total_length = payload.get("total_length")
    frequencies = payload.get("document_frequency")
    if (
        not isinstance(document_count, int)
        or not isinstance(total_length, int)
        or not isinstance(frequencies, dict)
    ):
        raise ValueError("invalid sparse statistics")
    document_frequency: dict[int, int] = {}
    for key, value in frequencies.items():
        if not isinstance(key, str) or not isinstance(value, int):
            raise ValueError("invalid sparse term statistics")
        document_frequency[int(key)] = value
    return SparseStatistics(
        document_count=document_count,
        total_length=total_length,
        document_frequency=document_frequency,
    )
