from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.domain.shared.exceptions import AlertAlreadyResolvedError


class AlertSeverity(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


@dataclass
class Alert:
    id: UUID
    sensor_id: UUID
    gas_level_ppm: float
    severity: AlertSeverity
    status: AlertStatus
    triggered_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: UUID | None = None
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None
    auto_resolved: bool = False
    notifications_sent: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if self.severity == AlertSeverity.WARNING and not (200 <= self.gas_level_ppm < 500):
            raise ValueError("Warning alerts must have gas level between 200 and 500 ppm")
        if self.severity == AlertSeverity.CRITICAL and self.gas_level_ppm < 500:
            raise ValueError("Critical alerts must have gas level >= 500 ppm")

    def acknowledge(self, user_id: UUID) -> None:
        if self.status == AlertStatus.RESOLVED:
            raise AlertAlreadyResolvedError(str(self.id))

        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.utcnow()
        self.acknowledged_by = user_id

    def resolve(self, user_id: UUID | None = None, auto: bool = False) -> None:
        if self.status == AlertStatus.RESOLVED:
            raise AlertAlreadyResolvedError(str(self.id))

        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.utcnow()
        self.resolved_by = user_id
        self.auto_resolved = auto

    def add_notification(self, notification_type: str, recipient: str, success: bool) -> None:
        self.notifications_sent.append(
            {
                "type": notification_type,
                "recipient": recipient,
                "success": success,
                "sent_at": datetime.utcnow().isoformat(),
            }
        )

    def is_active(self) -> bool:
        return self.status in (AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED)

    def is_critical(self) -> bool:
        return self.severity == AlertSeverity.CRITICAL
