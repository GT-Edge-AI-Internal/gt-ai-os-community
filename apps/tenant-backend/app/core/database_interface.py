"""
GT 2.0 Database Interface - DuckDB Implementation

Provides a unified interface for DuckDB database operations
following GT 2.0 principles of Zero Downtime, Perfect Tenant Isolation, and Elegant Simplicity.
Post-migration: SQLite has been completely replaced with DuckDB for enhanced MVCC performance.
"""

import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, AsyncGenerator, Union
from contextlib import asynccontextmanager
from dataclasses import dataclass


class DatabaseEngine(Enum):
    """Supported database engines - DEPRECATED: Use PostgreSQL directly"""
    POSTGRESQL = "postgresql"


@dataclass
class DatabaseConfig:
    """Database configuration"""
    engine: DatabaseEngine
    database_path: str
    tenant_id: str
    shard_id: Optional[str] = None
    encryption_key: Optional[str] = None
    connection_params: Optional[Dict[str, Any]] = None


@dataclass
class QueryResult:
    """Standardized query result"""
    rows: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    execution_time_ms: float


class DatabaseInterface(ABC):
    """
    Abstract database interface for GT 2.0 tenant isolation.
    
    DuckDB implementation with MVCC concurrency for true zero-downtime operations,
    perfect tenant isolation, and 10x analytical performance improvements.
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.tenant_id = config.tenant_id
        self.database_path = config.database_path
        self.engine = config.engine
    
    # Connection Management
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize database connection and create tables"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close database connections"""
        pass
    
    @abstractmethod
    async def is_initialized(self) -> bool:
        """Check if database is properly initialized"""
        pass
    
    @abstractmethod
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[Any, None]:
        """Get database session context manager"""
        pass
    
    # Schema Management
    @abstractmethod
    async def create_tables(self) -> None:
        """Create all required tables"""
        pass
    
    @abstractmethod
    async def get_schema_version(self) -> Optional[str]:
        """Get current database schema version"""
        pass
    
    @abstractmethod
    async def migrate_schema(self, target_version: str) -> bool:
        """Migrate database schema to target version"""
        pass
    
    # Query Operations
    @abstractmethod
    async def execute_query(
        self, 
        query: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """Execute SELECT query and return results"""
        pass
    
    @abstractmethod
    async def execute_command(
        self, 
        command: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> int:
        """Execute INSERT/UPDATE/DELETE command and return affected rows"""
        pass
    
    @abstractmethod
    async def execute_batch(
        self, 
        commands: List[str], 
        params: Optional[List[Dict[str, Any]]] = None
    ) -> List[int]:
        """Execute batch commands in transaction"""
        pass
    
    # Transaction Management
    @abstractmethod
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Any, None]:
        """Transaction context manager"""
        pass
    
    @abstractmethod
    async def begin_transaction(self) -> Any:
        """Begin transaction and return transaction handle"""
        pass
    
    @abstractmethod
    async def commit_transaction(self, tx: Any) -> None:
        """Commit transaction"""
        pass
    
    @abstractmethod
    async def rollback_transaction(self, tx: Any) -> None:
        """Rollback transaction"""
        pass
    
    # Health and Monitoring
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check database health and return status"""
        pass
    
    @abstractmethod
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        pass
    
    @abstractmethod
    async def optimize(self) -> bool:
        """Optimize database performance"""
        pass
    
    # Backup and Recovery
    @abstractmethod
    async def backup(self, backup_path: str) -> bool:
        """Create database backup"""
        pass
    
    @abstractmethod
    async def restore(self, backup_path: str) -> bool:
        """Restore from database backup"""
        pass
    
    # Sharding Support (DuckDB specific)
    @abstractmethod
    async def create_shard(self, shard_id: str) -> bool:
        """Create new database shard"""
        pass
    
    @abstractmethod
    async def get_shard_info(self) -> Dict[str, Any]:
        """Get information about current shard"""
        pass
    
    @abstractmethod
    async def migrate_to_shard(self, source_db: 'DatabaseInterface') -> bool:
        """Migrate data from another database instance"""
        pass
    
    # Vector Operations (ChromaDB integration)
    @abstractmethod
    async def store_embeddings(
        self,
        collection: str,
        embeddings: List[List[float]],
        documents: List[str],
        metadata: List[Dict[str, Any]]
    ) -> bool:
        """Store embeddings with documents and metadata"""
        pass
    
    @abstractmethod
    async def query_embeddings(
        self,
        collection: str,
        query_embedding: List[float],
        limit: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query embeddings by similarity"""
        pass
    
    # Data Import/Export
    @abstractmethod
    async def export_data(
        self, 
        format: str = "json",
        tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Export database data"""
        pass
    
    @abstractmethod
    async def import_data(
        self, 
        data: Dict[str, Any],
        format: str = "json",
        merge_strategy: str = "replace"
    ) -> bool:
        """Import database data"""
        pass
    
    # Security and Encryption
    @abstractmethod
    async def encrypt_database(self, encryption_key: str) -> bool:
        """Enable database encryption"""
        pass
    
    @abstractmethod
    async def verify_encryption(self) -> bool:
        """Verify database encryption status"""
        pass
    
    # Performance and Indexing
    @abstractmethod
    async def create_index(
        self, 
        table: str, 
        columns: List[str], 
        index_name: Optional[str] = None,
        unique: bool = False
    ) -> bool:
        """Create database index"""
        pass
    
    @abstractmethod
    async def drop_index(self, index_name: str) -> bool:
        """Drop database index"""
        pass
    
    @abstractmethod
    async def analyze_queries(self) -> Dict[str, Any]:
        """Analyze query performance"""
        pass
    
    # Utility Methods
    async def get_engine_info(self) -> Dict[str, Any]:
        """Get database engine information"""
        return {
            "engine": self.engine.value,
            "tenant_id": self.tenant_id,
            "database_path": self.database_path,
            "shard_id": self.config.shard_id,
            "supports_mvcc": self.engine == DatabaseEngine.POSTGRESQL,
            "supports_sharding": self.engine == DatabaseEngine.POSTGRESQL,
            "file_based": True
        }
    
    async def validate_tenant_isolation(self) -> bool:
        """Validate that tenant isolation is maintained"""
        try:
            stats = await self.get_statistics()
            return (
                self.tenant_id in self.database_path and
                stats.get("isolated", False)
            )
        except Exception:
            return False


class DatabaseFactory:
    """Factory for creating database instances"""
    
    @staticmethod
    async def create_database(config: DatabaseConfig) -> DatabaseInterface:
        """Create database instance - PostgreSQL only"""
        raise NotImplementedError("Database interface deprecated. Use PostgreSQL directly via postgresql_client.py")
    
    @staticmethod
    async def migrate_database(
        source_config: DatabaseConfig,
        target_config: DatabaseConfig,
        migration_options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Migrate data from source to target database"""
        source_db = await DatabaseFactory.create_database(source_config)
        target_db = await DatabaseFactory.create_database(target_config)
        
        try:
            await source_db.initialize()
            await target_db.initialize()
            
            # Export data from source
            data = await source_db.export_data()
            
            # Import data to target
            success = await target_db.import_data(data)
            
            if success and migration_options and migration_options.get("verify", True):
                # Verify migration
                source_stats = await source_db.get_statistics()
                target_stats = await target_db.get_statistics()
                
                return source_stats.get("row_count", 0) == target_stats.get("row_count", 0)
            
            return success
            
        finally:
            await source_db.close()
            await target_db.close()


# Error Classes
class DatabaseError(Exception):
    """Base database error"""
    pass


class DatabaseConnectionError(DatabaseError):
    """Database connection error"""
    pass


class DatabaseMigrationError(DatabaseError):
    """Database migration error"""
    pass


class DatabaseShardingError(DatabaseError):
    """Database sharding error"""
    pass