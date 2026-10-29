from collections.abc import Sequence
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from rag_app.persistence.schema import IngestionBatch, IngestionItem


@dataclass(frozen=True, slots=True)
class ImportItemInput:
    relative_path: str
    filename: str
    sha256: str
    confidence: str
    detected_product_ids: tuple[str, ...] = ()
    detected_product_name: str | None = None
    selected_product_ids: tuple[str, ...] = ()
    detected_version_label: str | None = None
    version_source: str = "unknown"
    document_type_codes: tuple[str, ...] = ()
    conflict_type: str | None = None


@dataclass(frozen=True, slots=True)
class ImportItemRecord:
    id: str
    filename: str
    sha256: str
    detected_product_ids: tuple[str, ...]
    detected_product_name: str | None
    selected_product_ids: tuple[str, ...]
    detected_version_label: str | None
    confidence: str
    conflict_type: str | None
    conflict_version_label: str | None
    status: str


@dataclass(frozen=True, slots=True)
class ImportConflictRecord:
    conflict_type: str
    version_label: str | None


@dataclass(frozen=True, slots=True)
class ImportBatchRecord:
    id: str
    source_type: str
    status: str
    created_by: str
    item_count: int


class ImportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_batch(
        self,
        *,
        created_by: str,
        source_type: str,
        items: Sequence[ImportItemInput],
    ) -> str:
        batch_id = uuid4().hex
        self._session.add(
            IngestionBatch(
                id=batch_id,
                source_type=source_type,
                status="queued",
                created_by=created_by,
            )
        )
        for item in items:
            self._session.add(
                IngestionItem(
                    id=uuid4().hex,
                    batch_id=batch_id,
                    relative_path=item.relative_path,
                    original_filename=item.filename,
                    sha256=item.sha256,
                    detected_product_ids=list(item.detected_product_ids),
                    detected_product_name=item.detected_product_name,
                    selected_product_ids=list(item.selected_product_ids),
                    detected_version_label=item.detected_version_label,
                    version_source=item.version_source,
                    document_type_codes=list(item.document_type_codes),
                    document_version_id=None,
                    index_version_id=None,
                    confidence=item.confidence,
                    conflict_type=item.conflict_type,
                    status=(
                        "conflict" if item.conflict_type else "uploaded"
                    ),
                )
            )
        self._session.flush()
        return batch_id

    def list_items(self, batch_id: str) -> tuple[ImportItemRecord, ...]:
        items = self._session.scalars(
            select(IngestionItem).where(IngestionItem.batch_id == batch_id)
            .execution_options(populate_existing=True)
        ).all()
        return tuple(
            ImportItemRecord(
                id=item.id,
                filename=item.original_filename,
                sha256=item.sha256,
                detected_product_ids=tuple(item.detected_product_ids),
                detected_product_name=item.detected_product_name,
                selected_product_ids=tuple(item.selected_product_ids),
                detected_version_label=item.detected_version_label,
                confidence=item.confidence,
                conflict_type=item.conflict_type,
                conflict_version_label=self._conflict_version_label(item),
                status=item.status,
            )
            for item in items
        )

    def list_batches(self) -> tuple[ImportBatchRecord, ...]:
        batches = self._session.scalars(
            select(IngestionBatch).order_by(
                IngestionBatch.created_at.desc()
            )
        ).all()
        records: list[ImportBatchRecord] = []
        for batch in batches:
            items = self.list_items(batch.id)
            active_items = tuple(
                item
                for item in items
                if item.status
                not in {"completed", "cancelled", "indexed"}
            )
            if not active_items:
                continue
            statuses = {item.status for item in active_items}
            summary_status = (
                "processing"
                if "processing" in statuses
                else "queued"
                if "queued" in statuses
                else "conflict"
                if "conflict" in statuses
                else "uploaded"
            )
            records.append(
                ImportBatchRecord(
                    id=batch.id,
                    source_type=batch.source_type,
                    status=summary_status,
                    created_by=batch.created_by,
                    item_count=len(active_items),
                )
            )
        return tuple(records)

    def find_conflict(self, filename: str, sha256: str) -> str | None:
        conflict = self.find_conflict_details(filename, sha256)
        return None if conflict is None else conflict.conflict_type

    def find_conflict_details(
        self,
        filename: str,
        sha256: str,
    ) -> ImportConflictRecord | None:
        existing = self._find_conflict_item(filename, sha256)
        if existing is None:
            return None
        return ImportConflictRecord(
            conflict_type=(
                "duplicate_content"
                if existing.sha256 == sha256
                else "same_name"
            ),
            version_label=existing.detected_version_label,
        )

    def resolve_conflict(
        self,
        item_id: str,
        action: str,
        new_filename: str | None,
    ) -> None:
        item = self._session.get(IngestionItem, item_id)
        if item is None:
            raise ValueError("import item not found")
        if action == "cancel":
            item.status = "cancelled"
            return
        if action == "replace_as_new_version":
            conflict = self._find_conflict_item(
                item.original_filename,
                item.sha256,
                exclude_id=item.id,
            )
            old_version = (
                conflict.detected_version_label
                if conflict is not None
                else None
            )
            new_version = item.detected_version_label
            if (
                new_version is None
                or (
                    old_version is not None
                    and old_version.strip().casefold()
                    == new_version.strip().casefold()
                )
            ):
                raise ValueError(
                    "a distinct version label is required"
                )
            item.conflict_type = None
            item.status = "uploaded"
            return
        if action == "rename_and_continue":
            if not new_filename or not new_filename.strip():
                raise ValueError("new filename is required")
            item.original_filename = new_filename.strip()
            item.relative_path = new_filename.strip()
            item.conflict_type = None
            item.status = "uploaded"
            return
        raise ValueError("unsupported conflict action")

    def update_item_metadata(
        self,
        item_id: str,
        *,
        product_ids: tuple[str, ...],
        version_label: str | None,
    ) -> None:
        if not product_ids:
            raise ValueError("at least one product must be selected")
        item = self._session.get(IngestionItem, item_id)
        if item is None:
            raise ValueError("import item not found")
        item.selected_product_ids = list(product_ids)
        item.detected_product_name = None
        item.detected_version_label = version_label
        item.version_source = "manual"
        item.confidence = "high" if version_label else "medium"
        item.status = "uploaded" if item.conflict_type is None else "conflict"
        self._session.flush()

    def set_detected_product_name(
        self,
        item_id: str,
        product_name: str | None,
    ) -> None:
        item = self._session.get(IngestionItem, item_id)
        if item is None:
            raise ValueError("import item not found")
        item.detected_product_name = product_name
        self._session.flush()

    def _conflict_version_label(
        self,
        item: IngestionItem,
    ) -> str | None:
        if item.conflict_type is None:
            return None
        conflict = self._find_conflict_item(
            item.original_filename,
            item.sha256,
            exclude_id=item.id,
        )
        return (
            None
            if conflict is None
            else conflict.detected_version_label
        )

    def _find_conflict_item(
        self,
        filename: str,
        sha256: str,
        *,
        exclude_id: str | None = None,
    ) -> IngestionItem | None:
        statement = select(IngestionItem).where(
            or_(
                IngestionItem.original_filename == filename,
                IngestionItem.sha256 == sha256,
            ),
            IngestionItem.status != "cancelled",
        )
        if exclude_id is not None:
            statement = statement.where(IngestionItem.id != exclude_id)
        return self._session.scalars(statement).first()
