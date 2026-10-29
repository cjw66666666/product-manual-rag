# Core RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build the framework-independent core modules for the product manual RAG system, with one module committed and verified at a time.

**Architecture:** Each business capability is a separate Python package with its own models and ports. A module may expose public types and protocols, but no module imports another module's internal files. Cross-module orchestration is added later in a composition root. This plan uses pure Python and fakes, so no database, vector store, remote model, or web framework is required.

**Tech Stack:** Python 3.12, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-10-26-product-manual-rag-design.md`

## Global Constraints

- Implement exactly one module in each task.
- Write the failing test before implementation code.
- Do not import one module's internal files from another module.
- Public cross-module use is allowed only through exported dataclasses and `Protocol` interfaces.
- Do not add LangGraph.
- Do not add MySQL, Qdrant, FastAPI, Langfuse, Next.js, or remote provider code in this plan.
- User-facing safety questions must use `AnswerMode.MANUAL_GROUNDED`; if evidence is insufficient, return `AnswerMode.REFUSED`.
- The answer loop stops after at most two attempts.
- Every task ends with tests, lint, type checking, and a focused commit.
- Keep `.git`, `docs/`, `.gitignore`, `.gitattributes`, `.python-version`, and `.idea/`.
- Remove the old application code before creating the new module structure.

## File Structure

```text
src/rag_app/
  __init__.py
  catalog/
    __init__.py
    models.py
    resolver.py
  document_versions/
    __init__.py
    models.py
    policy.py
  chunking/
    __init__.py
    models.py
    chunker.py
  retrieval/
    __init__.py
    models.py
    fusion.py
  answering/
    __init__.py
    models.py
    policy.py
    loop.py
  verification/
    __init__.py
    models.py
    verifier.py
  conversations/
    __init__.py
    models.py
    service.py
tests/
  catalog/
  document_versions/
  chunking/
  retrieval/
  answering/
  verification/
  conversations/
  integration/
```

Subsequent implementation plans:

1. Persistence, providers, ingestion, indexing, worker, and API.
2. Evaluation harness and Langfuse integration.
3. Next.js frontend, Docker Compose, end-to-end tests, and delivery.

---

### Task 0: Rebuild the Project Skeleton

**Files:**
- Delete: `src/`
- Delete: `tests/`
- Delete: `.venv/`
- Delete: `.pytest_cache/`
- Delete: `README.md`
- Delete: `pyproject.toml`
- Delete: `uv.lock`
- Delete: `.env.example`
- Create: `src/rag_app/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_package.py`
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `.env.example`

**Interfaces:**
- Consumes: none.
- Produces: installable `rag_app` package, pytest, Ruff, and mypy commands.

- [x] **Step 1: Verify and delete only the old application artifacts**

Run:

```powershell
$root = (Resolve-Path 'D:\1\项目汇总\rag重构').Path
$targets = @('src', 'tests', '.venv', '.pytest_cache') | ForEach-Object {
    Join-Path $root $_
}
$targets | ForEach-Object {
    $resolved = [System.IO.Path]::GetFullPath($_)
    if (-not $resolved.StartsWith($root + [System.IO.Path]::DirectorySeparatorChar)) {
        throw "Refusing to delete outside project: $resolved"
    }
}
$targets | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object {
    Remove-Item -LiteralPath $_ -Recurse -Force
}
Remove-Item -LiteralPath (Join-Path $root 'README.md') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $root 'pyproject.toml') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $root 'uv.lock') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $root '.env.example') -Force -ErrorAction SilentlyContinue
```

Expected: only `.git`, `docs`, tool metadata, and ignored IDE files remain.

- [x] **Step 2: Create package directories**

Run:

```powershell
New-Item -ItemType Directory -Force 'src\rag_app','tests','tests\integration' | Out-Null
New-Item -ItemType File -Force 'src\rag_app\__init__.py','tests\__init__.py' | Out-Null
```

- [x] **Step 3: Write the project configuration and smoke test**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "rag-refactor"
version = "0.1.0"
description = "Product manual RAG with grounded citations."
readme = "README.md"
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
dev = [
  "mypy>=1.13,<2.0",
  "pytest>=8.3,<9.0",
  "pytest-cov>=6.0,<7.0",
  "ruff>=0.9,<1.0",
]

[tool.hatch.build.targets.wheel]
packages = ["src/rag_app"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
addopts = "-q"

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true
files = ["src", "tests"]
```

Create `README.md`:

```markdown
# Product Manual RAG

Grounded product usage and safety question answering with citations.

Implementation is being rebuilt module by module from the design documents in
`docs/superpowers/specs/`.
```

Create `.env.example`:

```dotenv
APP_ENV=development
LOG_LEVEL=INFO
```

Create `tests/test_package.py`:

```python
import rag_app


def test_package_imports() -> None:
    assert rag_app.__name__ == "rag_app"
```

- [x] **Step 4: Install and verify tooling**

Run:

```powershell
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy .
```

Expected:

- pytest reports one passing test.
- Ruff exits 0.
- mypy exits 0.

- [x] **Step 5: Commit**

Run:

```powershell
git add pyproject.toml README.md .env.example uv.lock src/rag_app/__init__.py tests/__init__.py tests/test_package.py
git commit -m "chore: rebuild project skeleton"
```

---

### Task 1: Product Catalog and Alias Resolution

**Files:**
- Create: `src/rag_app/catalog/__init__.py`
- Create: `src/rag_app/catalog/models.py`
- Create: `src/rag_app/catalog/resolver.py`
- Create: `tests/catalog/__init__.py`
- Create: `tests/catalog/test_catalog.py`

**Interfaces:**

- Consumes: Python standard library only.
- Produces:
  - `ProductCategory(StrEnum)`
  - `Product(id: str, display_name: str, category: ProductCategory, aliases: tuple[str, ...])`
  - `MatchStatus(StrEnum)` with `RESOLVED`, `AMBIGUOUS`, `NOT_FOUND`
  - `ProductMatch(status: MatchStatus, products: tuple[Product, ...])`
  - `ProductCatalog(products: Sequence[Product])`
  - `ProductCatalog.resolve(text: str) -> ProductMatch`

- [x] **Step 1: Write the failing tests**

Create `tests/catalog/test_catalog.py`:

```python
import pytest

from rag_app.catalog import (
    MatchStatus,
    Product,
    ProductCatalog,
    ProductCategory,
)


def make_catalog() -> ProductCatalog:
    return ProductCatalog(
        (
            Product(
                id="huawei_c7",
                display_name="华为平板 C7",
                category=ProductCategory.TABLET,
                aliases=("C7", "DBY-W09", "华为平板C7"),
            ),
            Product(
                id="huawei_c5e",
                display_name="华为擎云 C5e",
                category=ProductCategory.TABLET,
                aliases=("C5e", "BZI-W00"),
            ),
        )
    )


def test_resolve_unique_product_alias() -> None:
    match = make_catalog().resolve("我的 DBY-W09 屏幕怎么清洁？")

    assert match.status is MatchStatus.RESOLVED
    assert [product.id for product in match.products] == ["huawei_c7"]


def test_resolve_is_case_insensitive_and_collapses_spaces() -> None:
    match = make_catalog().resolve("c7  支持蓝牙吗")

    assert match.status is MatchStatus.RESOLVED
    assert match.products[0].id == "huawei_c7"


def test_resolve_does_not_treat_c5e_as_c5() -> None:
    match = make_catalog().resolve("C5e 怎么连接键盘")

    assert match.status is MatchStatus.RESOLVED
    assert match.products[0].id == "huawei_c5e"


def test_resolve_returns_not_found_without_alias() -> None:
    match = make_catalog().resolve("这台设备怎么开机？")

    assert match.status is MatchStatus.NOT_FOUND
    assert match.products == ()


def test_duplicate_normalized_alias_is_rejected() -> None:
    with pytest.raises(ValueError, match="alias"):
        ProductCatalog(
            (
                Product("one", "One", ProductCategory.TABLET, ("Same",)),
                Product("two", "Two", ProductCategory.TABLET, ("same",)),
            )
        )
```

- [x] **Step 2: Run tests and verify failure**

Run:

```powershell
uv run pytest tests/catalog/test_catalog.py -v
```

Expected: import failure because `rag_app.catalog` does not exist.

- [x] **Step 3: Write the catalog models and resolver**

Create `src/rag_app/catalog/models.py`:

```python
from dataclasses import dataclass
from enum import StrEnum


class ProductCategory(StrEnum):
    TABLET = "tablet"
    LAPTOP = "laptop"
    MONITOR = "monitor"


@dataclass(frozen=True, slots=True)
class Product:
    id: str
    display_name: str
    category: ProductCategory
    aliases: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("product id cannot be blank")
        if not self.display_name.strip():
            raise ValueError("display name cannot be blank")
        if not self.aliases:
            raise ValueError("at least one alias is required")


class MatchStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class ProductMatch:
    status: MatchStatus
    products: tuple[Product, ...]
```

Create `src/rag_app/catalog/resolver.py`:

```python
import re
import unicodedata
from collections.abc import Sequence

from rag_app.catalog.models import MatchStatus, Product, ProductMatch


def normalize_alias(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = normalized.replace("-", "").replace("_", "")
    return re.sub(r"\s+", "", normalized)


class ProductCatalog:
    def __init__(self, products: Sequence[Product]) -> None:
        self._products = tuple(products)
        self._aliases: dict[str, tuple[Product, ...]] = {}

        for product in self._products:
            for alias in (*product.aliases, product.display_name):
                normalized = normalize_alias(alias)
                existing = self._aliases.get(normalized, ())
                if product not in existing:
                    self._aliases[normalized] = (*existing, product)

        duplicates = [
            aliases
            for aliases in self._aliases.values()
            if len({product.id for product in aliases}) > 1
        ]
        if duplicates:
            raise ValueError("alias maps to more than one product")

        self._ordered_aliases = tuple(
            sorted(self._aliases, key=len, reverse=True)
        )

    def resolve(self, text: str) -> ProductMatch:
        normalized_text = normalize_alias(text)
        matched: dict[str, Product] = {}

        for alias in self._ordered_aliases:
            if alias in normalized_text:
                for product in self._aliases[alias]:
                    matched[product.id] = product

        products = tuple(matched.values())
        if len(products) == 1:
            return ProductMatch(MatchStatus.RESOLVED, products)
        if len(products) > 1:
            return ProductMatch(MatchStatus.AMBIGUOUS, products)
        return ProductMatch(MatchStatus.NOT_FOUND, ())
```

Create `src/rag_app/catalog/__init__.py`:

```python
from rag_app.catalog.models import (
    MatchStatus,
    Product,
    ProductCategory,
    ProductMatch,
)
from rag_app.catalog.resolver import ProductCatalog, normalize_alias

__all__ = [
    "MatchStatus",
    "Product",
    "ProductCatalog",
    "ProductCategory",
    "ProductMatch",
    "normalize_alias",
]
```

- [x] **Step 4: Run focused and global checks**

Run:

```powershell
uv run pytest tests/catalog/test_catalog.py -v
uv run pytest
uv run ruff check src/rag_app/catalog tests/catalog
uv run mypy src/rag_app/catalog tests/catalog
```

Expected: all commands exit 0.

- [x] **Step 5: Commit**

```powershell
git add src/rag_app/catalog tests/catalog
git commit -m "feat: add product catalog resolution"
```

---

### Task 2: Document Version and Upload Conflict Policy

**Files:**
- Create: `src/rag_app/document_versions/__init__.py`
- Create: `src/rag_app/document_versions/models.py`
- Create: `src/rag_app/document_versions/policy.py`
- Create: `tests/document_versions/__init__.py`
- Create: `tests/document_versions/test_versions.py`

**Interfaces:**

- Consumes: standard library only.
- Produces:
  - `VersionStatus(StrEnum)`
  - `MetadataConfidence(StrEnum)`
  - `UploadDecision(StrEnum)`
  - `ExistingUpload(sha256: str, normalized_name: str)`
  - `UploadProbe(sha256: str, normalized_name: str)`
  - `classify_upload(probe, existing) -> UploadDecision`
  - `classify_metadata_confidence(has_product: bool, has_version: bool) -> MetadataConfidence`
  - `next_status(current, target) -> VersionStatus`
  - `provisional_version_key(received_at: datetime, sequence: int) -> str`

- [x] **Step 1: Write failing tests**

Create `tests/document_versions/test_versions.py`:

```python
from datetime import UTC, datetime

import pytest

from rag_app.document_versions import (
    ExistingUpload,
    MetadataConfidence,
    UploadDecision,
    UploadProbe,
    VersionStatus,
    classify_metadata_confidence,
    classify_upload,
    next_status,
    provisional_version_key,
)


def test_exact_hash_is_duplicate_even_when_name_differs() -> None:
    decision = classify_upload(
        UploadProbe("abc", "new-name.pdf"),
        (ExistingUpload("abc", "old-name.pdf"),),
    )

    assert decision is UploadDecision.DUPLICATE_CONTENT


def test_same_name_different_hash_is_conflict() -> None:
    decision = classify_upload(
        UploadProbe("new", "guide.pdf"),
        (ExistingUpload("old", "guide.pdf"),),
    )

    assert decision is UploadDecision.SAME_NAME_CONFLICT


def test_new_hash_and_name_is_new_document() -> None:
    decision = classify_upload(
        UploadProbe("new", "new.pdf"),
        (ExistingUpload("old", "old.pdf"),),
    )

    assert decision is UploadDecision.NEW_DOCUMENT


@pytest.mark.parametrize(
    ("has_product", "has_version", "expected"),
    [
        (True, True, MetadataConfidence.HIGH),
        (True, False, MetadataConfidence.MEDIUM),
        (False, True, MetadataConfidence.LOW),
        (False, False, MetadataConfidence.LOW),
    ],
)
def test_metadata_confidence(
    has_product: bool,
    has_version: bool,
    expected: MetadataConfidence,
) -> None:
    assert classify_metadata_confidence(has_product, has_version) is expected


def test_version_state_machine_allows_validation_and_activation() -> None:
    processed = next_status(VersionStatus.DRAFT, VersionStatus.PROCESSING)
    validated = next_status(processed, VersionStatus.VALIDATED)
    active = next_status(validated, VersionStatus.ACTIVE)

    assert active is VersionStatus.ACTIVE


def test_version_state_machine_rejects_skipping_validation() -> None:
    with pytest.raises(ValueError, match="invalid version transition"):
        next_status(VersionStatus.DRAFT, VersionStatus.ACTIVE)


def test_provisional_version_key_uses_received_time() -> None:
    key = provisional_version_key(
        datetime(2026, 10, 26, 9, 30, tzinfo=UTC),
        3,
    )

    assert key == "received-20261026T093000Z-003"
```

- [x] **Step 2: Run tests and verify failure**

```powershell
uv run pytest tests/document_versions/test_versions.py -v
```

Expected: import failure because the package does not exist.

- [x] **Step 3: Implement models and policy**

Create `src/rag_app/document_versions/models.py`:

```python
from dataclasses import dataclass
from enum import StrEnum


class VersionStatus(StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    VALIDATED = "validated"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class MetadataConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class UploadDecision(StrEnum):
    DUPLICATE_CONTENT = "duplicate_content"
    SAME_NAME_CONFLICT = "same_name_conflict"
    NEW_DOCUMENT = "new_document"


@dataclass(frozen=True, slots=True)
class ExistingUpload:
    sha256: str
    normalized_name: str


@dataclass(frozen=True, slots=True)
class UploadProbe:
    sha256: str
    normalized_name: str
```

Create `src/rag_app/document_versions/policy.py`:

```python
from collections.abc import Sequence
from datetime import datetime

from rag_app.document_versions.models import (
    ExistingUpload,
    MetadataConfidence,
    UploadDecision,
    UploadProbe,
    VersionStatus,
)


_ALLOWED_TRANSITIONS: dict[VersionStatus, frozenset[VersionStatus]] = {
    VersionStatus.DRAFT: frozenset({VersionStatus.PROCESSING}),
    VersionStatus.PROCESSING: frozenset(
        {VersionStatus.VALIDATED, VersionStatus.FAILED}
    ),
    VersionStatus.VALIDATED: frozenset({VersionStatus.ACTIVE}),
    VersionStatus.ACTIVE: frozenset({VersionStatus.SUPERSEDED}),
    VersionStatus.SUPERSEDED: frozenset(),
    VersionStatus.FAILED: frozenset({VersionStatus.PROCESSING}),
}


def classify_upload(
    probe: UploadProbe,
    existing: Sequence[ExistingUpload],
) -> UploadDecision:
    if any(item.sha256 == probe.sha256 for item in existing):
        return UploadDecision.DUPLICATE_CONTENT
    if any(
        item.normalized_name == probe.normalized_name for item in existing
    ):
        return UploadDecision.SAME_NAME_CONFLICT
    return UploadDecision.NEW_DOCUMENT


def classify_metadata_confidence(
    has_product: bool,
    has_version: bool,
) -> MetadataConfidence:
    if has_product and has_version:
        return MetadataConfidence.HIGH
    if has_product:
        return MetadataConfidence.MEDIUM
    return MetadataConfidence.LOW


def next_status(
    current: VersionStatus,
    target: VersionStatus,
) -> VersionStatus:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(
            f"invalid version transition: {current.value} -> {target.value}"
        )
    return target


def provisional_version_key(received_at: datetime, sequence: int) -> str:
    if sequence < 1:
        raise ValueError("sequence must be positive")
    return f"received-{received_at:%Y%m%dT%H%M%SZ}-{sequence:03d}"
```

Create `src/rag_app/document_versions/__init__.py`:

```python
from rag_app.document_versions.models import (
    ExistingUpload,
    MetadataConfidence,
    UploadDecision,
    UploadProbe,
    VersionStatus,
)
from rag_app.document_versions.policy import (
    classify_metadata_confidence,
    classify_upload,
    next_status,
    provisional_version_key,
)

__all__ = [
    "ExistingUpload",
    "MetadataConfidence",
    "UploadDecision",
    "UploadProbe",
    "VersionStatus",
    "classify_metadata_confidence",
    "classify_upload",
    "next_status",
    "provisional_version_key",
]
```

- [x] **Step 4: Run checks**

```powershell
uv run pytest tests/document_versions/test_versions.py -v
uv run pytest
uv run ruff check src/rag_app/document_versions tests/document_versions
uv run mypy src/rag_app/document_versions tests/document_versions
```

Expected: all commands exit 0.

- [x] **Step 5: Commit**

```powershell
git add src/rag_app/document_versions tests/document_versions
git commit -m "feat: add document version policy"
```

---

### Task 3: Structure-Aware Chunking

**Files:**
- Create: `src/rag_app/chunking/__init__.py`
- Create: `src/rag_app/chunking/models.py`
- Create: `src/rag_app/chunking/chunker.py`
- Create: `tests/chunking/__init__.py`
- Create: `tests/chunking/test_chunker.py`

**Interfaces:**

- Consumes: standard library only.
- Produces:
  - `BlockType(StrEnum)` with `HEADING`, `PARAGRAPH`, `LIST`, `TABLE`, `WARNING`
  - `ParsedBlock(type: BlockType, text: str, page: int)`
  - `ChunkDraft(content: str, page_start: int, page_end: int, section_path: tuple[str, ...], section_types: tuple[str, ...])`
  - `chunk_blocks(blocks: Sequence[ParsedBlock], target_chars: int = 450, max_chars: int = 800) -> tuple[ChunkDraft, ...]`

- [x] **Step 1: Write failing tests**

Create `tests/chunking/test_chunker.py`:

```python
from rag_app.chunking import (
    BlockType,
    ParsedBlock,
    chunk_blocks,
)


def test_heading_is_prefixed_to_chunk() -> None:
    chunks = chunk_blocks(
        (
            ParsedBlock(BlockType.HEADING, "电源", 2),
            ParsedBlock(BlockType.PARAGRAPH, "使用指定电源适配器。", 2),
        )
    )

    assert chunks[0].content == "电源\n使用指定电源适配器。"
    assert chunks[0].section_path == ("电源",)


def test_warning_never_merges_with_another_section() -> None:
    chunks = chunk_blocks(
        (
            ParsedBlock(BlockType.HEADING, "安全", 3),
            ParsedBlock(BlockType.WARNING, "请勿拆机。", 3),
            ParsedBlock(BlockType.HEADING, "使用", 4),
            ParsedBlock(BlockType.PARAGRAPH, "按压电源键开机。", 4),
        )
    )

    assert [chunk.content for chunk in chunks] == [
        "安全\n请勿拆机。",
        "使用\n按压电源键开机。",
    ]


def test_long_paragraph_is_split_without_exceeding_max() -> None:
    chunks = chunk_blocks(
        (
            ParsedBlock(BlockType.HEADING, "说明", 1),
            ParsedBlock(BlockType.PARAGRAPH, "甲" * 1000, 1),
        ),
        target_chars=300,
        max_chars=400,
    )

    assert len(chunks) >= 3
    assert all(len(chunk.content) <= 400 for chunk in chunks)
    assert all(chunk.section_path == ("说明",) for chunk in chunks)
    assert all(chunk.content.startswith("说明\n") for chunk in chunks)


def test_long_paragraph_has_overlap_between_adjacent_chunks() -> None:
    chunks = chunk_blocks(
        (
            ParsedBlock(BlockType.HEADING, "说明", 1),
            ParsedBlock(BlockType.PARAGRAPH, "甲" * 900, 1),
        ),
        target_chars=300,
        max_chars=400,
    )

    first_body = chunks[0].content.removeprefix("说明\n")
    second_body = chunks[1].content.removeprefix("说明\n")
    assert first_body[-100:] == second_body[:100]


def test_list_items_remain_together_when_possible() -> None:
    chunks = chunk_blocks(
        (
            ParsedBlock(BlockType.HEADING, "启动", 1),
            ParsedBlock(BlockType.LIST, "1. 接电源\n2. 按电源键\n3. 等待启动", 1),
        )
    )

    assert chunks[0].content.endswith("1. 接电源\n2. 按电源键\n3. 等待启动")
```

- [x] **Step 2: Run tests and verify failure**

```powershell
uv run pytest tests/chunking/test_chunker.py -v
```

Expected: import failure.

- [x] **Step 3: Implement chunking**

Create `src/rag_app/chunking/models.py`:

```python
from dataclasses import dataclass
from enum import StrEnum


class BlockType(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ParsedBlock:
    type: BlockType
    text: str
    page: int

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("block text cannot be blank")
        if self.page < 1:
            raise ValueError("page must be positive")


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    content: str
    page_start: int
    page_end: int
    section_path: tuple[str, ...]
    section_types: tuple[str, ...]
```

Create `src/rag_app/chunking/chunker.py`:

```python
from collections.abc import Sequence

from rag_app.chunking.models import BlockType, ChunkDraft, ParsedBlock


def _section_types(path: tuple[str, ...]) -> tuple[str, ...]:
    safety_words = {"安全", "警告", "注意", "safety", "warning"}
    if any(word in heading.casefold() for heading in path for word in safety_words):
        return ("safety",)
    return ("usage",)


def _split_long_text(
    text: str,
    max_chars: int,
    overlap_chars: int = 100,
) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        parts.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap_chars
    return parts


def chunk_blocks(
    blocks: Sequence[ParsedBlock],
    target_chars: int = 450,
    max_chars: int = 800,
) -> tuple[ChunkDraft, ...]:
    if target_chars < 1 or max_chars < target_chars:
        raise ValueError("invalid chunk size configuration")

    section_path: tuple[str, ...] = ()
    chunks: list[ChunkDraft] = []
    buffer: list[str] = []
    page_start = 1
    page_end = 1

    def flush() -> None:
        nonlocal buffer, page_start, page_end
        if not buffer:
            return
        prefix = "\n".join(section_path)
        body = "\n".join(buffer).strip()
        body_limit = max_chars - len(prefix) - 1 if prefix else max_chars
        if body_limit < 1:
            raise ValueError("section path is too long for max_chars")

        current_page = page_start
        for part in _split_long_text(body, body_limit):
            content = f"{prefix}\n{part}" if prefix else part
            chunks.append(
                ChunkDraft(
                    content=part,
                    page_start=current_page,
                    page_end=page_end,
                    section_path=section_path,
                    section_types=_section_types(section_path),
                )
            )
        buffer = []

    for block in blocks:
        if block.type is BlockType.HEADING:
            flush()
            section_path = (block.text.strip(),)
            page_start = block.page
            page_end = block.page
            continue

        protected = block.type in {BlockType.WARNING, BlockType.LIST, BlockType.TABLE}
        projected = sum(len(item) for item in buffer) + len(block.text)
        if buffer and projected > target_chars:
            flush()

        if not buffer:
            page_start = block.page
        page_end = block.page
        buffer.append(block.text.strip())

        if protected and block.type is BlockType.WARNING:
            flush()

    flush()
    return tuple(chunks)
```

Create `src/rag_app/chunking/__init__.py`:

```python
from rag_app.chunking.chunker import chunk_blocks
from rag_app.chunking.models import BlockType, ChunkDraft, ParsedBlock

__all__ = ["BlockType", "ChunkDraft", "ParsedBlock", "chunk_blocks"]
```

- [x] **Step 4: Run checks**

```powershell
uv run pytest tests/chunking/test_chunker.py -v
uv run pytest
uv run ruff check src/rag_app/chunking tests/chunking
uv run mypy src/rag_app/chunking tests/chunking
```

Expected: all commands exit 0.

- [x] **Step 5: Commit**

```powershell
git add src/rag_app/chunking tests/chunking
git commit -m "feat: add structure-aware chunking"
```

---

### Task 4: Reciprocal Rank Fusion

**Files:**
- Create: `src/rag_app/retrieval/__init__.py`
- Create: `src/rag_app/retrieval/models.py`
- Create: `src/rag_app/retrieval/fusion.py`
- Create: `tests/retrieval/__init__.py`
- Create: `tests/retrieval/test_fusion.py`

**Interfaces:**

- Consumes: standard library only.
- Produces:
  - `RankedCandidate(chunk_id: str, rank: int)`
  - `FusedCandidate(chunk_id: str, score: float)`
  - `reciprocal_rank_fusion(dense, sparse, limit=20, rrf_k=60) -> tuple[FusedCandidate, ...]`

- [x] **Step 1: Write failing tests**

Create `tests/retrieval/test_fusion.py`:

```python
import pytest

from rag_app.retrieval import RankedCandidate, reciprocal_rank_fusion


def test_rrf_combines_rankings() -> None:
    result = reciprocal_rank_fusion(
        (RankedCandidate("a", 1), RankedCandidate("b", 2)),
        (RankedCandidate("b", 1), RankedCandidate("c", 2)),
        limit=3,
    )

    assert [item.chunk_id for item in result] == ["b", "a", "c"]


def test_rrf_is_deterministic_for_ties() -> None:
    result = reciprocal_rank_fusion(
        (RankedCandidate("z", 1), RankedCandidate("a", 2)),
        (),
        limit=2,
    )

    assert [item.chunk_id for item in result] == ["z", "a"]


def test_rrf_rejects_duplicate_chunk_in_one_ranking() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        reciprocal_rank_fusion(
            (RankedCandidate("a", 1), RankedCandidate("a", 2)),
            (),
        )


def test_rrf_rejects_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="limit"):
        reciprocal_rank_fusion((), (), limit=0)
```

- [x] **Step 2: Run tests and verify failure**

```powershell
uv run pytest tests/retrieval/test_fusion.py -v
```

Expected: import failure.

- [x] **Step 3: Implement RRF**

Create `src/rag_app/retrieval/models.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    chunk_id: str
    rank: int


@dataclass(frozen=True, slots=True)
class FusedCandidate:
    chunk_id: str
    score: float
```

Create `src/rag_app/retrieval/fusion.py`:

```python
from collections.abc import Sequence

from rag_app.retrieval.models import FusedCandidate, RankedCandidate


def reciprocal_rank_fusion(
    dense: Sequence[RankedCandidate],
    sparse: Sequence[RankedCandidate],
    limit: int = 20,
    rrf_k: int = 60,
) -> tuple[FusedCandidate, ...]:
    if limit < 1:
        raise ValueError("limit must be positive")
    if rrf_k < 1:
        raise ValueError("rrf_k must be positive")

    scores: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    sequence = 0

    for ranking in (dense, sparse):
        seen: set[str] = set()
        for candidate in ranking:
            if candidate.chunk_id in seen:
                raise ValueError("duplicate chunk id in ranking")
            seen.add(candidate.chunk_id)
            scores[candidate.chunk_id] = scores.get(candidate.chunk_id, 0.0) + (
                1.0 / (rrf_k + candidate.rank)
            )
            if candidate.chunk_id not in first_seen:
                first_seen[candidate.chunk_id] = sequence
                sequence += 1

    ordered = sorted(
        scores.items(),
        key=lambda item: (-item[1], first_seen[item[0]]),
    )
    return tuple(
        FusedCandidate(chunk_id=chunk_id, score=score)
        for chunk_id, score in ordered[:limit]
    )
```

Create `src/rag_app/retrieval/__init__.py`:

```python
from rag_app.retrieval.fusion import reciprocal_rank_fusion
from rag_app.retrieval.models import FusedCandidate, RankedCandidate

__all__ = ["FusedCandidate", "RankedCandidate", "reciprocal_rank_fusion"]
```

- [x] **Step 4: Run checks**

```powershell
uv run pytest tests/retrieval/test_fusion.py -v
uv run pytest
uv run ruff check src/rag_app/retrieval tests/retrieval
uv run mypy src/rag_app/retrieval tests/retrieval
```

Expected: all commands exit 0.

- [x] **Step 5: Commit**

```powershell
git add src/rag_app/retrieval tests/retrieval
git commit -m "feat: add reciprocal rank fusion"
```

---

### Task 5: Answer Policy and Finite Loop

**Files:**
- Create: `src/rag_app/answering/__init__.py`
- Create: `src/rag_app/answering/models.py`
- Create: `src/rag_app/answering/policy.py`
- Create: `src/rag_app/answering/loop.py`
- Create: `tests/answering/__init__.py`
- Create: `tests/answering/test_answering.py`

**Interfaces:**

- Consumes: standard library only.
- Produces:
  - `AnswerMode(StrEnum)` with `MANUAL_GROUNDED`, `GENERAL_EXPLANATION`, `REFUSED`
  - `RiskLevel(StrEnum)` with `NORMAL`, `SAFETY_CRITICAL`
  - `Evidence(chunk_id: str, content: str, page: int)`
  - `DraftAnswer(text: str, citations: tuple[str, ...])`
  - `AnswerResult(mode: AnswerMode, text: str, citations: tuple[str, ...], attempts: int)`
  - `Retriever` protocol
  - `Generator` protocol
  - `AnswerVerifier` protocol
  - `AnswerLoop.run(question: str) -> AnswerResult`
  - `classify_risk(question: str) -> RiskLevel`

- [x] **Step 1: Write failing tests**

Create `tests/answering/test_answering.py`:

```python
from dataclasses import dataclass

from rag_app.answering import (
    AnswerLoop,
    AnswerMode,
    AnswerResult,
    DraftAnswer,
    Evidence,
    RiskLevel,
    classify_risk,
)


@dataclass
class FakeRetriever:
    responses: tuple[tuple[Evidence, ...], ...]
    attempts: int = 0

    def retrieve(self, question: str) -> tuple[Evidence, ...]:
        self.attempts += 1
        index = min(self.attempts - 1, len(self.responses) - 1)
        return self.responses[index]


@dataclass
class FakeGenerator:
    calls: int = 0

    def generate(
        self,
        question: str,
        evidence: tuple[Evidence, ...],
        mode: AnswerMode,
    ) -> DraftAnswer:
        self.calls += 1
        return DraftAnswer("不要拆机。[1]", ("chunk-1",))


@dataclass
class FakeVerifier:
    results: list[bool]

    def verify(
        self,
        draft: DraftAnswer,
        evidence: tuple[Evidence, ...],
    ) -> bool:
        return self.results.pop(0)


def test_safety_question_retries_once_then_answers() -> None:
    evidence = (Evidence("chunk-1", "请勿拆机。", 3),)
    retriever = FakeRetriever((evidence, evidence))
    generator = FakeGenerator()
    result = AnswerLoop(
        retriever=retriever,
        generator=generator,
        verifier=FakeVerifier([False, True]),
    ).run("设备冒烟了怎么办？")

    assert result.mode is AnswerMode.MANUAL_GROUNDED
    assert result.attempts == 2
    assert retriever.attempts == 2
    assert generator.calls == 2


def test_safety_question_without_evidence_refuses() -> None:
    result = AnswerLoop(
        retriever=FakeRetriever(((),)),
        generator=FakeGenerator(),
        verifier=FakeVerifier([True]),
    ).run("设备漏液了怎么办？")

    assert result.mode is AnswerMode.REFUSED
    assert result.attempts == 2


def test_non_safety_question_can_fall_back_to_general() -> None:
    result = AnswerLoop(
        retriever=FakeRetriever(((),)),
        generator=FakeGenerator(),
        verifier=FakeVerifier([True]),
        allow_general_fallback=True,
    ).run("什么是蓝牙？")

    assert result.mode is AnswerMode.GENERAL_EXPLANATION


def test_risk_classifier_detects_fire_smoke_and_battery_swelling() -> None:
    assert classify_risk("设备冒烟了") is RiskLevel.SAFETY_CRITICAL
    assert classify_risk("电池鼓包") is RiskLevel.SAFETY_CRITICAL
    assert classify_risk("怎么打开蓝牙") is RiskLevel.NORMAL
```

- [x] **Step 2: Run tests and verify failure**

```powershell
uv run pytest tests/answering/test_answering.py -v
```

Expected: import failure.

- [x] **Step 3: Implement answer models, policy, and loop**

Create `src/rag_app/answering/models.py`:

```python
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class AnswerMode(StrEnum):
    MANUAL_GROUNDED = "manual_grounded"
    GENERAL_EXPLANATION = "general_explanation"
    REFUSED = "refused"


class RiskLevel(StrEnum):
    NORMAL = "normal"
    SAFETY_CRITICAL = "safety_critical"


@dataclass(frozen=True, slots=True)
class Evidence:
    chunk_id: str
    content: str
    page: int


@dataclass(frozen=True, slots=True)
class DraftAnswer:
    text: str
    citations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnswerResult:
    mode: AnswerMode
    text: str
    citations: tuple[str, ...]
    attempts: int


class Retriever(Protocol):
    def retrieve(self, question: str) -> tuple[Evidence, ...]: ...


class Generator(Protocol):
    def generate(
        self,
        question: str,
        evidence: tuple[Evidence, ...],
        mode: AnswerMode,
    ) -> DraftAnswer: ...


class AnswerVerifier(Protocol):
    def verify(
        self,
        draft: DraftAnswer,
        evidence: tuple[Evidence, ...],
    ) -> bool: ...
```

Create `src/rag_app/answering/policy.py`:

```python
from rag_app.answering.models import RiskLevel


_SAFETY_TERMS = (
    "冒烟",
    "起火",
    "着火",
    "漏液",
    "触电",
    "拆机",
    "电池鼓包",
    "电池膨胀",
    "爆炸",
)


def classify_risk(question: str) -> RiskLevel:
    normalized = question.casefold()
    if any(term in normalized for term in _SAFETY_TERMS):
        return RiskLevel.SAFETY_CRITICAL
    return RiskLevel.NORMAL
```

Create `src/rag_app/answering/loop.py`:

```python
from rag_app.answering.models import (
    AnswerMode,
    AnswerResult,
    AnswerVerifier,
    DraftAnswer,
    Evidence,
    Generator,
    Retriever,
    RiskLevel,
)
from rag_app.answering.policy import classify_risk


class AnswerLoop:
    def __init__(
        self,
        retriever: Retriever,
        generator: Generator,
        verifier: AnswerVerifier,
        allow_general_fallback: bool = False,
        max_attempts: int = 2,
    ) -> None:
        if max_attempts < 1 or max_attempts > 2:
            raise ValueError("max_attempts must be between 1 and 2")
        self._retriever = retriever
        self._generator = generator
        self._verifier = verifier
        self._allow_general_fallback = allow_general_fallback
        self._max_attempts = max_attempts

    def run(self, question: str) -> AnswerResult:
        risk = classify_risk(question)
        evidence: tuple[Evidence, ...] = ()

        for attempt in range(1, self._max_attempts + 1):
            evidence = self._retriever.retrieve(question)
            if not evidence:
                continue

            draft = self._generator.generate(
                question,
                evidence,
                AnswerMode.MANUAL_GROUNDED,
            )
            if self._verifier.verify(draft, evidence):
                return AnswerResult(
                    mode=AnswerMode.MANUAL_GROUNDED,
                    text=draft.text,
                    citations=draft.citations,
                    attempts=attempt,
                )

        if (
            risk is RiskLevel.NORMAL
            and self._allow_general_fallback
        ):
            draft = self._generator.generate(
                question,
                (),
                AnswerMode.GENERAL_EXPLANATION,
            )
            if self._verifier.verify(draft, ()):
                return AnswerResult(
                    mode=AnswerMode.GENERAL_EXPLANATION,
                    text=draft.text,
                    citations=(),
                    attempts=self._max_attempts,
                )

        return AnswerResult(
            mode=AnswerMode.REFUSED,
            text="当前手册没有足够依据回答这个问题，请联系官方支持。",
            citations=(),
            attempts=self._max_attempts,
        )
```

Create `src/rag_app/answering/__init__.py`:

```python
from rag_app.answering.loop import AnswerLoop
from rag_app.answering.models import (
    AnswerMode,
    AnswerResult,
    AnswerVerifier,
    DraftAnswer,
    Evidence,
    Generator,
    Retriever,
    RiskLevel,
)
from rag_app.answering.policy import classify_risk

__all__ = [
    "AnswerLoop",
    "AnswerMode",
    "AnswerResult",
    "AnswerVerifier",
    "DraftAnswer",
    "Evidence",
    "Generator",
    "Retriever",
    "RiskLevel",
    "classify_risk",
]
```

- [x] **Step 4: Run checks**

```powershell
uv run pytest tests/answering/test_answering.py -v
uv run pytest
uv run ruff check src/rag_app/answering tests/answering
uv run mypy src/rag_app/answering tests/answering
```

Expected: all commands exit 0.

- [x] **Step 5: Commit**

```powershell
git add src/rag_app/answering tests/answering
git commit -m "feat: add bounded answer loop"
```

---

### Task 6: Deterministic Answer Verification

**Files:**
- Create: `src/rag_app/verification/__init__.py`
- Create: `src/rag_app/verification/models.py`
- Create: `src/rag_app/verification/verifier.py`
- Create: `tests/verification/__init__.py`
- Create: `tests/verification/test_verifier.py`

**Interfaces:**

- Consumes: standard library only.
- Produces:
  - `VerificationIssue(StrEnum)` with `MISSING_CITATION`, `UNKNOWN_CITATION`, `EMPTY_ANSWER`
  - `VerificationResult(passed: bool, issues: tuple[VerificationIssue, ...])`
  - `CitationVerifier.check(draft: DraftAnswer, evidence: Sequence[Evidence]) -> VerificationResult`
  - `CitationVerifier.verify(draft: DraftAnswer, evidence: Sequence[Evidence]) -> bool`

- [x] **Step 1: Write failing tests**

Create `tests/verification/test_verifier.py`:

```python
from rag_app.answering import DraftAnswer, Evidence
from rag_app.verification import (
    CitationVerifier,
    VerificationIssue,
)


def test_valid_citations_pass() -> None:
    result = CitationVerifier().check(
        DraftAnswer("不要拆机。[1]", ("chunk-1",)),
        (Evidence("chunk-1", "请勿拆机。", 3),),
    )

    assert result.passed is True
    assert result.issues == ()


def test_empty_answer_fails() -> None:
    result = CitationVerifier().check(
        DraftAnswer("", ()),
        (Evidence("chunk-1", "请勿拆机。", 3),),
    )

    assert result.passed is False
    assert VerificationIssue.EMPTY_ANSWER in result.issues


def test_missing_citation_fails() -> None:
    result = CitationVerifier().check(
        DraftAnswer("不要拆机。", ()),
        (Evidence("chunk-1", "请勿拆机。", 3),),
    )

    assert result.passed is False
    assert VerificationIssue.MISSING_CITATION in result.issues


def test_unknown_citation_fails() -> None:
    result = CitationVerifier().check(
        DraftAnswer("不要拆机。[1]", ("chunk-missing",)),
        (Evidence("chunk-1", "请勿拆机。", 3),),
    )

    assert result.passed is False
    assert VerificationIssue.UNKNOWN_CITATION in result.issues
```

- [x] **Step 2: Run tests and verify failure**

```powershell
uv run pytest tests/verification/test_verifier.py -v
```

Expected: import failure.

- [x] **Step 3: Implement deterministic verifier**

Create `src/rag_app/verification/models.py`:

```python
from dataclasses import dataclass
from enum import StrEnum


class VerificationIssue(StrEnum):
    MISSING_CITATION = "missing_citation"
    UNKNOWN_CITATION = "unknown_citation"
    EMPTY_ANSWER = "empty_answer"


@dataclass(frozen=True, slots=True)
class VerificationResult:
    passed: bool
    issues: tuple[VerificationIssue, ...]
```

Create `src/rag_app/verification/verifier.py`:

```python
from collections.abc import Sequence

from rag_app.answering import DraftAnswer, Evidence
from rag_app.verification.models import VerificationIssue, VerificationResult


class CitationVerifier:
    def check(
        self,
        draft: DraftAnswer,
        evidence: Sequence[Evidence],
    ) -> VerificationResult:
        issues: list[VerificationIssue] = []
        if not draft.text.strip():
            issues.append(VerificationIssue.EMPTY_ANSWER)
        if not draft.citations:
            issues.append(VerificationIssue.MISSING_CITATION)

        available = {item.chunk_id for item in evidence}
        if any(citation not in available for citation in draft.citations):
            issues.append(VerificationIssue.UNKNOWN_CITATION)

        return VerificationResult(
            passed=not issues,
            issues=tuple(issues),
        )

    def verify(
        self,
        draft: DraftAnswer,
        evidence: Sequence[Evidence],
    ) -> bool:
        return self.check(draft, evidence).passed
```

Create `src/rag_app/verification/__init__.py`:

```python
from rag_app.verification.models import VerificationIssue, VerificationResult
from rag_app.verification.verifier import CitationVerifier

__all__ = ["CitationVerifier", "VerificationIssue", "VerificationResult"]
```

- [x] **Step 4: Run checks**

```powershell
uv run pytest tests/verification/test_verifier.py -v
uv run pytest
uv run ruff check src/rag_app/verification tests/verification
uv run mypy src/rag_app/verification tests/verification
```

Expected: all commands exit 0.

- [x] **Step 5: Commit**

```powershell
git add src/rag_app/verification tests/verification
git commit -m "feat: add deterministic citation verification"
```

---

### Task 7: Conversation State and Explicit Preferences

**Files:**
- Create: `src/rag_app/conversations/__init__.py`
- Create: `src/rag_app/conversations/models.py`
- Create: `src/rag_app/conversations/service.py`
- Create: `tests/conversations/__init__.py`
- Create: `tests/conversations/test_conversations.py`

**Interfaces:**

- Consumes: standard library only.
- Produces:
  - `AnswerDetail(StrEnum)` with `BRIEF`, `DETAILED`
  - `UserPreference(language: str, answer_detail: AnswerDetail, show_citations: bool)`
  - `ConversationMessage(role: str, content: str)`
  - `ConversationState(conversation_id: str, product_id: str | None, messages: tuple[ConversationMessage, ...])`
  - `ConversationService.start(conversation_id: str) -> ConversationState`
  - `ConversationService.select_product(state, product_id) -> ConversationState`
  - `ConversationService.change_product(state, product_id) -> ConversationState`
  - `ConversationService.append_exchange(state, question, answer) -> ConversationState`
  - `summarize_old_messages(messages, keep_recent=6) -> tuple[str, tuple[ConversationMessage, ...]]`

- [x] **Step 1: Write failing tests**

Create `tests/conversations/test_conversations.py`:

```python
from rag_app.conversations import (
    ConversationMessage,
    ConversationService,
    summarize_old_messages,
)


def test_new_conversation_has_no_product() -> None:
    state = ConversationService().start("conversation-1")

    assert state.product_id is None
    assert state.messages == ()


def test_select_product_sets_current_product() -> None:
    service = ConversationService()
    state = service.start("conversation-1")

    state = service.select_product(state, "huawei_c7")

    assert state.product_id == "huawei_c7"


def test_changing_product_clears_old_messages() -> None:
    service = ConversationService()
    state = service.start("conversation-1")
    state = service.select_product(state, "huawei_c7")
    state = service.append_exchange(state, "怎么开机？", "按电源键。[1]")

    state = service.change_product(state, "huawei_b5_440")

    assert state.product_id == "huawei_b5_440"
    assert state.messages == ()


def test_summary_preserves_recent_messages() -> None:
    messages = tuple(
        ConversationMessage("user", f"question-{index}")
        for index in range(8)
    )

    summary, recent = summarize_old_messages(messages, keep_recent=6)

    assert summary == "user: question-0\nuser: question-1"
    assert len(recent) == 6
    assert recent[-1].content == "question-7"
```

- [x] **Step 2: Run tests and verify failure**

```powershell
uv run pytest tests/conversations/test_conversations.py -v
```

Expected: import failure.

- [x] **Step 3: Implement conversation module**

Create `src/rag_app/conversations/models.py`:

```python
from dataclasses import dataclass, replace
from enum import StrEnum


class AnswerDetail(StrEnum):
    BRIEF = "brief"
    DETAILED = "detailed"


@dataclass(frozen=True, slots=True)
class UserPreference:
    language: str = "zh-CN"
    answer_detail: AnswerDetail = AnswerDetail.BRIEF
    show_citations: bool = True


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ConversationState:
    conversation_id: str
    product_id: str | None
    messages: tuple[ConversationMessage, ...]

    def with_product(self, product_id: str) -> "ConversationState":
        return replace(self, product_id=product_id)

    def with_messages(
        self,
        messages: tuple[ConversationMessage, ...],
    ) -> "ConversationState":
        return replace(self, messages=messages)
```

Create `src/rag_app/conversations/service.py`:

```python
from collections.abc import Sequence

from rag_app.conversations.models import (
    ConversationMessage,
    ConversationState,
)


def summarize_old_messages(
    messages: Sequence[ConversationMessage],
    keep_recent: int = 6,
) -> tuple[str, tuple[ConversationMessage, ...]]:
    if keep_recent < 1:
        raise ValueError("keep_recent must be positive")
    if len(messages) <= keep_recent:
        return "", tuple(messages)

    old = messages[:-keep_recent]
    recent = tuple(messages[-keep_recent:])
    summary = "\n".join(f"{item.role}: {item.content}" for item in old)
    return summary, recent


class ConversationService:
    def start(self, conversation_id: str) -> ConversationState:
        return ConversationState(
            conversation_id=conversation_id,
            product_id=None,
            messages=(),
        )

    def select_product(
        self,
        state: ConversationState,
        product_id: str,
    ) -> ConversationState:
        return state.with_product(product_id)

    def change_product(
        self,
        state: ConversationState,
        product_id: str,
    ) -> ConversationState:
        return ConversationState(
            conversation_id=state.conversation_id,
            product_id=product_id,
            messages=(),
        )

    def append_exchange(
        self,
        state: ConversationState,
        question: str,
        answer: str,
    ) -> ConversationState:
        messages = (
            *state.messages,
            ConversationMessage("user", question),
            ConversationMessage("assistant", answer),
        )
        return state.with_messages(messages)
```

Create `src/rag_app/conversations/__init__.py`:

```python
from rag_app.conversations.models import (
    AnswerDetail,
    ConversationMessage,
    ConversationState,
    UserPreference,
)
from rag_app.conversations.service import (
    ConversationService,
    summarize_old_messages,
)

__all__ = [
    "AnswerDetail",
    "ConversationMessage",
    "ConversationService",
    "ConversationState",
    "UserPreference",
    "summarize_old_messages",
]
```

- [x] **Step 4: Run checks**

```powershell
uv run pytest tests/conversations/test_conversations.py -v
uv run pytest
uv run ruff check src/rag_app/conversations tests/conversations
uv run mypy src/rag_app/conversations tests/conversations
```

Expected: all commands exit 0.

- [x] **Step 5: Commit**

```powershell
git add src/rag_app/conversations tests/conversations
git commit -m "feat: add conversation state"
```

---

### Task 8: Core Integration Contract

**Files:**
- Create: `src/rag_app/core.py`
- Create: `tests/integration/test_core_flow.py`

**Interfaces:**

- Consumes:
  - `rag_app.answering`
  - `rag_app.verification`
  - `rag_app.conversations`
- Produces:
  - `build_core_answer_loop(retriever, generator) -> AnswerLoop`
  - no infrastructure imports

- [x] **Step 1: Write failing integration test**

Create `tests/integration/test_core_flow.py`:

```python
from rag_app.core import build_core_answer_loop


def test_core_composition_returns_a_refusal_without_evidence() -> None:
    from rag_app.answering import AnswerMode, DraftAnswer, Evidence

    class EmptyRetriever:
        def retrieve(self, question: str) -> tuple[Evidence, ...]:
            return ()

    class UnusedGenerator:
        def generate(
            self,
            question: str,
            evidence: tuple[Evidence, ...],
            mode: AnswerMode,
        ) -> DraftAnswer:
            raise AssertionError("generator should not be called")

    result = build_core_answer_loop(
        retriever=EmptyRetriever(),
        generator=UnusedGenerator(),
    ).run("怎么开机？")

    assert result.mode.value == "refused"
    assert result.attempts == 2
```

- [x] **Step 2: Run tests and verify failure**

```powershell
uv run pytest tests/integration/test_core_flow.py -v
```

Expected: import failure for `rag_app.core`.

- [x] **Step 3: Implement composition helper**

Create `src/rag_app/core.py`:

```python
from rag_app.answering import AnswerLoop, Generator, Retriever
from rag_app.verification import CitationVerifier


def build_core_answer_loop(
    retriever: Retriever,
    generator: Generator,
) -> AnswerLoop:
    return AnswerLoop(
        retriever=retriever,
        generator=generator,
        verifier=CitationVerifier(),
        allow_general_fallback=False,
    )
```

- [x] **Step 4: Run full verification**

```powershell
uv run pytest -v
uv run ruff check .
uv run mypy .
```

Expected:

- All tests pass.
- Ruff exits 0.
- mypy exits 0.

- [x] **Step 5: Commit**

```powershell
git add src/rag_app/core.py tests/integration/test_core_flow.py
git commit -m "test: verify core answer composition"
```

---

## Plan Self-Review

- Spec coverage for this phase: product resolution, document version policy, structured Chunking, RRF, finite answer loop, answer modes, deterministic verifier, conversation boundary, and explicit preferences.
- Deferred to later plans: MySQL persistence, MinerU/PDF parsing, remote providers, Qdrant, ingestion worker, API/SSE, Langfuse, harness, Next.js, Docker, and end-to-end delivery.
- Module boundaries: each package exports its own types and protocols; only `rag_app/core.py` composes modules.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation steps.
- Type consistency: `Evidence`, `DraftAnswer`, `AnswerMode`, and `AnswerVerifier` are defined in the answering module and reused by verification through its public package export.
