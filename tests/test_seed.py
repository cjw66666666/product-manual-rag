from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from rag_app.persistence import create_schema
from rag_app.persistence.schema import IndexVersion, Product, ProductAlias
from rag_app.seed import seed_initial_data


def test_seed_creates_products_and_index_version() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    with Session(engine) as session:
        seed_initial_data(session, index_version_id="i1")
        session.flush()

        assert len(session.scalars(select(Product)).all()) == 6
        assert len(session.scalars(select(ProductAlias)).all()) >= 6
        assert session.get(IndexVersion, "i1") is not None
