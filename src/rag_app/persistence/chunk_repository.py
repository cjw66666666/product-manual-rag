from collections.abc import Sequence
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.orm import Session

from rag_app.chunking import ChunkDraft
from rag_app.persistence.schema import Chunk, DocumentSection, DocumentVersion


class ChunkRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_version_chunks(
        self,
        document_version_id: str,
        chunks: Sequence[ChunkDraft],
    ) -> tuple[str, ...]:
        self._session.execute(
            delete(Chunk).where(
                Chunk.document_version_id == document_version_id
            )
        )
        self._session.execute(
            delete(DocumentSection).where(
                DocumentSection.document_version_id == document_version_id
            )
        )
        if any(
            "safety" in chunk.section_types for chunk in chunks
        ):
            version = self._session.get(DocumentVersion, document_version_id)
            if version is None:
                raise ValueError("document version not found")
            version.requires_manual_approval = True

        chunk_rows: list[Chunk] = []
        chunk_ids: list[str] = []
        for order, chunk in enumerate(chunks):
            section_id = uuid4().hex
            chunk_id = uuid4().hex
            self._session.add(
                DocumentSection(
                    id=section_id,
                    document_version_id=document_version_id,
                    parent_section_id=None,
                    section_path=list(chunk.section_path),
                    title=chunk.section_path[-1] if chunk.section_path else "正文",
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    section_types=list(chunk.section_types),
                    order_index=order,
                )
            )
            chunk_ids.append(chunk_id)
            chunk_rows.append(
                Chunk(
                    id=chunk_id,
                    document_version_id=document_version_id,
                    section_id=section_id,
                    content=chunk.content,
                    content_hash=sha256(
                        chunk.content.encode("utf-8")
                    ).hexdigest(),
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    section_path=list(chunk.section_path),
                    section_types=list(chunk.section_types),
                    block_ids=[],
                    order_index=order,
                    has_images=chunk.has_images,
                )
            )
        self._session.flush()
        self._session.add_all(chunk_rows)
        self._session.flush()
        return tuple(chunk_ids)
