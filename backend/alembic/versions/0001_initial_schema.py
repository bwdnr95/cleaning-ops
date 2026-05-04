"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def created_at_column() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "partners",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("manager_name", sa.String(length=80)),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("service_areas", sa.Text()),
        sa.Column("available_services", sa.Text()),
        sa.Column("memo", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamp_columns(),
    )
    op.create_index("ix_partners_name", "partners", ["name"])

    op.create_table(
        "service_categories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *timestamp_columns(),
    )
    op.create_index("ix_service_categories_name", "service_categories", ["name"])

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=255), unique=True),
        sa.Column("phone", sa.String(length=30)),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("partner_id", sa.String(length=36), sa.ForeignKey("partners.id")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        *timestamp_columns(),
    )
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "service_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("category_id", sa.String(length=36), sa.ForeignKey("service_categories.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("base_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *timestamp_columns(),
    )
    op.create_index("ix_service_items_name", "service_items", ["name"])

    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="신규접수"),
        sa.Column("received_date", sa.Date(), nullable=False),
        sa.Column("scheduled_date", sa.Date()),
        sa.Column("requested_time", sa.String(length=80)),
        sa.Column("partner_id", sa.String(length=36), sa.ForeignKey("partners.id")),
        sa.Column("team_name", sa.String(length=120)),
        sa.Column("service_category_id", sa.String(length=36), sa.ForeignKey("service_categories.id")),
        sa.Column("service_item_id", sa.String(length=36), sa.ForeignKey("service_items.id")),
        sa.Column("service_name", sa.String(length=160), nullable=False),
        sa.Column("size_or_quantity", sa.String(length=80)),
        sa.Column("service_detail", sa.Text()),
        sa.Column("special_request", sa.Text()),
        sa.Column("source_channel", sa.String(length=120)),
        sa.Column("customer_name", sa.String(length=80), nullable=False),
        sa.Column("customer_phone", sa.String(length=30), nullable=False),
        sa.Column("customer_address", sa.Text(), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2)),
        sa.Column("deposit_amount", sa.Numeric(12, 2)),
        sa.Column("balance_amount", sa.Numeric(12, 2)),
        sa.Column("onsite_extra_amount", sa.Numeric(12, 2)),
        sa.Column("vat_type", sa.String(length=20)),
        sa.Column("payment_status", sa.String(length=40)),
        sa.Column("payment_memo", sa.Text()),
        sa.Column("evidence_memo", sa.Text()),
        sa.Column("partner_payment_amount", sa.Numeric(12, 2)),
        sa.Column("partner_payment_status", sa.String(length=40)),
        sa.Column("customer_token", sa.String(length=80), nullable=False, unique=True),
        sa.Column("customer_visible_payment", sa.Boolean(), nullable=False, server_default=sa.false()),
        *timestamp_columns(),
    )
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_received_date", "orders", ["received_date"])
    op.create_index("ix_orders_scheduled_date", "orders", ["scheduled_date"])
    op.create_index("ix_orders_partner_id", "orders", ["partner_id"])
    op.create_index("ix_orders_customer_name", "orders", ["customer_name"])
    op.create_index("ix_orders_customer_phone", "orders", ["customer_phone"])
    op.create_index("ix_orders_customer_token", "orders", ["customer_token"])
    op.create_index("ix_orders_payment_status", "orders", ["payment_status"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        created_at_column(),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])
    op.create_index("ix_refresh_tokens_revoked_at", "refresh_tokens", ["revoked_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("ip_address", sa.String(length=80)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("details", sa.JSON()),
        created_at_column(),
    )
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_logs_severity", "audit_logs", ["severity"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])

    op.create_table(
        "order_photos",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("order_id", sa.String(length=36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("uploaded_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("photo_type", sa.String(length=20), nullable=False),
        sa.Column("file_url", sa.String(length=1000), nullable=False),
        sa.Column("file_name", sa.String(length=255)),
        sa.Column("file_size", sa.Integer()),
        sa.Column("is_customer_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        created_at_column(),
    )
    op.create_index("ix_order_photos_order_id", "order_photos", ["order_id"])
    op.create_index("ix_order_photos_photo_type", "order_photos", ["photo_type"])
    op.create_index("ix_order_photos_is_customer_visible", "order_photos", ["is_customer_visible"])

    op.create_table(
        "message_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("order_id", sa.String(length=36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("recipient_type", sa.String(length=20), nullable=False),
        sa.Column("recipient_name", sa.String(length=80), nullable=False),
        sa.Column("recipient_phone", sa.String(length=30), nullable=False),
        sa.Column("message_type", sa.String(length=80), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        created_at_column(),
    )
    op.create_index("ix_message_logs_order_id", "message_logs", ["order_id"])
    op.create_index("ix_message_logs_recipient_type", "message_logs", ["recipient_type"])
    op.create_index("ix_message_logs_message_type", "message_logs", ["message_type"])
    op.create_index("ix_message_logs_status", "message_logs", ["status"])

    op.create_table(
        "order_timeline",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("order_id", sa.String(length=36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), sa.ForeignKey("users.id")),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("metadata", sa.JSON()),
        created_at_column(),
    )
    op.create_index("ix_order_timeline_order_id", "order_timeline", ["order_id"])
    op.create_index("ix_order_timeline_event_type", "order_timeline", ["event_type"])


def downgrade() -> None:
    op.drop_table("order_timeline")
    op.drop_table("message_logs")
    op.drop_table("order_photos")
    op.drop_table("audit_logs")
    op.drop_table("refresh_tokens")
    op.drop_table("orders")
    op.drop_table("service_items")
    op.drop_table("users")
    op.drop_table("service_categories")
    op.drop_table("partners")
