from datetime import datetime
from uuid import UUID, uuid4

import structlog

from worker.shared.database import worker_db

logger = structlog.get_logger()


class AlertStore:

    async def _find_active_alert(self, sensor_id: UUID) -> dict | None:
        row = await worker_db.fetchrow(
            "SELECT id, severity, gas_level_ppm, triggered_at FROM alerts WHERE sensor_id = $1 AND status IN ('active', 'acknowledged') ORDER BY triggered_at DESC LIMIT 1",
            sensor_id,
        )
        return dict(row) if row else None

    async def _resolve_alert(self, alert_id: UUID) -> bool:
        try:
            now = datetime.utcnow()
            if now.tzinfo is not None:
                now = now.replace(tzinfo=None)
            await worker_db.execute(
                """
                UPDATE alerts
                SET status = 'resolved', resolved_at = $1, resolved_by = NULL, auto_resolved = true
                WHERE id = $2
                """,
                now,
                alert_id,
            )
            return True
        except Exception:
            return False

    async def resolve_active_alerts(self, device_id: str) -> bool:
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
                SET status = 'resolved', resolved_at = $1, resolved_by = NULL, auto_resolved = true
                WHERE sensor_id = $2 AND status IN ('active', 'acknowledged')
                """,
                now,
                sensor_id,
            )

            await worker_db.execute(
                """
                UPDATE dissipators
                SET locked_by_alert = false,
                    updated_at = $1
                WHERE sensor_id = $2 AND locked_by_alert = true
                """,
                now,
                sensor_id,
            )

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

            existing = await self._find_active_alert(sensor_id)
            if existing:
                if severity == "critical" and existing["severity"] == "warning":
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
                [],
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

    async def get_notification_targets(self, device_id: str) -> tuple[list[str], list[str]]:
        emails: list[str] = []
        tokens: list[str] = []

        rows = await worker_db.fetch(
            """
            SELECT u.email, pt.token
            FROM users u
            LEFT JOIN push_tokens pt ON pt.user_id = u.id AND pt.is_active = true
            INNER JOIN user_sensor_assignments usa ON usa.user_id = u.id
            INNER JOIN sensors s ON s.id = usa.sensor_id
            WHERE s.device_id = $1
              AND u.notifications_enabled = true
            """,
            device_id,
        )

        for row in rows:
            if row["email"]:
                emails.append(row["email"])
            if row["token"]:
                tokens.append(row["token"])

        return list(set(emails)), list(set(tokens))

    async def get_sensor_snapshot(self, device_id: str) -> dict | None:
        row = await worker_db.fetchrow(
            """
            SELECT s.id AS sensor_id,
                   s.device_id,
                   s.location,
                   s.status AS sensor_status,
                   s.mqtt_connected,
                   v.state AS valve_state,
                   d.state AS dissipator_state,
                   d.locked_by_alert
            FROM sensors s
            LEFT JOIN valves v ON v.sensor_id = s.id
            LEFT JOIN dissipators d ON d.sensor_id = s.id
            WHERE s.device_id = $1
            """,
            device_id,
        )
        return dict(row) if row else None

    async def update_valve_snapshot(self, device_id: str, state: str, source: str) -> bool:
        try:
            sensor = await self._find_sensor_by_device_id(device_id)
            if not sensor:
                return False

            now = datetime.utcnow()
            if now.tzinfo is not None:
                now = now.replace(tzinfo=None)

            await worker_db.execute(
                """
                UPDATE valves
                SET state = $1,
                    last_command_source = $2,
                    last_state_change = $3,
                    updated_at = $3
                WHERE sensor_id = $4
                """,
                state,
                source,
                now,
                sensor["id"],
            )
            return True
        except Exception as e:
            logger.error(
                "failed_to_update_valve_snapshot",
                device_id=device_id,
                state=state,
                error=str(e),
            )
            return False

    async def update_dissipator_snapshot(
        self,
        device_id: str,
        state: str,
        activation_mode: str,
        locked_by_alert: bool,
    ) -> bool:
        try:
            sensor = await self._find_sensor_by_device_id(device_id)
            if not sensor:
                return False

            now = datetime.utcnow()
            if now.tzinfo is not None:
                now = now.replace(tzinfo=None)

            await worker_db.execute(
                """
                UPDATE dissipators
                SET state = $1,
                    activation_mode = $2,
                    locked_by_alert = $3,
                    last_state_change = $4,
                    updated_at = $4
                WHERE sensor_id = $5
                """,
                state,
                activation_mode,
                locked_by_alert,
                now,
                sensor["id"],
            )
            return True
        except Exception as e:
            logger.error(
                "failed_to_update_dissipator_snapshot",
                device_id=device_id,
                state=state,
                activation_mode=activation_mode,
                error=str(e),
            )
            return False

    async def ensure_sensor_exists(
        self,
        device_id: str,
        location: str = "Unknown",
        sensor_type: str = "MQ2",
    ) -> UUID | None:
        sensor = await self._find_sensor_by_device_id(device_id)
        if sensor:
            return sensor["id"]

        sensor_id = uuid4()
        now = datetime.utcnow()
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
            "online",
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
