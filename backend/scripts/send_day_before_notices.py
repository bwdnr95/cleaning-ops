from app.db.session import SessionLocal
from app.services.messages import MessageService


def main() -> None:
    with SessionLocal() as db:
        result = MessageService(db).send_day_before_notices()
    print(
        "day_before_notices "
        f"target_date={result.target_date.isoformat()} "
        f"scanned={result.scanned} sent={result.sent} "
        f"skipped_already_sent={result.skipped_already_sent} failed={result.failed}"
    )


if __name__ == "__main__":
    main()
