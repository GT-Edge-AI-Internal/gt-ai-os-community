"""
Database configuration and utilities for GT 2.0 Control Panel
"""
import asyncio
from contextlib import asynccontextmanager, contextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from sqlalchemy.pool import StaticPool
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Create sync engine for session management (Issue #264)
# Uses psycopg2 instead of asyncpg for sync operations
sync_database_url = settings.DATABASE_URL.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")
if "+psycopg2" not in sync_database_url:
    sync_database_url = sync_database_url.replace("postgresql://", "postgresql+psycopg2://")

sync_engine = create_engine(
    sync_database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

# Create session makers
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

sync_session_maker = sessionmaker(
    sync_engine,
    class_=Session,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


@asynccontextmanager
async def get_db_session():
    """Get database session context manager"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db():
    """Dependency for getting async database session"""
    async with get_db_session() as session:
        yield session


@contextmanager
def get_sync_db_session():
    """Get synchronous database session context manager (for session management)"""
    session = sync_session_maker()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_sync_db():
    """Dependency for getting synchronous database session (for session management)"""
    with get_sync_db_session() as session:
        yield session


async def init_db():
    """Initialize database tables"""
    try:
        # Import all models to ensure they're registered
        from app.models import tenant, user, ai_resource, usage, audit, model_config, tenant_model_config

        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database tables created successfully")

    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise


async def check_db_connection():
    """Check database connection health"""
    try:
        async with get_db_session() as session:
            await session.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error("Database connection check failed", error=str(e))
        return False


def create_database_url(
    username: str,
    password: str,
    host: str,
    port: int,
    database: str,
    driver: str = "postgresql+asyncpg"
) -> str:
    """Create database URL from components"""
    return f"{driver}://{username}:{password}@{host}:{port}/{database}"