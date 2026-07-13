from secrets import token_urlsafe

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import op

revision = "0029_orders_as_intake_pending"
down_revision = "0028_orders_active_as_request_id"
branch_labels = None
depends_on = None

CUSTOMER_TOKEN_PREFIX = "ct2_"
GROUP_TOKEN_CHECK = "customer_token_ct2"
ORDER_TOKEN_CHECK = "customer_token_ct2_or_null"
GROUP_TOKEN_CHECK_EXPRESSION = "substr(customer_token, 1, 4) = 'ct2_'"
ORDER_TOKEN_CHECK_EXPRESSION = "customer_token IS NULL OR substr(customer_token, 1, 4) = 'ct2_'"

POSTGRES_ROTATE_TOKENS_SQL = sa.text(
    """
    UPDATE order_groups
    SET customer_token = 'ct2_'
        || replace(gen_random_uuid()::text, '-', '')
        || replace(gen_random_uuid()::text, '-', '')
    """
)
POSTGRES_MIRROR_TOKENS_SQL = sa.text(
    """
    UPDATE orders AS orders_line
    SET customer_token = order_groups.customer_token
    FROM order_groups
    WHERE orders_line.group_id = order_groups.id
      AND orders_line.customer_token IS DISTINCT FROM order_groups.customer_token
    """
)
POSTGRES_VERIFY_TOKENS_SQL = sa.text(
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM order_groups
            WHERE customer_token IS NULL
               OR substr(customer_token, 1, 4) <> 'ct2_'
        ) OR EXISTS (
            SELECT 1
            FROM orders AS orders_line
            LEFT JOIN order_groups ON order_groups.id = orders_line.group_id
            WHERE orders_line.customer_token IS NULL
               OR substr(orders_line.customer_token, 1, 4) <> 'ct2_'
               OR orders_line.customer_token IS DISTINCT FROM order_groups.customer_token
        ) THEN
            RAISE EXCEPTION 'customer token rotation verification failed';
        END IF;
    END
    $$
    """
)


def _next_customer_token(used_tokens: set[str]) -> str:
    while True:
        token = f"{CUSTOMER_TOKEN_PREFIX}{token_urlsafe(24)}"
        if token not in used_tokens:
            return token


def _rotate_existing_customer_tokens(connection: Connection) -> None:
    rows = (
        connection.execute(sa.text("SELECT id, customer_token FROM order_groups")).mappings().all()
    )
    used_tokens = {str(row["customer_token"]) for row in rows}
    for row in rows:
        group_id = str(row["id"])
        new_token = _next_customer_token(used_tokens)
        connection.execute(
            sa.text("UPDATE order_groups SET customer_token = :token WHERE id = :group_id"),
            {"token": new_token, "group_id": group_id},
        )
        connection.execute(
            sa.text("UPDATE orders SET customer_token = :token WHERE group_id = :group_id"),
            {"token": new_token, "group_id": group_id},
        )
        used_tokens.add(new_token)


def _create_token_constraints(dialect_name: str) -> None:
    if dialect_name == "sqlite":
        with op.batch_alter_table("order_groups") as batch_op:
            batch_op.create_check_constraint(
                GROUP_TOKEN_CHECK,
                GROUP_TOKEN_CHECK_EXPRESSION,
            )
        with op.batch_alter_table("orders") as batch_op:
            batch_op.create_check_constraint(
                ORDER_TOKEN_CHECK,
                ORDER_TOKEN_CHECK_EXPRESSION,
            )
        return
    op.create_check_constraint(
        GROUP_TOKEN_CHECK,
        "order_groups",
        GROUP_TOKEN_CHECK_EXPRESSION,
    )
    op.create_check_constraint(
        ORDER_TOKEN_CHECK,
        "orders",
        ORDER_TOKEN_CHECK_EXPRESSION,
    )


def _drop_token_constraints(dialect_name: str) -> None:
    if dialect_name == "sqlite":
        with op.batch_alter_table("orders") as batch_op:
            batch_op.drop_constraint(ORDER_TOKEN_CHECK, type_="check")
        with op.batch_alter_table("order_groups") as batch_op:
            batch_op.drop_constraint(GROUP_TOKEN_CHECK, type_="check")
        return
    op.drop_constraint(ORDER_TOKEN_CHECK, "orders", type_="check")
    op.drop_constraint(GROUP_TOKEN_CHECK, "order_groups", type_="check")


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "as_intake_pending",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    connection = op.get_bind()
    dialect_name = connection.dialect.name
    if dialect_name == "postgresql":
        op.execute("LOCK TABLE order_groups, orders IN ACCESS EXCLUSIVE MODE")
        op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_customer_token_key")
        op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS uq_orders_customer_token")
        op.execute(POSTGRES_ROTATE_TOKENS_SQL)
        op.execute(POSTGRES_MIRROR_TOKENS_SQL)
        op.execute(POSTGRES_VERIFY_TOKENS_SQL)
    else:
        _rotate_existing_customer_tokens(connection)
    _create_token_constraints(dialect_name)


def downgrade() -> None:
    _drop_token_constraints(op.get_bind().dialect.name)
    op.drop_column("orders", "as_intake_pending")
