from dataclasses import dataclass
from enum import StrEnum


class ProductCategory(StrEnum):
    TABLET = "tablet"
    LAPTOP = "laptop"
    MONITOR = "monitor"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class Product:
    id: str
    display_name: str
    category: ProductCategory
    aliases: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("product id cannot be blank")
        if not self.display_name.strip():
            raise ValueError("display name cannot be blank")
        if not self.aliases:
            raise ValueError("at least one alias is required")


class MatchStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class ProductMatch:
    status: MatchStatus
    products: tuple[Product, ...]
