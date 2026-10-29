import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from rag_app.catalog import MatchStatus, ProductCatalog


@dataclass(frozen=True, slots=True)
class MetadataExtraction:
    product_ids: tuple[str, ...]
    product_name: str | None
    version_label: str | None
    version_source: str
    confidence: str


_VERSION_PATTERNS = (
    re.compile(
        r"(?:版本(?:号)?|version)\s*[:：]?\s*[vV]?"
        r"([0-9]+(?:\.[0-9]+){1,3}(?:[_-][0-9]+)?)",
        re.IGNORECASE,
    ),
    re.compile(r"\b[Rr]([0-9]{4})\b"),
    re.compile(
        r"(?<![A-Za-z0-9])([Vv][0-9]+(?:\.[0-9]+){1,3})"
        r"(?![A-Za-z0-9])"
    ),
)


def extract_pdf_metadata_text(
    path: Path,
    *,
    max_pages: int = 10,
) -> str:
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    try:
        with pymupdf.open(path) as document:  # type: ignore[no-untyped-call]
            metadata = document.metadata or {}
            header = "\n".join(
                str(value)
                for key in ("title", "subject", "keywords")
                if (value := metadata.get(key))
            )
            pages = [
                page.get_text("text")
                for page in list(document)[:max_pages]
            ]
    except Exception:
        return ""
    return "\n".join((header, *pages)).strip()


def _version(text: str) -> tuple[str | None, str]:
    for pattern in _VERSION_PATTERNS:
        match = pattern.search(text)
        if match:
            label = match.group(1)
            if label[:1].casefold() == "v":
                label = label[1:]
            return label, "document_text"
    return None, "unknown"


def extract_metadata(
    text: str,
    catalog: ProductCatalog,
    *,
    source: str = "document_text",
) -> MetadataExtraction:
    match = catalog.resolve(text)
    product_ids = (
        tuple(product.id for product in match.products)
        if match.status is not MatchStatus.NOT_FOUND
        else ()
    )
    version, _ = _version(text)
    if product_ids and version:
        confidence = "high"
    elif product_ids:
        confidence = "medium"
    else:
        confidence = "low"
    return MetadataExtraction(
        product_ids=product_ids,
        product_name=(
            match.products[0].display_name
            if match.status is MatchStatus.RESOLVED
            else None
        ),
        version_label=version,
        version_source=source if version else "unknown",
        confidence=confidence,
    )
