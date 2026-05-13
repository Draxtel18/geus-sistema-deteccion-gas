from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.sensor.entities import Dissipator, Sensor, Valve


class ISensorRepository(ABC):
    @abstractmethod
    async def get_by_id(self, sensor_id: UUID) -> Sensor | None:
        pass

    @abstractmethod
    async def get_by_device_id(self, device_id: str) -> Sensor | None:
        pass

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Sensor]:
        pass

    @abstractmethod
    async def list_by_status(self, status: str, skip: int = 0, limit: int = 100) -> list[Sensor]:
        pass

    @abstractmethod
    async def save(self, sensor: Sensor) -> Sensor:
        pass

    @abstractmethod
    async def update(self, sensor: Sensor) -> Sensor:
        pass

    @abstractmethod
    async def delete(self, sensor_id: UUID) -> bool:
        pass

    @abstractmethod
    async def get_valve_by_sensor_id(self, sensor_id: UUID) -> Valve | None:
        pass

    @abstractmethod
    async def save_valve(self, valve: Valve) -> Valve:
        pass

    @abstractmethod
    async def update_valve(self, valve: Valve) -> Valve:
        pass

    @abstractmethod
    async def get_dissipator_by_sensor_id(self, sensor_id: UUID) -> Dissipator | None:
        pass

    @abstractmethod
    async def save_dissipator(self, dissipator: Dissipator) -> Dissipator:
        pass

    @abstractmethod
    async def update_dissipator(self, dissipator: Dissipator) -> Dissipator:
        pass
