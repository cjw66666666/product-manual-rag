import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from rag_app.seed import seed_initial_data
from rag_app.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed products and index version")
    parser.add_argument("--index-version-id", default="i1")
    args = parser.parse_args()

    settings = Settings()
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        seed_initial_data(
            session,
            index_version_id=args.index_version_id,
        )
        session.commit()
    print(f"Seeded products and index version {args.index_version_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
