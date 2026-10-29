from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_initial_migration_creates_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("RAG_DATABASE_URL", database_url)

    root = Path(__file__).parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, "head")

    names = set(inspect(create_engine(database_url)).get_table_names())
    assert {"document_versions", "chunks", "conversations"} <= names
    migration_engine = create_engine(database_url)
    inspector = inspect(migration_engine)
    assert "sequence" in {
        column["name"] for column in inspector.get_columns("messages")
    }
    assert "covered_sequence" in {
        column["name"]
        for column in inspector.get_columns("conversation_summaries")
    }
    assert "has_images" in {
        column["name"] for column in inspector.get_columns("chunks")
    }
    assert "requires_manual_approval" in {
        column["name"]
        for column in inspector.get_columns("document_versions")
    }
    assert "context_start_sequence" in {
        column["name"] for column in inspector.get_columns("conversations")
    }
    assert "product_index_bindings" in names
    assert "index_cleanup_jobs" in names
    assert "sparse_index_statistics" in names
    assert "detected_product_name" in {
        column["name"]
        for column in inspector.get_columns("ingestion_items")
    }
    cleanup_columns = {
        column["name"]
        for column in inspector.get_columns("index_cleanup_jobs")
    }
    assert {
        "document_version_id",
        "index_version_id",
        "status",
        "attempts",
        "available_at",
        "error_message",
    } <= cleanup_columns


def test_cleanup_queue_migration_upgrades_existing_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "upgrade.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("RAG_DATABASE_URL", database_url)
    root = Path(__file__).parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))

    command.upgrade(config, "20261029_0004")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS index_cleanup_jobs"))

    command.upgrade(config, "head")

    names = set(inspect(create_engine(database_url)).get_table_names())
    assert "index_cleanup_jobs" in names


def test_context_segment_migration_upgrades_existing_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "context-upgrade.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("RAG_DATABASE_URL", database_url)
    root = Path(__file__).parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))

    command.upgrade(config, "20261029_0005")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE conversations "
                "DROP COLUMN context_start_sequence"
            )
        )

    command.upgrade(config, "head")

    columns = {
        column["name"]
        for column in inspect(create_engine(database_url)).get_columns(
            "conversations"
        )
    }
    assert "context_start_sequence" in columns
