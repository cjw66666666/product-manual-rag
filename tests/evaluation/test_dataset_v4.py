import json
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path("datasets/eval/v4")


def test_v4_manifest_matches_frozen_files() -> None:
    if not ROOT.exists():
        pytest.skip("local evaluation dataset is not present")
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["dataset_version"] == "v4-frozen"
    assert manifest["usage"] == "dev_and_locked_test"
    for split, metadata in manifest["splits"].items():
        path = ROOT / f"{split}.jsonl"
        assert sha256(path.read_bytes()).hexdigest() == metadata["sha256"]
        cases = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(cases) == metadata["cases"] == 36
        assert all(
            case["dataset_version"] == "v4-frozen"
            for case in cases
        )
