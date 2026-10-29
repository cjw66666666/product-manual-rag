from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rag_app.persistence import create_schema
from rag_app.persistence.product_repository import ProductDirectoryRepository


def test_product_repository_creates_and_reuses_named_product() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    with Session(engine) as session:
        repository = ProductDirectoryRepository(session)

        first = repository.resolve_or_create(
            "HUAWEI MateBook B7-420",
        )
        second = repository.resolve_or_create(
            "huawei matebook b7-420",
        )
        products = repository.list_catalog_products()

    assert first == second
    assert len(products) == 1
    assert products[0].display_name == "HUAWEI MateBook B7-420"
    assert products[0].category.value == "other"
    assert products[0].aliases == ("HUAWEI MateBook B7-420",)


def test_product_repository_reuses_existing_alias() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)

    with Session(engine) as session:
        repository = ProductDirectoryRepository(session)
        created = repository.resolve_or_create("MateBook B7")

        found = repository.resolve_or_create("matebook b7")

    assert found == created
