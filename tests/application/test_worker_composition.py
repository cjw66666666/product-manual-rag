from pathlib import Path

import httpx
from qdrant_client import QdrantClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rag_app.application import IndexCleanupProcessor
from rag_app.bootstrap import (
    build_index_cleanup_processor,
    build_worker_loop,
)
from rag_app.file_store import Sha256FileStore
from rag_app.persistence import create_schema
from rag_app.settings import Settings
from rag_app.worker import WorkerLoop


def test_build_worker_loop_wires_real_components(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    worker = build_worker_loop(
        settings=Settings(),
        session=Session(engine),
        qdrant=QdrantClient(":memory:"),
        http_client=httpx.Client(),
        file_store=Sha256FileStore(tmp_path / "blobs"),
        index_version_id="i1",
    )

    assert isinstance(worker, WorkerLoop)


def test_build_index_cleanup_processor_wires_real_components() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    processor = build_index_cleanup_processor(
        session=Session(engine),
        qdrant=QdrantClient(":memory:"),
    )

    assert isinstance(processor, IndexCleanupProcessor)
