import json
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path("datasets/eval/v3")


def test_v3_manifest_matches_frozen_files() -> None:
    if not ROOT.exists():
        pytest.skip("local evaluation dataset is not present")
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["dataset_version"] == "v3-frozen"
    assert manifest["usage"] == "locked_test_only"
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
            case["dataset_version"] == "v3-frozen"
            for case in cases
        )
