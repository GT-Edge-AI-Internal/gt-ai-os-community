-- GT 2.0 Tenant Cluster Extensions Initialization
-- Installs all extensions for tenant database including PGVector
-- Requires pgvector/pgvector:pg15 Docker image

-- Enable logging
\set ON_ERROR_STOP on
\set ECHO all

-- NOTE: Removed \c gt2_tenants - Docker entrypoint runs this script
-- against POSTGRES_DB (gt2_tenants) automatically.

-- Vector extension for embeddings (PGVector) - Required for RAG/embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Full-text search support
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Statistics and monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pg_buffercache;

-- UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- JSON support enhancements
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Security extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Verify critical extensions are loaded
DO $$
DECLARE
    ext_count INTEGER;
BEGIN
    -- Check vector extension
    SELECT COUNT(*) INTO ext_count FROM pg_extension WHERE extname = 'vector';
    IF ext_count = 0 THEN
        RAISE EXCEPTION 'Vector extension not loaded - PGVector support required for embeddings';
    ELSE
        RAISE NOTICE 'Vector extension loaded successfully - PGVector enabled';
    END IF;

    -- Check pg_trgm extension
    SELECT COUNT(*) INTO ext_count FROM pg_extension WHERE extname = 'pg_trgm';
    IF ext_count = 0 THEN
        RAISE EXCEPTION 'pg_trgm extension not loaded - Full-text search support required';
    ELSE
        RAISE NOTICE 'pg_trgm extension loaded successfully - Full-text search enabled';
    END IF;

    -- Check pg_stat_statements extension
    SELECT COUNT(*) INTO ext_count FROM pg_extension WHERE extname = 'pg_stat_statements';
    IF ext_count = 0 THEN
        RAISE WARNING 'pg_stat_statements extension not loaded - Query monitoring limited';
    ELSE
        RAISE NOTICE 'pg_stat_statements extension loaded successfully - Query monitoring enabled';
    END IF;
END $$;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE '=== GT 2.0 TENANT EXTENSIONS SETUP ===';
    RAISE NOTICE 'Extensions configured in tenant database:';
    RAISE NOTICE '- gt2_tenants: PGVector + full-text search + monitoring + crypto';
    RAISE NOTICE 'All critical extensions verified and loaded';
    RAISE NOTICE '======================================';
END $$;
