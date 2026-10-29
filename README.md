# Product Manual RAG / 产品手册 RAG

[中文](#中文) | [English](#english)

## 中文

面向产品手册的可信 RAG 问答系统。系统使用混合检索、重排序、引用校验和
语义验证，在证据不足时安全拒答；只有通过验证的回答才会标记为
`manual_grounded`。

主要能力：

- FastAPI 问答与管理 API
- Next.js 聊天与文档管理界面
- MySQL 元数据、会话和审计记录
- Qdrant 稠密与稀疏向量检索
- 多轮追问改写、产品切换隔离和澄清模式
- 引用回查、否定词保护和危险答案拦截
- 可取消的模型调用与 SSE 阶段状态
- 可选 Langfuse Trace 和评测指标

### 快速启动

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

填写 `.env` 中的模型 API Key、管理员密码哈希和 Session Secret。

- Web：<http://localhost:3000>
- 管理端：<http://localhost:3000/admin>
- 健康检查：<http://localhost:8000/health/ready>
- MySQL：`localhost:3307`
- Qdrant：`localhost:6333`

### 本地数据说明

以下内容不会上传到 GitHub：

- `.env` 和所有密钥
- `logs/`、`reports/`、`data/` 和上传文件
- `datasets/eval/` 本地评测集
- `docs/doc1/` 原始 PDF

数据集测试在本地文件不存在时会自动跳过，因此新克隆仍可正常执行单元测试。

### 开发与验证

```powershell
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy src tests
```

```powershell
Set-Location apps/web
npm ci
npm run build
```

## English

Grounded product-manual question answering with hybrid retrieval, reranking,
citation checks, and semantic verification. The system safely refuses when
evidence is insufficient; only verified answers are marked
`manual_grounded`.

Key capabilities:

- FastAPI answer and administration APIs
- Next.js chat and document-management UI
- MySQL metadata, conversations, and audit records
- Dense and sparse retrieval with Qdrant
- Multi-turn query rewriting, product context isolation, and clarification
- Citation resolution, negation protection, and unsafe-answer blocking
- Cancellable model calls and SSE progress events
- Optional Langfuse traces and evaluation metrics

### Quick Start

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

Set the model API keys, Argon2 admin password hash, and session secret in
`.env`.

### Local-Only Data

The following files are intentionally excluded from GitHub:

- `.env` and all secrets
- `logs/`, `reports/`, `data/`, and uploaded files
- Local evaluation cases under `datasets/eval/`
- Source PDFs under `docs/doc1/`

Dataset integrity tests are skipped when those local files are absent, so a
fresh clone can still run the unit test suite.

### Development

```powershell
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy src tests
```

```powershell
Set-Location apps/web
npm ci
npm run build
```

## Architecture

```text
question
  -> product resolution
  -> hybrid dense/sparse retrieval
  -> reranking
  -> grounded generation
  -> citation and semantic verification
  -> verified answer or safe refusal
```

The Compose project name is pinned to `product-manual-rag`.

See [observability.md](docs/observability.md) and
[evaluation-baseline.md](docs/evaluation-baseline.md) for more detail.

## Repository Layout

```text
apps/web/          Next.js chat and admin application
docs/              Architecture and evaluation documentation
migrations/        Alembic database migrations
src/rag_app/       FastAPI, worker, RAG, persistence, and verification
tests/             Unit, API, persistence, and integration tests
tools/             Dataset and maintenance utilities
```
