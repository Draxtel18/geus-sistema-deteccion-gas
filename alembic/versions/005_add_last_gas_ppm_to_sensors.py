"""Add last_gas_ppm column to sensors table

Revision ID: 005
Revises: 004
Create Date: 2026-06-14

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: str = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('sensors', sa.Column('last_gas_ppm', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('sensors', 'last_gas_ppm')
