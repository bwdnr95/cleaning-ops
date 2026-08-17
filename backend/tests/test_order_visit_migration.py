from datetime import UTC, date, datetime
from pathlib import Path
from runpy import run_path

import pytest
import sqlalchemy as sa


def _migration_namespace() -> dict:
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0032_order_visit_dates.py"
    )
    return run_path(str(migration_path))


def _message_migration_namespace() -> dict:
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0033_day_before_target_visit_date.py"
    )
    return run_path(str(migration_path))


def _migration_tables() -> tuple[sa.MetaData, sa.Table, sa.Table]:
    metadata = sa.MetaData()
    orders = sa.Table(
        "orders",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scheduled_date", sa.Date()),
    )
    visits = sa.Table(
        "order_visits",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), nullable=False),
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.UniqueConstraint("order_id", "visit_date"),
    )
    return metadata, orders, visits


def test_migration_backfills_single_visit_from_scheduled_date() -> None:
    namespace = _migration_namespace()
    metadata, orders, visits = _migration_tables()
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            orders.insert(),
            [
                {"id": "scheduled", "scheduled_date": date(2026, 9, 2)},
                {"id": "unscheduled", "scheduled_date": None},
            ],
        )
        namespace["_backfill_existing_visits"](connection)
        rows = connection.execute(
            sa.select(visits.c.order_id, visits.c.visit_date)
        ).all()

    assert rows == [("scheduled", date(2026, 9, 2))]
    engine.dispose()


def test_migration_backfills_day_before_target_from_legacy_schedule() -> None:
    namespace = _message_migration_namespace()
    metadata = sa.MetaData()
    message_logs = sa.Table(
        "message_logs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), nullable=False),
        sa.Column("message_type", sa.String(80), nullable=False),
        sa.Column("target_visit_date", sa.Date()),
        sa.Column("requested_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            message_logs.insert(),
            [
                {
                    "id": "day-before",
                    "order_id": "scheduled",
                    "message_type": "customer_day_before",
                    "requested_at": datetime(2026, 9, 1, 14, 59, tzinfo=UTC),
                },
                {
                    "id": "other",
                    "order_id": "scheduled",
                    "message_type": "customer_schedule_confirmed",
                    "requested_at": datetime(2026, 9, 1, 14, 59, tzinfo=UTC),
                },
            ],
        )
        namespace["_backfill_day_before_target_dates"](connection)
        rows = connection.execute(
            sa.select(message_logs.c.id, message_logs.c.target_visit_date).order_by(
                message_logs.c.id
            )
        ).all()

    assert rows == [
        ("day-before", date(2026, 9, 2)),
        ("other", None),
    ]
    engine.dispose()


def test_migration_downgrade_rejects_multiple_visit_dates() -> None:
    namespace = _migration_namespace()
    metadata, orders, visits = _migration_tables()
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            orders.insert(),
            {"id": "multi", "scheduled_date": date(2026, 9, 2)},
        )
        connection.execute(
            visits.insert(),
            [
                {"id": "visit-1", "order_id": "multi", "visit_date": date(2026, 9, 2)},
                {"id": "visit-2", "order_id": "multi", "visit_date": date(2026, 9, 3)},
            ],
        )
        with pytest.raises(RuntimeError, match="multiple or mismatched visit dates"):
            namespace["_ensure_downgrade_is_representable"](connection)

    engine.dispose()
