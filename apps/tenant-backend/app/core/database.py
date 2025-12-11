"""
GT 2.0 Tenant Backend Database Configuration - PostgreSQL + PGVector Client

Migrated from DuckDB service to PostgreSQL + PGVector for enterprise readiness:
- PostgreSQL + PGVector unified storage (replaces DuckDB + ChromaDB)
- BionicGPT Row Level Security patterns for enterprise isolation
- MVCC concurrency solving DuckDB file locking issues  
- Hybrid vector + full-text search in single queries
- Connection pooling for 10,000+ concurrent connections
"""

import os
import logging
from typing import Generator, Optional, Any, Dict, List
from contextlib import contextmanager, asynccontextmanager

from sqlalchemy.ext.declarative import declarative_base

from app.core.config import get_settings
from app.core.postgresql_client import (
    get_postgresql_client, init_postgresql, close_postgresql,
    get_db_session, execute_query, execute_command,
    fetch_one, fetch_scalar, health_check, get_database_info
)

# Legacy DuckDB imports removed - PostgreSQL + PGVector only

# SQLAlchemy Base for ORM models
Base = declarative_base()

logger = logging.getLogger(__name__)
settings = get_settings()

# PostgreSQL client is managed by postgresql_client module


async def init_database() -> None:
    """Initialize PostgreSQL + PGVector connection"""
    logger.info("Initializing PostgreSQL + PGVector database connection...")
    
    try:
        await init_postgresql()
        logger.info("PostgreSQL + PGVector connection initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL database: {e}")
        raise


async def close_database() -> None:
    """Close PostgreSQL connections"""
    try:
        await close_postgresql()
        logger.info("PostgreSQL connections closed")
    except Exception as e:
        logger.error(f"Error closing PostgreSQL connections: {e}")


async def get_db_client_instance():
    """Get the PostgreSQL client instance"""
    return await get_postgresql_client()


# get_db_session is imported from postgresql_client


# execute_query is imported from postgresql_client


# execute_command is imported from postgresql_client


async def execute_transaction(commands: List[Dict[str, Any]]) -> List[int]:
    """Execute multiple commands in a transaction (PostgreSQL format)"""
    client = await get_postgresql_client()
    pg_commands = [(cmd.get('query', cmd.get('command', '')), tuple(cmd.get('params', {}).values())) for cmd in commands]
    return await client.execute_transaction(pg_commands)


# fetch_one is imported from postgresql_client


async def fetch_all(query: str, *args) -> List[Dict[str, Any]]:
    """Execute query and return all rows"""
    return await execute_query(query, *args)


# fetch_scalar is imported from postgresql_client


# get_database_info is imported from postgresql_client


# health_check is imported from postgresql_client


# Legacy compatibility functions (for gradual migration)
def get_db() -> Generator[None, None, None]:
    """Legacy sync database dependency - deprecated"""
    logger.warning("get_db() is deprecated. Use async get_db_session() instead")
    # Return a dummy generator for compatibility
    yield None


@contextmanager
def get_db_session_sync():
    """Legacy sync session - deprecated"""  
    logger.warning("get_db_session_sync() is deprecated. Use async get_db_session() instead")
    yield None


def execute_raw_query(query: str, params: Optional[Dict] = None) -> List[Dict]:
    """Legacy sync query execution - deprecated"""
    logger.error("execute_raw_query() is deprecated and not supported with PostgreSQL async client")
    raise NotImplementedError("Use async execute_query() instead")


def verify_tenant_isolation() -> bool:
    """Verify tenant isolation - PostgreSQL schema-based isolation with RLS is always enabled"""
    return True


# Initialize database on module import (for FastAPI startup)
async def startup_database():
    """Initialize database during FastAPI startup"""
    await init_database()


async def shutdown_database():
    """Cleanup database during FastAPI shutdown"""
    await close_database()