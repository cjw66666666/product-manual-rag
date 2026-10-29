import argparse
import json
import logging
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import cast

import httpx
from qdrant_client import QdrantClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rag_app.bootstrap import build_answer_service
from rag_app.evaluation import (
    CaseResult,
    LatestRetrievalTrace,
    evaluate_case,
    summarize,
)
from rag_app.observability import (
    CapturingTraceSink,
    LangfuseTraceSink,
    TracedAnswerService,
    TraceScoreSink,
    build_langfuse_sink,
)
from rag_app.settings import Settings

logger = logging.getLogger(__name__)


def _load_cases(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _verify_dataset_manifest(
    *,
    dataset_path: Path,
    split: str,
    manifest_path: Path,
) -> dict[str, object]:
    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("dataset manifest must be an object")
    manifest = cast(dict[str, object], parsed)
    splits = manifest.get("splits")
    if not isinstance(splits, dict):
        raise ValueError("dataset manifest has no splits")
    metadata = splits.get(split)
    if not isinstance(metadata, dict):
        raise ValueError(f"dataset manifest has no {split} split")
    if manifest.get("usage") == "locked_test_only" and split != "test":
        raise ValueError(
            "locked dataset may only be used for test evaluation"
        )
    expected_hash = metadata.get("sha256")
    expected_cases = metadata.get("cases")
    if (
        not isinstance(expected_hash, str)
        or not isinstance(expected_cases, int)
    ):
        raise ValueError("dataset manifest metadata is invalid")
    if sha256(dataset_path.read_bytes()).hexdigest() != expected_hash:
        raise ValueError("dataset checksum does not match manifest")
    actual_cases = sum(
        bool(line.strip())
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
    )
    if actual_cases != expected_cases:
        raise ValueError("dataset case count does not match manifest")
    return manifest


def _record_case_scores(
    *,
    sink: TraceScoreSink,
    trace_id: str,
    result: CaseResult,
) -> None:
    scores: list[tuple[str, float | bool]] = [
        ("case_passed", result.passed),
        ("mode_match", result.mode_match),
        ("required_facts_hit", result.required_facts_hit),
        ("citation_hit", result.citation_hit),
        ("latency_ms", result.latency_ms),
        ("invalid_citation_count", float(result.invalid_citation_count)),
        ("forbidden_claim_hit", result.forbidden_claim_hit),
    ]
    if result.recall_at_20 is not None:
        scores.append(("recall_at_20", result.recall_at_20))
    if result.recall_at_30 is not None:
        scores.append(("recall_at_30", result.recall_at_30))
    if result.final_top_k_hit is not None:
        scores.append(("final_top_k_hit", result.final_top_k_hit))

    for name, value in scores:
        try:
            sink.score_trace(
                trace_id=trace_id,
                name=name,
                value=value,
            )
        except Exception:
            logger.warning(
                "failed to record Langfuse score %s",
                name,
                exc_info=True,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run RAG evaluation")
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--dataset-version", default="v4")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    settings = Settings()
    dataset_path = Path(
        f"datasets/eval/{args.dataset_version}/{args.split}.jsonl"
    )
    if not dataset_path.exists():
        parser.error(f"evaluation dataset not found: {dataset_path}")
    manifest_path = dataset_path.parent / "manifest.json"
    if manifest_path.exists():
        try:
            _verify_dataset_manifest(
                dataset_path=dataset_path,
                split=args.split,
                manifest_path=manifest_path,
            )
        except ValueError as exc:
            parser.error(str(exc))
    cases = _load_cases(dataset_path)
    if args.limit:
        cases = cases[: args.limit]
    engine = create_engine(settings.database_url)
    qdrant = QdrantClient(url=settings.qdrant_url)
    retrieval_trace = LatestRetrievalTrace()
    trace_sink = build_langfuse_sink(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    capturing_sink = CapturingTraceSink(delegate=trace_sink)

    with (
        Session(engine) as session,
        httpx.Client(timeout=180) as http_client,
    ):
        service = build_answer_service(
            settings=settings,
            session=session,
            qdrant=qdrant,
            http_client=http_client,
            index_version_id=settings.index_version_id,
            retrieval_observer=retrieval_trace,
        )
        traced_service = TracedAnswerService(
            service=service,
            sink=capturing_sink,
        )
        results_list = []
        for case in cases:
            retrieval_trace.clear()
            case_result = evaluate_case(
                case,
                traced_service.answer,
                trace_fn=lambda: retrieval_trace.latest,
            )
            if capturing_sink.latest_trace_id is not None:
                _record_case_scores(
                    sink=trace_sink,
                    trace_id=capturing_sink.latest_trace_id,
                    result=case_result,
                )
            results_list.append(case_result)
        results = tuple(results_list)
        if isinstance(trace_sink, LangfuseTraceSink):
            trace_sink.flush()

    summary = summarize(results)
    report = {
        "dataset_version": (
            str(cases[0]["dataset_version"]) if cases else "empty"
        ),
        "split": args.split,
        "summary": asdict(summary),
        "cases": [asdict(result) for result in results],
    }
    output = args.output or Path(
        f"reports/eval-{args.split}-v2.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    print(f"report={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
