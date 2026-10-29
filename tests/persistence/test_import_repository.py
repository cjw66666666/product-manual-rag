import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from rag_app.persistence import create_schema
from rag_app.persistence.import_repository import (
    ImportItemInput,
    ImportRepository,
)
from rag_app.persistence.schema import IngestionItem


def test_repository_creates_batch_and_items() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    with Session(engine) as session:
        repo = ImportRepository(session)
        batch_id = repo.create_batch(
            created_by="admin",
            source_type="files",
            items=(
                ImportItemInput(
                    relative_path="tablet/manual.pdf",
                    filename="manual.pdf",
                    sha256="a" * 64,
                    confidence="high",
                ),
            ),
        )
        items = session.scalars(select(IngestionItem)).all()

        assert batch_id
        assert len(items) == 1
        assert items[0].sha256 == "a" * 64
        assert items[0].status == "uploaded"


def test_repository_reports_version_of_same_name_conflict() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    with Session(engine) as session:
        repo = ImportRepository(session)
        repo.create_batch(
            created_by="admin",
            source_type="files",
            items=(
                ImportItemInput(
                    relative_path="manual.pdf",
                    filename="manual.pdf",
                    sha256="a" * 64,
                    confidence="high",
                    detected_version_label="1.0",
                ),
            ),
        )
        conflict = repo.find_conflict_details(
            "manual.pdf",
            "b" * 64,
        )

    assert conflict is not None
    assert conflict.conflict_type == "same_name"
    assert conflict.version_label == "1.0"


def test_replace_conflict_requires_distinct_version() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    with Session(engine) as session:
        repo = ImportRepository(session)
        repo.create_batch(
            created_by="admin",
            source_type="files",
            items=(
                ImportItemInput(
                    relative_path="manual.pdf",
                    filename="manual.pdf",
                    sha256="a" * 64,
                    confidence="high",
                    detected_version_label="1.0",
                ),
                ImportItemInput(
                    relative_path="manual.pdf",
                    filename="manual.pdf",
                    sha256="b" * 64,
                    confidence="high",
                    detected_version_label="1.0",
                    conflict_type="same_name",
                ),
            ),
        )
        new_item = session.scalars(
            select(IngestionItem).where(IngestionItem.sha256 == "b" * 64)
        ).one()

        with pytest.raises(ValueError, match="distinct version"):
            repo.resolve_conflict(
                new_item.id,
                "replace_as_new_version",
                None,
            )


def test_cancelled_item_does_not_create_future_conflict() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    with Session(engine) as session:
        repo = ImportRepository(session)
        repo.create_batch(
            created_by="admin",
            source_type="files",
            items=(
                ImportItemInput(
                    relative_path="manual.pdf",
                    filename="manual.pdf",
                    sha256="a" * 64,
                    confidence="high",
                ),
            ),
        )
        item = session.scalars(select(IngestionItem)).one()
        repo.resolve_conflict(item.id, "cancel", None)

        conflict = repo.find_conflict_details("manual.pdf", "b" * 64)

    assert conflict is None


def test_replace_allows_new_version_when_old_version_is_unknown() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    with Session(engine) as session:
        repo = ImportRepository(session)
        repo.create_batch(
            created_by="admin",
            source_type="files",
            items=(
                ImportItemInput(
                    relative_path="manual.pdf",
                    filename="manual.pdf",
                    sha256="a" * 64,
                    confidence="medium",
                ),
                ImportItemInput(
                    relative_path="manual.pdf",
                    filename="manual.pdf",
                    sha256="b" * 64,
                    confidence="high",
                    detected_version_label="2.0",
                    conflict_type="same_name",
                ),
            ),
        )
        new_item = session.scalars(
            select(IngestionItem).where(IngestionItem.sha256 == "b" * 64)
        ).one()

        repo.resolve_conflict(
            new_item.id,
            "replace_as_new_version",
            None,
        )

    assert new_item.conflict_type is None
    assert new_item.status == "uploaded"


def test_list_batches_keeps_only_actionable_items() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    with Session(engine) as session:
        repo = ImportRepository(session)
        completed_batch = repo.create_batch(
            created_by="admin",
            source_type="files",
            items=(
                ImportItemInput(
                    relative_path="done.pdf",
                    filename="done.pdf",
                    sha256="a" * 64,
                    confidence="high",
                ),
            ),
        )
        active_batch = repo.create_batch(
            created_by="admin",
            source_type="files",
            items=(
                ImportItemInput(
                    relative_path="waiting.pdf",
                    filename="waiting.pdf",
                    sha256="b" * 64,
                    confidence="low",
                ),
                ImportItemInput(
                    relative_path="done.pdf",
                    filename="done.pdf",
                    sha256="c" * 64,
                    confidence="high",
                ),
            ),
        )
        repo.create_batch(
            created_by="admin",
            source_type="files",
            items=(),
        )
        completed_items = session.scalars(
            select(IngestionItem).where(
                IngestionItem.batch_id == completed_batch
            )
        ).all()
        for item in completed_items:
            item.status = "completed"
        active_items = session.scalars(
            select(IngestionItem).where(
                IngestionItem.batch_id == active_batch
            )
        ).all()
        active_items[-1].status = "completed"
        session.flush()

        batches = repo.list_batches()

    assert [batch.id for batch in batches] == [active_batch]
    assert batches[0].item_count == 1
