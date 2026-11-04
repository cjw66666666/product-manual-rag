import json
from pathlib import Path
from typing import Any

import pytest

DATASET = Path("datasets/eval/v1/dev.jsonl")


def load_cases() -> dict[str, dict[str, Any]]:
    if not DATASET.exists():
        pytest.skip("local v1 development dataset is not present")
    return {
        case["case_id"]: case
        for case in (
            json.loads(line)
            for line in DATASET.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }


def test_c7_charging_case_targets_charging_instructions() -> None:
    case = load_cases()["huawei_c7-002"]

    assert "使用充电器充电" in case["reference_answer"]
    assert "低电量" not in case["must_cite"][0]["evidence_quote"]


def test_hm740_system_settings_case_targets_system_sidebar() -> None:
    case = load_cases()["huawei_hm740-004"]
    citation = case["must_cite"][0]

    assert citation["page"] == 173
    assert "单击左侧边栏的系统" in citation["evidence_quote"]
    assert "键盘" not in citation["evidence_quote"]


def test_hm740_power_on_case_accepts_fingerprint_power_key_evidence() -> None:
    case = load_cases()["huawei_hm740-001"]
    citation = case["must_cite"][0]

    assert citation["page"] == 20
    assert "短按此键，将电脑开机或唤醒" in citation["evidence_quote"]
