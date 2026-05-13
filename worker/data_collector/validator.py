import structlog
from pydantic import ValidationError

from worker.shared.schemas import SensorReadingSchema

logger = structlog.get_logger()


class ReadingValidator:
    def validate(self, data: dict) -> tuple[bool, SensorReadingSchema | None, str | None]:
        try:
            reading = SensorReadingSchema(**data)
            return True, reading, None
        except ValidationError as e:
            error_msg = str(e)
            logger.warning(
                "invalid_sensor_reading",
                errors=e.errors(),
                data=data,
            )
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Unexpected validation error: {str(e)}"
            logger.error(
                "validation_exception",
                error=str(e),
                data=data,
            )
            return False, None, error_msg

    def validate_device_id(self, device_id: str) -> bool:
        return bool(device_id and len(device_id.strip()) > 0 and len(device_id) <= 64)

    def validate_gas_level(self, gas_ppm: float) -> bool:
        return 0 <= gas_ppm <= 10000

    def validate_temperature(self, temperature_c: float) -> bool:
        return -40 <= temperature_c <= 85

    def validate_humidity(self, humidity_percent: float) -> bool:
        return 0 <= humidity_percent <= 100
