from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.connection import get_db


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


def get_current_session(
    session: AsyncSession = Depends(get_database_session),
) -> AsyncSession:
    return session
