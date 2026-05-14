from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.infrastructure.database.base import Base


class SensorModel(Base):
    __tablename__ = "sensors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id = Column(String(64), unique=True, nullable=False, index=True)
    location = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, index=True)
    wifi_signal = Column(Integer, nullable=True)
    mqtt_connected = Column(Boolean, default=False, nullable=False)
    uptime_seconds = Column(Integer, default=0, nullable=False)
    test_mode = Column(Boolean, default=False, nullable=False)
    test_mode_expires_at = Column(DateTime, nullable=True)
    correction_factor = Column(Float, default=1.0, nullable=False)
    last_reading_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    valve = relationship("ValveModel", back_populates="sensor", uselist=False, cascade="all, delete-orphan")
    dissipator = relationship("DissipatorModel", back_populates="sensor", uselist=False, cascade="all, delete-orphan")
    alerts = relationship("AlertModel", back_populates="sensor", cascade="all, delete-orphan")
    sensor_assignments = relationship("UserSensorAssignmentModel", back_populates="sensor", cascade="all, delete-orphan")


class ValveModel(Base):
    __tablename__ = "valves"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    sensor_id = Column(UUID(as_uuid=True), ForeignKey("sensors.id", ondelete="CASCADE"), unique=True, nullable=False)
    state = Column(String(10), nullable=False)
    last_state_change = Column(DateTime, nullable=False)
    mechanical_status = Column(String(10), default="ok", nullable=False)
    last_command_source = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    sensor = relationship("SensorModel", back_populates="valve")


class DissipatorModel(Base):
    __tablename__ = "dissipators"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    sensor_id = Column(UUID(as_uuid=True), ForeignKey("sensors.id", ondelete="CASCADE"), unique=True, nullable=False)
    state = Column(String(10), nullable=False)
    activation_mode = Column(String(10), nullable=False)
    last_state_change = Column(DateTime, nullable=False)
    mechanical_status = Column(String(10), default="ok", nullable=False)
    locked_by_alert = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    sensor = relationship("SensorModel", back_populates="dissipator")
