# Persistence and Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add MySQL persistence, real PDF parsing, Qdrant indexing, remote model adapters, and ingestion/retrieval orchestration around the completed RAG core.

**Architecture:** Each adapter owns its models and protocols. Persistence and external integrations do not import each other. The ingestion and retrieval application services depend only on local `Protocol` interfaces and are tested with fakes. A later API plan will wire implementations through a composition root.

**Tech Stack:** Python 3.12, SQLAlchemy 2, Alembic, MySQL 8, PyMySQL, Qdrant, httpx, PyMuPDF, pytest.

**Spec:** `docs/superpowers/specs/2026-10-26-product-manual-rag-design.md`

## Global Constraints

- Implement exactly one module per task.
- Write failing tests before production code.
- Do not let modules import another module's internal files.
- External services are injected through `Protocol` interfaces.
- MySQL is the source of truth; Qdrant is rebuildable.
- Never store vectors in MySQL.
- Never use upload time as the real document version.
- Every ingestion step must be idempotent.
- Remote model calls must record provider, model, revision, latency, and token usage.
- Do not add FastAPI, Langfuse, or Next.js in this plan.
- Run focused tests, full tests, Ruff, and mypy before each commit.

## File Structure

```text
src/rag_app/
  settings.py
  persistence/
    __init__.py
    schema.py
    repositories.py
  pdf_parsing/
    __init__.py
    models.py
    pymupdf_parser.py
  qdrant_index/
    __init__.py
    models.py
    adapter.py
  remote_models/
    __init__.py
    models.py
    http_clients.py
  ingestion/
    __init__.py
    models.py
    service.py
  retrieval/
    models.py
    service.py
tests/
  persistence/
  pdf_parsing/
  qdrant_index/
  remote_models/
  ingestion/
  retrieval/
  integration/
```

---

### Task 0: Add Persistence and Adapter Dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Create: `src/rag_app/settings.py`
- Create: `tests/test_settings.py`

**Interfaces:**

- Produces `Settings` with:
  - `database_url: str`
  - `qdrant_url: str`
  - `qdrant_api_key: str | None`
  - `embedding_base_url: str`
  - `embedding_api_key: str`
  - `embedding_model: str`
  - `reranker_base_url: str`
  - `reranker_api_key: str`
  - `reranker_model: str`
  - `llm_base_url: str`
  - `llm_api_key: str`
  - `llm_model: str`

- [x] **Step 1: Add dependencies**

Run:

```powershell
uv add "sqlalchemy>=2.0,<3.0" "alembic>=1.14,<2.0" "pymysql>=1.1,<2.0" "qdrant-client>=1.12,<2.0" "httpx>=0.28,<1.0" "pymupdf>=1.25,<2.0" "pydantic-settings>=2.6,<3.0"
uv add --dev "pytest-asyncio>=0.24,<1.0"
```

- [x] **Step 2: Write the failing settings test**

Create `tests/test_settings.py`:

```python
from rag_app.settings import Settings


def test_settings_reads_prefixed_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv("RAG_DATABASE_URL", "mysql+pymysql://db/test")
    monkeypatch.setenv("RAG_QDRANT_URL", "http://localhost:6333")

    settings = Settings()

    assert settings.database_url == "mysql+pymysql://db/test"
    assert settings.qdrant_url == "http://localhost:6333"
```

- [x] **Step 3: Run and verify failure**

Run:

```powershell
uv run pytest tests/test_settings.py -v
```

Expected: module import failure.

- [x] **Step 4: Implement settings**

Create `src/rag_app/settings.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RAG_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = "mysql+pymysql://root:root@localhost:3306/rag"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    embedding_base_url: str = "https://example.invalid/v1"
    embedding_api_key: str = "change-me"
    embedding_model: str = "BAAI/bge-m3"
    reranker_base_url: str = "https://example.invalid/v1"
    reranker_api_key: str = "change-me"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    llm_base_url: str = "https://example.invalid/v1"
    llm_api_key: str = "change-me"
    llm_model: str = "change-me"
```

- [x] **Step 5: Update `.env.example`**

```dotenv
APP_ENV=development
LOG_LEVEL=INFO
RAG_DATABASE_URL=mysql+pymysql://root:root@localhost:3306/rag
RAG_QDRANT_URL=http://localhost:6333
RAG_QDRANT_API_KEY=
RAG_EMBEDDING_BASE_URL=https://example.invalid/v1
RAG_EMBEDDING_API_KEY=change-me
RAG_EMBEDDING_MODEL=BAAI/bge-m3
RAG_RERANKER_BASE_URL=https://example.invalid/v1
RAG_RERANKER_API_KEY=change-me
RAG_RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RAG_LLM_BASE_URL=https://example.invalid/v1
RAG_LLM_API_KEY=change-me
RAG_LLM_MODEL=change-me
```

- [x] **Step 6: Verify and commit**

```powershell
uv run pytest tests/test_settings.py -v
uv run pytest
uv run ruff check src/rag_app/settings.py tests/test_settings.py
uv run mypy src/rag_app/settings.py tests/test_settings.py
git add pyproject.toml uv.lock .env.example src/rag_app/settings.py tests/test_settings.py
git commit -m "chore: add backend adapter configuration"
```

---

### Task 1: SQLAlchemy Schema

**Files:**
- Create: `src/rag_app/persistence/__init__.py`
- Create: `src/rag_app/persistence/schema.py`
- Create: `tests/persistence/__init__.py`
- Create: `tests/persistence/test_schema.py`

**Interfaces:**

- Consumes: SQLAlchemy only.
- Produces:
  - `Base`
  - Table names listed in the spec.
  - `create_schema(engine)` for tests and local bootstrap.

- [x] **Step 1: Write failing schema tests**

Create `tests/persistence/test_schema.py`:

```python
from sqlalchemy import create_engine, inspect

from rag_app.persistence import create_schema


def test_schema_creates_source_of_truth_tables() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    names = set(inspect(engine).get_table_names())

    assert {
        "products",
        "product_aliases",
        "documents",
        "document_versions",
        "file_blobs",
        "product_document_bindings",
        "document_types",
        "document_version_types",
        "document_sections",
        "chunks",
        "index_versions",
        "document_indexes",
        "ingestion_batches",
        "ingestion_items",
        "conversations",
        "messages",
        "conversation_summaries",
        "visitor_preferences",
        "answer_runs",
        "feedback",
    } <= names


def test_document_version_has_hash_and_status() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    columns = {
        column["name"]
        for column in inspect(engine).get_columns("document_versions")
    }

    assert {"sha256", "version_label", "status", "received_at"} <= columns
```

- [x] **Step 2: Run and verify failure**

```powershell
uv run pytest tests/persistence/test_schema.py -v
```

Expected: import failure.

- [x] **Step 3: Implement SQLAlchemy schema**

Create `src/rag_app/persistence/schema.py`:

```python
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
    selected_product_ids: Mapped[list[str]] = mapped_column(JSON)
    detected_version_label: Mapped[str | None] = mapped_column(String(255))
    version_source: Mapped[str] = mapped_column(String(64))
    document_type_codes: Mapped[list[str]] = mapped_column(JSON)
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
```

Create `src/rag_app/persistence/__init__.py`:

```python
from rag_app.persistence.schema import Base, create_schema

__all__ = ["Base", "create_schema"]
```

- [x] **Step 4: Verify schema**

```powershell
uv run pytest tests/persistence/test_schema.py -v
uv run pytest
uv run ruff check src/rag_app/persistence tests/persistence
uv run mypy src/rag_app/persistence tests/persistence
```

- [x] **Step 5: Commit**

```powershell
git add src/rag_app/persistence tests/persistence
git commit -m "feat: add MySQL source-of-truth schema"
```

---

### Task 2: Document and Version Repositories

**Files:**
- Create: `src/rag_app/persistence/repositories.py`
- Modify: `src/rag_app/persistence/__init__.py`
- Create: `tests/persistence/test_repositories.py`

**Interfaces:**

- Consumes: `persistence.schema`, SQLAlchemy `Session`.
- Produces:
  - `DocumentRepository.find_by_sha256(sha256) -> DocumentVersionRecord | None`
  - `DocumentRepository.find_by_normalized_name(product_id, name) -> ...`
  - `DocumentRepository.add_document_version(...) -> str`
  - `DocumentRepository.activate_version(product_id, document_id, version_id)`
  - `DocumentRepository.active_version_ids(product_id) -> tuple[str, ...]`

- [x] **Step 1: Write failing repository tests**

Create `tests/persistence/test_repositories.py` with SQLite in-memory setup:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rag_app.persistence import create_schema
from rag_app.persistence.repositories import DocumentRepository
from rag_app.persistence.schema import Document, FileBlob, Product


def test_active_version_is_product_specific() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Product(
                    id="p1",
                    display_name="P1",
                    category="tablet",
                    brand="brand",
                ),
                Document(
                    id="d1",
                    canonical_name="Guide",
                    manufacturer="brand",
                ),
                FileBlob(
                    id=1,
                    sha256="a" * 64,
                    storage_uri="storage/a.pdf",
                    size_bytes=10,
                    original_filename="guide.pdf",
                    content_type="application/pdf",
                ),
            ]
        )
        session.commit()
        repo = DocumentRepository(session)
        version_id = repo.add_document_version(
            document_id="d1",
            file_blob_id=1,
            version_label="2026.1",
            version_key="d1:2026.1",
            version_source="cover",
            version_confidence="high",
            sha256="a" * 64,
            received_at="2026-10-26T00:00:00+00:00",
            status="validated",
        )
        repo.bind_product("p1", "d1")
        repo.activate_version("p1", "d1", version_id)

        assert repo.active_version_ids("p1") == (version_id,)
```

- [x] **Step 2: Run and verify failure**

```powershell
uv run pytest tests/persistence/test_repositories.py -v
```

Expected: import failure.

- [x] **Step 3: Implement repository**

Implement `DocumentRepository` using SQLAlchemy `session.get`, `select`, and a `ProductDocumentBinding` update. Use a small frozen `DocumentVersionRecord` dataclass for output. Ensure `active_version_ids` only returns `active` versions.

- [x] **Step 4: Verify and commit**

```powershell
uv run pytest tests/persistence/test_repositories.py -v
uv run pytest
uv run ruff check src/rag_app/persistence tests/persistence
uv run mypy src/rag_app/persistence tests/persistence
git add src/rag_app/persistence tests/persistence
git commit -m "feat: add document repositories"
```

---

### Task 3: PyMuPDF Parser Adapter

**Files:**
- Create: `src/rag_app/pdf_parsing/__init__.py`
- Create: `src/rag_app/pdf_parsing/models.py`
- Create: `src/rag_app/pdf_parsing/pymupdf_parser.py`
- Create: `tests/pdf_parsing/__init__.py`
- Create: `tests/pdf_parsing/test_pymupdf_parser.py`

**Interfaces:**

- Produces:
  - `ParsedPage(page: int, text: str, text_char_count: int)`
  - `PdfParseResult(pages: tuple[ParsedPage, ...])`
  - `PdfParser` protocol
  - `PyMuPdfParser.parse(path: Path) -> PdfParseResult`

- [x] **Step 1: Write failing tests**

Create a tiny PDF with PyMuPDF inside the test, then parse it:

```python
import fitz

from rag_app.pdf_parsing import PyMuPdfParser


def test_parser_extracts_page_text(tmp_path) -> None:
    path = tmp_path / "manual.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Safety warning")
    document.save(path)
    document.close()

    result = PyMuPdfParser().parse(path)

    assert len(result.pages) == 1
    assert "Safety warning" in result.pages[0].text
    assert result.pages[0].text_char_count > 0
```

- [x] **Step 2: Verify failure**

```powershell
uv run pytest tests/pdf_parsing/test_pymupdf_parser.py -v
```

- [x] **Step 3: Implement parser**

Create immutable models and `PyMuPdfParser` using `fitz.open(path)`. Reject non-PDF suffixes and pages with zero extracted characters by recording `text_char_count=0`; do not invent text.

- [x] **Step 4: Verify and commit**

```powershell
uv run pytest tests/pdf_parsing/test_pymupdf_parser.py -v
uv run pytest
uv run ruff check src/rag_app/pdf_parsing tests/pdf_parsing
uv run mypy src/rag_app/pdf_parsing tests/pdf_parsing
git add src/rag_app/pdf_parsing tests/pdf_parsing
git commit -m "feat: add PyMuPDF parser adapter"
```

---

### Task 4: Qdrant Index Adapter

**Files:**
- Create: `src/rag_app/qdrant_index/__init__.py`
- Create: `src/rag_app/qdrant_index/models.py`
- Create: `src/rag_app/qdrant_index/adapter.py`
- Create: `tests/qdrant_index/__init__.py`
- Create: `tests/qdrant_index/test_adapter.py`

**Interfaces:**

- Produces:
  - `IndexPoint(id, dense, sparse, payload)`
  - `IndexFilter(product_id, document_version_ids, index_version_id)`
  - `QdrantIndex.ensure_collection(dimension: int) -> None`
  - `QdrantIndex.upsert(points: Sequence[IndexPoint]) -> None`
  - `QdrantIndex.search_dense(vector, filters, limit) -> tuple[IndexHit, ...]`
  - `QdrantIndex.search_sparse(vector, filters, limit) -> tuple[IndexHit, ...]`

- [x] **Step 1: Write failing in-memory tests**

Use `QdrantClient(":memory:")` and assert:

- Collection creation succeeds.
- A point can be upserted.
- Dense search returns the point.
- Product and index-version filters exclude unrelated points.
- Re-upserting the same ID does not duplicate the result.

- [x] **Step 2: Verify failure and implement**

Run the focused test, then implement the adapter using named vectors `dense` and `sparse`, payload indexes for `product_id`, `document_version_id`, and `index_version_id`, and Qdrant query filters.

- [x] **Step 3: Verify and commit**

```powershell
uv run pytest tests/qdrant_index/test_adapter.py -v
uv run pytest
uv run ruff check src/rag_app/qdrant_index tests/qdrant_index
uv run mypy src/rag_app/qdrant_index tests/qdrant_index
git add src/rag_app/qdrant_index tests/qdrant_index
git commit -m "feat: add Qdrant index adapter"
```

---

### Task 5: Remote Model Clients

**Files:**
- Create: `src/rag_app/remote_models/__init__.py`
- Create: `src/rag_app/remote_models/models.py`
- Create: `src/rag_app/remote_models/http_clients.py`
- Create: `tests/remote_models/__init__.py`
- Create: `tests/remote_models/test_http_clients.py`

**Interfaces:**

- Produces:
  - `DenseEmbedding(vector: tuple[float, ...], model: str)`
  - `RerankScore(index: int, score: float)`
  - `Generation(text: str, prompt_tokens: int, completion_tokens: int)`
  - `HttpEmbeddingClient.embed(texts, model) -> tuple[DenseEmbedding, ...]`
  - `HttpRerankerClient.rerank(query, documents, model) -> tuple[RerankScore, ...]`
  - `HttpLlmClient.generate(prompt, model) -> Generation`

- [x] **Step 1: Write httpx MockTransport tests**

Test exact request URLs, authorization header, JSON body, response parsing, timeouts, and non-2xx mapping to a local `ProviderError`.

- [x] **Step 2: Verify failure and implement**

Use a shared injected `httpx.Client`, no global client, no API key logging, and configurable timeouts. Do not couple this module to `answering` or `persistence`.

- [x] **Step 3: Verify and commit**

```powershell
uv run pytest tests/remote_models/test_http_clients.py -v
uv run pytest
uv run ruff check src/rag_app/remote_models tests/remote_models
uv run mypy src/rag_app/remote_models tests/remote_models
git add src/rag_app/remote_models tests/remote_models
git commit -m "feat: add remote model clients"
```

---

### Task 6: Ingestion Application Service

**Files:**
- Create: `src/rag_app/ingestion/__init__.py`
- Create: `src/rag_app/ingestion/models.py`
- Create: `src/rag_app/ingestion/service.py`
- Create: `tests/ingestion/__init__.py`
- Create: `tests/ingestion/test_ingestion.py`

**Interfaces:**

- Consumes only local `Protocol` definitions:
  - `DocumentStore`
  - `Parser`
  - `Chunker`
  - `Embedder`
  - `IndexWriter`
- Produces `IngestionService.ingest(command: IngestDocument) -> IngestionResult`.

- [x] **Step 1: Write fake-driven tests**

Cover:

- Duplicate SHA returns the existing version without re-parsing.
- New version starts as validated but not active.
- Activation happens only after index success.
- Index failure leaves the previous active version unchanged.
- Re-running the same command is idempotent.

- [x] **Step 2: Verify failure and implement**

Implement a sequential state machine with explicit stages. Do not import the persistence, PDF parsing, Qdrant, or remote model packages. Those adapters are injected by a later composition root.

- [x] **Step 3: Verify and commit**

```powershell
uv run pytest tests/ingestion/test_ingestion.py -v
uv run pytest
uv run ruff check src/rag_app/ingestion tests/ingestion
uv run mypy src/rag_app/ingestion tests/ingestion
git add src/rag_app/ingestion tests/ingestion
git commit -m "feat: add ingestion orchestration"
```

---

### Task 7: Retrieval Application Service

**Files:**
- Create: `src/rag_app/retrieval/service.py`
- Modify: `src/rag_app/retrieval/__init__.py`
- Create: `tests/retrieval/test_service.py`

**Interfaces:**

- Consumes local protocols:
  - `DenseSearch`
  - `SparseSearch`
  - `Reranker`
- Produces:
  - `HybridRetrievalService.search(question, product_id, document_version_ids, index_version_id) -> tuple[EvidenceHit, ...]`

- [x] **Step 1: Write fake-driven tests**

Cover:

- Dense and sparse results are fused by RRF.
- Final output is limited to 6.
- Duplicate Chunk IDs are removed.
- Filters are passed unchanged to both searches.
- Reranker receives at most 20 candidates.

- [x] **Step 2: Verify failure and implement**

Compose the existing `reciprocal_rank_fusion` function rather than duplicating RRF. Do not import Qdrant, remote model clients, or API code.

- [x] **Step 3: Verify and commit**

```powershell
uv run pytest tests/retrieval/test_service.py -v
uv run pytest
uv run ruff check src/rag_app/retrieval tests/retrieval
uv run mypy src/rag_app/retrieval tests/retrieval
git add src/rag_app/retrieval tests/retrieval
git commit -m "feat: add hybrid retrieval orchestration"
```

---

## Plan Self-Review

- Spec coverage for this phase: MySQL schema, document versions, repository primitives, PDF extraction, Qdrant indexing, remote provider calls, ingestion orchestration, and hybrid retrieval orchestration.
- Deferred: Alembic migration CLI integration, FastAPI/SSE, admin authentication, Langfuse, harness, Next.js, Docker Compose, and end-to-end product runs.
- Module boundaries: persistence, PDF parsing, Qdrant, remote models, ingestion, and retrieval do not import each other's internals.
- Type consistency: `IndexPoint`, `IndexFilter`, `DenseEmbedding`, `RerankScore`, and `EvidenceHit` are defined in their owning modules and used through public protocols.
- Placeholder scan: no `TBD`, `TODO`, or unspecified steps. The plan intentionally uses test-driven details for repository and adapter payloads rather than repeating the already approved design.
