from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ActionType(StrEnum):
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    SENSOR_CREATED = "sensor_created"
    SENSOR_UPDATED = "sensor_updated"
    SENSOR_DELETED = "sensor_deleted"
    ALERT_CREATED = "alert_created"
    ALERT_ACKNOWLEDGED = "alert_acknowledged"
    ALERT_RESOLVED = "alert_resolved"
    VALVE_CLOSED = "valve_closed"
    VALVE_OPENED = "valve_opened"
    DISSIPATOR_ACTIVATED = "dissipator_activated"
    DISSIPATOR_DEACTIVATED = "dissipator_deactivated"
    TEST_MODE_ACTIVATED = "test_mode_activated"
    PANIC_BUTTON_PRESSED = "panic_button_pressed"
    CONFIG_UPDATED = "config_updated"
    DATA_EXPORTED = "data_exported"


@dataclass
class AuditLog:
    id: UUID
    user_id: UUID | None
    action_type: ActionType
    resource_type: str
    resource_id: UUID | None
    details: dict
    ip_address: str | None
    user_agent: str | None
    timestamp: datetime
    created_at: datetime

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "action_type": self.action_type.value,
            "resource_type": self.resource_type,
            "resource_id": str(self.resource_id) if self.resource_id else None,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "timestamp": self.timestamp.isoformat(),
            "created_at": self.created_at.isoformat(),
        }
