import pytest

from rag_app.chunking import ChunkDraft
from rag_app.pdf_chunking import build_page_chunks
from rag_app.pdf_parsing import ParsedPage, PdfParseResult


def test_build_page_chunks_skips_empty_pages() -> None:
    parsed = PdfParseResult(
        pages=(
            ParsedPage(1, "", 0),
            ParsedPage(2, "按电源键开机。", 8),
            ParsedPage(3, "请勿拆机。", 5),
        )
    )

    chunks: tuple[ChunkDraft, ...] = build_page_chunks(parsed)

    assert len(chunks) == 2
    assert "按电源键开机" in chunks[0].content
    assert "请勿拆机" in chunks[1].content
    assert chunks[0].page_start == 2
    assert chunks[0].page_end == 2
    assert chunks[1].page_start == 3
    assert chunks[1].page_end == 3


def test_build_page_chunks_preserves_safety_heading_and_warning() -> None:
    parsed = PdfParseResult(
        pages=(
            ParsedPage(
                4,
                "安全信息\n警告：设备进水后请勿充电。\n联系官方支持。",
                25,
            ),
        )
    )

    chunks = build_page_chunks(parsed)

    assert chunks[0].section_path == ("安全信息",)
    assert "safety" in chunks[0].section_types
    assert "警告" in chunks[0].content


def test_build_page_chunks_fails_closed_when_image_page_needs_ocr() -> None:
    parsed = PdfParseResult(
        pages=(
            ParsedPage(
                5,
                "",
                0,
                has_images=True,
            ),
        )
    )

    with pytest.raises(ValueError, match="page 5 requires OCR"):
        build_page_chunks(parsed)


def test_build_page_chunks_marks_image_backed_content() -> None:
    parsed = PdfParseResult(
        pages=(
            ParsedPage(
                6,
                "安装说明\n将支架插入卡槽。",
                12,
                has_images=True,
            ),
        )
    )

    chunks = build_page_chunks(parsed)

    assert chunks[0].has_images is True
