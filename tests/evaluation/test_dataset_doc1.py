import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

import pytest


def test_doc1_dev_dataset_has_six_cases_per_file() -> None:
    root = Path(__file__).parents[2] / "datasets" / "eval" / "doc1"
    if not root.exists():
        pytest.skip("local evaluation dataset is not present")
    path = root / "dev.jsonl"
    manifest = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
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
    assert set(Counter(case["product_id"] for case in cases).values()) == {6}
    assert all(case["split"] == "dev" for case in cases)
    assert all(case["must_cite"] for case in cases)
    assert all(
        citation["evidence_quote"]
        for case in cases
        for citation in case["must_cite"]
    )
