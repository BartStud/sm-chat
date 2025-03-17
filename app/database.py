import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://user:password@postgres/sm_chat_db"
)

engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore


async def get_db():
    """Dependency do pobierania sesji bazy danych"""
    async with SessionLocal() as session:  # type: ignore
        yield session
