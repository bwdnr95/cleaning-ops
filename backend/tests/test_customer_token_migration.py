from collections.abc import Callable
from pathlib import Path
from runpy import run_path
from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Column, MetaData, String, Table, create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError


def test_existing_customer_tokens_are_rotated_and_mirrored() -> None:
    migration_path = (
        Path(__file__).parents[1] / "alembic" / "versions" / "0029_orders_as_intake_pending.py"
    )
    namespace = run_path(str(migration_path))
    rotate_tokens = cast(
        Callable[[Connection], None],
        namespace["_rotate_existing_customer_tokens"],
    )
    engine = create_engine("sqlite://")

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE order_groups "
                "(id VARCHAR PRIMARY KEY, customer_token VARCHAR UNIQUE NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE orders "
                "(id VARCHAR PRIMARY KEY, group_id VARCHAR NOT NULL, customer_token VARCHAR)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO order_groups (id, customer_token) "
                "VALUES ('group-a', 'legacy-a'), ('group-b', 'legacy-b')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO orders (id, group_id, customer_token) VALUES "
                "('order-a1', 'group-a', 'legacy-a'), "
                "('order-a2', 'group-a', 'legacy-a'), "
                "('order-b1', 'group-b', 'legacy-b')"
            )
        )

        rotate_tokens(connection)

        group_rows = (
            connection.execute(text("SELECT id, customer_token FROM order_groups")).mappings().all()
        )
        groups: dict[str, str] = {str(row["id"]): str(row["customer_token"]) for row in group_rows}
        order_rows = (
            connection.execute(text("SELECT group_id, customer_token FROM orders")).mappings().all()
        )
        orders = [(str(row["group_id"]), str(row["customer_token"])) for row in order_rows]

    assert set(groups.values()).isdisjoint({"legacy-a", "legacy-b"})
    assert len(set(groups.values())) == 2
    assert all(token.startswith("ct2_") for token in groups.values())
    assert all(token == groups[group_id] for group_id, token in orders)


def test_customer_token_constraints_require_a_literal_underscore() -> None:
    migration_path = (
        Path(__file__).parents[1] / "alembic" / "versions" / "0029_orders_as_intake_pending.py"
    )
    namespace = run_path(str(migration_path))
    group_expression = str(namespace["GROUP_TOKEN_CHECK_EXPRESSION"])
    order_expression = str(namespace["ORDER_TOKEN_CHECK_EXPRESSION"])
    metadata = MetaData()
    group_tokens = Table(
        "group_tokens",
        metadata,
        Column("id", String, primary_key=True),
        Column("customer_token", String, nullable=False),
        CheckConstraint(group_expression),
    )
    order_tokens = Table(
        "order_tokens",
        metadata,
        Column("id", String, primary_key=True),
        Column("customer_token", String),
        CheckConstraint(order_expression),
    )
    engine = create_engine("sqlite://")
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(group_tokens.insert().values(id="valid", customer_token="ct2_valid"))
        connection.execute(order_tokens.insert().values(id="nullable", customer_token=None))

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                group_tokens.insert().values(id="invalid-group", customer_token="ct2Xlegacy")
            )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                order_tokens.insert().values(id="invalid-order", customer_token="ct2Xlegacy")
            )
