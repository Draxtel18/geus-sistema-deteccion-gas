from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.infrastructure.database.connection import Base


class AlertModel(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    sensor_id = Column(UUID(as_uuid=True), ForeignKey("sensors.id", ondelete="CASCADE"), nullable=False, index=True)
    gas_level_ppm = Column(Float, nullable=False)
    severity = Column(String(10), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    triggered_at = Column(DateTime, nullable=False, index=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    auto_resolved = Column(Boolean, default=False, nullable=False)
    notifications_sent = Column(JSONB, default=list, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sensor = relationship("SensorModel", back_populates="alerts")
    acknowledger = relationship("UserModel", foreign_keys=[acknowledged_by])
    resolver = relationship("UserModel", foreign_keys=[resolved_by])
