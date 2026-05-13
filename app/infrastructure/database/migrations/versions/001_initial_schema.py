"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2026-05-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, index=True),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('notifications_enabled', sa.Boolean(), default=True, nullable=False),
        sa.Column('notification_devices', postgresql.JSONB(), default=list, nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('last_login_ip', postgresql.INET(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'sensors',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('device_id', sa.String(64), unique=True, nullable=False, index=True),
        sa.Column('location', sa.String(255), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('wifi_signal', sa.Integer(), nullable=True),
        sa.Column('mqtt_connected', sa.Boolean(), default=False, nullable=False),
        sa.Column('uptime_seconds', sa.Integer(), default=0, nullable=False),
        sa.Column('test_mode', sa.Boolean(), default=False, nullable=False),
        sa.Column('test_mode_expires_at', sa.DateTime(), nullable=True),
        sa.Column('correction_factor', sa.Float(), default=1.0, nullable=False),
        sa.Column('last_reading_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'valves',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('sensor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sensors.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('state', sa.String(10), nullable=False),
        sa.Column('last_state_change', sa.DateTime(), nullable=False),
        sa.Column('mechanical_status', sa.String(10), default='ok', nullable=False),
        sa.Column('last_command_source', sa.String(10), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'dissipators',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('sensor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sensors.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('state', sa.String(10), nullable=False),
        sa.Column('activation_mode', sa.String(10), nullable=False),
        sa.Column('last_state_change', sa.DateTime(), nullable=False),
        sa.Column('mechanical_status', sa.String(10), default='ok', nullable=False),
        sa.Column('locked_by_alert', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('sensor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sensors.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('gas_level_ppm', sa.Float(), nullable=False),
        sa.Column('severity', sa.String(10), nullable=False, index=True),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('triggered_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('auto_resolved', sa.Boolean(), default=False, nullable=False),
        sa.Column('notifications_sent', postgresql.JSONB(), default=list, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'user_sensor_assignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sensor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sensors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.Column('assigned_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )

    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('user_role', sa.String(20), nullable=True),
        sa.Column('action', sa.String(100), nullable=False, index=True),
        sa.Column('sensor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sensors.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('details', postgresql.JSONB(), default=dict, nullable=False),
        sa.Column('ip_origin', postgresql.INET(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'global_config',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('key', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('value', postgresql.JSONB(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('global_config')
    op.drop_table('audit_logs')
    op.drop_table('user_sensor_assignments')
    op.drop_table('alerts')
    op.drop_table('dissipators')
    op.drop_table('valves')
    op.drop_table('sensors')
    op.drop_table('users')
