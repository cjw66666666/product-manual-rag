from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(32))
    brand: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="active")


class ProductAlias(Base):
    __tablename__ = "product_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id"),
        index=True,
    )
    alias: Mapped[str] = mapped_column(String(255))
    normalized_alias: Mapped[str] = mapped_column(
        String(255),
        unique=True,
    )
    alias_type: Mapped[str] = mapped_column(String(32))


class FileBlob(Base):
    __tablename__ = "file_blobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    storage_uri: Mapped[str] = mapped_column(String(1024))
    size_bytes: Mapped[int] = mapped_column(Integer)
    original_filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(512))
    manufacturer: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active")


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id"),
        index=True,
    )
    file_blob_id: Mapped[int] = mapped_column(ForeignKey("file_blobs.id"))
    version_label: Mapped[str | None] = mapped_column(String(255))
    version_key: Mapped[str] = mapped_column(String(255), unique=True)
    version_source: Mapped[str] = mapped_column(String(64))
    version_confidence: Mapped[str] = mapped_column(String(32))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    requires_manual_approval: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    approved_by: Mapped[str | None] = mapped_column(String(128))
    metadata_confidence: Mapped[str] = mapped_column(String(32))
    metadata_evidence: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class ProductDocumentBinding(TimestampMixin, Base):
    __tablename__ = "product_document_bindings"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "document_id",
            name="uq_product_document",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    active_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_versions.id")
    )


class DocumentType(Base):
    __tablename__ = "document_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))


class DocumentVersionType(Base):
    __tablename__ = "document_version_types"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id",
            "document_type_id",
            name="uq_document_version_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id")
    )
    document_type_id: Mapped[int] = mapped_column(
        ForeignKey("document_types.id")
    )


class DocumentSection(Base):
    __tablename__ = "document_sections"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id"),
        index=True,
    )
    parent_section_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_sections.id")
    )
    section_path: Mapped[list[str]] = mapped_column(JSON)
    title: Mapped[str] = mapped_column(String(512))
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    section_types: Mapped[list[str]] = mapped_column(JSON)
    order_index: Mapped[int] = mapped_column(Integer)


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id"),
        index=True,
    )
    section_id: Mapped[str] = mapped_column(ForeignKey("document_sections.id"))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    section_path: Mapped[list[str]] = mapped_column(JSON)
    section_types: Mapped[list[str]] = mapped_column(JSON)
    block_ids: Mapped[list[str]] = mapped_column(JSON)
    order_index: Mapped[int] = mapped_column(Integer)
    has_images: Mapped[bool] = mapped_column(Boolean, default=False)


class IndexVersion(Base):
    __tablename__ = "index_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chunker_version: Mapped[str] = mapped_column(String(64))
    dense_provider: Mapped[str] = mapped_column(String(128))
    dense_model: Mapped[str] = mapped_column(String(255))
    dense_model_revision: Mapped[str] = mapped_column(String(128))
    dense_dimension: Mapped[int] = mapped_column(Integer)
    sparse_method: Mapped[str] = mapped_column(String(64))
    sparse_tokenizer: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class SparseIndexStatistics(Base):
    __tablename__ = "sparse_index_statistics"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id",
            "index_version_id",
            name="uq_sparse_statistics_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id"),
        index=True,
    )
    index_version_id: Mapped[str] = mapped_column(
        ForeignKey("index_versions.id"),
    )
    statistics: Mapped[dict[str, object]] = mapped_column(JSON)


class DocumentIndex(Base):
    __tablename__ = "document_indexes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id")
    )
    index_version_id: Mapped[str] = mapped_column(
        ForeignKey("index_versions.id")
    )
    status: Mapped[str] = mapped_column(String(32))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)


class ProductIndexBinding(TimestampMixin, Base):
    __tablename__ = "product_index_bindings"

    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id"),
        primary_key=True,
    )
    index_version_id: Mapped[str] = mapped_column(
        ForeignKey("index_versions.id")
    )


class IndexCleanupJob(TimestampMixin, Base):
    __tablename__ = "index_cleanup_jobs"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id",
            "index_version_id",
            name="uq_index_cleanup_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id"),
        index=True,
    )
    index_version_id: Mapped[str] = mapped_column(
        ForeignKey("index_versions.id"),
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text)


class IngestionBatch(Base):
    __tablename__ = "ingestion_batches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class IngestionItem(Base):
    __tablename__ = "ingestion_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("ingestion_batches.id"))
    relative_path: Mapped[str] = mapped_column(String(1024))
    original_filename: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    detected_product_ids: Mapped[list[str]] = mapped_column(JSON)
    detected_product_name: Mapped[str | None] = mapped_column(String(255))
    selected_product_ids: Mapped[list[str]] = mapped_column(JSON)
    detected_version_label: Mapped[str | None] = mapped_column(String(255))
    version_source: Mapped[str] = mapped_column(String(64))
    document_type_codes: Mapped[list[str]] = mapped_column(JSON)
    document_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_versions.id")
    )
    index_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("index_versions.id")
    )
    confidence: Mapped[str] = mapped_column(String(32))
    conflict_type: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    visitor_id: Mapped[str] = mapped_column(String(64), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"))
    status: Mapped[str] = mapped_column(String(32))
    context_start_sequence: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"),
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    rewritten_query: Mapped[str | None] = mapped_column(Text)
    sequence: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"),
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text)
    covered_message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id")
    )
    covered_sequence: Mapped[int] = mapped_column(Integer)
    token_estimate: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class VisitorPreference(TimestampMixin, Base):
    __tablename__ = "visitor_preferences"

    visitor_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    language: Mapped[str] = mapped_column(String(16), default="zh-CN")
    answer_detail: Mapped[str] = mapped_column(String(32), default="brief")
    show_citations: Mapped[bool] = mapped_column(Boolean, default=True)


class AnswerRun(Base):
    __tablename__ = "answer_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"),
        index=True,
    )
    user_message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"))
    assistant_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id")
    )
    mode: Mapped[str] = mapped_column(String(32))
    trace_id: Mapped[str | None] = mapped_column(String(128))
    index_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("index_versions.id")
    )
    retrieved_document_version_ids: Mapped[list[str]] = mapped_column(JSON)
    citations_snapshot: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    verification_result: Mapped[dict[str, object]] = mapped_column(JSON)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0)
    token_usage: Mapped[dict[str, int]] = mapped_column(JSON)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    answer_run_id: Mapped[str] = mapped_column(ForeignKey("answer_runs.id"))
    rating: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)
