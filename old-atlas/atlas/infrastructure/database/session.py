from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from atlas.config import Settings


class Database:
    def __init__(self, settings: Settings, *, echo: bool = False) -> None:
        self.engine: AsyncEngine = create_async_engine(
            settings.database_url,
            echo=echo,
            pool_pre_ping=True,
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    def session(self) -> AsyncSession:
        return self.sessions()

    async def dispose(self) -> None:
        await self.engine.dispose()
