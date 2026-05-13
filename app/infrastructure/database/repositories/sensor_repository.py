from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.sensor.entities import (
    ActivationMode,
    CommandSource,
    Dissipator,
    DissipatorState,
    MechanicalStatus,
    Sensor,
    SensorStatus,
    Valve,
    ValveState,
)
from app.domain.sensor.repository import ISensorRepository
from app.domain.shared.value_objects import Location
from app.infrastructure.database.models.sensor import DissipatorModel, SensorModel, ValveModel


class SensorRepository(ISensorRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, sensor_id: UUID) -> Sensor | None:
        result = await self.session.execute(
            select(SensorModel).where(SensorModel.id == sensor_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_device_id(self, device_id: str) -> Sensor | None:
        result = await self.session.execute(
            select(SensorModel).where(SensorModel.device_id == device_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Sensor]:
        result = await self.session.execute(
            select(SensorModel).offset(skip).limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def list_by_status(self, status: str, skip: int = 0, limit: int = 100) -> list[Sensor]:
        result = await self.session.execute(
            select(SensorModel).where(SensorModel.status == status).offset(skip).limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def save(self, sensor: Sensor) -> Sensor:
        model = self._to_model(sensor)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def update(self, sensor: Sensor) -> Sensor:
        result = await self.session.execute(
            select(SensorModel).where(SensorModel.id == sensor.id)
        )
        model = result.scalar_one_or_none()
        
        if model:
            model.device_id = sensor.device_id
            model.location = sensor.location.description
            model.status = sensor.status.value
            model.wifi_signal = sensor.wifi_signal
            model.mqtt_connected = sensor.mqtt_connected
            model.uptime_seconds = sensor.uptime_seconds
            model.test_mode = sensor.test_mode
            model.test_mode_expires_at = sensor.test_mode_expires_at
            model.correction_factor = sensor.correction_factor
            model.last_reading_at = sensor.last_reading_at
            model.updated_at = sensor.updated_at
            
            await self.session.flush()
            await self.session.refresh(model)
            return self._to_entity(model)
        
        return sensor

    async def delete(self, sensor_id: UUID) -> bool:
        result = await self.session.execute(
            select(SensorModel).where(SensorModel.id == sensor_id)
        )
        model = result.scalar_one_or_none()
        
        if model:
            await self.session.delete(model)
            await self.session.flush()
            return True
        
        return False

    async def get_valve_by_sensor_id(self, sensor_id: UUID) -> Valve | None:
        result = await self.session.execute(
            select(ValveModel).where(ValveModel.sensor_id == sensor_id)
        )
        model = result.scalar_one_or_none()
        return self._valve_to_entity(model) if model else None

    async def save_valve(self, valve: Valve) -> Valve:
        model = self._valve_to_model(valve)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._valve_to_entity(model)

    async def update_valve(self, valve: Valve) -> Valve:
        result = await self.session.execute(
            select(ValveModel).where(ValveModel.id == valve.id)
        )
        model = result.scalar_one_or_none()
        
        if model:
            model.state = valve.state.value
            model.last_state_change = valve.last_state_change
            model.mechanical_status = valve.mechanical_status.value
            model.last_command_source = valve.last_command_source.value if valve.last_command_source else None
            model.updated_at = valve.updated_at
            
            await self.session.flush()
            await self.session.refresh(model)
            return self._valve_to_entity(model)
        
        return valve

    async def get_dissipator_by_sensor_id(self, sensor_id: UUID) -> Dissipator | None:
        result = await self.session.execute(
            select(DissipatorModel).where(DissipatorModel.sensor_id == sensor_id)
        )
        model = result.scalar_one_or_none()
        return self._dissipator_to_entity(model) if model else None

    async def save_dissipator(self, dissipator: Dissipator) -> Dissipator:
        model = self._dissipator_to_model(dissipator)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._dissipator_to_entity(model)

    async def update_dissipator(self, dissipator: Dissipator) -> Dissipator:
        result = await self.session.execute(
            select(DissipatorModel).where(DissipatorModel.id == dissipator.id)
        )
        model = result.scalar_one_or_none()
        
        if model:
            model.state = dissipator.state.value
            model.activation_mode = dissipator.activation_mode.value
            model.last_state_change = dissipator.last_state_change
            model.mechanical_status = dissipator.mechanical_status.value
            model.locked_by_alert = dissipator.locked_by_alert
            model.updated_at = dissipator.updated_at
            
            await self.session.flush()
            await self.session.refresh(model)
            return self._dissipator_to_entity(model)
        
        return dissipator

    def _to_entity(self, model: SensorModel) -> Sensor:
        return Sensor(
            id=model.id,
            device_id=model.device_id,
            location=Location(model.location),
            status=SensorStatus(model.status),
            wifi_signal=model.wifi_signal,
            mqtt_connected=model.mqtt_connected,
            uptime_seconds=model.uptime_seconds,
            test_mode=model.test_mode,
            test_mode_expires_at=model.test_mode_expires_at,
            correction_factor=model.correction_factor,
            last_reading_at=model.last_reading_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: Sensor) -> SensorModel:
        return SensorModel(
            id=entity.id,
            device_id=entity.device_id,
            location=entity.location.description,
            status=entity.status.value,
            wifi_signal=entity.wifi_signal,
            mqtt_connected=entity.mqtt_connected,
            uptime_seconds=entity.uptime_seconds,
            test_mode=entity.test_mode,
            test_mode_expires_at=entity.test_mode_expires_at,
            correction_factor=entity.correction_factor,
            last_reading_at=entity.last_reading_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def _valve_to_entity(self, model: ValveModel) -> Valve:
        return Valve(
            id=model.id,
            sensor_id=model.sensor_id,
            state=ValveState(model.state),
            last_state_change=model.last_state_change,
            mechanical_status=MechanicalStatus(model.mechanical_status),
            last_command_source=CommandSource(model.last_command_source) if model.last_command_source else None,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _valve_to_model(self, entity: Valve) -> ValveModel:
        return ValveModel(
            id=entity.id,
            sensor_id=entity.sensor_id,
            state=entity.state.value,
            last_state_change=entity.last_state_change,
            mechanical_status=entity.mechanical_status.value,
            last_command_source=entity.last_command_source.value if entity.last_command_source else None,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def _dissipator_to_entity(self, model: DissipatorModel) -> Dissipator:
        return Dissipator(
            id=model.id,
            sensor_id=model.sensor_id,
            state=DissipatorState(model.state),
            activation_mode=ActivationMode(model.activation_mode),
            last_state_change=model.last_state_change,
            mechanical_status=MechanicalStatus(model.mechanical_status),
            locked_by_alert=model.locked_by_alert,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _dissipator_to_model(self, entity: Dissipator) -> DissipatorModel:
        return DissipatorModel(
            id=entity.id,
            sensor_id=entity.sensor_id,
            state=entity.state.value,
            activation_mode=entity.activation_mode.value,
            last_state_change=entity.last_state_change,
            mechanical_status=entity.mechanical_status.value,
            locked_by_alert=entity.locked_by_alert,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
