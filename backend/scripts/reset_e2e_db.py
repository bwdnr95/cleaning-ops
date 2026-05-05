from app.core.config import settings
from app.db.seed import seed_dev_data
from app.db.session import SessionLocal, engine
from app.models import Base


def main() -> None:
    if settings.environment != "e2e" or "e2e_cleaning_ops" not in settings.database_url:
        raise RuntimeError("reset_e2e_db must run with the isolated e2e database")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        seed_dev_data(db)

    print("E2E database reset complete")


if __name__ == "__main__":
    main()
