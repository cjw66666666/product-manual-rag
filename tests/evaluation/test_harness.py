from rag_app.answering import AnswerMode, AnswerResult, Evidence
from rag_app.evaluation import (
    LatestRetrievalTrace,
    evaluate_case,
    summarize,
)
from rag_app.retrieval import (
    EvidenceHit,
    RetrievalTrace,
    SearchHit,
)


def search_hit(chunk_id: str, page: int, content: str) -> SearchHit:
    return SearchHit(chunk_id=chunk_id, content=content, page=page)


def evidence_hit(
    chunk_id: str,
    page: int,
    content: str,
    score: float = 1.0,
) -> EvidenceHit:
    return EvidenceHit(
        chunk_id=chunk_id,
        content=content,
        page=page,
        score=score,
    )


def test_evaluate_case_scores_mode_evidence_and_facts() -> None:
    case: dict[str, object] = {
        "case_id": "case-1",
        "messages": ["怎么开机？"],
        "product_id": "p1",
        "expected_mode": "manual_grounded",
        "must_cite": [{"page": 10}],
        "required_facts": ["电源键"],
    }

    def answer(
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
    ) -> AnswerResult:
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="按电源键开机。[1]",
            citations=("chunk-1",),
            attempts=1,
            evidence=(Evidence("chunk-1", "按电源键开机。", 10),),
        )

    hit = search_hit("chunk-1", 10, "按电源键开机。")
    trace = RetrievalTrace(
        dense=(hit,),
        sparse=(hit,),
        rrf=(hit,),
        reranked=(evidence_hit("chunk-1", 10, hit.content),),
        final=(evidence_hit("chunk-1", 10, hit.content),),
    )

    result = evaluate_case(case, answer, trace=trace)
    summary = summarize((result,))

    assert result.passed is True
    assert result.recall_at_20 == 1.0
    assert result.recall_at_30 == 1.0
    assert result.rrf_best_rank == 1
    assert result.rerank_best_rank == 1
    assert result.final_top_k_hit is True
    assert result.citation_hit is True
    assert summary.pass_rate == 1.0
    assert summary.recall_at_20_mean == 1.0
    assert summary.recall_at_30_mean == 1.0


def test_required_facts_normalize_symbols_and_quotes() -> None:
    case: dict[str, object] = {
        "case_id": "case-normalized-facts",
        "messages": ["显示规格和底座状态是什么？"],
        "product_id": "p1",
        "expected_mode": "manual_grounded",
        "must_cite": [{"page": 10}],
        "required_facts": ["1920 x 1080", "咔哒声"],
        "forbidden_claims": [],
    }

    def answer(
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
    ) -> AnswerResult:
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="最大分辨率为 1920 × 1080，听到“咔哒”声表示安装好。[1]",
            citations=("chunk-1",),
            attempts=1,
            evidence=(
                Evidence(
                    "chunk-1",
                    "最大分辨率 1920 x 1080，听到咔哒声表示安装好。",
                    10,
                ),
            ),
        )

    result = evaluate_case(case, answer)

    assert result.required_facts_hit is True
    assert result.passed is True


def test_evidence_quote_requires_location_to_match() -> None:
    case: dict[str, object] = {
        "case_id": "case-2",
        "messages": ["怎么连接 HDMI？"],
        "product_id": "p1",
        "expected_mode": "manual_grounded",
        "must_cite": [
            {
                "page": 4,
                "document_sha256": "a" * 64,
                "section_path": ["连接", "HDMI"],
                "evidence_quote": "通过 HDMI 线缆将显示器连接至计算机",
            }
        ],
        "required_facts": ["HDMI"],
    }

    def answer(
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
    ) -> AnswerResult:
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="使用 HDMI 线缆连接。[1]",
            citations=("chunk-1",),
            attempts=1,
            evidence=(
                Evidence(
                    "chunk-1",
                    "通过 HDMI 线缆将显示器连接至计算机等设备。",
                    4,
                    document_sha256="a" * 64,
                    section_path=("连接", "HDMI"),
                ),
            ),
        )

    result = evaluate_case(case, answer)

    assert result.citation_hit is True


def test_evidence_quote_can_declare_an_alternate_duplicate_page() -> None:
    case: dict[str, object] = {
        "case_id": "case-duplicate-page",
        "messages": ["如何安装底座？"],
        "product_id": "p1",
        "expected_mode": "manual_grounded",
        "must_cite": [
            {
                "page": 5,
                "alternate_pages": [6],
                "document_sha256": "a" * 64,
                "section_path": ["安装与拆卸显示器"],
                "evidence_quote": (
                    "将显示器立柱稍微向上抬起，然后将底座安装到立柱下端，"
                    "听到咔哒声表示已安装好。"
                ),
            }
        ],
        "required_facts": ["咔哒声"],
        "forbidden_claims": [],
    }

    def answer(
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
    ) -> AnswerResult:
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="听到“咔哒”声表示底座安装好。[1]",
            citations=("chunk-1",),
            attempts=1,
            evidence=(
                Evidence(
                    "chunk-1",
                    "将显示器立柱稍微向上抬起，然后将底座安装到立柱下端，"
                    "听到咔哒声表示已安装好。",
                    6,
                    document_sha256="a" * 64,
                    section_path=("用户指南", "安装与拆卸显示器"),
                ),
            ),
        )

    result = evaluate_case(case, answer)

    assert result.citation_hit is True
    assert result.passed is True


def test_evidence_quote_does_not_hide_wrong_page() -> None:
    case: dict[str, object] = {
        "case_id": "case-wrong-page",
        "messages": ["怎么连接 HDMI？"],
        "product_id": "p1",
        "expected_mode": "manual_grounded",
        "must_cite": [
            {
                "page": 99,
                "document_sha256": "a" * 64,
                "section_path": ["连接", "HDMI"],
                "evidence_quote": "通过 HDMI 线缆将显示器连接至计算机",
            }
        ],
        "required_facts": ["HDMI"],
        "forbidden_claims": [],
    }

    def answer(
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
    ) -> AnswerResult:
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="使用 HDMI 线缆连接。[1]",
            citations=("chunk-1",),
            attempts=1,
            evidence=(
                Evidence(
                    "chunk-1",
                    "通过 HDMI 线缆将显示器连接至计算机等设备。",
                    4,
                    document_sha256="a" * 64,
                    section_path=("连接", "HDMI"),
                ),
            ),
        )

    result = evaluate_case(case, answer)

    assert result.citation_hit is False
    assert result.passed is False


def test_evidence_location_accepts_more_specific_extracted_heading() -> None:
    case: dict[str, object] = {
        "case_id": "case-section-subset",
        "messages": ["怎么设置？"],
        "product_id": "p1",
        "expected_mode": "manual_grounded",
        "must_cite": [
            {
                "page": 92,
                "document_sha256": "a" * 64,
                "section_path": ["设置", "安全", "密码保险箱"],
                "evidence_quote": "使用密码保险箱之前，请先设置锁屏密码。",
            }
        ],
        "required_facts": ["密码保险箱"],
        "forbidden_claims": [],
    }

    def answer(
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
    ) -> AnswerResult:
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="请先设置锁屏密码。[1]",
            citations=("chunk-1",),
            attempts=1,
            evidence=(
                Evidence(
                    "chunk-1",
                    "使用密码保险箱之前，请先设置锁屏密码。",
                    92,
                    document_sha256="a" * 64,
                    section_path=(
                        "安全",
                        "使用密码保险箱，自动填充帐号和密码",
                    ),
                ),
            ),
        )

    result = evaluate_case(case, answer)

    assert result.citation_hit is True


def test_refusal_passes_without_citations() -> None:
    case: dict[str, object] = {
        "case_id": "case-3",
        "messages": ["这个型号支持某个未记录功能吗？"],
        "product_id": "p1",
        "expected_mode": "refused",
        "must_cite": [],
        "required_facts": [],
    }

    def answer(
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
    ) -> AnswerResult:
        return AnswerResult(
            mode=AnswerMode.REFUSED,
            text="当前手册没有足够依据。",
            citations=(),
            attempts=2,
        )

    result = evaluate_case(case, answer)
    summary = summarize((result,))

    assert result.passed is True
    assert result.citation_hit is True
    assert result.recall_at_20 is None
    assert summary.answerable_total == 0
    assert summary.refused_total == 1


def test_final_top_six_can_miss_even_when_rrf_recall_is_complete() -> None:
    case: dict[str, object] = {
        "case_id": "case-4",
        "messages": ["如何连接 HDMI？"],
        "product_id": "p1",
        "expected_mode": "manual_grounded",
        "must_cite": [
            {
                "page": 8,
                "evidence_quote": "将 HDMI 线缆接入显示器的 HDMI 接口",
            }
        ],
        "required_facts": ["HDMI"],
    }
    target = search_hit(
        "chunk-target",
        8,
        "将 HDMI 线缆接入显示器的 HDMI 接口。",
    )
    filler = tuple(
        search_hit(f"chunk-{index}", index, "无关内容")
        for index in range(1, 31)
    )
    reranked = tuple(
        evidence_hit(item.chunk_id, item.page, item.content)
        for item in (*filler[:19], target)
    )
    final = reranked[:6]
    trace = RetrievalTrace(
        dense=filler[:30],
        sparse=filler[:30],
        rrf=(*filler[:19], target),
        reranked=reranked,
        final=final,
    )

    def answer(
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
    ) -> AnswerResult:
        evidence = tuple(
            Evidence(item.chunk_id, item.content, item.page)
            for item in final
        )
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="请使用 HDMI 连接。[1]",
            citations=(final[0].chunk_id,),
            attempts=1,
            evidence=evidence,
        )

    result = evaluate_case(case, answer, trace=trace)

    assert result.recall_at_20 == 1.0
    assert result.recall_at_30 == 1.0
    assert result.rrf_best_rank == 20
    assert result.rerank_best_rank == 20
    assert result.final_top_k_hit is False
    assert result.citation_hit is False
    assert result.passed is False


def test_unresolvable_citation_is_counted_as_invalid() -> None:
    case: dict[str, object] = {
        "case_id": "case-5",
        "messages": ["怎么开机？"],
        "product_id": "p1",
        "expected_mode": "manual_grounded",
        "must_cite": [{"page": 10}],
        "required_facts": ["电源键"],
    }

    def answer(
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
    ) -> AnswerResult:
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="按电源键开机。[1]",
            citations=("missing-chunk",),
            attempts=1,
            evidence=(Evidence("chunk-1", "按电源键开机。", 10),),
        )

    result = evaluate_case(case, answer)

    assert result.invalid_citation_count == 1
    assert result.citation_hit is False
    assert result.passed is False


def test_trace_provider_is_read_after_the_answer_finishes() -> None:
    case: dict[str, object] = {
        "case_id": "case-6",
        "messages": ["怎么开机？"],
        "product_id": "p1",
        "expected_mode": "manual_grounded",
        "must_cite": [{"page": 10}],
        "required_facts": ["电源键"],
    }
    captured: dict[str, RetrievalTrace] = {}

    def answer(
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
    ) -> AnswerResult:
        hit = search_hit("chunk-1", 10, "按电源键开机。")
        captured["trace"] = RetrievalTrace(
            dense=(hit,),
            sparse=(hit,),
            rrf=(hit,),
            reranked=(evidence_hit("chunk-1", 10, hit.content),),
            final=(evidence_hit("chunk-1", 10, hit.content),),
        )
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="按电源键开机。[1]",
            citations=("chunk-1",),
            attempts=1,
            evidence=(Evidence("chunk-1", "按电源键开机。", 10),),
        )

    result = evaluate_case(
        case,
        answer,
        trace_fn=lambda: captured.get("trace"),
    )

    assert result.rrf_best_rank == 1
    assert result.rerank_best_rank == 1


def test_latest_retrieval_trace_keeps_only_the_last_attempt() -> None:
    recorder = LatestRetrievalTrace()
    first = search_hit("first", 1, "first")
    second = search_hit("second", 2, "second")
    recorder.record(
        RetrievalTrace(
            dense=(first,),
            sparse=(),
            rrf=(first,),
            reranked=(),
            final=(),
        )
    )
    recorder.record(
        RetrievalTrace(
            dense=(second,),
            sparse=(),
            rrf=(second,),
            reranked=(),
            final=(),
        )
    )

    assert recorder.latest is not None
    assert recorder.latest.rrf[0].chunk_id == "second"
    recorder.clear()
    assert recorder.latest is None


def test_all_required_citations_must_match() -> None:
    case: dict[str, object] = {
        "case_id": "case-multi-cite",
        "messages": ["怎么安装？"],
        "product_id": "p1",
        "expected_mode": "manual_grounded",
        "must_cite": [
            {"page": 1},
            {"page": 2},
        ],
        "required_facts": ["安装"],
        "forbidden_claims": [],
    }

    def answer(
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
    ) -> AnswerResult:
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="开始安装。[1]",
            citations=("chunk-1",),
            attempts=1,
            evidence=(Evidence("chunk-1", "开始安装。", 1),),
        )

    result = evaluate_case(case, answer)

    assert result.citation_hit is False
    assert result.passed is False


def test_forbidden_claim_fails_even_with_correct_citation() -> None:
    case: dict[str, object] = {
        "case_id": "case-forbidden",
        "messages": ["怎么开机？"],
        "product_id": "p1",
        "expected_mode": "manual_grounded",
        "must_cite": [{"page": 10}],
        "required_facts": ["电源键"],
        "forbidden_claims": ["保修三年"],
    }

    def answer(
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
    ) -> AnswerResult:
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="按电源键开机，保修三年。[1]",
            citations=("chunk-1",),
            attempts=1,
            evidence=(Evidence("chunk-1", "按电源键开机。", 10),),
        )

    result = evaluate_case(case, answer)

    assert result.forbidden_claim_hit is True
    assert result.passed is False


def test_multi_turn_case_executes_every_message_in_one_conversation() -> None:
    case: dict[str, object] = {
        "case_id": "case-multi-turn",
        "messages": ["C7 支持蓝牙吗？", "那怎么连接？"],
        "product_id": "p1",
        "expected_mode": "manual_grounded",
        "must_cite": [{"page": 10}],
        "required_facts": ["蓝牙"],
        "forbidden_claims": [],
    }
    calls: list[tuple[str, str | None]] = []

    def answer(
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
    ) -> AnswerResult:
        calls.append((question, conversation_id))
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="打开设置并连接蓝牙设备。[1]",
            citations=("chunk-1",),
            attempts=1,
            evidence=(Evidence("chunk-1", "连接蓝牙设备。", 10),),
        )

    result = evaluate_case(case, answer)

    assert [call[0] for call in calls] == [
        "C7 支持蓝牙吗？",
        "那怎么连接？",
    ]
    assert calls[0][1] == calls[1][1]
    assert calls[0][1] is not None
    assert calls[0][1].startswith("eval-case-multi-turn-")
    assert result.passed is True


def test_repeated_evaluations_start_with_fresh_conversations() -> None:
    case: dict[str, object] = {
        "case_id": "case-fresh-context",
        "messages": ["C7 支持蓝牙吗？"],
        "product_id": "p1",
        "expected_mode": "manual_grounded",
        "must_cite": [{"page": 10}],
        "required_facts": ["蓝牙"],
        "forbidden_claims": [],
    }
    conversation_ids: list[str | None] = []

    def answer(
        question: str,
        product_id: str,
        *,
        conversation_id: str | None = None,
    ) -> AnswerResult:
        conversation_ids.append(conversation_id)
        return AnswerResult(
            mode=AnswerMode.MANUAL_GROUNDED,
            text="支持蓝牙。[1]",
            citations=("chunk-1",),
            attempts=1,
            evidence=(Evidence("chunk-1", "支持蓝牙。", 10),),
        )

    evaluate_case(case, answer)
    evaluate_case(case, answer)

    assert conversation_ids[0] is not None
    assert conversation_ids[1] is not None
    assert conversation_ids[0] != conversation_ids[1]
