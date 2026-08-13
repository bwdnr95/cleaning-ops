from datetime import UTC, date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from alembic import op

revision = "0031_partner_billing_periods"
down_revision = "0030_drop_token_constraints"
branch_labels = None
depends_on = None


def month_keys(start: date, end: date) -> list[str]:
    cursor = start.replace(day=1)
    last = end.replace(day=1)
    result: list[str] = []
    while cursor <= last:
        result.append(f"{cursor.year:04d}-{cursor.month:02d}")
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return result


def business_date(value: date | datetime) -> date:
    if not isinstance(value, datetime):
        return value
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(ZoneInfo("Asia/Seoul")).date()


def seoul_today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(ZoneInfo("Asia/Seoul")).date()


def ensure_legacy_recurring_lifecycle_reconcilable(connection) -> None:
    contracts = sa.table(
        "recurring_contracts",
        sa.column("id", sa.String(36)),
        sa.column("end_date", sa.Date()),
        sa.column("status", sa.String(20)),
        sa.column("billing_mode", sa.String(20)),
        sa.column("partner_billing_mode", sa.String(20)),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
    )
    ambiguous = connection.execute(
        sa.select(contracts.c.id).where(
            sa.or_(
                contracts.c.billing_mode == "monthly",
                contracts.c.partner_billing_mode == "monthly",
            ),
            sa.or_(
                contracts.c.status == "paused",
                sa.and_(
                    contracts.c.status == "ended",
                    contracts.c.end_date.is_(None),
                ),
            ),
        )
    ).all()
    if ambiguous:
        ids = ", ".join(str(row.id) for row in ambiguous)
        raise RuntimeError(
            "cannot infer legacy recurring billing cutoff; "
            f"reconcile paused/ended contracts before upgrade: {ids}"
        )


def backfill_incurred_monthly_statuses(connection, *, today: date | None = None) -> None:
    today = today or seoul_today()
    ensure_legacy_recurring_lifecycle_reconcilable(connection)
    contracts = sa.table(
        "recurring_contracts",
        sa.column("id", sa.String(36)),
        sa.column("start_date", sa.Date()),
        sa.column("end_date", sa.Date()),
        sa.column("status", sa.String(20)),
        sa.column("billing_mode", sa.String(20)),
        sa.column("partner_billing_mode", sa.String(20)),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
    )
    statuses = sa.table(
        "recurring_monthly_status",
        sa.column("id", sa.String(36)),
        sa.column("contract_id", sa.String(36)),
        sa.column("billing_month", sa.String(7)),
        sa.column("tax_invoice_issued", sa.Boolean()),
        sa.column("balance_paid", sa.Boolean()),
        sa.column("partner_payment_paid", sa.Boolean()),
    )
    existing = set(
        connection.execute(
            sa.select(statuses.c.contract_id, statuses.c.billing_month)
        ).all()
    )
    rows: list[dict[str, object]] = []
    stmt = sa.select(
        contracts.c.id,
        contracts.c.start_date,
        contracts.c.end_date,
        contracts.c.status,
        contracts.c.deleted_at,
    ).where(
        sa.or_(
            contracts.c.billing_mode == "monthly",
            contracts.c.partner_billing_mode == "monthly",
        ),
        contracts.c.status.in_(("active", "ended")),
    )
    rows_to_backfill = list(connection.execute(stmt))
    for contract_id, start_date, end_date, status, deleted_at in rows_to_backfill:
        last_day = min(
            value
            for value in (
                today,
                end_date,
                business_date(deleted_at) if deleted_at is not None else None,
            )
            if value is not None
        )
        if status == "ended" and end_date is None:
            continue
        if start_date > last_day:
            continue
        for month in month_keys(start_date, last_day):
            if (contract_id, month) in existing:
                continue
            rows.append(
                {
                    "id": str(uuid4()),
                    "contract_id": contract_id,
                    "billing_month": month,
                    "tax_invoice_issued": False,
                    "balance_paid": False,
                    "partner_payment_paid": False,
                }
            )
    if rows:
        connection.execute(statuses.insert(), rows)


def reconcile_legacy_recurring_order_settlements(connection) -> None:
    ensure_legacy_recurring_order_settlements_reconcilable(connection)


def ensure_legacy_recurring_order_settlements_reconcilable(connection) -> None:
    orders = sa.table(
        "orders",
        sa.column("id", sa.String(36)),
        sa.column("recurring_contract_id", sa.String(36)),
        sa.column("recurring_planned_date", sa.Date()),
        sa.column("scheduled_date", sa.Date()),
        sa.column("partner_payment_amount", sa.Numeric(12, 2)),
        sa.column("partner_payment_status", sa.String(40)),
        sa.column("partner_settled_at", sa.DateTime(timezone=True)),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
    )
    contracts = sa.table(
        "recurring_contracts",
        sa.column("id", sa.String(36)),
        sa.column("partner_billing_mode", sa.String(20)),
    )
    ambiguous = connection.execute(
        sa.select(orders.c.id).where(
            orders.c.recurring_contract_id.is_not(None),
            orders.c.deleted_at.is_(None),
            orders.c.recurring_planned_date.is_(None),
            orders.c.scheduled_date.is_(None),
            sa.or_(
                orders.c.partner_payment_amount.is_not(None),
                orders.c.partner_payment_status.is_not(None),
                orders.c.partner_settled_at.is_not(None),
            ),
        )
    ).all()
    if ambiguous:
        ids = ", ".join(str(row.id) for row in ambiguous)
        raise RuntimeError(
            "cannot resolve legacy recurring settlement month; "
            f"assign a scheduled date before upgrade: {ids}"
        )
    unresolved_monthly = connection.execute(
        sa.select(orders.c.id)
        .select_from(orders.join(contracts, orders.c.recurring_contract_id == contracts.c.id))
        .where(
            orders.c.deleted_at.is_(None),
            contracts.c.partner_billing_mode == "monthly",
            sa.or_(
                orders.c.partner_payment_amount.is_not(None),
                orders.c.partner_payment_status.is_not(None),
                orders.c.partner_settled_at.is_not(None),
            ),
        )
    ).all()
    if unresolved_monthly:
        ids = ", ".join(str(row.id) for row in unresolved_monthly)
        raise RuntimeError(
            "cannot infer legacy recurring order billing mode; "
            f"reconcile before upgrade: {ids}"
        )


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE orders DROP CONSTRAINT IF EXISTS "
            "ck_orders_customer_token_ct2_or_null"
        )
        op.execute(
            "ALTER TABLE order_groups DROP CONSTRAINT IF EXISTS "
            "ck_order_groups_customer_token_ct2"
        )
    ensure_legacy_recurring_lifecycle_reconcilable(connection)
    ensure_legacy_recurring_order_settlements_reconcilable(connection)
    op.add_column(
        "partners",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_partners_deleted_at", "partners", ["deleted_at"])
    op.add_column(
        "orders",
        sa.Column(
            "recurring_partner_settlement_retained",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "recurring_monthly_status",
        sa.Column("retained_partner_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "recurring_monthly_status",
        sa.Column("retained_partner_payment_amount", sa.Numeric(12, 2), nullable=True),
    )
    op.create_foreign_key(
        "fk_recurring_monthly_retained_partner",
        "recurring_monthly_status",
        "partners",
        ["retained_partner_id"],
        ["id"],
    )
    op.add_column(
        "recurring_contracts",
        sa.Column("active_segment_start_date", sa.Date(), nullable=True),
    )

    op.create_table(
        "recurring_partner_billing_periods",
        sa.Column("contract_id", sa.String(length=36), nullable=False),
        sa.Column("effective_month", sa.String(length=7), nullable=False),
        sa.Column("partner_id", sa.String(length=36), nullable=True),
        sa.Column("billing_mode", sa.String(length=20), nullable=False),
        sa.Column("partner_payment_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["recurring_contracts.id"],
            name="fk_recurring_partner_billing_contract",
        ),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["partners.id"],
            name="fk_recurring_partner_billing_partner",
        ),
        sa.PrimaryKeyConstraint(
            "contract_id",
            "effective_month",
            name="pk_recurring_partner_billing_periods",
        ),
    )
    op.execute(
        sa.text(
            "INSERT INTO recurring_partner_billing_periods "
            "(contract_id, effective_month, partner_id, billing_mode, partner_payment_amount) "
            "SELECT id, '0001-01', default_partner_id, partner_billing_mode, "
            "partner_payment_amount "
            "FROM recurring_contracts"
        )
    )
    reconcile_legacy_recurring_order_settlements(op.get_bind())
    backfill_incurred_monthly_statuses(op.get_bind())
    op.execute(
        sa.text(
            "UPDATE recurring_contracts "
            "SET active_segment_start_date = start_date "
            "WHERE status = 'active' AND deleted_at IS NULL"
        )
    )


def lock_downgrade_state(connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(
            sa.text(
                "LOCK TABLE partners, recurring_contracts, "
                "orders, recurring_monthly_status, recurring_partner_billing_periods "
                "IN ACCESS EXCLUSIVE MODE"
            )
        )


def ensure_downgrade_preserves_billing_history(connection) -> None:
    history_exists = connection.execute(
        sa.text(
            "SELECT 1 FROM recurring_partner_billing_periods "
            "WHERE effective_month <> '0001-01' LIMIT 1"
        )
    ).first()
    if history_exists is not None:
        raise RuntimeError(
            "cannot downgrade 0031: effective-month partner billing history exists"
        )
    archived_partner_exists = connection.execute(
        sa.text("SELECT 1 FROM partners WHERE deleted_at IS NOT NULL LIMIT 1")
    ).first()
    if archived_partner_exists is not None:
        raise RuntimeError("cannot downgrade 0031: archived partner state exists")
    resumed_segment_exists = connection.execute(
        sa.text(
            "SELECT 1 FROM recurring_contracts "
            "WHERE active_segment_start_date IS NOT NULL "
            "AND (active_segment_start_date <> start_date "
            "OR status <> 'active' OR deleted_at IS NOT NULL) LIMIT 1"
        )
    ).first()
    if resumed_segment_exists is not None:
        raise RuntimeError("cannot downgrade 0031: resumed billing segment exists")
    retained_order_exists = connection.execute(
        sa.text(
            "SELECT 1 FROM orders "
            "WHERE recurring_partner_settlement_retained IS TRUE LIMIT 1"
        )
    ).first()
    if retained_order_exists is not None:
        raise RuntimeError("cannot downgrade 0031: retained per-visit settlement exists")
    retained_monthly_exists = connection.execute(
        sa.text(
            "SELECT 1 FROM recurring_monthly_status "
            "WHERE retained_partner_payment_amount IS NOT NULL LIMIT 1"
        )
    ).first()
    if retained_monthly_exists is not None:
        raise RuntimeError("cannot downgrade 0031: retained monthly settlement exists")


def downgrade() -> None:
    connection = op.get_bind()
    lock_downgrade_state(connection)
    ensure_downgrade_preserves_billing_history(connection)
    op.drop_table("recurring_partner_billing_periods")
    op.drop_column("recurring_contracts", "active_segment_start_date")
    op.drop_column("orders", "recurring_partner_settlement_retained")
    op.drop_constraint(
        "fk_recurring_monthly_retained_partner",
        "recurring_monthly_status",
        type_="foreignkey",
    )
    op.drop_column("recurring_monthly_status", "retained_partner_payment_amount")
    op.drop_column("recurring_monthly_status", "retained_partner_id")
    op.drop_index("ix_partners_deleted_at", table_name="partners")
    op.drop_column("partners", "deleted_at")
