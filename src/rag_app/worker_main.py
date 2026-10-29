import argparse
import time

import httpx
from qdrant_client import QdrantClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rag_app.bootstrap import (
    build_index_cleanup_processor,
    build_worker_loop,
)
from rag_app.file_store import Sha256FileStore
from rag_app.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ingestion worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--index-version-id", required=True)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()

    settings = Settings()
    engine = create_engine(settings.database_url)
    qdrant = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
    )
    with (
        Session(engine) as session,
        httpx.Client(timeout=60) as http_client,
    ):
        worker = build_worker_loop(
            settings=settings,
            session=session,
            qdrant=qdrant,
            http_client=http_client,
            file_store=Sha256FileStore(settings.file_storage_root),
            index_version_id=args.index_version_id,
        )
        cleanup_processor = build_index_cleanup_processor(
            session=session,
            qdrant=qdrant,
        )
        if args.once:
            worker.run(max_jobs=args.batch_size)
            cleanup_processor.run(max_jobs=args.batch_size)
            return 0

        while True:
            processed = worker.run(max_jobs=args.batch_size)
            cleanup_processor.run(max_jobs=args.batch_size)
            if processed == 0:
                time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
