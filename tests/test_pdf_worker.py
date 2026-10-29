from pathlib import Path

import pymupdf

from rag_app.file_store import Sha256FileStore
from rag_app.pdf_parsing import PyMuPdfParser
from rag_app.pdf_worker import PdfParseHandler
from rag_app.worker import Job


def test_pdf_handler_parses_content_addressed_file(tmp_path: Path) -> None:
    source = tmp_path / "manual.pdf"
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    page = document.new_page()
    page.insert_text((72, 72), "Safety warning")
    document.save(source)  # type: ignore[no-untyped-call]
    document.close()  # type: ignore[no-untyped-call]
    content = source.read_bytes()

    store = Sha256FileStore(tmp_path / "blobs")
    uri = store.put(content)
    digest = Path(uri).stem
    handler = PdfParseHandler(file_store=store, parser=PyMuPdfParser())

    handler.handle(Job("job-1", digest))
