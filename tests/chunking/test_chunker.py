from rag_app.chunking import BlockType, ParsedBlock, chunk_blocks


def test_heading_is_prefixed_to_chunk() -> None:
    chunks = chunk_blocks(
        (
            ParsedBlock(BlockType.HEADING, "电源", 2),
            ParsedBlock(BlockType.PARAGRAPH, "使用指定电源适配器。", 2),
        )
    )

    assert chunks[0].content == "电源\n使用指定电源适配器。"
    assert chunks[0].section_path == ("电源",)


def test_warning_never_merges_with_another_section() -> None:
    chunks = chunk_blocks(
        (
            ParsedBlock(BlockType.HEADING, "安全", 3),
            ParsedBlock(BlockType.WARNING, "请勿拆机。", 3),
            ParsedBlock(BlockType.HEADING, "使用", 4),
            ParsedBlock(BlockType.PARAGRAPH, "按压电源键开机。", 4),
        )
    )

    assert [chunk.content for chunk in chunks] == [
        "安全\n请勿拆机。",
        "使用\n按压电源键开机。",
    ]


def test_long_paragraph_is_split_without_exceeding_max() -> None:
    chunks = chunk_blocks(
        (
            ParsedBlock(BlockType.HEADING, "说明", 1),
            ParsedBlock(BlockType.PARAGRAPH, "甲" * 1000, 1),
        ),
        target_chars=300,
        max_chars=400,
    )

    assert len(chunks) >= 3
    assert all(len(chunk.content) <= 400 for chunk in chunks)
    assert all(chunk.section_path == ("说明",) for chunk in chunks)
    assert all(chunk.content.startswith("说明\n") for chunk in chunks)


def test_long_paragraph_has_overlap_between_adjacent_chunks() -> None:
    chunks = chunk_blocks(
        (
            ParsedBlock(BlockType.HEADING, "说明", 1),
            ParsedBlock(BlockType.PARAGRAPH, "甲" * 900, 1),
        ),
        target_chars=300,
        max_chars=400,
    )

    first_body = chunks[0].content.removeprefix("说明\n")
    second_body = chunks[1].content.removeprefix("说明\n")
    assert first_body[-100:] == second_body[:100]


def test_list_items_remain_together_when_possible() -> None:
    chunks = chunk_blocks(
        (
            ParsedBlock(BlockType.HEADING, "启动", 1),
            ParsedBlock(BlockType.LIST, "1. 接电源\n2. 按电源键\n3. 等待启动", 1),
        )
    )

    assert chunks[0].content.endswith("1. 接电源\n2. 按电源键\n3. 等待启动")


def test_table_is_separate_from_surrounding_paragraphs() -> None:
    chunks = chunk_blocks(
        (
            ParsedBlock(BlockType.HEADING, "参数", 2),
            ParsedBlock(BlockType.PARAGRAPH, "以下是规格。", 2),
            ParsedBlock(BlockType.TABLE, "项目 | 值\n重量 | 500g", 2),
            ParsedBlock(BlockType.PARAGRAPH, "请妥善保管。", 2),
        )
    )

    assert [chunk.content for chunk in chunks] == [
        "参数\n以下是规格。",
        "参数\n项目 | 值\n重量 | 500g",
        "参数\n请妥善保管。",
    ]


def test_large_table_repeats_header_in_every_chunk() -> None:
    rows = "\n".join(f"项目{index} | 数值{index}" for index in range(20))
    table = f"项目 | 值\n{rows}"

    chunks = chunk_blocks(
        (
            ParsedBlock(BlockType.HEADING, "参数", 2),
            ParsedBlock(BlockType.TABLE, table, 2),
        ),
        target_chars=100,
        max_chars=150,
    )

    assert len(chunks) > 1
    assert all("项目 | 值" in chunk.content for chunk in chunks)
    assert all(len(chunk.content) <= 150 for chunk in chunks)


def test_page_boundary_flushes_chunk_for_exact_citation_page() -> None:
    chunks = chunk_blocks(
        (
            ParsedBlock(BlockType.HEADING, "充电", 1),
            ParsedBlock(BlockType.PARAGRAPH, "第一页说明。", 1),
            ParsedBlock(
                BlockType.PARAGRAPH,
                "使用原装充电器连接平板。",
                2,
            ),
        )
    )

    assert [chunk.page_start for chunk in chunks] == [1, 2]
    assert [chunk.page_end for chunk in chunks] == [1, 2]
    assert "使用原装充电器连接平板。" in chunks[1].content
