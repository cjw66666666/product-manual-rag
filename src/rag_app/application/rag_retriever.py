from dataclasses import dataclass
from typing import Protocol

from rag_app.answering import Evidence
from rag_app.retrieval import EvidenceHit


@dataclass(frozen=True, slots=True)
class IndexScope:
    document_version_ids: tuple[str, ...]
    index_version_id: str


class ScopeProvider(Protocol):
    def current(self, product_id: str) -> IndexScope: ...


class RetrievalEngine(Protocol):
    def search(
        self,
        question: str,
        *,
        product_id: str,
        document_version_ids: tuple[str, ...],
        index_version_id: str,
    ) -> tuple[EvidenceHit, ...]: ...


class RagRetriever:
    def __init__(
        self,
        *,
        scope_provider: ScopeProvider,
        engine: RetrievalEngine,
    ) -> None:
        self._scope_provider = scope_provider
        self._engine = engine

    def retrieve(
        self,
        question: str,
        product_id: str,
    ) -> tuple[Evidence, ...]:
        scope = self._scope_provider.current(product_id)
        hits = self._engine.search(
            question,
            product_id=product_id,
            document_version_ids=scope.document_version_ids,
            index_version_id=scope.index_version_id,
        )
        return tuple(
            Evidence(
                chunk_id=hit.chunk_id,
                content=hit.content,
                page=hit.page,
                product_id=hit.product_id,
                document_version_id=hit.document_version_id,
                index_version_id=hit.index_version_id,
                document_sha256=hit.document_sha256,
                document_name=hit.document_name,
                version_label=hit.version_label,
                section_path=hit.section_path,
            )
            for hit in hits
        )
