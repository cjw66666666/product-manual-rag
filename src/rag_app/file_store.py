from hashlib import sha256
from pathlib import Path


class Sha256FileStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def put(self, content: bytes) -> str:
        digest = sha256(content).hexdigest()
        relative = self._relative_path(digest)
        target = self._root / relative
        if target.exists():
            return relative.as_posix()

        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        return relative.as_posix()

    def read(self, storage_uri: str) -> bytes:
        relative = Path(storage_uri)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("invalid storage URI")
        target = (self._root / relative).resolve()
        if not target.is_relative_to(self._root):
            raise ValueError("storage URI escapes root")
        return target.read_bytes()

    def path_for_sha256(self, digest: str) -> Path:
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("invalid sha256")
        target = (self._root / self._relative_path(digest)).resolve()
        if not target.is_relative_to(self._root):
            raise ValueError("digest path escapes root")
        return target

    @staticmethod
    def _relative_path(digest: str) -> Path:
        return Path(digest[:2]) / digest[2:4] / f"{digest}.pdf"
