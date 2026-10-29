import logging
import re
from collections.abc import Callable
from dataclasses import replace
from time import perf_counter
from typing import Protocol

from rag_app.answering import (
    AnswerCancelled,
    AnswerLoop,
    AnswerMode,
    AnswerObserver,
    AnswerResult,
    AnswerVerifier,
    Evidence,
    Generator,
)
from rag_app.conversations import ConversationExchange, ConversationState
from rag_app.remote_models import cancellation_scope

logger = logging.getLogger(__name__)

_GENERIC_ACTION_QUESTION = re.compile(
    r"^\s*(?:那|那么)?(?:怎么|如何)(?:连接|配对|设置|使用)"
    r"(?:呢)?[？?]?\s*$"
)
_CLARIFICATION_TEXT = (
    "请说明要连接、配对或设置的具体设备或目标，"
    "例如蓝牙耳机、手环或其他设备。"
)


class ProductScopedRetriever(Protocol):
    def retrieve(
        self,
        question: str,
        product_id: str,
    ) -> tuple[Evidence, ...]: ...


class BaseAnswerService(Protocol):
    def answer(
        self,
        question: str,
        product_id: str,
        *,
        observer: AnswerObserver | None = None,
        risk_question: str | None = None,
    ) -> AnswerResult: ...


class ConversationContextStore(Protocol):
    def product_id(
        self,
        conversation_id: str,
        *,
        visitor_id: str | None = None,
    ) -> str | None: ...

    def open(
        self,
        conversation_id: str,
        product_id: str,
        *,
        visitor_id: str | None = None,
    ) -> ConversationState: ...

    def begin_exchange(
        self,
        conversation_id: str,
        product_id: str,
        question: str,
        *,
        visitor_id: str | None = None,
    ) -> str: ...

    def complete_exchange(
        self,
        conversation_id: str,
        product_id: str,
        user_message_id: str,
        answer: str,
        *,
        visitor_id: str | None = None,
    ) -> ConversationExchange: ...


class QueryRewriter(Protocol):
    def rewrite(
        self,
        question: str,
        *,
        context: ConversationState,
    ) -> str: ...


class AnswerRunRecorder(Protocol):
    def record(
        self,
        *,
        conversation_id: str,
        exchange: ConversationExchange,
        result: AnswerResult,
        latency_ms: float,
    ) -> str: ...

    def record_failure(
        self,
        *,
        conversation_id: str,
        user_message_id: str,
        status: str,
        error_type: str,
        latency_ms: float,
    ) -> str: ...


class _BoundRetriever:
    def __init__(
        self,
        retriever: ProductScopedRetriever,
        question_product_id: str,
    ) -> None:
        self._retriever = retriever
        self._product_id = question_product_id

    def retrieve(self, question: str) -> tuple[Evidence, ...]:
        return self._retriever.retrieve(question, self._product_id)


class ChatAnswerService:
    def __init__(
        self,
        *,
        retriever: ProductScopedRetriever,
        generator: Generator,
        verifier: AnswerVerifier,
        allow_general_fallback: bool = False,
    ) -> None:
        self._retriever = retriever
        self._generator = generator
        self._verifier = verifier
        self._allow_general_fallback = allow_general_fallback

    def answer(
        self,
        question: str,
        product_id: str,
        *,
        observer: AnswerObserver | None = None,
        risk_question: str | None = None,
    ) -> AnswerResult:
        with cancellation_scope(
            observer.check_cancelled if observer is not None else None
        ):
            return AnswerLoop(
                retriever=_BoundRetriever(self._retriever, product_id),
                generator=self._generator,
                verifier=self._verifier,
                allow_general_fallback=self._allow_general_fallback,
            ).run(
                question,
                observer=observer,
                risk_question=risk_question,
            )


class ConversationalAnswerService:
    def __init__(
        self,
        *,
        service: BaseAnswerService,
        contexts: ConversationContextStore,
        rewriter: QueryRewriter,
        answer_runs: AnswerRunRecorder | None = None,
        commit: Callable[[], None] = lambda: None,
    ) -> None:
        self._service = service
        self._contexts = contexts
        self._rewriter = rewriter
        self._answer_runs = answer_runs
        self._commit = commit

    def conversation_product(
        self,
        conversation_id: str,
        *,
        visitor_id: str | None = None,
    ) -> str | None:
        return self._contexts.product_id(
            conversation_id,
            visitor_id=visitor_id,
        )

    def answer(
        self,
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
        observer: AnswerObserver | None = None,
        visitor_id: str | None = None,
    ) -> AnswerResult:
        if conversation_id is None:
            return self._service.answer(
                question,
                product_id,
                observer=observer,
            )

        started = perf_counter()
        context = self._contexts.open(
            conversation_id,
            product_id,
            visitor_id=visitor_id,
        )
        clarification = (
            _CLARIFICATION_TEXT
            if _GENERIC_ACTION_QUESTION.fullmatch(question)
            else None
        )
        if clarification is not None and observer is not None:
            observer.stage("clarifying")
        rewritten = question
        if clarification is None:
            with cancellation_scope(
                observer.check_cancelled
                if observer is not None
                else None
            ):
                try:
                    rewritten = self._rewriter.rewrite(
                        question,
                        context=context,
                    )
                except AnswerCancelled:
                    raise
                except Exception:
                    logger.warning(
                        "follow-up rewrite failed for conversation %s",
                        conversation_id,
                        exc_info=True,
                    )

        user_message_id = self._contexts.begin_exchange(
            conversation_id,
            product_id,
            question,
            visitor_id=visitor_id,
        )
        try:
            result = (
                AnswerResult(
                    mode=AnswerMode.CLARIFICATION,
                    text=clarification,
                    citations=(),
                    attempts=0,
                )
                if clarification is not None
                else self._service.answer(
                    rewritten,
                    product_id,
                    observer=observer,
                    risk_question=question,
                )
            )
        except Exception as exc:
            if self._answer_runs is not None:
                self._answer_runs.record_failure(
                    conversation_id=conversation_id,
                    user_message_id=user_message_id,
                    status=(
                        "cancelled"
                        if isinstance(exc, AnswerCancelled)
                        else "failed"
                    ),
                    error_type=type(exc).__name__,
                    latency_ms=(perf_counter() - started) * 1000,
                )
            self._commit()
            raise

        exchange = self._contexts.complete_exchange(
            conversation_id,
            product_id,
            user_message_id,
            result.text,
            visitor_id=visitor_id,
        )
        if self._answer_runs is not None:
            self._answer_runs.record(
                conversation_id=conversation_id,
                exchange=exchange,
                result=result,
                latency_ms=(perf_counter() - started) * 1000,
            )
        self._commit()
        return replace(
            result,
            assistant_message_id=exchange.assistant_message_id,
        )
