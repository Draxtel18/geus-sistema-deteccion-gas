from datetime import datetime
from uuid import UUID, uuid4

import structlog

from app.domain.user.entities import UserSensorAssignment
from app.domain.user.repository import IUserRepository

logger = structlog.get_logger()


class AssignSensors:
    def __init__(self, user_repository: IUserRepository) -> None:
        self.user_repository = user_repository

    async def execute(self, user_id: UUID, sensor_ids: list[UUID]) -> dict:
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        existing_assignments = await self.user_repository.get_sensor_assignments(user_id)
        existing_sensor_ids = {assignment.sensor_id for assignment in existing_assignments}

        new_assignments = []
        for sensor_id in sensor_ids:
            if sensor_id not in existing_sensor_ids:
                assignment = UserSensorAssignment(
                    id=uuid4(),
                    user_id=user_id,
                    sensor_id=sensor_id,
                    assigned_at=datetime.utcnow(),
                )
                saved_assignment = await self.user_repository.assign_sensor(assignment)
                new_assignments.append(saved_assignment)

        logger.info(
            "sensors_assigned",
            user_id=str(user_id),
            sensor_count=len(new_assignments),
            total_sensors=len(sensor_ids),
        )

        return {
            "user_id": str(user_id),
            "assigned_sensors": [str(sid) for sid in sensor_ids],
            "new_assignments": len(new_assignments),
            "total_assignments": len(existing_sensor_ids) + len(new_assignments),
        }
