from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class PdfTextBlock:
    text: str
    kind: Literal["heading", "paragraph", "warning"] = "paragraph"
    heading_level: int = 1


@dataclass(frozen=True, slots=True)
class ParsedPage:
    page: int
    text: str
    text_char_count: int
    has_images: bool = False
    ocr_used: bool = False
    blocks: tuple[PdfTextBlock, ...] = ()


@dataclass(frozen=True, slots=True)
class PdfParseResult:
    pages: tuple[ParsedPage, ...]


class PdfParser(Protocol):
    def parse(self, path: Path) -> PdfParseResult: ...
