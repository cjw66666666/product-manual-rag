import re
import unicodedata
from collections.abc import Sequence

from rag_app.catalog.models import MatchStatus, Product, ProductMatch


def normalize_alias(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = normalized.replace("-", "").replace("_", "")
    return re.sub(r"\s+", "", normalized)


class ProductCatalog:
    def __init__(self, products: Sequence[Product]) -> None:
        self._products = tuple(products)
        self._aliases: dict[str, tuple[Product, ...]] = {}

        for product in self._products:
            for alias in (*product.aliases, product.display_name):
                normalized = normalize_alias(alias)
                existing = self._aliases.get(normalized, ())
                if product not in existing:
                    self._aliases[normalized] = (*existing, product)

        duplicates = [
            aliases
            for aliases in self._aliases.values()
            if len({product.id for product in aliases}) > 1
        ]
        if duplicates:
            raise ValueError("alias maps to more than one product")

        self._ordered_aliases = tuple(
            sorted(self._aliases, key=len, reverse=True)
        )

    def resolve(self, text: str) -> ProductMatch:
        normalized_text = normalize_alias(text)
        matched: dict[str, Product] = {}

        for alias in self._ordered_aliases:
            if alias in normalized_text:
                for product in self._aliases[alias]:
                    matched[product.id] = product

        products = tuple(matched.values())
        if len(products) == 1:
            return ProductMatch(MatchStatus.RESOLVED, products)
        if len(products) > 1:
            return ProductMatch(MatchStatus.AMBIGUOUS, products)
        return ProductMatch(MatchStatus.NOT_FOUND, ())
