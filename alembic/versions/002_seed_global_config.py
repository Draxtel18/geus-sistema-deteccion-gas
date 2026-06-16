"""Seed global config

Revision ID: 002
Revises: 001
Create Date: 2026-05-12

"""
from collections.abc import Sequence
from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.constants import GAS_THRESHOLD_CRITICAL, GAS_THRESHOLD_WARNING

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    global_config_table = sa.table(
        "global_config",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("key", sa.String),
        sa.column("value", postgresql.JSONB),
        sa.column("updated_at", sa.DateTime),
        sa.column("updated_by", postgresql.UUID(as_uuid=True)),
    )

    op.bulk_insert(
        global_config_table,
        [
            {
                "id": uuid4(),
                "key": "gas_threshold_warning",
                "value": {"value": int(GAS_THRESHOLD_WARNING), "unit": "ppm"},
                "updated_at": datetime.utcnow(),
                "updated_by": None,
            },
            {
                "id": uuid4(),
                "key": "gas_threshold_critical",
                "value": {"value": int(GAS_THRESHOLD_CRITICAL), "unit": "ppm"},
                "updated_at": datetime.utcnow(),
                "updated_by": None,
            },
            {
                "id": uuid4(),
                "key": "test_mode_timeout_minutes",
                "value": {"value": 30},
                "updated_at": datetime.utcnow(),
                "updated_by": None,
            },
            {
                "id": uuid4(),
                "key": "alert_notification_timeout_seconds",
                "value": {"value": 30},
                "updated_at": datetime.utcnow(),
                "updated_by": None,
            },
            {
                "id": uuid4(),
                "key": "data_retention_days",
                "value": {"value": 180},
                "updated_at": datetime.utcnow(),
                "updated_by": None,
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM global_config WHERE key IN ('gas_threshold_warning', 'gas_threshold_critical', 'test_mode_timeout_minutes', 'alert_notification_timeout_seconds', 'data_retention_days')"
    )
