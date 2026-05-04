from app.db.seed import seed_dev_data
from app.db.session import SessionLocal


def main() -> None:
    with SessionLocal() as db:
        summary = seed_dev_data(db)

    print("Development seed complete")
    print(f"Admin: {summary.admin_email} / {summary.admin_password}")
    print(f"Partner: {summary.partner_phone} / {summary.partner_password}")
    print(f"Sample order: {summary.order_id}")
    print(f"Customer token: {summary.customer_token}")


if __name__ == "__main__":
    main()
