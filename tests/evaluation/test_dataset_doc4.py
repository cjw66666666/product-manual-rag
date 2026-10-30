import json
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path

import pymupdf
import pytest


def _normalized(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def test_doc4_dev_dataset_has_two_cases_per_file() -> None:
    root = Path(__file__).parents[2]
    dataset_root = root / "datasets" / "eval" / "doc4"
    document_root = root / "docs" / "doc4"
    if not dataset_root.exists() or not document_root.exists():
        pytest.skip("local doc4 dataset is not present")

    path = dataset_root / "dev.jsonl"
    manifest = json.loads(
        (dataset_root / "manifest.json").read_text(encoding="utf-8")
    )
    cases = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert manifest["splits"]["dev"]["cases"] == 8
    assert manifest["splits"]["dev"]["sha256"] == sha256(
        path.read_bytes()
    ).hexdigest()
    assert len(cases) == 8
    assert len({case["case_id"] for case in cases}) == 8
    assert set(Counter(case["source_file"] for case in cases).values()) == {2}

    cases_by_file: dict[str, list[dict[str, object]]] = {}
    for case in cases:
        cases_by_file.setdefault(str(case["source_file"]), []).append(case)

    for source_file, source_cases in cases_by_file.items():
        assert Counter(case["case_type"] for case in source_cases) == {
            "normal": 1,
            "safety": 1,
        }
        assert len({case["product_id"] for case in source_cases}) == 1
        document_path = document_root / source_file
        assert document_path.exists()
        document_sha256 = sha256(document_path.read_bytes()).hexdigest()
        with pymupdf.open(document_path) as document:  # type: ignore[no-untyped-call]
            for case in source_cases:
                assert case["expected_mode"] == "manual_grounded"
                citations = case["must_cite"]
                assert isinstance(citations, list)
                assert len(citations) == 1
                citation = citations[0]
                assert isinstance(citation, dict)
                assert citation["document_sha256"] == document_sha256
                page_number = citation["page"]
                quote = citation["evidence_quote"]
                assert isinstance(page_number, int)
                assert isinstance(quote, str)
                page_text = " ".join(
                    document[page_number - 1].get_text("text").split()
                )
                assert _normalized(quote) in _normalized(page_text)
                facts = case["required_facts"]
                assert isinstance(facts, list)
                assert facts
                assert all(
                    _normalized(str(fact)) in _normalized(quote)
                    for fact in facts
                )
