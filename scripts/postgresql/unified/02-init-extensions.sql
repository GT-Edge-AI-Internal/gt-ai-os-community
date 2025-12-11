-- GT 2.0 Unified Extensions Initialization
-- Ensures all required extensions are properly configured for all databases
-- Run after user creation (02-prefix ensures execution order)

-- Enable logging (but don't stop on errors for database connections)
\set ECHO all

-- Connect to gt2_tenants database first for PGVector setup
\c gt2_tenants
\set ON_ERROR_STOP on

-- Vector extension for embeddings (PGVector) - Required for tenant database
CREATE EXTENSION IF NOT EXISTS vector;

-- Full-text search support
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Statistics and monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pg_buffercache;

-- UUID generation (built-in in PostgreSQL 13+, but ensure availability)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- JSON support enhancements
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Security extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Connect to control panel database and add required extensions (if it exists)
\set ON_ERROR_STOP off
\c gt2_control_panel
\set ON_ERROR_STOP on

-- Basic extensions for control panel
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Connect to admin database and add required extensions (if it exists)
\set ON_ERROR_STOP off
\c gt2_admin
\set ON_ERROR_STOP on

-- Basic extensions for admin database
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Switch back to tenant database for verification
\set ON_ERROR_STOP off
\c gt2_tenants
\set ON_ERROR_STOP on

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
    RAISE NOTICE '=== GT 2.0 UNIFIED EXTENSIONS SETUP ===';
    RAISE NOTICE 'Extensions configured in all databases:';
    RAISE NOTICE '- gt2_tenants: PGVector + full-text + monitoring';
    RAISE NOTICE '- gt2_control_panel: Basic extensions + crypto';
    RAISE NOTICE '- gt2_admin: Basic extensions + crypto';
    RAISE NOTICE 'All critical extensions verified and loaded';
    RAISE NOTICE '=====================================';
END $$;