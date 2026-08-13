from datetime import UTC, date, datetime
from pathlib import Path
from runpy import run_path

import pytest
import sqlalchemy as sa


def migration_namespace():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0031_partner_archive_and_recurring_billing_periods.py"
    )
    return run_path(str(migration_path))


def test_migration_clock_uses_seoul_business_date_at_utc_month_boundary() -> None:
    namespace = migration_namespace()

    result = namespace["seoul_today"](
        datetime(2026, 8, 31, 15, 30, tzinfo=UTC)
    )

    assert result == date(2026, 9, 1)


def test_backfill_materializes_elapsed_active_monthly_obligations() -> None:
    namespace = migration_namespace()
    metadata = sa.MetaData()
    contracts = sa.Table(
        "recurring_contracts",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("billing_mode", sa.String(20), nullable=False),
        sa.Column("partner_billing_mode", sa.String(20), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    statuses = sa.Table(
        "recurring_monthly_status",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("contract_id", sa.String(36), nullable=False),
        sa.Column("billing_month", sa.String(7), nullable=False),
        sa.Column("tax_invoice_issued", sa.Boolean(), nullable=False),
        sa.Column("balance_paid", sa.Boolean(), nullable=False),
        sa.Column("partner_payment_paid", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("contract_id", "billing_month"),
    )
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            contracts.insert(),
            [
                {
                    "id": "active-monthly",
                    "start_date": date(2026, 7, 10),
                    "end_date": None,
                    "status": "active",
                    "updated_at": datetime(2026, 8, 1, tzinfo=UTC),
                    "billing_mode": "per_visit",
                    "partner_billing_mode": "monthly",
                    "deleted_at": None,
                },
                {
                    "id": "active-customer-monthly",
                    "start_date": date(2026, 7, 10),
                    "end_date": None,
                    "status": "active",
                    "updated_at": datetime(2026, 8, 1, tzinfo=UTC),
                    "billing_mode": "monthly",
                    "partner_billing_mode": "per_visit",
                    "deleted_at": None,
                },
                {
                    "id": "active-with-past-end",
                    "start_date": date(2026, 6, 10),
                    "end_date": date(2026, 7, 31),
                    "status": "active",
                    "updated_at": datetime(2026, 8, 1, tzinfo=UTC),
                    "billing_mode": "per_visit",
                    "partner_billing_mode": "monthly",
                    "deleted_at": None,
                },
                {
                    "id": "deleted-active",
                    "start_date": date(2026, 6, 10),
                    "end_date": None,
                    "status": "active",
                    "updated_at": datetime(2026, 8, 1, tzinfo=UTC),
                    "billing_mode": "per_visit",
                    "partner_billing_mode": "monthly",
                    "deleted_at": datetime(2026, 7, 5, 3, tzinfo=UTC),
                },
                {
                    "id": "active-per-visit",
                    "start_date": date(2026, 7, 10),
                    "end_date": None,
                    "status": "active",
                    "updated_at": datetime(2026, 8, 1, tzinfo=UTC),
                    "billing_mode": "per_visit",
                    "partner_billing_mode": "per_visit",
                    "deleted_at": None,
                },
            ],
        )
        namespace["backfill_incurred_monthly_statuses"](
            connection,
            today=date(2026, 8, 12),
        )
        rows = connection.execute(
            sa.select(statuses.c.contract_id, statuses.c.billing_month).order_by(
                statuses.c.contract_id,
                statuses.c.billing_month,
            )
        ).all()

    assert rows == [
        ("active-customer-monthly", "2026-07"),
        ("active-customer-monthly", "2026-08"),
        ("active-monthly", "2026-07"),
        ("active-monthly", "2026-08"),
        ("active-with-past-end", "2026-06"),
        ("active-with-past-end", "2026-07"),
        ("deleted-active", "2026-06"),
        ("deleted-active", "2026-07"),
    ]
    engine.dispose()


@pytest.mark.parametrize(
    ("status", "deleted_at"),
    [
        ("paused", None),
        ("ended", None),
        ("paused", datetime(2026, 8, 1, tzinfo=UTC)),
        ("ended", datetime(2026, 8, 1, tzinfo=UTC)),
    ],
)
def test_backfill_rejects_ambiguous_legacy_lifecycle(status: str, deleted_at) -> None:
    namespace = migration_namespace()
    metadata = sa.MetaData()
    contracts = sa.Table(
        "recurring_contracts",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("billing_mode", sa.String(20), nullable=False),
        sa.Column("partner_billing_mode", sa.String(20), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    sa.Table(
        "recurring_monthly_status",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("contract_id", sa.String(36), nullable=False),
        sa.Column("billing_month", sa.String(7), nullable=False),
        sa.Column("tax_invoice_issued", sa.Boolean(), nullable=False),
        sa.Column("balance_paid", sa.Boolean(), nullable=False),
        sa.Column("partner_payment_paid", sa.Boolean(), nullable=False),
    )
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            contracts.insert().values(
                id="ambiguous-contract",
                start_date=date(2026, 1, 1),
                end_date=None,
                status=status,
                billing_mode="per_visit",
                partner_billing_mode="monthly",
                deleted_at=deleted_at,
            )
        )
        with pytest.raises(RuntimeError, match="cannot infer legacy recurring billing cutoff"):
            namespace["backfill_incurred_monthly_statuses"](
                connection,
                today=date(2026, 8, 12),
            )
    engine.dispose()


def _legacy_settlement_tables():
    metadata = sa.MetaData()
    contracts = sa.Table(
        "recurring_contracts",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("partner_billing_mode", sa.String(20), nullable=False),
    )
    orders = sa.Table(
        "orders",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recurring_contract_id", sa.String(36)),
        sa.Column("recurring_planned_date", sa.Date()),
        sa.Column("scheduled_date", sa.Date()),
        sa.Column("partner_payment_amount", sa.Numeric(12, 2)),
        sa.Column("partner_payment_status", sa.String(40)),
        sa.Column("partner_settled_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    return metadata, contracts, orders


def test_upgrade_rejects_and_preserves_unresolved_monthly_order_fields() -> None:
    namespace = migration_namespace()
    metadata, contracts, orders = _legacy_settlement_tables()
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            contracts.insert().values(id="monthly-contract", partner_billing_mode="monthly")
        )
        connection.execute(
            orders.insert().values(
                id="legacy-order",
                recurring_contract_id="monthly-contract",
                recurring_planned_date=None,
                scheduled_date=date(2026, 8, 3),
                partner_payment_amount=70000,
                partner_payment_status="unpaid",
                partner_settled_at=None,
                deleted_at=None,
            )
        )
        with pytest.raises(RuntimeError, match="cannot infer legacy recurring order billing mode"):
            namespace["reconcile_legacy_recurring_order_settlements"](connection)
        row = connection.execute(sa.select(orders)).one()
        assert row.partner_payment_amount == 70000
        assert row.partner_payment_status == "unpaid"
        assert row.partner_settled_at is None
    engine.dispose()


@pytest.mark.parametrize(
    ("scheduled_date", "payment_status", "settled_at", "message"),
    [
        (None, "unpaid", None, "cannot resolve legacy recurring settlement month"),
        (
            date(2026, 8, 3),
            "paid",
            datetime(2026, 8, 5, tzinfo=UTC),
            "cannot infer legacy recurring order billing mode",
        ),
    ],
)
def test_upgrade_rejects_ambiguous_or_settled_legacy_order(
    scheduled_date,
    payment_status,
    settled_at,
    message,
) -> None:
    namespace = migration_namespace()
    metadata, contracts, orders = _legacy_settlement_tables()
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            contracts.insert().values(id="monthly-contract", partner_billing_mode="monthly")
        )
        connection.execute(
            orders.insert().values(
                id="legacy-order",
                recurring_contract_id="monthly-contract",
                recurring_planned_date=None,
                scheduled_date=scheduled_date,
                partner_payment_amount=70000,
                partner_payment_status=payment_status,
                partner_settled_at=settled_at,
                deleted_at=None,
            )
        )
        with pytest.raises(RuntimeError, match=message):
            namespace["reconcile_legacy_recurring_order_settlements"](connection)
    engine.dispose()


def test_upgrade_ignores_soft_deleted_legacy_order_settlement_history() -> None:
    namespace = migration_namespace()
    metadata, contracts, orders = _legacy_settlement_tables()
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            contracts.insert().values(id="monthly-contract", partner_billing_mode="monthly")
        )
        connection.execute(
            orders.insert().values(
                id="deleted-legacy-order",
                recurring_contract_id="monthly-contract",
                recurring_planned_date=None,
                scheduled_date=None,
                partner_payment_amount=70000,
                partner_payment_status="unpaid",
                partner_settled_at=None,
                deleted_at=datetime(2026, 8, 1, tzinfo=UTC),
            )
        )

        namespace["reconcile_legacy_recurring_order_settlements"](connection)
        row = connection.execute(sa.select(orders)).one()

    assert row.partner_payment_amount == 70000
    assert row.partner_payment_status == "unpaid"
    engine.dispose()


def add_downgrade_orders_table(metadata: sa.MetaData) -> sa.Table:
    return sa.Table(
        "orders",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "recurring_partner_settlement_retained",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def add_downgrade_monthly_status_table(metadata: sa.MetaData) -> sa.Table:
    return sa.Table(
        "recurring_monthly_status",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("retained_partner_payment_amount", sa.Numeric(12, 2)),
    )


def test_downgrade_rejects_effective_month_billing_history() -> None:
    namespace = migration_namespace()
    metadata = sa.MetaData()
    periods = sa.Table(
        "recurring_partner_billing_periods",
        metadata,
        sa.Column("contract_id", sa.String(36), primary_key=True),
        sa.Column("effective_month", sa.String(7), primary_key=True),
    )
    sa.Table(
        "recurring_contracts",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("active_segment_start_date", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    partners = sa.Table(
        "partners",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    add_downgrade_orders_table(metadata)
    add_downgrade_monthly_status_table(metadata)
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(partners.insert().values(id="partner-1", deleted_at=None))
        connection.execute(
            periods.insert().values(
                contract_id="contract-1",
                effective_month="0001-01",
            )
        )
        namespace["ensure_downgrade_preserves_billing_history"](connection)
        connection.execute(
            periods.insert().values(
                contract_id="contract-1",
                effective_month="2026-08",
            )
        )
        with pytest.raises(RuntimeError, match="effective-month partner billing history exists"):
            namespace["ensure_downgrade_preserves_billing_history"](connection)

    engine.dispose()


def test_downgrade_rejects_archived_partner_state() -> None:
    namespace = migration_namespace()
    metadata = sa.MetaData()
    sa.Table(
        "recurring_partner_billing_periods",
        metadata,
        sa.Column("contract_id", sa.String(36), primary_key=True),
        sa.Column("effective_month", sa.String(7), primary_key=True),
    )
    sa.Table(
        "recurring_contracts",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("active_segment_start_date", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    partners = sa.Table(
        "partners",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    add_downgrade_orders_table(metadata)
    add_downgrade_monthly_status_table(metadata)
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            partners.insert().values(
                id="archived-partner",
                deleted_at=datetime.now(UTC),
            )
        )
        with pytest.raises(RuntimeError, match="archived partner state exists"):
            namespace["ensure_downgrade_preserves_billing_history"](connection)

    engine.dispose()


def test_downgrade_rejects_retained_per_visit_settlement() -> None:
    namespace = migration_namespace()
    metadata = sa.MetaData()
    sa.Table(
        "recurring_partner_billing_periods",
        metadata,
        sa.Column("contract_id", sa.String(36), primary_key=True),
        sa.Column("effective_month", sa.String(7), primary_key=True),
    )
    sa.Table(
        "recurring_contracts",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("active_segment_start_date", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    sa.Table(
        "partners",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    orders = add_downgrade_orders_table(metadata)
    add_downgrade_monthly_status_table(metadata)
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            orders.insert().values(
                id="retained-order",
                recurring_partner_settlement_retained=True,
            )
        )
        with pytest.raises(RuntimeError, match="retained per-visit settlement exists"):
            namespace["ensure_downgrade_preserves_billing_history"](connection)

    engine.dispose()


def test_downgrade_rejects_retained_monthly_settlement() -> None:
    namespace = migration_namespace()
    metadata = sa.MetaData()
    sa.Table(
        "recurring_partner_billing_periods",
        metadata,
        sa.Column("contract_id", sa.String(36), primary_key=True),
        sa.Column("effective_month", sa.String(7), primary_key=True),
    )
    sa.Table(
        "recurring_contracts",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("active_segment_start_date", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    sa.Table(
        "partners",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    add_downgrade_orders_table(metadata)
    statuses = add_downgrade_monthly_status_table(metadata)
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            statuses.insert().values(
                id="retained-monthly",
                retained_partner_payment_amount=250000,
            )
        )
        with pytest.raises(RuntimeError, match="retained monthly settlement exists"):
            namespace["ensure_downgrade_preserves_billing_history"](connection)

    engine.dispose()


@pytest.mark.parametrize(
    ("active_segment_start", "status", "deleted_at"),
    [
        (date(2026, 5, 1), "active", None),
        (date(2026, 1, 1), "paused", None),
        (date(2026, 1, 1), "ended", None),
        (date(2026, 1, 1), "ended", datetime(2026, 6, 1, tzinfo=UTC)),
    ],
)
def test_downgrade_rejects_nonrepresentable_billing_segment(
    active_segment_start,
    status,
    deleted_at,
) -> None:
    namespace = migration_namespace()
    metadata = sa.MetaData()
    sa.Table(
        "recurring_partner_billing_periods",
        metadata,
        sa.Column("contract_id", sa.String(36), primary_key=True),
        sa.Column("effective_month", sa.String(7), primary_key=True),
    )
    partners = sa.Table(
        "partners",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    contracts = sa.Table(
        "recurring_contracts",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("active_segment_start_date", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    add_downgrade_orders_table(metadata)
    add_downgrade_monthly_status_table(metadata)
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(partners.insert().values(id="partner-1", deleted_at=None))
        connection.execute(
            contracts.insert().values(
                id="resumed-contract",
                start_date=date(2026, 1, 1),
                active_segment_start_date=active_segment_start,
                status=status,
                deleted_at=deleted_at,
            )
        )
        with pytest.raises(RuntimeError, match="resumed billing segment exists"):
            namespace["ensure_downgrade_preserves_billing_history"](connection)

    engine.dispose()
