from typing import Protocol

from rag_app.application.rag_retriever import IndexScope


class ActiveVersionProvider(Protocol):
    def active_version_ids(self, product_id: str) -> tuple[str, ...]: ...

    def active_index_version(self, product_id: str) -> str | None: ...


class ProductIndexScopeProvider:
    def __init__(
        self,
        *,
        versions: ActiveVersionProvider,
        index_version_id: str,
    ) -> None:
        self._versions = versions
        self._index_version_id = index_version_id

    def current(self, product_id: str) -> IndexScope:
        return IndexScope(
            document_version_ids=self._versions.active_version_ids(product_id),
            index_version_id=(
                self._versions.active_index_version(product_id)
                or self._index_version_id
            ),
        )
