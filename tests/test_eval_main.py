import json
from hashlib import sha256
from pathlib import Path

import pytest

from rag_app.eval_main import (
    _record_case_scores,
    _verify_dataset_manifest,
)
from rag_app.evaluation import CaseResult


class RecordingScoreSink:
    def __init__(self) -> None:
        self.scores: list[tuple[str, str, float | bool]] = []

    def score_trace(
        self,
        *,
        trace_id: str,
        name: str,
        value: float | bool,
    ) -> None:
        self.scores.append((trace_id, name, value))


def test_evaluation_scores_are_attached_to_answer_trace() -> None:
    sink = RecordingScoreSink()
    result = CaseResult(
        case_id="case-1",
        expected_mode="manual_grounded",
        mode_match=True,
        required_facts_hit=True,
        citation_count=2,
        invalid_citation_count=0,
        latency_ms=123.0,
        passed=True,
        answer="answer",
        expected_pages=(10,),
        cited_pages=(10,),
        citation_hit=True,
        recall_at_20=1.0,
        recall_at_30=1.0,
        rrf_best_rank=1,
        rerank_best_rank=1,
        final_top_k_hit=True,
    )

    _record_case_scores(
        sink=sink,
        trace_id="trace-1",
        result=result,
    )

    scores = {name: value for _, name, value in sink.scores}
    assert scores["case_passed"] is True
    assert scores["recall_at_20"] == 1.0
    assert scores["recall_at_30"] == 1.0
    assert scores["final_top_k_hit"] is True
    assert scores["latency_ms"] == 123.0
    assert all(trace_id == "trace-1" for trace_id, _, _ in sink.scores)


def test_locked_manifest_rejects_dev_tuning(tmp_path: Path) -> None:
    dataset = tmp_path / "dev.jsonl"
    dataset.write_text("{}\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({
            "usage": "locked_test_only",
            "splits": {
                "dev": {
                    "cases": 1,
                    "sha256": sha256(dataset.read_bytes()).hexdigest(),
                }
            },
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="only be used"):
        _verify_dataset_manifest(
            dataset_path=dataset,
            split="dev",
            manifest_path=manifest,
        )
