from rag_app.application.filename_product_extractor import (
    LlmFilenameProductExtractor,
)
from rag_app.remote_models import Generation


class JsonLlm:
    def __init__(self, text: str) -> None:
        self.text = text
        self.prompt = ""
        self.system_prompt = ""

    def generate(
        self,
        prompt: str,
        *,
        model: str,
        system_prompt: str | None = None,
    ) -> Generation:
        self.prompt = prompt
        self.system_prompt = system_prompt or ""
        return Generation(self.text, 10, 2)


def test_filename_extractor_returns_literal_product_name() -> None:
    llm = JsonLlm('{"product_name":"HUAWEI MateBook B7-420"}')

    product_name = LlmFilenameProductExtractor(
        llm=llm,
        model="chat",
    ).extract(
        "HUAWEI MateBook B7-420 用户指南-(MRGFZ,Windows11).pdf"
    )

    assert product_name == "HUAWEI MateBook B7-420"
    assert "<filename>" in llm.prompt
    assert "untrusted data" in llm.system_prompt
    assert "do not create" in llm.system_prompt.casefold()


def test_filename_extractor_fails_closed_on_invalid_output() -> None:
    extractor = LlmFilenameProductExtractor(
        llm=JsonLlm("not-json"),
        model="chat",
    )

    assert extractor.extract("manual.pdf") is None


def test_filename_extractor_ignores_blank_product_name() -> None:
    extractor = LlmFilenameProductExtractor(
        llm=JsonLlm('{"product_name":"   "}'),
        model="chat",
    )

    assert extractor.extract("manual.pdf") is None
