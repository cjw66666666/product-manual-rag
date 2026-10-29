from sqlalchemy.orm import Session

from rag_app.indexing_worker import IndexingCommand
from rag_app.persistence.schema import IngestionItem


class IndexingContextProvider:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, job_id: str) -> IndexingCommand:
        item = self._session.get(IngestionItem, job_id)
        if item is None:
            raise ValueError("ingestion item not found")
        if item.document_version_id is None:
            raise ValueError("document version is not assigned")
        if item.index_version_id is None:
            raise ValueError("index version is not assigned")
        if len(item.selected_product_ids) != 1:
            raise ValueError("exactly one product must be selected")
        return IndexingCommand(
            sha256=item.sha256,
            document_version_id=item.document_version_id,
            index_version_id=item.index_version_id,
            product_id=item.selected_product_ids[0],
            document_name=item.original_filename,
            version_label=item.detected_version_label,
        )
