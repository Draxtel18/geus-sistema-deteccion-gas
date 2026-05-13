from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import relationship

from app.infrastructure.database.connection import Base


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_role = Column(String(20), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    sensor_id = Column(UUID(as_uuid=True), ForeignKey("sensors.id", ondelete="SET NULL"), nullable=True, index=True)
    details = Column(JSONB, default=dict, nullable=False)
    ip_origin = Column(INET, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("UserModel", back_populates="audit_logs")
    sensor = relationship("SensorModel")
