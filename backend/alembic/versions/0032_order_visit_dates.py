from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "0032_order_visit_dates"
down_revision = "0031_partner_billing_periods"
branch_labels = None
depends_on = None


LEGACY_SYNC_FUNCTION = "sync_order_visits_from_legacy_schedule"
LEGACY_INSERT_TRIGGER = "trg_orders_sync_visits_after_insert"
LEGACY_UPDATE_TRIGGER = "trg_orders_sync_visits_after_schedule_update"


def lock_upgrade_state(connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(
            sa.text("LOCK TABLE orders IN SHARE ROW EXCLUSIVE MODE")
        )


def _create_legacy_schedule_sync(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    connection.execute(
        sa.text(
            f"""
            CREATE FUNCTION {LEGACY_SYNC_FUNCTION}()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                visit_count bigint;
                canonical_date date;
            BEGIN
                SELECT count(*), min(visit_date)
                INTO visit_count, canonical_date
                FROM order_visits
                WHERE order_id = NEW.id;

                IF visit_count > 1 AND (
                    NEW.scheduled_date IS NULL
                    OR canonical_date IS DISTINCT FROM NEW.scheduled_date
                ) THEN
                    RAISE EXCEPTION 'visit_dates_required_for_multi_visit_order'
                        USING ERRCODE = '23514';
                END IF;

                IF NEW.scheduled_date IS NULL THEN
                    DELETE FROM order_visits WHERE order_id = NEW.id;
                ELSIF canonical_date IS DISTINCT FROM NEW.scheduled_date THEN
                    DELETE FROM order_visits WHERE order_id = NEW.id;
                    INSERT INTO order_visits (id, order_id, visit_date)
                    VALUES (
                        md5(
                            NEW.id || NEW.scheduled_date::text
                            || clock_timestamp()::text || random()::text
                        ),
                        NEW.id,
                        NEW.scheduled_date
                    );
                END IF;
                RETURN NULL;
            END;
            $$
            """
        )
    )
    connection.execute(
        sa.text(
            f"""
            CREATE CONSTRAINT TRIGGER {LEGACY_INSERT_TRIGGER}
            AFTER INSERT ON orders
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW
            EXECUTE FUNCTION {LEGACY_SYNC_FUNCTION}()
            """
        )
    )
    connection.execute(
        sa.text(
            f"""
            CREATE CONSTRAINT TRIGGER {LEGACY_UPDATE_TRIGGER}
            AFTER UPDATE OF scheduled_date ON orders
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW
            EXECUTE FUNCTION {LEGACY_SYNC_FUNCTION}()
            """
        )
    )


def _drop_legacy_schedule_sync(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    connection.execute(
        sa.text(f"DROP TRIGGER IF EXISTS {LEGACY_INSERT_TRIGGER} ON orders")
    )
    connection.execute(
        sa.text(f"DROP TRIGGER IF EXISTS {LEGACY_UPDATE_TRIGGER} ON orders")
    )
    connection.execute(
        sa.text(f"DROP FUNCTION IF EXISTS {LEGACY_SYNC_FUNCTION}()")
    )


def _backfill_existing_visits(connection) -> None:
    orders = sa.table(
        "orders",
        sa.column("id", sa.String(36)),
        sa.column("scheduled_date", sa.Date()),
    )
    visits = sa.table(
        "order_visits",
        sa.column("id", sa.String(36)),
        sa.column("order_id", sa.String(36)),
        sa.column("visit_date", sa.Date()),
    )
    rows = connection.execute(
        sa.select(orders.c.id, orders.c.scheduled_date).where(
            orders.c.scheduled_date.is_not(None)
        )
    ).all()
    if rows:
        connection.execute(
            visits.insert(),
            [
                {
                    "id": str(uuid4()),
                    "order_id": order_id,
                    "visit_date": scheduled_date,
                }
                for order_id, scheduled_date in rows
            ],
        )


def _ensure_downgrade_is_representable(connection) -> None:
    orders = sa.table(
        "orders",
        sa.column("id", sa.String(36)),
        sa.column("scheduled_date", sa.Date()),
    )
    visits = sa.table(
        "order_visits",
        sa.column("order_id", sa.String(36)),
        sa.column("visit_date", sa.Date()),
    )
    nonrepresentable = connection.execute(
        sa.select(visits.c.order_id)
        .select_from(visits.join(orders, orders.c.id == visits.c.order_id))
        .group_by(visits.c.order_id, orders.c.scheduled_date)
        .having(
            sa.or_(
                sa.func.count(visits.c.order_id) > 1,
                orders.c.scheduled_date.is_(None),
                sa.func.min(visits.c.visit_date) != orders.c.scheduled_date,
            )
        )
        .limit(1)
    ).first()
    if nonrepresentable is not None:
        raise RuntimeError(
            "cannot downgrade while orders contain multiple or mismatched visit dates"
        )


def lock_downgrade_state(connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(
            sa.text("LOCK TABLE orders IN SHARE ROW EXCLUSIVE MODE")
        )
        connection.execute(
            sa.text("LOCK TABLE order_visits IN ACCESS EXCLUSIVE MODE")
        )


def upgrade() -> None:
    connection = op.get_bind()
    lock_upgrade_state(connection)
    op.create_table(
        "order_visits",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_order_visits_order_id_orders",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_order_visits"),
        sa.UniqueConstraint(
            "order_id",
            "visit_date",
            name="uq_order_visits_order_date",
        ),
    )
    op.create_index("ix_order_visits_order_id", "order_visits", ["order_id"])
    op.create_index("ix_order_visits_visit_date", "order_visits", ["visit_date"])
    _backfill_existing_visits(connection)
    _create_legacy_schedule_sync(connection)


def downgrade() -> None:
    connection = op.get_bind()
    lock_downgrade_state(connection)
    _drop_legacy_schedule_sync(connection)
    _ensure_downgrade_is_representable(connection)
    op.drop_index("ix_order_visits_visit_date", table_name="order_visits")
    op.drop_index("ix_order_visits_order_id", table_name="order_visits")
    op.drop_table("order_visits")
