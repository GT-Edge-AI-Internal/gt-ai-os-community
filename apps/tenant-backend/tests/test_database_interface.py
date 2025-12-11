"""
Unit Tests for GT 2.0 Database Interface

Tests the abstract interface contract and ensures all implementations
comply with GT 2.0 principles of Perfect Tenant Isolation and Zero Downtime.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any, List
from contextlib import asynccontextmanager

from app.core.database_interface import (
    DatabaseInterface,
    DatabaseEngine, 
    DatabaseConfig,
    DatabaseFactory,
    QueryResult,
    DatabaseError,
    DatabaseConnectionError,
    DatabaseMigrationError,
    DatabaseShardingError
)


class MockDatabase(DatabaseInterface):
    """Mock database implementation for testing interface contract"""
    
    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self.initialized = False
        self.closed = False
        self.tables_created = False
        self.schema_version = "1.0.0"
        
    async def initialize(self) -> None:
        self.initialized = True
        
    async def close(self) -> None:
        self.closed = True
        
    async def is_initialized(self) -> bool:
        return self.initialized
        
    async def get_session(self):
        yield Mock()
        
    async def create_tables(self) -> None:
        self.tables_created = True
        
    async def get_schema_version(self) -> str:
        return self.schema_version
        
    async def migrate_schema(self, target_version: str) -> bool:
        self.schema_version = target_version
        return True
        
    async def execute_query(self, query: str, params=None) -> QueryResult:
        return QueryResult(
            rows=[{"id": 1, "name": "test"}],
            row_count=1,
            columns=["id", "name"],
            execution_time_ms=10.0
        )
        
    async def execute_command(self, command: str, params=None) -> int:
        return 1
        
    async def execute_batch(self, commands: List[str], params=None) -> List[int]:
        return [1] * len(commands)
        
    @asynccontextmanager
    async def transaction(self):
        yield Mock()
        
    async def begin_transaction(self):
        return Mock()
        
    async def commit_transaction(self, tx):
        pass
        
    async def rollback_transaction(self, tx):
        pass
        
    async def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "engine": self.engine.value}
        
    async def get_statistics(self) -> Dict[str, Any]:
        return {
            "row_count": 100,
            "table_count": 5,
            "isolated": True,
            "file_size_bytes": 1024000
        }
        
    async def optimize(self) -> bool:
        return True
        
    async def backup(self, backup_path: str) -> bool:
        return True
        
    async def restore(self, backup_path: str) -> bool:
        return True
        
    async def create_shard(self, shard_id: str) -> bool:
        return True
        
    async def get_shard_info(self) -> Dict[str, Any]:
        return {"shard_id": "shard_1", "status": "active"}
        
    async def migrate_to_shard(self, source_db: DatabaseInterface) -> bool:
        return True
        
    async def store_embeddings(self, collection: str, embeddings: List[List[float]], 
                             documents: List[str], metadata: List[Dict[str, Any]]) -> bool:
        return True
        
    async def query_embeddings(self, collection: str, query_embedding: List[float],
                             limit: int = 10, filter_metadata=None) -> List[Dict[str, Any]]:
        return [{"id": "doc1", "score": 0.95, "document": "test document"}]
        
    async def export_data(self, format: str = "json", tables=None) -> Dict[str, Any]:
        return {"tables": {"users": [{"id": 1, "name": "test"}]}}
        
    async def import_data(self, data: Dict[str, Any], format: str = "json", 
                         merge_strategy: str = "replace") -> bool:
        return True
        
    async def encrypt_database(self, encryption_key: str) -> bool:
        return True
        
    async def verify_encryption(self) -> bool:
        return True
        
    async def create_index(self, table: str, columns: List[str], 
                          index_name=None, unique: bool = False) -> bool:
        return True
        
    async def drop_index(self, index_name: str) -> bool:
        return True
        
    async def analyze_queries(self) -> Dict[str, Any]:
        return {"total_queries": 100, "avg_execution_time_ms": 50.0}


@pytest.fixture
def sqlite_config():
    """SQLite database configuration for testing (legacy support)"""
    return DatabaseConfig(
        engine=DatabaseEngine.SQLITE,
        database_path="/tmp/test_tenant.db",
        tenant_id="test_tenant",
        encryption_key="test_key"
    )


@pytest.fixture  
def duckdb_config():
    """DuckDB database configuration for testing (primary engine)"""
    return DatabaseConfig(
        engine=DatabaseEngine.DUCKDB,
        database_path="/tmp/test_tenant.duckdb",
        tenant_id="test_tenant",
        shard_id="shard_1"
    )


@pytest.fixture
def mock_database(duckdb_config):
    """Mock database instance for testing (using DuckDB config)"""
    return MockDatabase(duckdb_config)


class TestDatabaseInterface:
    """Test database interface abstract contract"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, mock_database):
        """Test database initialization"""
        assert not mock_database.initialized
        await mock_database.initialize()
        assert mock_database.initialized
        assert await mock_database.is_initialized()
        
    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, mock_database):
        """Test connection lifecycle management"""
        await mock_database.initialize()
        assert mock_database.initialized
        
        await mock_database.close()
        assert mock_database.closed
        
    @pytest.mark.asyncio
    async def test_schema_management(self, mock_database):
        """Test schema management operations"""
        await mock_database.initialize()
        
        # Test table creation
        await mock_database.create_tables()
        assert mock_database.tables_created
        
        # Test schema version
        version = await mock_database.get_schema_version()
        assert version == "1.0.0"
        
        # Test schema migration
        success = await mock_database.migrate_schema("1.1.0")
        assert success
        assert await mock_database.get_schema_version() == "1.1.0"
        
    @pytest.mark.asyncio
    async def test_query_operations(self, mock_database):
        """Test query execution operations"""
        await mock_database.initialize()
        
        # Test query execution
        result = await mock_database.execute_query("SELECT * FROM users")
        assert isinstance(result, QueryResult)
        assert result.row_count == 1
        assert len(result.rows) == 1
        assert result.columns == ["id", "name"]
        
        # Test command execution
        affected = await mock_database.execute_command("INSERT INTO users VALUES (?, ?)", {"id": 1, "name": "test"})
        assert affected == 1
        
        # Test batch execution
        commands = ["INSERT INTO users VALUES (1, 'test1')", "INSERT INTO users VALUES (2, 'test2')"]
        results = await mock_database.execute_batch(commands)
        assert len(results) == 2
        assert all(r == 1 for r in results)
        
    @pytest.mark.asyncio
    async def test_transaction_management(self, mock_database):
        """Test transaction operations"""
        await mock_database.initialize()
        
        # Test transaction context manager
        async with mock_database.transaction() as tx:
            assert tx is not None
            
        # Test manual transaction management
        tx = await mock_database.begin_transaction()
        assert tx is not None
        await mock_database.commit_transaction(tx)
        
        tx2 = await mock_database.begin_transaction() 
        await mock_database.rollback_transaction(tx2)
        
    @pytest.mark.asyncio
    async def test_health_monitoring(self, mock_database):
        """Test health check and monitoring"""
        await mock_database.initialize()
        
        # Test health check
        health = await mock_database.health_check()
        assert health["status"] == "healthy"
        assert "engine" in health
        
        # Test statistics
        stats = await mock_database.get_statistics()
        assert stats["row_count"] > 0
        assert stats["isolated"] is True
        
        # Test optimization
        success = await mock_database.optimize()
        assert success
        
    @pytest.mark.asyncio
    async def test_backup_operations(self, mock_database):
        """Test backup and restore operations"""
        await mock_database.initialize()
        
        # Test backup
        success = await mock_database.backup("/tmp/backup.db")
        assert success
        
        # Test restore
        success = await mock_database.restore("/tmp/backup.db")
        assert success
        
    @pytest.mark.asyncio
    async def test_sharding_support(self, mock_database):
        """Test sharding operations"""
        await mock_database.initialize()
        
        # Test shard creation
        success = await mock_database.create_shard("new_shard")
        assert success
        
        # Test shard info
        shard_info = await mock_database.get_shard_info()
        assert "shard_id" in shard_info
        assert shard_info["status"] == "active"
        
        # Test shard migration
        source_db = MockDatabase(mock_database.config)
        success = await mock_database.migrate_to_shard(source_db)
        assert success
        
    @pytest.mark.asyncio
    async def test_vector_operations(self, mock_database):
        """Test vector/embedding operations"""
        await mock_database.initialize()
        
        # Test embedding storage
        embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        documents = ["doc1", "doc2"]
        metadata = [{"type": "test"}, {"type": "test"}]
        
        success = await mock_database.store_embeddings("test_collection", embeddings, documents, metadata)
        assert success
        
        # Test embedding query
        results = await mock_database.query_embeddings("test_collection", [0.1, 0.2, 0.3])
        assert len(results) > 0
        assert "score" in results[0]
        
    @pytest.mark.asyncio
    async def test_data_import_export(self, mock_database):
        """Test data import/export operations"""
        await mock_database.initialize()
        
        # Test export
        data = await mock_database.export_data()
        assert "tables" in data
        assert len(data["tables"]) > 0
        
        # Test import
        success = await mock_database.import_data(data)
        assert success
        
    @pytest.mark.asyncio
    async def test_security_operations(self, mock_database):
        """Test security and encryption operations"""
        await mock_database.initialize()
        
        # Test encryption
        success = await mock_database.encrypt_database("encryption_key")
        assert success
        
        # Test encryption verification
        encrypted = await mock_database.verify_encryption()
        assert encrypted
        
    @pytest.mark.asyncio
    async def test_index_management(self, mock_database):
        """Test index operations"""
        await mock_database.initialize()
        
        # Test index creation
        success = await mock_database.create_index("users", ["name"], "idx_user_name")
        assert success
        
        # Test index dropping
        success = await mock_database.drop_index("idx_user_name")
        assert success
        
    @pytest.mark.asyncio
    async def test_engine_info(self, mock_database):
        """Test engine information retrieval"""
        info = await mock_database.get_engine_info()
        assert info["engine"] == "duckdb"
        assert info["tenant_id"] == "test_tenant"
        assert info["file_based"] is True
        
    @pytest.mark.asyncio
    async def test_tenant_isolation_validation(self, mock_database):
        """Test tenant isolation validation"""
        await mock_database.initialize()
        
        # Mock the database path to contain tenant ID
        mock_database.database_path = "/data/test_tenant/database.db"
        
        isolated = await mock_database.validate_tenant_isolation()
        assert isolated


class TestDatabaseConfig:
    """Test database configuration"""
    
    def test_sqlite_config(self, sqlite_config):
        """Test SQLite configuration (legacy support)"""
        assert sqlite_config.engine == DatabaseEngine.SQLITE
        assert sqlite_config.tenant_id == "test_tenant"
        assert sqlite_config.database_path.endswith(".db")
        
    def test_duckdb_config(self, duckdb_config):
        """Test DuckDB configuration (primary engine)"""
        assert duckdb_config.engine == DatabaseEngine.DUCKDB
        assert duckdb_config.shard_id == "shard_1"
        assert duckdb_config.database_path.endswith(".duckdb")


class TestQueryResult:
    """Test query result structure"""
    
    def test_query_result_creation(self):
        """Test query result creation"""
        result = QueryResult(
            rows=[{"id": 1, "name": "test"}],
            row_count=1,
            columns=["id", "name"],
            execution_time_ms=25.5
        )
        
        assert len(result.rows) == 1
        assert result.row_count == 1
        assert len(result.columns) == 2
        assert result.execution_time_ms > 0


class TestDatabaseFactory:
    """Test database factory"""
    
    @pytest.mark.asyncio
    async def test_factory_creation(self, duckdb_config):
        """Test database factory creation with DuckDB"""
        # Test DuckDB database creation (primary engine)
        db = await DatabaseFactory.create_database(duckdb_config)
        assert db is not None
        assert db.engine == DatabaseEngine.DUCKDB
        assert db.tenant_id == "test_tenant"
            
    def test_unsupported_engine(self):
        """Test unsupported database engine"""
        config = DatabaseConfig(
            engine="postgresql",  # Not a valid DatabaseEngine
            database_path="/tmp/test.db", 
            tenant_id="test"
        )
        
        with pytest.raises((ValueError, AttributeError)):
            # This will fail because "postgresql" is not a valid DatabaseEngine
            asyncio.run(DatabaseFactory.create_database(config))


class TestErrorClasses:
    """Test custom error classes"""
    
    def test_database_error(self):
        """Test base database error"""
        error = DatabaseError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
        
    def test_connection_error(self):
        """Test database connection error"""
        error = DatabaseConnectionError("Connection failed")
        assert isinstance(error, DatabaseError)
        assert isinstance(error, Exception)
        
    def test_migration_error(self):
        """Test database migration error"""
        error = DatabaseMigrationError("Migration failed")
        assert isinstance(error, DatabaseError)
        
    def test_sharding_error(self):
        """Test database sharding error"""
        error = DatabaseShardingError("Sharding failed")
        assert isinstance(error, DatabaseError)


# Integration Tests
class TestGT2ComplianceRequirements:
    """Test GT 2.0 principle compliance"""
    
    @pytest.mark.asyncio
    async def test_perfect_tenant_isolation(self, mock_database):
        """Test Perfect Tenant Isolation principle"""
        await mock_database.initialize()
        
        # Tenant ID must be in database path
        assert mock_database.tenant_id in mock_database.database_path
        
        # Tenant isolation validation must pass
        mock_database.database_path = f"/data/{mock_database.tenant_id}/database.db"
        isolated = await mock_database.validate_tenant_isolation()
        assert isolated
        
    @pytest.mark.asyncio
    async def test_zero_downtime_operations(self, mock_database):
        """Test Zero Downtime principle"""
        await mock_database.initialize()
        
        # Backup should work while database is active
        success = await mock_database.backup("/tmp/backup.db")
        assert success
        
        # Health checks should always work
        health = await mock_database.health_check()
        assert health["status"] == "healthy"
        
    @pytest.mark.asyncio
    async def test_elegant_simplicity(self, mock_database):
        """Test Elegant Simplicity principle"""
        # Interface should be simple and clean
        methods = [method for method in dir(mock_database) if not method.startswith('_')]
        
        # Should have all essential operations but not be overly complex
        essential_methods = [
            'initialize', 'close', 'execute_query', 'execute_command',
            'transaction', 'health_check', 'backup', 'optimize'
        ]
        
        for method in essential_methods:
            assert hasattr(mock_database, method)
            
    @pytest.mark.asyncio
    async def test_file_based_architecture(self, mock_database):
        """Test file-based database architecture"""
        info = await mock_database.get_engine_info()
        assert info["file_based"] is True
        
        # Database path should point to a file
        assert mock_database.database_path.endswith(('.db', '.duckdb', '.sqlite'))
        
    @pytest.mark.asyncio
    async def test_self_contained_security(self, mock_database):
        """Test Self-Contained Security principle"""
        await mock_database.initialize()
        
        # Should support encryption
        success = await mock_database.encrypt_database("test_key")
        assert success
        
        # Should verify encryption
        encrypted = await mock_database.verify_encryption()
        assert encrypted


class TestDuckDBSpecificFeatures:
    """Test DuckDB-specific features that enhance GT 2.0 principles"""
    
    @pytest.mark.asyncio
    async def test_mvcc_support(self, duckdb_config):
        """Test MVCC (Multi-Version Concurrency Control) support"""
        mock_db = MockDatabase(duckdb_config)
        await mock_db.initialize()
        
        # DuckDB supports MVCC which enables Zero Downtime operations
        info = await mock_db.get_engine_info()
        assert info["supports_mvcc"] is True
        
    @pytest.mark.asyncio
    async def test_enhanced_sharding(self, duckdb_config):
        """Test DuckDB's enhanced sharding capabilities"""
        mock_db = MockDatabase(duckdb_config)
        await mock_db.initialize()
        
        # DuckDB has built-in sharding support
        info = await mock_db.get_engine_info()
        assert info["supports_sharding"] is True
        
        # Test shard creation
        success = await mock_db.create_shard("analytics_shard")
        assert success
        
    @pytest.mark.asyncio  
    async def test_analytical_performance(self, duckdb_config):
        """Test DuckDB's analytical query performance features"""
        mock_db = MockDatabase(duckdb_config)
        await mock_db.initialize()
        
        # DuckDB should provide query analysis
        analysis = await mock_db.analyze_queries()
        assert "total_queries" in analysis
        assert "avg_execution_time_ms" in analysis
        
    @pytest.mark.asyncio
    async def test_zero_downtime_operations(self, duckdb_config):
        """Test Zero Downtime operations with DuckDB MVCC"""
        mock_db = MockDatabase(duckdb_config)
        await mock_db.initialize()
        
        # MVCC enables concurrent operations without blocking
        async with mock_db.transaction() as tx:
            # This transaction shouldn't block other operations
            result = await mock_db.execute_query("SELECT COUNT(*) FROM users")
            assert result.row_count >= 0
            
        # Health checks should always work during operations
        health = await mock_db.health_check()
        assert health["status"] == "healthy"