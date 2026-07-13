"""Drop token-format constraints left by the original 0029 rollout.

Existing customer links are preserved. New tokens are generated with the ct2_ prefix
by application code, while rollback-compatible legacy rows remain valid.

Revision ID: 0030_drop_legacy_customer_token_constraints
Revises: 0029_orders_as_intake_pending
"""

import sqlalchemy as sa

from alembic import op

revision = "0030_drop_legacy_customer_token_constraints"
down_revision = "0029_orders_as_intake_pending"
branch_labels = None
depends_on = None

GROUP_TOKEN_CHECK = "customer_token_ct2"
ORDER_TOKEN_CHECK = "customer_token_ct2_or_null"


def _sqlite_constraint_names(table_name: str) -> set[str]:
    return {
        str(item["name"])
        for item in sa.inspect(op.get_bind()).get_check_constraints(table_name)
        if item.get("name")
    }


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        order_constraints = _sqlite_constraint_names("orders")
        if ORDER_TOKEN_CHECK in order_constraints:
            with op.batch_alter_table("orders") as batch_op:
                batch_op.drop_constraint(ORDER_TOKEN_CHECK, type_="check")
        group_constraints = _sqlite_constraint_names("order_groups")
        if GROUP_TOKEN_CHECK in group_constraints:
            with op.batch_alter_table("order_groups") as batch_op:
                batch_op.drop_constraint(GROUP_TOKEN_CHECK, type_="check")
        return

    op.execute(
        f"ALTER TABLE orders DROP CONSTRAINT IF EXISTS {ORDER_TOKEN_CHECK}"
    )
    op.execute(
        f"ALTER TABLE order_groups DROP CONSTRAINT IF EXISTS {GROUP_TOKEN_CHECK}"
    )


def downgrade() -> None:
    # Constraint removal is intentionally forward-only. Re-adding the format gate
    # would make preserved pre-ct2 customer links invalid during a code rollback.
    pass
