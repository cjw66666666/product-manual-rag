from sqlalchemy import create_engine, inspect

from rag_app.persistence import create_schema


def test_schema_creates_source_of_truth_tables() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    names = set(inspect(engine).get_table_names())

    assert {
        "products",
        "product_aliases",
        "documents",
        "document_versions",
        "file_blobs",
        "product_document_bindings",
        "document_types",
        "document_version_types",
        "document_sections",
        "chunks",
        "index_versions",
        "document_indexes",
        "ingestion_batches",
        "ingestion_items",
        "conversations",
        "messages",
        "conversation_summaries",
        "visitor_preferences",
        "answer_runs",
        "feedback",
    } <= names


def test_document_version_has_hash_and_status() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    columns = {
        column["name"]
        for column in inspect(engine).get_columns("document_versions")
    }

    assert {"sha256", "version_label", "status", "received_at"} <= columns
