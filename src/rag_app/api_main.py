import httpx
import uvicorn
from fastapi import FastAPI
from qdrant_client import QdrantClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from rag_app.admin_auth import AdminAuth
from rag_app.api.app import create_app
from rag_app.application import (
    ConversationalAnswerService,
    ConversationApplicationService,
    PersistentImportService,
    SessionScopedAnswerService,
    SessionScopedConversationService,
    SessionScopedImportService,
    SessionScopedPublicationService,
    VersionPublicationService,
    build_publication_service,
)
from rag_app.application.filename_product_extractor import (
    LlmFilenameProductExtractor,
)
from rag_app.bootstrap import build_answer_service
from rag_app.catalog import Product, ProductCatalog
from rag_app.file_store import Sha256FileStore
from rag_app.observability import (
    LangfuseTraceSink,
    TracedAnswerService,
    build_langfuse_sink,
)
from rag_app.persistence.conversation_repository import (
    SqlConversationRepository,
)
from rag_app.persistence.document_index_repository import (
    DocumentIndexRepository,
)
from rag_app.persistence.import_repository import ImportRepository
from rag_app.persistence.import_version_binder import ImportVersionBinder
from rag_app.persistence.index_cleanup_repository import (
    IndexCleanupRepository,
)
from rag_app.persistence.product_repository import ProductDirectoryRepository
from rag_app.persistence.repositories import DocumentRepository
from rag_app.remote_models import HttpLlmClient
from rag_app.seed import PRODUCTS
from rag_app.settings import Settings


def build_runtime_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    if not settings.admin_password_hash.startswith("$argon2"):
        raise ValueError("RAG_ADMIN_PASSWORD_HASH is not configured")
    if len(settings.session_secret) < 32:
        raise ValueError("RAG_SESSION_SECRET is too short")

    engine = create_engine(settings.database_url)
    session_factory = sessionmaker(engine, expire_on_commit=False)
    qdrant = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
    )
    http_client = httpx.Client(timeout=60)
    file_store = Sha256FileStore(settings.file_storage_root)
    products = tuple(
        Product(
            item.id,
            item.name,
            item.category,
            (item.id, *item.aliases),
        )
        for item in PRODUCTS
    )
    filename_product_extractor = LlmFilenameProductExtractor(
        llm=HttpLlmClient(
            http_client,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        ),
        model=settings.llm_model,
    )
    admin_auth = AdminAuth(
        password_hash=settings.admin_password_hash,
        session_secret=settings.session_secret,
    )
    def import_service_factory(
        session: Session,
    ) -> PersistentImportService:
        return PersistentImportService(
            repository=ImportRepository(session),
            file_store=file_store,
            created_by="admin",
            catalog_provider=lambda: ProductCatalog(
                ProductDirectoryRepository(
                    session
                ).list_catalog_products()
            ),
            products=ProductDirectoryRepository(session),
            filename_product_extractor=filename_product_extractor,
            version_binder=ImportVersionBinder(session),
            index_version_id=settings.index_version_id,
            commit=session.commit,
        )

    def answer_service_factory(
        session: Session,
    ) -> ConversationalAnswerService:
        return build_answer_service(
            settings=settings,
            session=session,
            qdrant=qdrant,
            http_client=http_client,
            index_version_id=settings.index_version_id,
        )

    def publication_service_factory(
        session: Session,
    ) -> VersionPublicationService:
        return build_publication_service(
            versions=DocumentRepository(session),
            indexes=DocumentIndexRepository(session),
            cleanup_queue=IndexCleanupRepository(session),
            commit=session.commit,
        )

    def conversation_service_factory(
        session: Session,
    ) -> ConversationApplicationService:
        return ConversationApplicationService(
            conversations=SqlConversationRepository(session),
            commit=session.commit,
        )

    import_service = SessionScopedImportService(
        session_factory=session_factory,
        service_factory=import_service_factory,
    )
    scoped_answer_service = SessionScopedAnswerService(
        session_factory=session_factory,
        service_factory=answer_service_factory,
    )
    publication_service = SessionScopedPublicationService(
        session_factory=session_factory,
        service_factory=publication_service_factory,
    )
    conversation_service = SessionScopedConversationService(
        session_factory=session_factory,
        service_factory=conversation_service_factory,
    )
    trace_sink = build_langfuse_sink(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    traced_answer_service = TracedAnswerService(
        service=scoped_answer_service,
        sink=trace_sink,
    )

    def load_products() -> tuple[Product, ...]:
        with session_factory() as session:
            return ProductDirectoryRepository(
                session
            ).list_catalog_products()

    def ready() -> bool:
        try:
            with session_factory() as session:
                session.execute(text("SELECT 1"))
            qdrant.get_collections()
        except Exception:
            return False
        return True

    app = create_app(
        readiness_check=ready,
        products=products,
        product_loader=load_products,
        answer_service=traced_answer_service,
        admin_auth=admin_auth,
        import_service=import_service,
        max_upload_bytes=settings.max_upload_bytes,
        max_batch_upload_bytes=settings.max_batch_upload_bytes,
        max_requests_per_minute=settings.max_requests_per_minute,
        publication_service=publication_service,
        conversation_service=conversation_service,
    )
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.qdrant = qdrant
    app.state.http_client = http_client
    app.state.trace_sink = trace_sink
    return app


app = build_runtime_app()


def main() -> int:
    uvicorn.run(
        "rag_app.api_main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
    trace_sink = getattr(app.state, "trace_sink", None)
    if isinstance(trace_sink, LangfuseTraceSink):
        trace_sink.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
