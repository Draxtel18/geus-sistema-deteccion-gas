"""Persistencia de alertas en PostgreSQL desde el worker."""

from datetime import datetime
from uuid import UUID, uuid4

import structlog

from worker.shared.database import worker_db

logger = structlog.get_logger()


class AlertStore:
    """Guarda alertas en PostgreSQL buscando primero el sensor por device_id."""

    async def _find_active_alert(self, sensor_id: UUID) -> dict | None:
        """Devuelve la alerta activa del sensor, o None si no hay."""
        row = await worker_db.fetchrow(
            "SELECT id, severity, gas_level_ppm, triggered_at FROM alerts WHERE sensor_id = $1 AND status = 'active' LIMIT 1",
            sensor_id,
        )
        return dict(row) if row else None

    async def _resolve_alert(self, alert_id: UUID) -> bool:
        """Marca una alerta específica como resuelta."""
        try:
            now = datetime.utcnow()
            if now.tzinfo is not None:
                now = now.replace(tzinfo=None)
            await worker_db.execute(
                """
                UPDATE alerts
                SET status = 'resolved', resolved_at = $1, auto_resolved = true
                WHERE id = $2
                """,
                now,
                alert_id,
            )
            return True
        except Exception:
            return False

    async def resolve_active_alerts(self, device_id: str) -> bool:
        """Resuelve todas las alertas activas del sensor cuando el gas vuelve a niveles seguros."""
        try:
            sensor = await self._find_sensor_by_device_id(device_id)
            if not sensor:
                return False

            sensor_id = sensor["id"]
            now = datetime.utcnow()
            if now.tzinfo is not None:
                now = now.replace(tzinfo=None)

            result = await worker_db.execute(
                """
                UPDATE alerts
                SET status = 'resolved', resolved_at = $1, auto_resolved = true
                WHERE sensor_id = $2 AND status = 'active'
                """,
                now,
                sensor_id,
            )

            # asyncpg devuelve una string como 'UPDATE 1' en result
            affected = int(result.split()[-1]) if isinstance(result, str) and result.startswith("UPDATE") else 0
            if affected > 0:
                logger.info(
                    "alerts_auto_resolved",
                    device_id=device_id,
                    sensor_id=str(sensor_id),
                    count=affected,
                )
                return True
            return False

        except Exception as e:
            logger.error(
                "failed_to_resolve_alerts",
                device_id=device_id,
                error=str(e),
            )
            return False

    async def save_alert(
        self,
        device_id: str,
        severity: str,
        gas_level_ppm: float,
        triggered_at: datetime | None = None,
    ) -> bool:
        """Busca el sensor por device_id y crea la alerta si no hay una activa."""
        try:
            sensor = await self._find_sensor_by_device_id(device_id)
            if not sensor:
                logger.warning(
                    "sensor_not_found_for_alert",
                    device_id=device_id,
                    severity=severity,
                    gas_level_ppm=gas_level_ppm,
                )
                return False

            sensor_id = sensor["id"]

            # Evitar alertas duplicadas y permitir upgrade de severidad
            existing = await self._find_active_alert(sensor_id)
            if existing:
                if severity == "critical" and existing["severity"] == "warning":
                    # Upgrade: resolver warning, crear critical
                    await self._resolve_alert(existing["id"])
                    logger.info(
                        "alert_severity_upgraded",
                        device_id=device_id,
                        sensor_id=str(sensor_id),
                        from_severity="warning",
                        to_severity="critical",
                        gas_level_ppm=gas_level_ppm,
                    )
                else:
                    logger.info(
                        "alert_already_active_skipped",
                        device_id=device_id,
                        sensor_id=str(sensor_id),
                        severity=severity,
                        gas_level_ppm=gas_level_ppm,
                    )
                    return True

            alert_id = uuid4()
            now = triggered_at or datetime.utcnow()
            # asyncpg requiere datetime offset-naive para columnas DateTime
            if now.tzinfo is not None:
                now = now.replace(tzinfo=None)

            await worker_db.execute(
                """
                INSERT INTO alerts (
                    id, sensor_id, gas_level_ppm, severity, status,
                    triggered_at, auto_resolved, notifications_sent, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                alert_id,
                sensor_id,
                gas_level_ppm,
                severity,
                "active",
                now,
                False,
                "[]",
                now,
            )

            logger.info(
                "alert_saved_to_postgres",
                alert_id=str(alert_id),
                sensor_id=str(sensor_id),
                device_id=device_id,
                severity=severity,
                gas_level_ppm=gas_level_ppm,
            )
            return True

        except Exception as e:
            logger.error(
                "failed_to_save_alert",
                device_id=device_id,
                severity=severity,
                error=str(e),
            )
            return False

    async def _find_sensor_by_device_id(self, device_id: str) -> dict | None:
        row = await worker_db.fetchrow(
            "SELECT id, device_id, location, status FROM sensors WHERE device_id = $1",
            device_id,
        )
        if row:
            return dict(row)
        return None

    async def ensure_sensor_exists(
        self,
        device_id: str,
        location: str = "Unknown",
        sensor_type: str = "MQ2",
    ) -> UUID | None:
        """Crea el sensor si no existe."""
        sensor = await self._find_sensor_by_device_id(device_id)
        if sensor:
            return sensor["id"]

        sensor_id = uuid4()
        now = datetime.utcnow()
        # asyncpg requiere datetime offset-naive para columnas DateTime
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        await worker_db.execute(
            """
            INSERT INTO sensors (
                id, device_id, location, status,
                wifi_signal, mqtt_connected, uptime_seconds,
                test_mode, correction_factor, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            sensor_id,
            device_id,
            location,
            "active",
            None,
            True,
            0,
            False,
            1.0,
            now,
            now,
        )

        logger.info(
            "auto_registered_sensor",
            sensor_id=str(sensor_id),
            device_id=device_id,
        )
        return sensor_id
