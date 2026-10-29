import json
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path("datasets/eval/v2")


def _load_cases(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _messages(case: dict[str, object]) -> list[object]:
    messages = case["messages"]
    assert isinstance(messages, list)
    return messages


def test_v2_manifest_matches_frozen_files() -> None:
    if not ROOT.exists():
        pytest.skip("local evaluation dataset is not present")
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["usage"] == "locked_test_only"
    for split, metadata in manifest["splits"].items():
        path = ROOT / f"{split}.jsonl"
        cases = _load_cases(path)
        assert len(cases) == metadata["cases"] == 36
        assert sha256(path.read_bytes()).hexdigest() == metadata["sha256"]
        assert all(
            case["dataset_version"] == "v2-frozen"
            for case in cases
        )


def test_v2_has_general_and_multiturn_coverage() -> None:
    if not ROOT.exists():
        pytest.skip("local evaluation dataset is not present")
    for split in ("dev", "test"):
        cases = _load_cases(ROOT / f"{split}.jsonl")
        assert sum(
            len(_messages(case)) > 1 for case in cases
        ) >= 6
        assert any(
            case["expected_mode"] == "general_explanation"
            for case in cases
        )
