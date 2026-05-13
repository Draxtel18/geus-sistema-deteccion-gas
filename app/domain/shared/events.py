from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(kw_only=True)
class DomainEvent(ABC):
    aggregate_id: UUID | None = None
    event_version: int = 1
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "event_type": self.__class__.__name__,
            "occurred_at": self.occurred_at.isoformat(),
            "aggregate_id": str(self.aggregate_id) if self.aggregate_id else None,
            "event_version": self.event_version,
        }


@dataclass
class GasDetectedEvent(DomainEvent):
    sensor_id: UUID
    gas_ppm: float
    temperature_c: float
    humidity_percent: float
    is_critical: bool


@dataclass
class ValveClosedEvent(DomainEvent):
    sensor_id: UUID
    valve_id: UUID
    source: str
    gas_level_ppm: float


@dataclass
class ValveOpenedEvent(DomainEvent):
    sensor_id: UUID
    valve_id: UUID
    opened_by: UUID | None


@dataclass
class DissipatorActivatedEvent(DomainEvent):
    sensor_id: UUID
    dissipator_id: UUID
    activation_mode: str
    triggered_by_alert: bool


@dataclass
class DissipatorDeactivatedEvent(DomainEvent):
    sensor_id: UUID
    dissipator_id: UUID
    deactivated_by: UUID | None


@dataclass
class AlertCreatedEvent(DomainEvent):
    alert_id: UUID
    sensor_id: UUID
    gas_level_ppm: float
    severity: str


@dataclass
class AlertAcknowledgedEvent(DomainEvent):
    alert_id: UUID
    acknowledged_by: UUID


@dataclass
class AlertResolvedEvent(DomainEvent):
    alert_id: UUID
    resolved_by: UUID | None
    auto_resolved: bool
