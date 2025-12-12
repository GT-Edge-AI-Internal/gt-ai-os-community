"""
GT 2.0 PostgreSQL + PGVector Client for Tenant Backend

Replaces DuckDB service with direct PostgreSQL connections, providing:
- PostgreSQL + PGVector unified storage (replaces DuckDB + ChromaDB)
- BionicGPT Row Level Security patterns for enterprise isolation
- MVCC concurrency solving DuckDB file locking issues
- Hybrid vector + full-text search in single queries
- Connection pooling for 10,000+ concurrent connections
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator, Tuple, Union
from contextlib import asynccontextmanager
import json
from datetime import datetime
from uuid import UUID

import asyncpg
from asyncpg import Pool, Connection
from asyncpg.exceptions import PostgresError

from app.core.config import get_settings, get_tenant_schema_name

logger = logging.getLogger(__name__)

class PostgreSQLClient:
    """PostgreSQL + PGVector client for tenant backend operations"""
    
    def __init__(self, database_url: str, tenant_domain: str):
        self.database_url = database_url
        self.tenant_domain = tenant_domain
        self.schema_name = get_tenant_schema_name(tenant_domain)
        self._pool: Optional[Pool] = None
        self._initialized = False
        
    async def __aenter__(self):
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def initialize(self) -> None:
        """Initialize connection pool and verify schema"""
        if self._initialized:
            return
            
        logger.info(f"Initializing PostgreSQL connection pool for tenant: {self.tenant_domain}")
        logger.info(f"Schema: {self.schema_name}, URL: {self.database_url}")
        
        try:
            # Create connection pool with resilient settings
            # Sized for 100+ concurrent users with RAG/vector search workloads
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=10,
                max_size=50,  # Increased from 20 to handle 100+ concurrent users
                command_timeout=120,  # Increased from 60s for queries under load
                timeout=10,  # Connection acquire timeout increased for high load
                max_inactive_connection_lifetime=3600,  # Recycle connections after 1 hour
                server_settings={
                    'application_name': f'gt2_tenant_{self.tenant_domain}'
                },
                # Enable prepared statements for direct postgres connection (performance gain)
                statement_cache_size=100
            )
            
            # Verify schema exists and has required tables
            await self._verify_schema()
            
            self._initialized = True
            logger.info(f"PostgreSQL client initialized successfully for tenant: {self.tenant_domain}")
            
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL client: {e}")
            if self._pool:
                await self._pool.close()
                self._pool = None
            raise
    
    async def close(self) -> None:
        """Close connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False
            logger.info(f"PostgreSQL connection pool closed for tenant: {self.tenant_domain}")
    
    async def _verify_schema(self) -> None:
        """Verify tenant schema exists and has required tables"""
        async with self._pool.acquire() as conn:
            # Check if schema exists
            schema_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.schemata 
                    WHERE schema_name = $1
                )
            """, self.schema_name)
            
            if not schema_exists:
                raise RuntimeError(f"Tenant schema '{self.schema_name}' does not exist. Run schema initialization first.")
            
            # Check for required tables
            required_tables = ['tenants', 'users', 'agents', 'datasets', 'conversations', 'messages', 'documents', 'document_chunks']
            
            for table in required_tables:
                table_exists = await conn.fetchval(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_schema = $1 AND table_name = $2
                    )
                """, self.schema_name, table)
                
                if not table_exists:
                    logger.warning(f"Table '{table}' not found in schema '{self.schema_name}'")
            
            logger.info(f"Schema verification complete for tenant: {self.tenant_domain}")
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[Connection, None]:
        """Get a connection from the pool"""
        if not self._pool:
            raise RuntimeError("PostgreSQL client not initialized. Call initialize() first.")
        
        async with self._pool.acquire() as conn:
            try:
                # Set schema search path for this connection
                await conn.execute(f"SET search_path TO {self.schema_name}, public")

                # Session variable logging removed - no longer using RLS

                yield conn
            except Exception as e:
                logger.error(f"Database connection error: {e}")
                raise
    
    async def execute_query(self, query: str, *args) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results"""
        async with self.get_connection() as conn:
            try:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows]
            except PostgresError as e:
                logger.error(f"Query execution failed: {e}, Query: {query}")
                raise
    
    async def execute_command(self, command: str, *args) -> int:
        """Execute an INSERT/UPDATE/DELETE command and return affected rows"""
        async with self.get_connection() as conn:
            try:
                result = await conn.execute(command, *args)
                # Parse result like "INSERT 0 5" to get affected rows
                return int(result.split()[-1]) if result else 0
            except PostgresError as e:
                logger.error(f"Command execution failed: {e}, Command: {command}")
                raise
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Execute query and return first row"""
        async with self.get_connection() as conn:
            try:
                row = await conn.fetchrow(query, *args)
                return dict(row) if row else None
            except PostgresError as e:
                logger.error(f"Fetch one failed: {e}, Query: {query}")
                raise
    
    async def fetch_scalar(self, query: str, *args) -> Any:
        """Execute query and return single value"""
        async with self.get_connection() as conn:
            try:
                return await conn.fetchval(query, *args)
            except PostgresError as e:
                logger.error(f"Fetch scalar failed: {e}, Query: {query}")
                raise
    
    async def execute_transaction(self, commands: List[Tuple[str, tuple]]) -> List[int]:
        """Execute multiple commands in a transaction"""
        async with self.get_connection() as conn:
            async with conn.transaction():
                results = []
                for command, args in commands:
                    try:
                        result = await conn.execute(command, *args)
                        results.append(int(result.split()[-1]) if result else 0)
                    except PostgresError as e:
                        logger.error(f"Transaction command failed: {e}, Command: {command}")
                        raise
                return results
    
    # Vector Search Operations (PGVector)
    
    async def vector_similarity_search(
        self, 
        query_vector: List[float], 
        table: str = "document_chunks",
        limit: int = 10,
        similarity_threshold: float = 0.3,
        user_id: Optional[str] = None,
        dataset_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search using PGVector"""
        
        # Convert Python list to PostgreSQL array format
        vector_str = '[' + ','.join(map(str, query_vector)) + ']'
        
        query = f"""
            SELECT 
                id,
                content,
                1 - (embedding <=> $1::vector) as similarity_score,
                metadata
            FROM {table}
            WHERE embedding IS NOT NULL
              AND 1 - (embedding <=> $1::vector) > $2
        """
        
        params = [vector_str, similarity_threshold]
        param_idx = 3
        
        # Add user isolation if specified
        if user_id:
            query += f" AND user_id = ${param_idx}"
            params.append(user_id)
            param_idx += 1
            
        # Add dataset filtering if specified
        if dataset_id:
            query += f" AND dataset_id = ${param_idx}"
            params.append(dataset_id)
            param_idx += 1
        
        query += f" ORDER BY embedding <=> $1::vector LIMIT ${param_idx}"
        params.append(limit)
        
        return await self.execute_query(query, *params)
    
    async def hybrid_search(
        self,
        query_text: str,
        query_vector: List[float],
        user_id: str,
        limit: int = 10,
        similarity_threshold: float = 0.3,
        text_weight: float = 0.3,
        vector_weight: float = 0.7,
        dataset_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining vector similarity and full-text search"""
        
        vector_str = '[' + ','.join(map(str, query_vector)) + ']'
        
        # Use the enhanced_hybrid_search_chunks function from BionicGPT integration
        query = """
            SELECT 
                id,
                document_id,
                content,
                similarity_score,
                text_rank,
                combined_score,
                metadata,
                access_verified
            FROM enhanced_hybrid_search_chunks($1, $2::vector, $3::uuid, $4, $5, $6, $7, $8)
        """
        
        return await self.execute_query(
            query,
            query_text,
            vector_str, 
            user_id,
            dataset_id,
            limit,
            similarity_threshold,
            text_weight,
            vector_weight
        )
    
    async def insert_document_chunk(
        self,
        document_id: str,
        tenant_id: int,
        user_id: str,
        chunk_index: int,
        content: str,
        content_hash: str,
        embedding: List[float],
        dataset_id: Optional[str] = None,
        token_count: int = 0,
        metadata: Optional[Dict] = None
    ) -> str:
        """Insert a document chunk with vector embedding"""

        vector_str = '[' + ','.join(map(str, embedding)) + ']'
        metadata_json = json.dumps(metadata or {})

        query = """
            INSERT INTO document_chunks (
                document_id, tenant_id, user_id, dataset_id, chunk_index,
                content, content_hash, token_count, embedding, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::vector, $10::jsonb)
            RETURNING id
        """

        return await self.fetch_scalar(
            query,
            document_id, tenant_id, user_id, dataset_id, chunk_index,
            content, content_hash, token_count, vector_str, metadata_json
        )
    
    # Health Check and Statistics
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on PostgreSQL connection"""
        try:
            if not self._pool:
                return {"status": "unhealthy", "reason": "Connection pool not initialized"}
            
            # Test basic connectivity
            test_result = await self.fetch_scalar("SELECT 1")
            
            # Get pool statistics
            pool_stats = {
                "size": self._pool.get_size(),
                "min_size": self._pool.get_min_size(),
                "max_size": self._pool.get_max_size(),
                "idle_size": self._pool.get_idle_size()
            }
            
            # Test schema access
            schema_test = await self.fetch_scalar("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.schemata 
                    WHERE schema_name = $1
                )
            """, self.schema_name)
            
            return {
                "status": "healthy" if test_result == 1 and schema_test else "degraded",
                "connectivity": "ok" if test_result == 1 else "failed",
                "schema_access": "ok" if schema_test else "failed",
                "tenant_domain": self.tenant_domain,
                "schema_name": self.schema_name,
                "pool_stats": pool_stats,
                "database_type": "postgresql_pgvector"
            }
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            return {"status": "unhealthy", "reason": str(e)}
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics for monitoring"""
        try:
            # Get table counts and sizes
            stats_query = """
                SELECT 
                    schemaname,
                    tablename,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes,
                    n_live_tup as live_tuples,
                    n_dead_tup as dead_tuples
                FROM pg_stat_user_tables 
                WHERE schemaname = $1
            """
            
            table_stats = await self.execute_query(stats_query, self.schema_name)
            
            # Get total schema size
            size_query = """
                SELECT pg_size_pretty(
                    SUM(pg_total_relation_size(quote_ident(schemaname)||'.'||quote_ident(tablename)))
                ) as schema_size
                FROM pg_tables 
                WHERE schemaname = $1
            """
            
            schema_size = await self.fetch_scalar(size_query, self.schema_name)
            
            # Get vector index statistics if available
            vector_stats_query = """
                SELECT 
                    COUNT(*) as vector_count,
                    AVG(vector_dims(embedding)) as avg_dimensions
                FROM document_chunks 
                WHERE embedding IS NOT NULL
            """
            
            try:
                vector_stats = await self.fetch_one(vector_stats_query)
            except:
                vector_stats = {"vector_count": 0, "avg_dimensions": 0}
            
            return {
                "tenant_domain": self.tenant_domain,
                "schema_name": self.schema_name,
                "schema_size": schema_size,
                "table_stats": table_stats,
                "vector_stats": vector_stats,
                "engine_type": "PostgreSQL + PGVector",
                "mvcc_enabled": True,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get database statistics: {e}")
            return {"error": str(e)}


# Global client instance (singleton pattern for tenant backend)
_pg_client: Optional[PostgreSQLClient] = None


async def get_postgresql_client() -> PostgreSQLClient:
    """Get or create PostgreSQL client instance"""
    global _pg_client
    
    if not _pg_client:
        settings = get_settings()
        _pg_client = PostgreSQLClient(
            database_url=settings.database_url,
            tenant_domain=settings.tenant_domain
        )
        await _pg_client.initialize()
    
    return _pg_client


async def init_postgresql() -> None:
    """Initialize PostgreSQL client during startup"""
    logger.info("Initializing PostgreSQL client...")
    await get_postgresql_client()
    logger.info("PostgreSQL client initialized successfully")


async def close_postgresql() -> None:
    """Close PostgreSQL client during shutdown"""
    global _pg_client
    
    if _pg_client:
        await _pg_client.close()
        _pg_client = None
        logger.info("PostgreSQL client closed")


# Context manager for database operations
@asynccontextmanager
async def get_db_session():
    """Async context manager for database operations"""
    client = await get_postgresql_client()
    async with client.get_connection() as conn:
        yield conn


# Convenience functions for common operations
async def execute_query(query: str, *args) -> List[Dict[str, Any]]:
    """Execute a SELECT query"""
    client = await get_postgresql_client()
    return await client.execute_query(query, *args)


async def execute_command(command: str, *args) -> int:
    """Execute an INSERT/UPDATE/DELETE command"""
    client = await get_postgresql_client()
    return await client.execute_command(command, *args)


async def fetch_one(query: str, *args) -> Optional[Dict[str, Any]]:
    """Execute query and return first row"""
    client = await get_postgresql_client()
    return await client.fetch_one(query, *args)


async def fetch_scalar(query: str, *args) -> Any:
    """Execute query and return single value"""
    client = await get_postgresql_client()
    return await client.fetch_scalar(query, *args)


async def health_check() -> Dict[str, Any]:
    """Perform database health check"""
    try:
        client = await get_postgresql_client()
        return await client.health_check()
    except Exception as e:
        return {"status": "unhealthy", "reason": str(e)}


async def get_database_info() -> Dict[str, Any]:
    """Get database information and statistics"""
    try:
        client = await get_postgresql_client()
        return await client.get_database_stats()
    except Exception as e:
        return {"error": str(e)}