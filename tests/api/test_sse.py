import json
from time import sleep

import httpx
import pytest

from rag_app.answering import (
    AnswerMode,
    AnswerObserver,
    AnswerResult,
    Evidence,
)
from rag_app.api.app import create_app
from rag_app.catalog import Product, ProductCategory


class FakeAnswerService:
    def conversation_product(
        self,
        conversation_id: str,
        *,
        visitor_id: str | None = None,
    ) -> str | None:
        return None

    def answer(
        self,
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
        observer: AnswerObserver | None = None,
        visitor_id: str | None = None,
    ) -> AnswerResult:
        assert question == "怎么开机？"
        assert product_id == "huawei_c7"
        assert conversation_id == "conversation-1"
        self._observe(observer)
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="按电源键。[1]",
            citations=("chunk-1",),
            attempts=1,
            evidence=(
                Evidence(
                    "chunk-1",
                    "按电源键开机。",
                    3,
                    product_id="huawei_c7",
                    document_version_id="version-1",
                    index_version_id="index-1",
                    document_sha256="a" * 64,
                    document_name="C7 manual.pdf",
                    version_label="2.1",
                    section_path=("基础使用", "开机"),
                ),
            ),
        )

    @staticmethod
    def _observe(observer: AnswerObserver | None) -> None:
        if observer is None:
            return
        for stage in (
            "retrieving",
            "reranking",
            "generating",
            "verifying",
        ):
            observer.stage(stage)
            observer.check_cancelled()


class InferredProductAnswerService:
    def conversation_product(
        self,
        conversation_id: str,
        *,
        visitor_id: str | None = None,
    ) -> str | None:
        return None

    def answer(
        self,
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
        observer: AnswerObserver | None = None,
        visitor_id: str | None = None,
    ) -> AnswerResult:
        assert "C7" in question
        assert product_id == "huawei_c7"
        assert conversation_id == "conversation-1"
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="按电源键。[1]",
            citations=("chunk-1",),
            attempts=1,
            evidence=(Evidence("chunk-1", "按电源键开机。", 3),),
        )


class FailingAnswerService:
    def conversation_product(
        self,
        conversation_id: str,
        *,
        visitor_id: str | None = None,
    ) -> str | None:
        return None

    def answer(
        self,
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
        observer: AnswerObserver | None = None,
        visitor_id: str | None = None,
    ) -> AnswerResult:
        raise RuntimeError("provider timeout")


class SlowAnswerService(FakeAnswerService):
    def answer(
        self,
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
        observer: AnswerObserver | None = None,
        visitor_id: str | None = None,
    ) -> AnswerResult:
        if observer is not None:
            observer.stage("retrieving")
            observer.check_cancelled()
        sleep(0.05)
        return super().answer(
            question,
            product_id,
            conversation_id=conversation_id,
            observer=observer,
            visitor_id=visitor_id,
        )


class ConversationProductAnswerService(FakeAnswerService):
    def conversation_product(
        self,
        conversation_id: str,
        *,
        visitor_id: str | None = None,
    ) -> str | None:
        assert conversation_id == "conversation-1"
        return "huawei_c7"

    def answer(
        self,
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
        observer: AnswerObserver | None = None,
        visitor_id: str | None = None,
    ) -> AnswerResult:
        assert question == "那怎么连接？"
        assert product_id == "huawei_c7"
        assert conversation_id == "conversation-1"
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="打开设置并连接蓝牙设备。[1]",
            citations=("chunk-1",),
            attempts=1,
            evidence=(Evidence("chunk-1", "连接蓝牙设备。", 10),),
        )


class SwitchingProductAnswerService(FakeAnswerService):
    def conversation_product(
        self,
        conversation_id: str,
        *,
        visitor_id: str | None = None,
    ) -> str | None:
        return "huawei_c7"

    def answer(
        self,
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
        observer: AnswerObserver | None = None,
        visitor_id: str | None = None,
    ) -> AnswerResult:
        assert "B5-440" in question
        assert product_id == "huawei_b5_440"
        return AnswerResult(
            mode=AnswerMode.REFUSED,
            text="insufficient evidence",
            citations=(),
            attempts=2,
        )


@pytest.mark.asyncio
async def test_sse_emits_answer_only_after_verified_service_result() -> None:
    transport = httpx.ASGITransport(
        app=create_app(answer_service=FakeAnswerService())
    )
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/conversations/conversation-1/messages/stream",
            json={
                "question": "怎么开机？",
                "product_id": "huawei_c7",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [
        line.removeprefix("event: ")
        for line in response.text.splitlines()
        if line.startswith("event: ")
    ]
    assert events == [
        "run_started",
        "product_resolved",
        "status",
        "status",
        "status",
        "status",
        "answer_delta",
        "citations",
        "done",
    ]
    stages = [
        json.loads(line.split("data: ", 1)[1])["stage"]
        for line in response.text.splitlines()
        if line.startswith("data: ") and '"stage"' in line
    ]
    assert stages == [
        "retrieving",
        "reranking",
        "generating",
        "verifying",
    ]
    done_data = response.text.split("event: done\ndata: ", 1)[1].split("\n", 1)[0]
    assert json.loads(done_data)["mode"] == "manual_grounded"
    citations_data = response.text.split(
        "event: citations\ndata: ",
        1,
    )[1].split("\n", 1)[0]
    assert json.loads(citations_data)["items"][0]["page"] == 3
    citation = json.loads(citations_data)["items"][0]
    assert citation["document_sha256"] == "a" * 64
    assert citation["document_name"] == "C7 manual.pdf"
    assert citation["version_label"] == "2.1"
    assert citation["section_path"] == ["基础使用", "开机"]


@pytest.mark.asyncio
async def test_sse_infers_product_from_question() -> None:
    product = Product(
        "huawei_c7",
        "华为平板 C7",
        ProductCategory.TABLET,
        ("C7", "DBY-W09"),
    )
    transport = httpx.ASGITransport(
        app=create_app(
            products=(product,),
            answer_service=InferredProductAnswerService(),
        )
    )
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/conversations/conversation-1/messages/stream",
            json={"question": "怎么开机？C7"},
        )

    assert response.status_code == 200
    assert '"source": "inferred"' in response.text


@pytest.mark.asyncio
async def test_sse_reports_answer_service_failure() -> None:
    transport = httpx.ASGITransport(
        app=create_app(answer_service=FailingAnswerService())
    )
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/conversations/test/messages/stream",
            json={"question": "怎么开机？", "product_id": "huawei_c7"},
        )

    assert response.status_code == 200
    assert "event: error" in response.text
    assert "provider timeout" not in response.text
    assert "answer generation failed" in response.text


@pytest.mark.asyncio
async def test_sse_emits_heartbeat_while_answer_is_pending() -> None:
    transport = httpx.ASGITransport(
        app=create_app(
            answer_service=SlowAnswerService(),
            sse_heartbeat_seconds=0.01,
        )
    )
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/conversations/conversation-1/messages/stream",
            json={
                "question": "怎么开机？",
                "product_id": "huawei_c7",
            },
        )

    assert ": keep-alive" in response.text


@pytest.mark.asyncio
async def test_sse_uses_product_from_existing_conversation() -> None:
    transport = httpx.ASGITransport(
        app=create_app(
            answer_service=ConversationProductAnswerService(),
        )
    )
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/conversations/conversation-1/messages/stream",
            json={"question": "那怎么连接？"},
        )

    assert response.status_code == 200
    assert '"source": "conversation"' in response.text


@pytest.mark.asyncio
async def test_sse_prefers_explicit_product_over_conversation_product() -> None:
    products = (
        Product(
            "huawei_c7",
            "华为平板 C7",
            ProductCategory.TABLET,
            ("C7",),
        ),
        Product(
            "huawei_b5_440",
            "HUAWEI MateBook B5-440",
            ProductCategory.LAPTOP,
            ("B5-440",),
        ),
    )
    transport = httpx.ASGITransport(
        app=create_app(
            products=products,
            answer_service=SwitchingProductAnswerService(),
        )
    )
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/conversations/conversation-1/messages/stream",
            json={"question": "MateBook B5-440 怎么开机？"},
        )

    assert response.status_code == 200
    assert '"product_id": "huawei_b5_440"' in response.text


@pytest.mark.asyncio
async def test_sse_rate_limits_public_messages() -> None:
    transport = httpx.ASGITransport(
        app=create_app(
            answer_service=FakeAnswerService(),
            max_requests_per_minute=1,
        )
    )
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        request = {
            "question": "怎么开机？",
            "product_id": "huawei_c7",
        }
        first = await client.post(
            "/api/conversations/conversation-1/messages/stream",
            json=request,
        )
        second = await client.post(
            "/api/conversations/conversation-1/messages/stream",
            json=request,
        )

    assert first.status_code == 200
    assert second.status_code == 429
