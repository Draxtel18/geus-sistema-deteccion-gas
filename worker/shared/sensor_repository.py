"""Repositorio para consultar sensores registrados en PostgreSQL desde workers."""

import structlog

from worker.shared.database import worker_db

logger = structlog.get_logger()


class WorkerSensorRepository:
    """Consulta sensores en PostgreSQL para validar/mapear device_ids."""

    async def find_by_device_id(self, device_id: str) -> dict | None:
        """Busca sensor exacto por device_id."""
        row = await worker_db.fetchrow(
            "SELECT id, device_id, location, status FROM sensors WHERE device_id = $1",
            device_id,
        )
        return dict(row) if row else None

    async def find_by_suffix(self, suffix: str) -> list[dict]:
        """Busca sensores cuyo device_id termine con el sufijo dado."""
        rows = await worker_db.fetch(
            "SELECT id, device_id, location, status FROM sensors WHERE device_id LIKE $1",
            f"%{suffix}",
        )
        return [dict(r) for r in rows]
