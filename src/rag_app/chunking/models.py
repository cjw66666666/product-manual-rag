from dataclasses import dataclass
from enum import StrEnum


class BlockType(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ParsedBlock:
    type: BlockType
    text: str
    page: int
    heading_level: int = 1
    has_images: bool = False

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("block text cannot be blank")
        if self.page < 1:
            raise ValueError("page must be positive")
        if self.heading_level < 1:
            raise ValueError("heading level must be positive")


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    content: str
    page_start: int
    page_end: int
    section_path: tuple[str, ...]
    section_types: tuple[str, ...]
    has_images: bool = False
