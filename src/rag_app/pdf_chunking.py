import re

from rag_app.chunking import BlockType, ChunkDraft, ParsedBlock, chunk_blocks
from rag_app.pdf_parsing import PdfParseResult

_WARNING_TERMS = ("危险", "警告", "注意", "严禁", "禁止")
_HEADING_PREFIX = re.compile(
    r"^(第[一二三四五六七八九十百0-9]+[章节]|[0-9]+(?:\.[0-9]+)*)"
)


def _heading_level(text: str) -> int:
    match = _HEADING_PREFIX.match(text)
    if match is None:
        return 1
    value = match.group(1)
    if value.startswith("第"):
        return 1
    return value.count(".") + 1


def _looks_like_heading(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) > 60:
        return False
    if any(term in stripped for term in _WARNING_TERMS):
        return False
    if _HEADING_PREFIX.match(stripped):
        return True
    if any(mark in stripped for mark in "。！？；，,.;:："):
        return False
    return len(stripped) <= 30


def _page_blocks(parsed: PdfParseResult) -> tuple[ParsedBlock, ...]:
    blocks: list[ParsedBlock] = []
    for page in parsed.pages:
        lines = [
            line.strip() for line in page.text.splitlines() if line.strip()
        ]
        if page.blocks:
            for block in page.blocks:
                block_type = {
                    "heading": BlockType.HEADING,
                    "warning": BlockType.WARNING,
                    "paragraph": BlockType.PARAGRAPH,
                }[block.kind]
                blocks.append(
                    ParsedBlock(
                        type=block_type,
                        text=block.text,
                        page=page.page,
                        heading_level=block.heading_level,
                        has_images=page.has_images,
                    )
                )
            continue
        if not lines:
            if page.has_images:
                raise ValueError(
                    f"page {page.page} requires OCR before indexing"
                )
            continue
        for line in lines:
            if _looks_like_heading(line):
                block_type = BlockType.HEADING
            elif any(term in line for term in _WARNING_TERMS):
                block_type = BlockType.WARNING
            else:
                block_type = BlockType.PARAGRAPH
            blocks.append(
                ParsedBlock(
                    type=block_type,
                    text=line,
                    page=page.page,
                    heading_level=_heading_level(line),
                    has_images=page.has_images,
                )
            )
    return tuple(blocks)


def build_page_chunks(
    parsed: PdfParseResult,
    *,
    target_chars: int = 450,
    max_chars: int = 800,
) -> tuple[ChunkDraft, ...]:
    return chunk_blocks(
        _page_blocks(parsed),
        target_chars=target_chars,
        max_chars=max_chars,
    )
