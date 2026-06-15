from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import relationship

from app.infrastructure.database.base import Base


class UserModel(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    notifications_enabled = Column(Boolean, default=True, nullable=False)
    notification_devices = Column(JSONB, default=list, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(INET, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    sensor_assignments = relationship("UserSensorAssignmentModel", back_populates="user", foreign_keys="[UserSensorAssignmentModel.user_id]", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLogModel", back_populates="user", foreign_keys="[AuditLogModel.user_id]")
    push_tokens = relationship("PushTokenModel", back_populates="user", cascade="all, delete-orphan")


class UserSensorAssignmentModel(Base):
    __tablename__ = "user_sensor_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sensor_id = Column(UUID(as_uuid=True), ForeignKey("sensors.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    user = relationship("UserModel", back_populates="sensor_assignments", foreign_keys=[user_id])
    sensor = relationship("SensorModel", back_populates="sensor_assignments")
    assigner = relationship("UserModel", foreign_keys=[assigned_by])
