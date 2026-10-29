from pathlib import Path

from rag_app.file_store import Sha256FileStore


def test_file_store_is_content_addressed_and_idempotent(tmp_path: Path) -> None:
    store = Sha256FileStore(tmp_path)

    first = store.put(b"%PDF-1.7 content")
    second = store.put(b"%PDF-1.7 content")

    assert first == second
    assert store.read(first) == b"%PDF-1.7 content"
