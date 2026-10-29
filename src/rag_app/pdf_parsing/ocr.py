import shutil
import subprocess
from collections.abc import Sequence
from typing import Protocol


class OcrEngine(Protocol):
    @property
    def available(self) -> bool: ...

    def image_to_text(self, image: bytes) -> str: ...


class TesseractOcrEngine:
    def __init__(
        self,
        *,
        command: str = "tesseract",
        languages: Sequence[str] = ("chi_sim", "eng"),
    ) -> None:
        self._executable = shutil.which(command)
        self._languages = "+".join(languages)

    @property
    def available(self) -> bool:
        return self._executable is not None

    def image_to_text(self, image: bytes) -> str:
        if self._executable is None:
            return ""
        try:
            result = subprocess.run(
                [
                    self._executable,
                    "stdin",
                    "stdout",
                    "-l",
                    self._languages,
                ],
                input=image,
                capture_output=True,
                check=True,
                timeout=120,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return result.stdout.decode("utf-8", errors="replace").strip()
