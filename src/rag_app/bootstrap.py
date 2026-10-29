import httpx
from qdrant_client import QdrantClient
from sqlalchemy.orm import Session

from rag_app.application import (
    Bm25QueryEncoder,
    ChatAnswerService,
    CompensatingIndexer,
    ConversationalAnswerService,
    IndexCleanupProcessor,
    IndexPublicationService,
    LlmFollowUpRewriter,
    ProductIndexScopeProvider,
    QdrantDenseSearch,
    QdrantSparseSearch,
    RagRetriever,
    RemoteAnswerGenerator,
    RemoteReranker,
)
from rag_app.conversations import SqlConversationContextStore
from rag_app.file_store import Sha256FileStore
from rag_app.indexing_pipeline import IndexingPipeline
from rag_app.indexing_worker import IndexingJobHandler
from rag_app.pdf_parsing import PyMuPdfParser
from rag_app.pdf_parsing.ocr import TesseractOcrEngine
from rag_app.persistence.answer_run_repository import AnswerRunRepository
from rag_app.persistence.chunk_repository import ChunkRepository
from rag_app.persistence.document_index_repository import (
    DocumentIndexRepository,
)
from rag_app.persistence.index_cleanup_repository import (
    IndexCleanupRepository,
)
from rag_app.persistence.indexing_context import IndexingContextProvider
from rag_app.persistence.job_queue import IngestionJobQueue
from rag_app.persistence.repositories import DocumentRepository
from rag_app.persistence.sparse_statistics_repository import (
    SparseStatisticsRepository,
)
from rag_app.qdrant_index import QdrantIndex
from rag_app.remote_models import (
    HttpEmbeddingClient,
    HttpLlmClient,
    HttpRerankerClient,
)
from rag_app.retrieval import HybridRetrievalService, RetrievalObserver
from rag_app.settings import Settings
from rag_app.sparse_encoder import Bm25SparseEncoder
from rag_app.verification import (
    CitationVerifier,
    RemoteSemanticSupportChecker,
)
from rag_app.worker import WorkerLoop


def build_answer_service(
    *,
    settings: Settings,
    session: Session,
    qdrant: QdrantClient,
    http_client: httpx.Client,
    index_version_id: str,
    retrieval_observer: RetrievalObserver | None = None,
) -> ConversationalAnswerService:
    index = QdrantIndex(qdrant)
    retrieval = HybridRetrievalService(
        encoder=Bm25QueryEncoder(
            embedder=HttpEmbeddingClient(
                http_client,
                base_url=settings.embedding_base_url,
                api_key=settings.embedding_api_key,
            ),
            statistics=SparseStatisticsRepository(session),
            model=settings.embedding_model,
        ),
        dense_search=QdrantDenseSearch(index),
        sparse_search=QdrantSparseSearch(index),
        reranker=RemoteReranker(
            client=HttpRerankerClient(
                http_client,
                base_url=settings.reranker_base_url,
                api_key=settings.reranker_api_key,
            ),
            model=settings.reranker_model,
        ),
        observer=retrieval_observer,
    )
    retriever = RagRetriever(
        scope_provider=ProductIndexScopeProvider(
            versions=DocumentRepository(session),
            index_version_id=index_version_id,
        ),
        engine=retrieval,
    )
    llm = HttpLlmClient(
        http_client,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )
    answer_service = ChatAnswerService(
        retriever=retriever,
        generator=RemoteAnswerGenerator(
            llm=llm,
            model=settings.llm_model,
        ),
        verifier=CitationVerifier(
            semantic_checker=RemoteSemanticSupportChecker(
                llm=llm,
                model=settings.verifier_model or settings.llm_model,
            )
        ),
        allow_general_fallback=True,
    )
    return ConversationalAnswerService(
        service=answer_service,
        contexts=SqlConversationContextStore(
            session,
            visitor_id="anonymous",
        ),
        rewriter=LlmFollowUpRewriter(
            llm=llm,
            model=settings.llm_model,
        ),
        answer_runs=AnswerRunRepository(session),
        commit=session.commit,
    )


def build_worker_loop(
    *,
    settings: Settings,
    session: Session,
    qdrant: QdrantClient,
    http_client: httpx.Client,
    file_store: Sha256FileStore,
    index_version_id: str,
) -> WorkerLoop:
    index = QdrantIndex(qdrant)
    index.ensure_collection(settings.embedding_dimension)
    document_repo = DocumentRepository(session)
    index_status = DocumentIndexRepository(session)
    pipeline = IndexingPipeline(
        parser=PyMuPdfParser(
            ocr_engine=TesseractOcrEngine(
                command=settings.ocr_command,
                languages=tuple(settings.ocr_languages.split("+")),
            )
        ),
        embedder=HttpEmbeddingClient(
            http_client,
            base_url=settings.embedding_base_url,
            api_key=settings.embedding_api_key,
        ),
        chunk_store=ChunkRepository(session),
        index=index,
        sparse_encoder=Bm25SparseEncoder(),
        statistics_store=SparseStatisticsRepository(session),
        embedding_model=settings.embedding_model,
    )
    publisher = IndexPublicationService(
        versions=document_repo,
        activator=document_repo,
        index_status=index_status,
        cleanup_queue=IndexCleanupRepository(session),
    )
    indexer = CompensatingIndexer(
        pipeline=pipeline,
        publisher=publisher,
        cleanup=index,
    )
    handler = IndexingJobHandler(
        contexts=IndexingContextProvider(session),
        file_store=file_store,
        indexer=indexer,
    )
    return WorkerLoop(
        queue=IngestionJobQueue(session),
        handler=handler,
        transaction=session,
    )


def build_index_cleanup_processor(
    *,
    session: Session,
    qdrant: QdrantClient,
) -> IndexCleanupProcessor:
    return IndexCleanupProcessor(
        repository=IndexCleanupRepository(session),
        cleanup=QdrantIndex(qdrant),
        transaction=session,
    )
