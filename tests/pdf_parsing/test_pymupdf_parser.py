from pathlib import Path

import pymupdf

from rag_app.pdf_parsing import PyMuPdfParser


def test_parser_extracts_page_text(tmp_path: Path) -> None:
    path = tmp_path / "manual.pdf"
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    page = document.new_page()
    page.insert_text((72, 72), "Safety warning")
    document.save(path)  # type: ignore[no-untyped-call]
    document.close()  # type: ignore[no-untyped-call]

    result = PyMuPdfParser().parse(path)

    assert len(result.pages) == 1
    assert "Safety warning" in result.pages[0].text
    assert result.pages[0].text_char_count > 0


def test_parser_uses_ocr_for_image_only_page(tmp_path: Path) -> None:
    path = tmp_path / "scanned.pdf"
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    page = document.new_page()
    image = pymupdf.Pixmap(  # type: ignore[no-untyped-call]
        pymupdf.csRGB,
        pymupdf.IRect(0, 0, 8, 8),  # type: ignore[no-untyped-call]
        False,
    )
    image.clear_with(255)  # type: ignore[no-untyped-call]
    page.insert_image(  # type: ignore[no-untyped-call]
        pymupdf.Rect(72, 72, 120, 120),  # type: ignore[no-untyped-call]
        stream=image.tobytes("png"),  # type: ignore[no-untyped-call]
    )
    document.save(path)  # type: ignore[no-untyped-call]
    document.close()  # type: ignore[no-untyped-call]

    class FakeOcr:
        available = True

        def image_to_text(self, image: bytes) -> str:
            assert image.startswith(b"\x89PNG")
            return "警告：请勿拆机。"

    result = PyMuPdfParser(
        ocr_engine=FakeOcr(),
        ocr_min_chars=20,
    ).parse(path)

    assert "警告" in result.pages[0].text
    assert result.pages[0].ocr_used is True


def test_parser_preserves_font_based_heading_hierarchy(
    tmp_path: Path,
) -> None:
    path = tmp_path / "headings.pdf"
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    page = document.new_page()
    page.insert_text((72, 72), "基础使用", fontsize=18)
    page.insert_text((72, 110), "开关机和重启", fontsize=14)
    page.insert_text((72, 145), "长按电源键开机。", fontsize=11)
    document.save(path)  # type: ignore[no-untyped-call]
    document.close()  # type: ignore[no-untyped-call]

    result = PyMuPdfParser().parse(path)
    blocks = result.pages[0].blocks

    assert [
        (block.kind, block.heading_level) for block in blocks
    ] == [
        ("heading", 1),
        ("heading", 2),
        ("paragraph", 1),
    ]


def test_parser_keeps_numbered_step_as_paragraph(
    tmp_path: Path,
) -> None:
    path = tmp_path / "numbered-step.pdf"
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    page = document.new_page()
    page.insert_text((72, 72), "使用超级快充", fontsize=18)
    page.insert_text(
        (72, 110),
        "2 使用华为原装超级快充充电器和数据线连接平板。",
        fontsize=15,
    )
    page.insert_text(
        (72, 145),
        (
            "充电时请保持接口清洁，并使用干燥的软布擦拭设备。"
            "请勿使用烈性化学制品清洁设备或其配件。"
            "设备异常发热时应立即停止充电并断开电源。"
        ),
        fontsize=12,
    )
    document.save(path)  # type: ignore[no-untyped-call]
    document.close()  # type: ignore[no-untyped-call]

    result = PyMuPdfParser().parse(path)

    assert result.pages[0].blocks[1].kind == "paragraph"


def test_parser_uses_document_wide_heading_levels(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cross-page-headings.pdf"
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    first = document.new_page()
    first.insert_text((72, 72), "电池", fontsize=18)
    first.insert_text(
        (72, 110),
        "设备使用内置电池，请勿自行拆卸或更换。",
        fontsize=12,
    )
    second = document.new_page()
    second.insert_text((72, 72), "查看耗电情况", fontsize=14)
    second.insert_text(
        (72, 110),
        "进入设置查看各应用耗电排行和使用情况。",
        fontsize=12,
    )
    document.save(path)  # type: ignore[no-untyped-call]
    document.close()  # type: ignore[no-untyped-call]

    result = PyMuPdfParser().parse(path)

    assert result.pages[0].blocks[0].heading_level == 1
    assert result.pages[1].blocks[0].heading_level == 2
