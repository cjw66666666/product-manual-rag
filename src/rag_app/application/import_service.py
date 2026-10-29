from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Protocol

from rag_app.application.filename_product_extractor import (
    FilenameProductExtractor,
)
from rag_app.catalog import MatchStatus, ProductCatalog
from rag_app.file_store import Sha256FileStore
from rag_app.metadata_extraction import (
    MetadataExtraction,
    extract_metadata,
    extract_pdf_metadata_text,
)
from rag_app.persistence.import_repository import (
    ImportItemInput,
    ImportRepository,
)


@dataclass(frozen=True, slots=True)
class UploadedDocument:
    filename: str
    content_type: str
    content: bytes
    sha256: str
    relative_path: str | None = None


@dataclass(frozen=True, slots=True)
class ImportBatchResult:
    batch_id: str | None
    accepted: int
    rejected: tuple["ImportRejection", ...] = ()


@dataclass(frozen=True, slots=True)
class ImportRejection:
    filename: str
    reason: str


@dataclass(frozen=True, slots=True)
class ImportItemView:
    item_id: str
    filename: str
    sha256: str
    product_ids: tuple[str, ...]
    version_label: str | None
    confidence: str
    conflict_type: str | None
    status: str
    conflict_version_label: str | None = None
    detected_product_name: str | None = None


@dataclass(frozen=True, slots=True)
class ImportBatchView:
    batch_id: str
    items: tuple[ImportItemView, ...]


@dataclass(frozen=True, slots=True)
class ImportBatchSummary:
    batch_id: str
    source_type: str
    status: str
    created_by: str
    item_count: int


class ConflictAction(StrEnum):
    REPLACE_AS_NEW_VERSION = "replace_as_new_version"
    RENAME_AND_CONTINUE = "rename_and_continue"
    CANCEL = "cancel"


class ImportService(Protocol):
    def enqueue(
        self,
        files: tuple[UploadedDocument, ...],
    ) -> ImportBatchResult: ...

    def get_batch(self, batch_id: str) -> ImportBatchView: ...

    def list_batches(self) -> tuple[ImportBatchSummary, ...]: ...

    def resolve_conflict(
        self,
        batch_id: str,
        item_id: str,
        action: ConflictAction,
        new_filename: str | None = None,
    ) -> ImportBatchView: ...

    def prepare_item(
        self,
        batch_id: str,
        item_id: str,
    ) -> ImportBatchView: ...

    def update_item_metadata(
        self,
        batch_id: str,
        item_id: str,
        *,
        product_ids: tuple[str, ...],
        version_label: str | None,
    ) -> ImportBatchView: ...

    def update_item_product_name(
        self,
        batch_id: str,
        item_id: str,
        *,
        product_name: str,
        version_label: str | None,
    ) -> ImportBatchView: ...


class VersionBinder(Protocol):
    def bind(self, *, item_id: str, index_version_id: str) -> str: ...


class ProductDirectory(Protocol):
    def resolve_or_create(self, display_name: str) -> str: ...


class PersistentImportService:
    def __init__(
        self,
        *,
        repository: ImportRepository,
        file_store: Sha256FileStore,
        created_by: str,
        catalog: ProductCatalog | None = None,
        catalog_provider: Callable[[], ProductCatalog] | None = None,
        products: ProductDirectory | None = None,
        filename_product_extractor: FilenameProductExtractor | None = None,
        version_binder: VersionBinder | None = None,
        index_version_id: str | None = None,
        commit: Callable[[], None] = lambda: None,
    ) -> None:
        self._repository = repository
        self._file_store = file_store
        self._created_by = created_by
        self._catalog = catalog
        self._catalog_provider = catalog_provider
        self._products = products
        self._filename_product_extractor = filename_product_extractor
        self._version_binder = version_binder
        self._index_version_id = index_version_id
        self._commit = commit

    def enqueue(
        self,
        files: tuple[UploadedDocument, ...],
    ) -> ImportBatchResult:
        items: list[ImportItemInput] = []
        for file in files:
            digest = sha256(file.content).hexdigest()
            self._file_store.put(file.content)
            metadata = None
            catalog = (
                self._catalog_provider()
                if self._catalog_provider is not None
                else self._catalog
            )
            if catalog is not None:
                document_text = extract_pdf_metadata_text(
                    self._file_store.path_for_sha256(digest)
                )
                document_metadata = extract_metadata(
                    document_text,
                    catalog,
                    source="document_text",
                )
                filename_metadata = extract_metadata(
                    file.filename,
                    catalog,
                    source="filename",
                )
                product_ids = (
                    document_metadata.product_ids
                    or filename_metadata.product_ids
                )
                version_label = (
                    document_metadata.version_label
                    or filename_metadata.version_label
                )
                version_source = (
                    "document_text"
                    if document_metadata.version_label
                    else "filename"
                    if filename_metadata.version_label
                    else "unknown"
                )
                product_name = (
                    document_metadata.product_name
                    or filename_metadata.product_name
                )
                if (
                    not product_ids
                    and self._filename_product_extractor is not None
                ):
                    candidate = self._filename_product_extractor.extract(
                        file.filename
                    )
                    if candidate:
                        candidate_match = catalog.resolve(candidate)
                        if (
                            candidate_match.status is MatchStatus.RESOLVED
                        ):
                            product_ids = tuple(
                                product.id
                                for product in candidate_match.products
                            )
                            product_name = candidate_match.products[
                                0
                            ].display_name
                        else:
                            product_name = candidate
                confidence = (
                    "high"
                    if product_ids and version_label
                    else "medium"
                    if product_ids
                    else "low"
                )
                metadata = MetadataExtraction(
                    product_ids=product_ids,
                    product_name=product_name,
                    version_label=version_label,
                    version_source=version_source,
                    confidence=confidence,
                )
            conflict = self._repository.find_conflict(
                file.filename,
                digest,
            )
            items.append(
                ImportItemInput(
                    relative_path=file.relative_path or file.filename,
                    filename=file.filename,
                    sha256=digest,
                    confidence=metadata.confidence if metadata else "low",
                    detected_product_ids=(
                        metadata.product_ids if metadata else ()
                    ),
                    detected_product_name=(
                        metadata.product_name if metadata else None
                    ),
                    selected_product_ids=(
                        metadata.product_ids if metadata else ()
                    ),
                    detected_version_label=(
                        metadata.version_label if metadata else None
                    ),
                    version_source=(
                        metadata.version_source if metadata else "unknown"
                    ),
                    conflict_type=conflict,
                )
            )
        batch_id = self._repository.create_batch(
            created_by=self._created_by,
            source_type="files",
            items=tuple(items),
        )
        self._commit()
        return ImportBatchResult(batch_id=batch_id, accepted=len(items))

    def get_batch(self, batch_id: str) -> ImportBatchView:
        return ImportBatchView(
            batch_id=batch_id,
            items=tuple(
                ImportItemView(
                    item_id=item.id,
                    filename=item.filename,
                    sha256=item.sha256,
                    product_ids=item.selected_product_ids,
                    version_label=item.detected_version_label,
                    detected_product_name=item.detected_product_name,
                    confidence=item.confidence,
                    conflict_type=item.conflict_type,
                    conflict_version_label=item.conflict_version_label,
                    status=item.status,
                )
                for item in self._repository.list_items(batch_id)
            ),
        )

    def list_batches(self) -> tuple[ImportBatchSummary, ...]:
        return tuple(
            ImportBatchSummary(
                batch_id=item.id,
                source_type=item.source_type,
                status=item.status,
                created_by=item.created_by,
                item_count=item.item_count,
            )
            for item in self._repository.list_batches()
        )

    def resolve_conflict(
        self,
        batch_id: str,
        item_id: str,
        action: ConflictAction,
        new_filename: str | None = None,
    ) -> ImportBatchView:
        self._repository.resolve_conflict(
            item_id,
            action.value,
            new_filename,
        )
        self._commit()
        return self.get_batch(batch_id)

    def update_item_product_name(
        self,
        batch_id: str,
        item_id: str,
        *,
        product_name: str,
        version_label: str | None,
    ) -> ImportBatchView:
        if self._products is None:
            raise ValueError("product directory is not configured")
        product_id = self._products.resolve_or_create(product_name)
        self._repository.update_item_metadata(
            item_id,
            product_ids=(product_id,),
            version_label=version_label,
        )
        self._repository.set_detected_product_name(item_id, product_name)
        self._commit()
        return self.get_batch(batch_id)

    def prepare_item(
        self,
        batch_id: str,
        item_id: str,
    ) -> ImportBatchView:
        if self._version_binder is None or self._index_version_id is None:
            raise ValueError("version binding is not configured")
        self._version_binder.bind(
            item_id=item_id,
            index_version_id=self._index_version_id,
        )
        self._commit()
        return self.get_batch(batch_id)

    def update_item_metadata(
        self,
        batch_id: str,
        item_id: str,
        *,
        product_ids: tuple[str, ...],
        version_label: str | None,
    ) -> ImportBatchView:
        self._repository.update_item_metadata(
            item_id,
            product_ids=product_ids,
            version_label=version_label,
        )
        self._commit()
        return self.get_batch(batch_id)
