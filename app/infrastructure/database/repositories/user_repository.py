from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.user.entities import UserRole, User, UserSensorAssignment, UserStatus
from app.domain.user.repository import IUserRepository
from app.infrastructure.database.models.user import UserModel, UserSensorAssignmentModel


class UserRepository(IUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        result = await self.session.execute(
            select(UserModel).offset(skip).limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def list_by_role(self, role: UserRole, skip: int = 0, limit: int = 100) -> list[User]:
        result = await self.session.execute(
            select(UserModel).where(UserModel.role == role.value).offset(skip).limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def save(self, user: User) -> User:
        model = self._to_model(user)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def update(self, user: User) -> User:
        result = await self.session.execute(
            select(UserModel).where(UserModel.id == user.id)
        )
        model = result.scalar_one_or_none()

        if model:
            model.email = user.email
            model.password_hash = user.password_hash
            model.name = user.full_name
            model.role = user.role.value
            model.status = user.status.value
            model.last_login_at = user.last_login_at
            model.updated_at = user.updated_at

            await self.session.flush()
            await self.session.refresh(model)
            return self._to_entity(model)

        return user

    async def delete(self, user_id: UUID) -> bool:
        result = await self.session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        model = result.scalar_one_or_none()

        if model:
            await self.session.delete(model)
            await self.session.flush()
            return True

        return False

    async def get_sensor_assignments(self, user_id: UUID) -> list[UserSensorAssignment]:
        result = await self.session.execute(
            select(UserSensorAssignmentModel).where(UserSensorAssignmentModel.user_id == user_id)
        )
        models = result.scalars().all()
        return [self._assignment_to_entity(model) for model in models]

    async def get_assigned_sensors(self, user_id: UUID) -> list[UUID]:
        result = await self.session.execute(
            select(UserSensorAssignmentModel.sensor_id).where(
                UserSensorAssignmentModel.user_id == user_id
            )
        )
        return list(result.scalars().all())

    async def assign_sensor(self, assignment: UserSensorAssignment) -> UserSensorAssignment:
        model = self._assignment_to_model(assignment)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._assignment_to_entity(model)

    async def unassign_sensor(self, user_id: UUID, sensor_id: UUID) -> bool:
        result = await self.session.execute(
            select(UserSensorAssignmentModel).where(
                UserSensorAssignmentModel.user_id == user_id,
                UserSensorAssignmentModel.sensor_id == sensor_id
            )
        )
        model = result.scalar_one_or_none()

        if model:
            await self.session.delete(model)
            await self.session.flush()
            return True

        return False

    async def delete_sensor_assignment(self, assignment_id: UUID) -> bool:
        result = await self.session.execute(
            select(UserSensorAssignmentModel).where(UserSensorAssignmentModel.id == assignment_id)
        )
        model = result.scalar_one_or_none()

        if model:
            await self.session.delete(model)
            await self.session.flush()
            return True

        return False

    def _to_entity(self, model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            full_name=model.name,
            role=UserRole(model.role),
            status=UserStatus(model.status),
            last_login_at=model.last_login_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: User) -> UserModel:
        return UserModel(
            id=entity.id,
            email=entity.email,
            password_hash=entity.password_hash,
            name=entity.full_name,
            role=entity.role.value,
            status=entity.status.value,
            last_login_at=entity.last_login_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def _assignment_to_entity(self, model: UserSensorAssignmentModel) -> UserSensorAssignment:
        return UserSensorAssignment(
            id=model.id,
            user_id=model.user_id,
            sensor_id=model.sensor_id,
            assigned_at=model.assigned_at,
            assigned_by=getattr(model, 'assigned_by', None),
        )

    def _assignment_to_model(self, entity: UserSensorAssignment) -> UserSensorAssignmentModel:
        return UserSensorAssignmentModel(
            id=entity.id,
            user_id=entity.user_id,
            sensor_id=entity.sensor_id,
            assigned_at=entity.assigned_at,
        )
