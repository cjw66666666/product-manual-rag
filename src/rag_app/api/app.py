from collections.abc import Callable, Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag_app.admin_auth import AdminAuth
from rag_app.api.admin import build_admin_router
from rag_app.api.admin_imports import build_import_router
from rag_app.api.admin_publications import (
    PublicationService,
    build_publication_router,
)
from rag_app.api.conversations import (
    ConversationService,
    build_conversation_router,
)
from rag_app.api.docs import build_docs_router
from rag_app.api.health import build_health_router
from rag_app.api.products import build_products_router
from rag_app.api.sse import AnswerService, build_sse_router
from rag_app.application import ImportService
from rag_app.catalog import Product


def create_app(
    readiness_check: Callable[[], bool] | None = None,
    products: Sequence[Product] = (),
    product_loader: Callable[[], Sequence[Product]] | None = None,
    answer_service: AnswerService | None = None,
    admin_auth: AdminAuth | None = None,
    import_service: ImportService | None = None,
    sse_heartbeat_seconds: float = 15.0,
    max_upload_bytes: int = 50 * 1024 * 1024,
    max_batch_upload_bytes: int = 200 * 1024 * 1024,
    max_requests_per_minute: int = 20,
    publication_service: PublicationService | None = None,
    conversation_service: ConversationService | None = None,
) -> FastAPI:
    title = "Product Manual RAG"
    app = FastAPI(
        title=title,
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:3000",
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_docs_router(title))
    app.include_router(
        build_health_router(readiness_check or (lambda: True))
    )
    app.include_router(build_products_router(products, product_loader))
    app.include_router(
        build_conversation_router(conversation_service)
    )
    app.include_router(
        build_sse_router(
            answer_service,
            tuple(products),
            product_loader=product_loader,
            heartbeat_seconds=sse_heartbeat_seconds,
            max_requests_per_minute=max_requests_per_minute,
        )
    )
    app.include_router(build_admin_router(admin_auth))
    app.include_router(
        build_import_router(
            admin_auth,
            import_service,
            max_upload_bytes=max_upload_bytes,
            max_batch_upload_bytes=max_batch_upload_bytes,
        )
    )
    app.include_router(
        build_publication_router(
            admin_auth,
            publication_service,
        )
    )
    return app
