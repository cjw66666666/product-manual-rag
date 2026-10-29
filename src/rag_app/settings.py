from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RAG_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = "mysql+pymysql://root:root@localhost:3306/rag"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    embedding_base_url: str = "https://example.invalid/v1"
    embedding_api_key: str = "change-me"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024
    reranker_base_url: str = "https://example.invalid/v1"
    reranker_api_key: str = "change-me"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    llm_base_url: str = "https://example.invalid/v1"
    llm_api_key: str = "change-me"
    llm_model: str = "change-me"
    verifier_model: str | None = None
    file_storage_root: Path = Path("data/files")
    max_upload_bytes: int = 50 * 1024 * 1024
    max_batch_upload_bytes: int = 200 * 1024 * 1024
    max_requests_per_minute: int = 20
    ocr_command: str = "tesseract"
    ocr_languages: str = "chi_sim+eng"
    admin_password_hash: str = ""
    session_secret: str = "change-me"
    index_version_id: str = "i1"
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://127.0.0.1:3001"

    @field_validator("qdrant_api_key", mode="before")
    @classmethod
    def empty_qdrant_key_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator(
        "langfuse_public_key",
        "langfuse_secret_key",
        mode="before",
    )
    @classmethod
    def empty_langfuse_key_is_none(cls, value: object) -> object:
        return None if value == "" else value
