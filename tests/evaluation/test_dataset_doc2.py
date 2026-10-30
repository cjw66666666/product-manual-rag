import json
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path

import pymupdf
import pytest


def _normalized(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def test_doc2_dev_dataset_has_six_cases_per_file() -> None:
    root = Path(__file__).parents[2]
    dataset_root = root / "datasets" / "eval" / "doc2"
    document_root = root / "docs" / "doc2"
    if not dataset_root.exists() or not document_root.exists():
        pytest.skip("local doc2 dataset is not present")

    path = dataset_root / "dev.jsonl"
    manifest = json.loads(
        (dataset_root / "manifest.json").read_text(encoding="utf-8")
    )
    cases = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert manifest["splits"]["dev"]["cases"] == 30
    assert manifest["splits"]["dev"]["sha256"] == sha256(
        path.read_bytes()
    ).hexdigest()
    assert len(cases) == 30
    assert len({case["case_id"] for case in cases}) == 30
    assert set(Counter(case["source_file"] for case in cases).values()) == {6}

    cases_by_file: dict[str, list[dict[str, object]]] = {}
    for case in cases:
        cases_by_file.setdefault(str(case["source_file"]), []).append(case)

    for source_file, source_cases in cases_by_file.items():
        document_path = document_root / source_file
        assert document_path.exists()
        document_sha256 = sha256(document_path.read_bytes()).hexdigest()
        with pymupdf.open(document_path) as document:  # type: ignore[no-untyped-call]
            for case in source_cases:
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
