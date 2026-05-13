from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.alert.entities import Alert, AlertSeverity, AlertStatus


class IAlertRepository(ABC):
    @abstractmethod
    async def get_by_id(self, alert_id: UUID) -> Alert | None:
        pass

    @abstractmethod
    async def list_by_sensor(self, sensor_id: UUID, skip: int = 0, limit: int = 100) -> list[Alert]:
        pass

    @abstractmethod
    async def list_by_status(
        self, status: AlertStatus, skip: int = 0, limit: int = 100
    ) -> list[Alert]:
        pass

    @abstractmethod
    async def list_active_alerts(self, skip: int = 0, limit: int = 100) -> list[Alert]:
        pass

    @abstractmethod
    async def list_by_severity(
        self, severity: AlertSeverity, skip: int = 0, limit: int = 100
    ) -> list[Alert]:
        pass

    @abstractmethod
    async def list_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        sensor_id: UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Alert]:
        pass

    @abstractmethod
    async def save(self, alert: Alert) -> Alert:
        pass

    @abstractmethod
    async def update(self, alert: Alert) -> Alert:
        pass

    @abstractmethod
    async def get_active_alert_for_sensor(self, sensor_id: UUID) -> Alert | None:
        pass
