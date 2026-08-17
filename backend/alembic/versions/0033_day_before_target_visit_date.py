from datetime import UTC, timedelta
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from alembic import op

revision = "0033_day_before_target_visit_date"
down_revision = "0032_order_visit_dates"
branch_labels = None
depends_on = None


def _backfill_day_before_target_dates(connection) -> None:
    message_logs = sa.table(
        "message_logs",
        sa.column("id", sa.String(36)),
        sa.column("message_type", sa.String(80)),
        sa.column("target_visit_date", sa.Date()),
        sa.column("requested_at", sa.DateTime(timezone=True)),
        sa.column("sent_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    rows = connection.execute(
        sa.select(
            message_logs.c.id,
            message_logs.c.requested_at,
            message_logs.c.sent_at,
            message_logs.c.created_at,
        ).where(
            message_logs.c.message_type == "customer_day_before",
            message_logs.c.target_visit_date.is_(None),
        )
    ).all()
    business_timezone = ZoneInfo("Asia/Seoul")
    for log_id, requested_at, sent_at, created_at in rows:
        attempted_at = requested_at or sent_at or created_at
        if attempted_at is None:
            continue
        if attempted_at.tzinfo is None:
            attempted_at = attempted_at.replace(tzinfo=UTC)
        target_visit_date = attempted_at.astimezone(business_timezone).date() + timedelta(
            days=1
        )
        connection.execute(
            message_logs.update()
            .where(message_logs.c.id == log_id)
            .values(target_visit_date=target_visit_date)
        )


def upgrade() -> None:
    connection = op.get_bind()
    op.add_column("message_logs", sa.Column("target_visit_date", sa.Date(), nullable=True))
    _backfill_day_before_target_dates(connection)


def downgrade() -> None:
    op.drop_column("message_logs", "target_visit_date")
