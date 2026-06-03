"""Database session management with async support."""
import logging
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings

logger = logging.getLogger(__name__)

LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "postgres", "db"}


def _build_connect_args(database_url: str) -> dict:
    """
    Choose asyncpg SSL behavior based on the target database host.

    Local Docker and localhost Postgres instances do not support SSL by
    default, while hosted providers such as Neon typically require it.
    """
    url = make_url(database_url)
    host = (url.host or "").lower()
    sslmode = str(url.query.get("sslmode", "")).lower()

    if sslmode in {"disable", "allow", "prefer"}:
        return {"ssl": False}
    if sslmode in {"require", "verify-ca", "verify-full"}:
        return {"ssl": "require"}
    if host in LOCAL_DB_HOSTS:
        return {"ssl": False}
    return {"ssl": "require"}


# Create async engine with connection pooling optimizations
engine = create_async_engine(
    settings.database_url,
    echo=False,  # Set to True for SQL debugging
    pool_size=5,  # Neon free tier has limited connections
    max_overflow=2,
    pool_pre_ping=True,  # Test connections before using from pool
    pool_recycle=300,  # Neon suspends idle connections after ~5 min
    connect_args=_build_connect_args(settings.database_url),
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """Dependency injection for database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()
