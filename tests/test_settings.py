import pytest

from rag_app.settings import Settings


def test_settings_reads_prefixed_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_DATABASE_URL", "mysql+pymysql://db/test")
    monkeypatch.setenv("RAG_QDRANT_URL", "http://localhost:6333")

    settings = Settings()

    assert settings.database_url == "mysql+pymysql://db/test"
    assert settings.qdrant_url == "http://localhost:6333"


def test_empty_qdrant_key_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_QDRANT_API_KEY", "")

    assert Settings().qdrant_api_key is None


def test_settings_reads_langfuse_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("RAG_LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("RAG_LANGFUSE_HOST", "http://127.0.0.1:3001")

    settings = Settings()

    assert settings.langfuse_public_key == "pk-test"
    assert settings.langfuse_secret_key == "sk-test"
    assert settings.langfuse_host == "http://127.0.0.1:3001"


def test_empty_langfuse_keys_are_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAG_LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("RAG_LANGFUSE_SECRET_KEY", "")

    settings = Settings()

    assert settings.langfuse_public_key is None
    assert settings.langfuse_secret_key is None
