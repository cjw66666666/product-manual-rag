from collections.abc import Sequence

from rag_app.chunking.models import BlockType, ChunkDraft, ParsedBlock


def _section_types(path: tuple[str, ...]) -> tuple[str, ...]:
    safety_words = {"安全", "警告", "注意", "safety", "warning"}
    type_words = (
        ("safety", safety_words),
        ("specification", {"规格", "参数", "specification"}),
        ("installation", {"安装", "组装", "installation"}),
        ("troubleshooting", {"故障", "排查", "troubleshooting"}),
        ("maintenance", {"维护", "保养", "maintenance"}),
        ("legal", {"法律", "声明", "legal"}),
    )
    normalized = tuple(heading.casefold() for heading in path)
    types = tuple(
        section_type
        for section_type, words in type_words
        if any(word in heading for heading in normalized for word in words)
    )
    return types or ("usage",)


def _split_long_text(
    text: str,
    max_chars: int,
    overlap_chars: int = 100,
) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    effective_overlap = min(overlap_chars, max_chars - 1)
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        parts.append(text[start:end])
        if end == len(text):
            break
        start = end - effective_overlap
    return parts


def _split_table(text: str, max_chars: int) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len("\n".join(lines)) <= max_chars:
        return ["\n".join(lines)]
    if len(lines) < 2:
        raise ValueError("table without a header is too long")

    header = lines[0]
    if len(header) + 1 >= max_chars:
        raise ValueError("table header is too long for max_chars")

    parts: list[str] = []
    current = [header]
    for row in lines[1:]:
        candidate = "\n".join((*current, row))
        if len(candidate) > max_chars and len(current) > 1:
            parts.append("\n".join(current))
            current = [header, row]
        else:
            current.append(row)
    parts.append("\n".join(current))
    return parts


def chunk_blocks(
    blocks: Sequence[ParsedBlock],
    target_chars: int = 450,
    max_chars: int = 800,
) -> tuple[ChunkDraft, ...]:
    if target_chars < 1 or max_chars < target_chars:
        raise ValueError("invalid chunk size configuration")

    heading_stack: list[tuple[int, str]] = []
    section_path: tuple[str, ...] = ()
    chunks: list[ChunkDraft] = []
    buffer: list[str] = []
    page_start = 1
    page_end = 1
    buffer_has_images = False
    buffer_has_warning = False

    def flush() -> None:
        nonlocal buffer
        nonlocal buffer_has_images
        nonlocal buffer_has_warning
        nonlocal page_end
        nonlocal page_start
        if not buffer:
            return

        prefix = "\n".join(section_path)
        body = "\n".join(buffer).strip()
        body_limit = max_chars - len(prefix) - 1 if prefix else max_chars
        if body_limit < 1:
            raise ValueError("section path is too long for max_chars")

        for part in _split_long_text(body, body_limit):
            content = f"{prefix}\n{part}" if prefix else part
            section_types = _section_types(section_path)
            if buffer_has_warning and "safety" not in section_types:
                section_types = (*section_types, "safety")
            chunks.append(
                ChunkDraft(
                    content=content,
                    page_start=page_start,
                    page_end=page_end,
                    section_path=section_path,
                    section_types=section_types,
                    has_images=buffer_has_images,
                )
            )
        buffer = []
        buffer_has_images = False
        buffer_has_warning = False

    for block in blocks:
        if block.type is BlockType.HEADING:
            flush()
            level = block.heading_level
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, block.text.strip()))
            section_path = tuple(item[1] for item in heading_stack)
            page_start = block.page
            page_end = block.page
            continue

        if buffer and block.page != page_end:
            flush()

        if block.type is BlockType.TABLE:
            flush()
            prefix = "\n".join(section_path)
            body_limit = max_chars - len(prefix) - 1 if prefix else max_chars
            if body_limit < 1:
                raise ValueError("section path is too long for max_chars")
            for part in _split_table(block.text.strip(), body_limit):
                content = f"{prefix}\n{part}" if prefix else part
                chunks.append(
                    ChunkDraft(
                        content=content,
                        page_start=block.page,
                        page_end=block.page,
                        section_path=section_path,
                        section_types=_section_types(section_path),
                        has_images=block.has_images,
                    )
                )
            page_start = block.page
            page_end = block.page
            continue

        projected = sum(len(item) for item in buffer) + len(block.text)
        if buffer and projected > target_chars:
            flush()

        if not buffer:
            page_start = block.page
        page_end = block.page
        buffer.append(block.text.strip())
        buffer_has_images = buffer_has_images or block.has_images
        buffer_has_warning = (
            buffer_has_warning or block.type is BlockType.WARNING
        )

        if block.type is BlockType.WARNING:
            flush()

    flush()
    return tuple(chunks)
