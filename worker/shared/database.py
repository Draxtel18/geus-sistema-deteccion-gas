"""Conexion PostgreSQL simple para workers usando asyncpg."""

import json
from collections.abc import AsyncGenerator

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
        self._tx_conn: asyncpg.Connection | None = None

    async def connect(self) -> None:
        if self.pool:
            logger.info("postgres_already_connected")
            return
        logger.info("connecting_to_postgres", host=settings.host, db=settings.db)

        async def _init_connection(conn: asyncpg.Connection) -> None:
            await conn.set_type_codec(
                "jsonb",
                encoder=json.dumps,
                decoder=json.loads,
                schema="pg_catalog",
            )

        self.pool = await asyncpg.create_pool(
            dsn=settings.dsn,
            min_size=1,
            max_size=5,
            init=_init_connection,
        )
        logger.info("postgres_connected")

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("postgres_disconnected")

    async def fetchrow(self, query: str, *args) -> asyncpg.Record | None:
        if not self.pool:
            raise RuntimeError("Database not connected")
        if self._tx_conn:
            return await self._tx_conn.fetchrow(query, *args)
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetch(self, query: str, *args) -> list[asyncpg.Record]:
        if not self.pool:
            raise RuntimeError("Database not connected")
        if self._tx_conn:
            return await self._tx_conn.fetch(query, *args)
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def execute(self, query: str, *args) -> str:
        if not self.pool:
            raise RuntimeError("Database not connected")
        if self._tx_conn:
            return await self._tx_conn.execute(query, *args)
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def transaction(self) -> AsyncGenerator[None]:
        if not self.pool:
            raise RuntimeError("Database not connected")
        conn = await self.pool.acquire()
        self._tx_conn = conn
        try:
            async with conn.transaction():
                yield
        finally:
            self._tx_conn = None
            await self.pool.release(conn)


worker_db = WorkerDatabase()
