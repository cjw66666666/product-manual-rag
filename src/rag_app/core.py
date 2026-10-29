from rag_app.answering import AnswerLoop, Generator, Retriever
from rag_app.verification import CitationVerifier


def build_core_answer_loop(
    retriever: Retriever,
    generator: Generator,
) -> AnswerLoop:
    return AnswerLoop(
        retriever=retriever,
        generator=generator,
        verifier=CitationVerifier(),
        allow_general_fallback=False,
    )
