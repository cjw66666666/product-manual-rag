# API Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the initial Alembic migration and a tested FastAPI application foundation without coupling HTTP code to adapter internals.

**Architecture:** Alembic owns schema migration history. FastAPI is a thin transport layer with explicit dependency injection. Health checks report process and database readiness separately. Product and chat endpoints will be added only after their application services have concrete adapters.

**Tech Stack:** Python 3.12, SQLAlchemy 2, Alembic, FastAPI, httpx.

**Spec:** `docs/superpowers/specs/2026-10-26-product-manual-rag-design.md`

## Global Constraints

- One module per task.
- Write failing tests first.
- API modules may import only public application contracts.
- No SQLAlchemy queries inside route handlers.
- Langfuse must remain optional.
- Tests must not require a live MySQL server.

## Task 0: Alembic Initial Migration

**Files:**
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `migrations/versions/20261027_0001_initial_schema.py`
- Create: `tests/persistence/test_migrations.py`

**Interfaces:**

- Consumes: `rag_app.persistence.schema.Base`.
- Produces: `alembic upgrade head` creates the complete initial schema.

- [x] **Step 1: Write the failing migration test**

Create a test that sets `RAG_DATABASE_URL` to a temporary SQLite database, runs Alembic via its Python API, and asserts required table names exist.

- [x] **Step 2: Run and verify failure**

Run:

```powershell
uv run pytest tests/persistence/test_migrations.py -v
```

Expected: Alembic configuration is missing.

- [x] **Step 3: Implement initial migration**

Create `migrations/env.py` that imports `Base`, reads `Settings().database_url`, and supports offline and online upgrades.

Create revision `20261027_0001`:

```python
def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
```

This is an initial bootstrap migration; later schema changes must use explicit operations.

- [x] **Step 4: Verify and commit**

```powershell
uv run pytest tests/persistence/test_migrations.py -v
uv run pytest
uv run ruff check migrations tests/persistence
uv run mypy migrations tests/persistence
git add alembic.ini migrations tests/persistence/test_migrations.py
git commit -m "feat: add initial Alembic migration"
```

## Task 1: FastAPI Application and Health Checks

**Files:**
- Create: `src/rag_app/api/__init__.py`
- Create: `src/rag_app/api/app.py`
- Create: `src/rag_app/api/health.py`
- Create: `tests/api/__init__.py`
- Create: `tests/api/test_health.py`

**Interfaces:**

- `create_app(readiness_check: Callable[[], bool] | None = None) -> FastAPI`
- `GET /health/live -> {"status": "ok"}`
- `GET /health/ready -> 200 {"status": "ready"}` or `503 {"status": "not_ready"}`

- [x] **Step 1: Write failing API tests**

Use `TestClient` to assert:

- Live endpoint always returns 200.
- Ready endpoint returns 200 when the injected checker returns true.
- Ready endpoint returns 503 when the checker returns false.

- [x] **Step 2: Verify failure**

```powershell
uv run pytest tests/api/test_health.py -v
```

Expected: API package does not exist.

- [x] **Step 3: Implement application factory**

`create_app` constructs all routes without global mutable state. The default readiness checker returns true only until a concrete database dependency is wired; the application factory must allow tests and future composition to replace it.

- [x] **Step 4: Verify and commit**

```powershell
uv run pytest tests/api/test_health.py -v
uv run pytest
uv run ruff check src/rag_app/api tests/api
uv run mypy src/rag_app/api tests/api
git add src/rag_app/api tests/api
git commit -m "feat: add FastAPI health foundation"
```

## Deferred to the Next API Plan

- Product catalog endpoint.
- Conversation creation.
- Message submission.
- Verified SSE answer streaming.
- Admin login.
- Import preview and conflict resolution.

These endpoints remain blocked until a composition root maps the public API contracts to concrete persistence and model adapters.

## Plan Self-Review

- Scope is limited to migrations and API foundation.
- No route performs database access.
- No SSE behavior is claimed before verification exists.
- No module imports another module's internal implementation.
- Migration bootstrap is explicitly documented as a one-time exception.
