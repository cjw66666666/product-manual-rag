import re
from pathlib import Path
from typing import Any, cast

import pymupdf

from rag_app.pdf_parsing.models import (
    ParsedPage,
    PdfParseResult,
    PdfTextBlock,
)
from rag_app.pdf_parsing.ocr import OcrEngine, TesseractOcrEngine

_STEP_PREFIX = re.compile(r"^\s*(?:\d+\s+|[•●▪])")
_SENTENCE_ENDINGS = ("。", "！", "？", "；", "：")


class PyMuPdfParser:
    def __init__(
        self,
        *,
        ocr_engine: OcrEngine | None = None,
        ocr_min_chars: int = 20,
    ) -> None:
        if ocr_min_chars < 0:
            raise ValueError("ocr_min_chars cannot be negative")
        self._ocr_engine = ocr_engine or TesseractOcrEngine()
        self._ocr_min_chars = ocr_min_chars

    def parse(self, path: Path) -> PdfParseResult:
        if path.suffix.casefold() != ".pdf":
            raise ValueError("only PDF files are supported")
        if not path.is_file():
            raise FileNotFoundError(path)

        page_records: list[
            tuple[str, bool, bool, tuple[tuple[str, float, bool], ...]]
        ] = []
        with pymupdf.open(path) as document:  # type: ignore[no-untyped-call]
            for page in document:
                text = page.get_text("text")
                has_images = bool(page.get_images(full=True))
                ocr_used = False
                raw_blocks = _text_blocks(page)
                if (
                    len(text.strip()) < self._ocr_min_chars
                    and has_images
                    and self._ocr_engine.available
                ):
                    pixmap = page.get_pixmap(
                        matrix=pymupdf.Matrix(2, 2),  # type: ignore[no-untyped-call]
                        alpha=False,
                    )
                    ocr_text = self._ocr_engine.image_to_text(
                        pixmap.tobytes("png")
                    )
                    if ocr_text:
                        text = "\n".join(
                            item for item in (text, ocr_text) if item.strip()
                        )
                        ocr_used = True
                        raw_blocks = (*raw_blocks, (ocr_text, 0.0, False))
                page_records.append((text, has_images, ocr_used, raw_blocks))

        heading_levels = _heading_levels(
            tuple(
                block
                for _, _, _, raw_blocks in page_records
                for block in raw_blocks
            )
        )
        pages = tuple(
            ParsedPage(
                page=index,
                text=text,
                text_char_count=len(text),
                has_images=has_images,
                ocr_used=ocr_used,
                blocks=_classified_blocks(
                    raw_blocks,
                    heading_levels=heading_levels,
                ),
            )
            for index, (
                text,
                has_images,
                ocr_used,
                raw_blocks,
            ) in enumerate(page_records, start=1)
        )
        return PdfParseResult(pages=tuple(pages))


def _text_blocks(
    page: Any,
) -> tuple[tuple[str, float, bool], ...]:
    data = cast(dict[str, object], page.get_text("dict"))
    raw_blocks = data.get("blocks")
    if not isinstance(raw_blocks, list):
        return ()
    result: list[tuple[str, float, bool]] = []
    for block in raw_blocks:
        if not isinstance(block, dict):
            continue
        record = cast(dict[str, object], block)
        if record.get("type") != 0:
            continue
        lines = record.get("lines")
        if not isinstance(lines, list):
            continue
        texts: list[str] = []
        sizes: list[float] = []
        bold = False
        for line in lines:
            if not isinstance(line, dict):
                continue
            spans = cast(dict[str, object], line).get("spans")
            if not isinstance(spans, list):
                continue
            for span in spans:
                if not isinstance(span, dict):
                    continue
                span_record = cast(dict[str, object], span)
                value = span_record.get("text")
                if isinstance(value, str):
                    texts.append(value)
                size = span_record.get("size")
                if isinstance(size, int | float):
                    sizes.append(float(size))
                flags = span_record.get("flags")
                if isinstance(flags, int) and flags & 16:
                    bold = True
        text = "".join(texts).strip()
        if text:
            result.append(
                (text, max(sizes, default=0.0), bold)
            )
    return tuple(result)


def _classified_blocks(
    raw_blocks: tuple[tuple[str, float, bool], ...],
    *,
    heading_levels: dict[float, int] | None = None,
) -> tuple[PdfTextBlock, ...]:
    levels = heading_levels or _heading_levels(raw_blocks)
    warning_terms = ("危险", "警告", "注意", "严禁", "禁止")
    blocks: list[PdfTextBlock] = []
    for text, size, _bold in raw_blocks:
        rounded_size = round(size, 1)
        is_heading = (
            rounded_size in levels
            and _STEP_PREFIX.match(text) is None
            and not text.rstrip().endswith(_SENTENCE_ENDINGS)
        )
        if is_heading:
            blocks.append(
                PdfTextBlock(
                    text=text,
                    kind="heading",
                    heading_level=levels.get(rounded_size, 1),
                )
            )
        elif any(term in text for term in warning_terms):
            blocks.append(PdfTextBlock(text=text, kind="warning"))
        else:
            blocks.append(PdfTextBlock(text=text))
    return tuple(blocks)


def _heading_levels(
    raw_blocks: tuple[tuple[str, float, bool], ...],
) -> dict[float, int]:
    weighted_sizes = sorted(
        (size, max(1, len(text)))
        for text, size, _ in raw_blocks
        if size > 0
    )
    size_weights: dict[float, int] = {}
    for size, weight in weighted_sizes:
        size_weights[size] = size_weights.get(size, 0) + weight
    body_size = max(
        size_weights,
        key=lambda size: size_weights[size],
        default=0.0,
    )
    heading_sizes = sorted(
        {
            round(size, 1)
            for _, size, _ in raw_blocks
            if size > body_size * 1.12
        },
        reverse=True,
    )
    heading_levels = {
        size: index
        for index, size in enumerate(heading_sizes, start=1)
    }
    return heading_levels
