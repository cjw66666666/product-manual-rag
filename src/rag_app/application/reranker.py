from typing import Protocol

from rag_app.remote_models import RerankScore
from rag_app.retrieval import EvidenceHit, SearchHit


class RerankerClient(Protocol):
    def rerank(
        self,
        query: str,
        documents: tuple[str, ...],
        *,
        model: str,
    ) -> tuple[RerankScore, ...]: ...


class RemoteReranker:
    def __init__(self, *, client: RerankerClient, model: str) -> None:
        self._client = client
        self._model = model

    def rerank(
        self,
        question: str,
        hits: tuple[SearchHit, ...],
    ) -> tuple[EvidenceHit, ...]:
        scores = self._client.rerank(
            question,
            tuple(hit.content for hit in hits),
            model=self._model,
        )
        if not scores:
            return tuple(
                EvidenceHit(
                    chunk_id=hit.chunk_id,
                    content=hit.content,
                    page=hit.page,
                    score=0.0,
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
        result: list[EvidenceHit] = []
        for score in scores:
            if not 0 <= score.index < len(hits):
                raise ValueError("reranker returned an invalid index")
            hit = hits[score.index]
            result.append(
                EvidenceHit(
                    chunk_id=hit.chunk_id,
                    content=hit.content,
                    page=hit.page,
                    score=score.score,
                    product_id=hit.product_id,
                    document_version_id=hit.document_version_id,
                    index_version_id=hit.index_version_id,
                    document_sha256=hit.document_sha256,
                    document_name=hit.document_name,
                    version_label=hit.version_label,
                    section_path=hit.section_path,
                )
            )
        return tuple(result)
