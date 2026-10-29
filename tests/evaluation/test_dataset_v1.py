import json
from pathlib import Path

import pytest

DATASETS = (
    Path("datasets/eval/v1/dev.jsonl"),
    Path("datasets/eval/v1/test.jsonl"),
)


def _load_cases(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_v1_splits_have_balanced_grounded_and_refusal_cases() -> None:
    if not all(path.exists() for path in DATASETS):
        pytest.skip("local evaluation dataset is not present")
    for path in DATASETS:
        cases = _load_cases(path)

        assert len(cases) == 30
        assert len({case["case_id"] for case in cases}) == 30
        assert sum(
            case["expected_mode"] == "manual_grounded" for case in cases
        ) == 26
        assert sum(case["expected_mode"] == "refused" for case in cases) == 4


def test_v1_evidence_contract_matches_expected_mode() -> None:
    if not all(path.exists() for path in DATASETS):
        pytest.skip("local evaluation dataset is not present")
    for path in DATASETS:
        for case in _load_cases(path):
            must_cite = case["must_cite"]
            required_facts = case["required_facts"]
            forbidden_claims = case["forbidden_claims"]
            assert isinstance(must_cite, list)
            assert isinstance(required_facts, list)
            assert isinstance(forbidden_claims, list)

            if case["expected_mode"] == "manual_grounded":
                assert must_cite
                assert required_facts
                for citation in must_cite:
                    assert isinstance(citation, dict)
                    assert isinstance(citation["page"], int)
                    assert citation["evidence_quote"]
                    assert isinstance(citation["section_path"], list)
                    assert citation["section_path"]
            else:
                assert case["expected_mode"] == "refused"
                assert must_cite == []
                assert required_facts == []
