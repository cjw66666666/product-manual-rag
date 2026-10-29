import json
from pathlib import Path

import pytest


def load_cases(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_seed_dataset_has_balanced_splits() -> None:
    root = Path("datasets/eval/v0")
    if not root.exists():
        pytest.skip("local evaluation dataset is not present")
    dev = load_cases(root / "dev.jsonl")
    test = load_cases(root / "test.jsonl")

    assert len(dev) == 30
    assert len(test) == 30
    assert len({case["case_id"] for case in dev + test}) == 60
    assert {case["product_id"] for case in dev + test} == {
        "huawei_c7",
        "huawei_c5e_gen4",
        "huawei_b5_440",
        "huawei_hm740",
        "huawei_b5_341w",
        "huawei_m272q",
    }
