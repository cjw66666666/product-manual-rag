from rag_app.file_store import Sha256FileStore
from rag_app.pdf_parsing import PdfParser
from rag_app.worker import Job


class PdfParseHandler:
    def __init__(
        self,
        *,
        file_store: Sha256FileStore,
        parser: PdfParser,
    ) -> None:
        self._file_store = file_store
        self._parser = parser

    def handle(self, job: Job) -> None:
        path = self._file_store.path_for_sha256(job.payload)
        result = self._parser.parse(path)
        if not result.pages or not any(
            page.text.strip() for page in result.pages
        ):
            raise ValueError("PDF contains no extractable text")
