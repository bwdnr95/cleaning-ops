from pathlib import Path
from runpy import run_path


def test_as_intake_migration_does_not_rotate_existing_customer_tokens() -> None:
    migration_path = (
        Path(__file__).parents[1] / "alembic" / "versions" / "0029_orders_as_intake_pending.py"
    )
    namespace = run_path(str(migration_path))
    source = migration_path.read_text(encoding="utf-8")

    assert namespace["revision"] == "0029_orders_as_intake_pending"
    assert namespace["down_revision"] == "0028_orders_active_as_request_id"
    assert "_rotate_existing_customer_tokens" not in namespace
    assert "UPDATE order_groups" not in source
    assert "UPDATE orders" not in source
    assert "create_check_constraint" not in source


def test_constraint_cleanup_revision_fits_alembic_version_column() -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0030_drop_legacy_customer_token_constraints.py"
    )
    namespace = run_path(str(migration_path))

    assert len(namespace["revision"]) <= 32
    assert namespace["down_revision"] == "0029_orders_as_intake_pending"
