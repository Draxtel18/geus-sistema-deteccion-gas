"""Conexion PostgreSQL simple para workers usando asyncpg."""

import asyncpg
import structlog
from pydantic_settings import BaseSettings

logger = structlog.get_logger()


class DatabaseSettings(BaseSettings):
    class Config:
        env_file = ".env"
        env_prefix = "POSTGRES_"

    host: str = "localhost"
    port: int = 5432
    db: str = "geus_gas_detection"
    user: str = "geus_user"
    password: str = "geus_password"

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


settings = DatabaseSettings()


class WorkerDatabase:
    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        logger.info("connecting_to_postgres", host=settings.host, db=settings.db)
        self.pool = await asyncpg.create_pool(
            dsn=settings.dsn,
            min_size=1,
            max_size=5,
        )
        logger.info("postgres_connected")

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            logger.info("postgres_disconnected")

    async def fetchrow(self, query: str, *args) -> asyncpg.Record | None:
        if not self.pool:
            raise RuntimeError("Database not connected")
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetch(self, query: str, *args) -> list[asyncpg.Record]:
        if not self.pool:
            raise RuntimeError("Database not connected")
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def execute(self, query: str, *args) -> str:
        if not self.pool:
            raise RuntimeError("Database not connected")
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)


worker_db = WorkerDatabase()
