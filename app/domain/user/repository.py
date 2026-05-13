from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.user.entities import User, UserRole, UserSensorAssignment


class IUserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None:
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        pass

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        pass

    @abstractmethod
    async def list_by_role(self, role: UserRole, skip: int = 0, limit: int = 100) -> list[User]:
        pass

    @abstractmethod
    async def save(self, user: User) -> User:
        pass

    @abstractmethod
    async def update(self, user: User) -> User:
        pass

    @abstractmethod
    async def delete(self, user_id: UUID) -> bool:
        pass

    @abstractmethod
    async def get_sensor_assignments(self, user_id: UUID) -> list[UserSensorAssignment]:
        pass

    @abstractmethod
    async def assign_sensor(self, assignment: UserSensorAssignment) -> UserSensorAssignment:
        pass

    @abstractmethod
    async def unassign_sensor(self, user_id: UUID, sensor_id: UUID) -> bool:
        pass

    @abstractmethod
    async def get_assigned_sensors(self, user_id: UUID) -> list[UUID]:
        pass
