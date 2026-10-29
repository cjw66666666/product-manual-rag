import asyncio
import json
import logging
import secrets
import threading
from collections import deque
from collections.abc import AsyncIterator, Callable, Sequence
from time import monotonic
from typing import Protocol
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rag_app.answering import AnswerCancelled, AnswerObserver, AnswerResult
from rag_app.catalog import MatchStatus, Product, ProductCatalog

logger = logging.getLogger(__name__)


class AnswerService(Protocol):
    def conversation_product(
        self,
        conversation_id: str,
        *,
        visitor_id: str | None = None,
    ) -> str | None: ...

    def answer(
        self,
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
        observer: AnswerObserver | None = None,
        visitor_id: str | None = None,
    ) -> AnswerResult: ...


class MessageRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    product_id: str | None = None


def _event(name: str, data: dict[str, object]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {name}\ndata: {payload}\n\n"


class _QueueObserver:
    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        stages: asyncio.Queue[str],
        cancelled: threading.Event,
    ) -> None:
        self._loop = loop
        self._stages = stages
        self._cancelled = cancelled

    def stage(self, stage: str) -> None:
        self.check_cancelled()
        self._loop.call_soon_threadsafe(self._stages.put_nowait, stage)

    def check_cancelled(self) -> None:
        if self._cancelled.is_set():
            raise AnswerCancelled("client disconnected")


class _RateLimiter:
    def __init__(
        self,
        *,
        max_requests: int,
        window_seconds: float = 60.0,
    ) -> None:
        if max_requests < 1 or window_seconds <= 0:
            raise ValueError("invalid rate limit")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            timestamps = self._requests.setdefault(key, deque())
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()
            if len(timestamps) >= self._max_requests:
                return False
            timestamps.append(now)
            return True


def build_sse_router(
    service: AnswerService | None,
    products: tuple[Product, ...],
    *,
    product_loader: Callable[[], Sequence[Product]] | None = None,
    heartbeat_seconds: float = 15.0,
    max_requests_per_minute: int = 20,
) -> APIRouter:
    if heartbeat_seconds <= 0:
        raise ValueError("heartbeat_seconds must be positive")
    router = APIRouter(prefix="/api", tags=["conversations"])
    rate_limiter = _RateLimiter(
        max_requests=max_requests_per_minute,
    )

    @router.post(
        "/conversations/{conversation_id}/messages/stream",
    )
    async def stream_message(
        conversation_id: str,
        payload: MessageRequest,
        request: Request,
    ) -> StreamingResponse:
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="answer service is not configured",
            )
        client_host = request.client.host if request.client else "unknown"
        if not rate_limiter.allow(client_host):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="too many requests",
            )

        visitor_id = (
            request.cookies.get("rag_visitor_id")
            or request.headers.get("X-Visitor-ID")
            or secrets.token_urlsafe(32)
        )
        try:
            conversation_product = service.conversation_product(
                conversation_id,
                visitor_id=visitor_id,
            )
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="conversation access denied",
            ) from exc

        product_id = payload.product_id
        resolution_source = "provided"
        if not product_id:
            available_products = (
                product_loader() if product_loader is not None else products
            )
            catalog = (
                ProductCatalog(available_products)
                if available_products
                else None
            )
            match = catalog.resolve(payload.question) if catalog else None
            if match is not None and match.status is MatchStatus.RESOLVED:
                product_id = match.products[0].id
                resolution_source = "inferred"
            elif match is not None and match.status is MatchStatus.AMBIGUOUS:
                candidates = (
                    [
                        {
                            "id": product.id,
                            "display_name": product.display_name,
                        }
                        for product in match.products
                    ]
                    if match is not None
                    else []
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "message": "请选择产品或在问题中写明型号",
                        "candidates": candidates,
                    },
                )
            else:
                product_id = conversation_product
                if product_id:
                    resolution_source = "conversation"
        if not product_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "请选择产品或在问题中写明型号",
                    "candidates": [],
                },
            )

        run_id = uuid4().hex

        async def events() -> AsyncIterator[str]:
            stage_queue: asyncio.Queue[str] = asyncio.Queue()
            cancelled = threading.Event()
            observer = _QueueObserver(
                loop=asyncio.get_running_loop(),
                stages=stage_queue,
                cancelled=cancelled,
            )
            answer_task = asyncio.create_task(
                asyncio.to_thread(
                    service.answer,
                    payload.question,
                    product_id,
                    conversation_id=conversation_id,
                    observer=observer,
                    visitor_id=visitor_id,
                )
            )
            yield _event("run_started", {"run_id": run_id})
            yield _event(
                "product_resolved",
                {
                    "product_id": product_id,
                    "source": resolution_source,
                },
            )
            stage_task = asyncio.create_task(stage_queue.get())
            try:
                while not answer_task.done():
                    done, _ = await asyncio.wait(
                        {answer_task, stage_task},
                        timeout=heartbeat_seconds,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if stage_task in done:
                        yield _event(
                            "status",
                            {"stage": stage_task.result()},
                        )
                        stage_task = asyncio.create_task(
                            stage_queue.get()
                        )
                    if not done:
                        yield ": keep-alive\n\n"

                await asyncio.sleep(0)
                if stage_task.done() and not stage_task.cancelled():
                    yield _event(
                        "status",
                        {"stage": stage_task.result()},
                    )
                else:
                    stage_task.cancel()
                    await asyncio.gather(
                        stage_task,
                        return_exceptions=True,
                    )
                while not stage_queue.empty():
                    yield _event(
                        "status",
                        {"stage": stage_queue.get_nowait()},
                    )
                result = await answer_task
            except AnswerCancelled:
                return
            except asyncio.CancelledError:
                cancelled.set()
                answer_task.cancel()
                raise
            except Exception:
                logger.exception(
                    "answer service failed for conversation %s",
                    conversation_id,
                )
                yield _event(
                    "error",
                    {
                        "code": "answer_generation_failed",
                        "message": "answer generation failed",
                    },
                )
                return
            finally:
                if not answer_task.done():
                    cancelled.set()
                    answer_task.cancel()

            evidence_by_id = {
                item.chunk_id: item for item in result.evidence
            }
            citations = [
                {
                    "chunk_id": chunk_id,
                    "page": evidence_by_id[chunk_id].page,
                    "content": evidence_by_id[chunk_id].content,
                    "product_id": evidence_by_id[chunk_id].product_id,
                    "document_version_id": evidence_by_id[
                        chunk_id
                    ].document_version_id,
                    "index_version_id": evidence_by_id[
                        chunk_id
                    ].index_version_id,
                    "document_sha256": evidence_by_id[
                        chunk_id
                    ].document_sha256,
                    "document_name": evidence_by_id[
                        chunk_id
                    ].document_name,
                    "version_label": evidence_by_id[
                        chunk_id
                    ].version_label,
                    "section_path": list(
                        evidence_by_id[chunk_id].section_path
                    ),
                }
                for chunk_id in result.citations
                if chunk_id in evidence_by_id
            ]
            for offset in range(0, len(result.text), 80):
                yield _event(
                    "answer_delta",
                    {"text": result.text[offset : offset + 80]},
                )
            yield _event("citations", {"items": citations})
            yield _event(
                "done",
                {
                    "mode": result.mode.value,
                    "attempts": result.attempts,
                    "conversation_id": conversation_id,
                    "message_id": result.assistant_message_id,
                },
            )

        response = StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
        response.set_cookie(
            "rag_visitor_id",
            visitor_id,
            max_age=365 * 24 * 60 * 60,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
        )
        return response

    return router
