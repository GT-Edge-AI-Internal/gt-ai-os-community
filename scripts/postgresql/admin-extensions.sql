-- GT 2.0 Admin Cluster Extensions Initialization
-- Installs basic extensions for admin/control panel databases
-- Does NOT include PGVector (not available in postgres:15-alpine image)

-- Enable logging
\set ON_ERROR_STOP on
\set ECHO all

-- NOTE: Removed \c gt2_admin - Docker entrypoint runs this script
-- against POSTGRES_DB (gt2_admin) automatically.

-- Basic extensions for admin database
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_buffercache";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Log completion
DO $$
BEGIN
    RAISE NOTICE '=== GT 2.0 ADMIN EXTENSIONS SETUP ===';
    RAISE NOTICE 'Extensions configured in admin database:';
    RAISE NOTICE '- gt2_admin: uuid-ossp, pg_stat_statements, pg_buffercache, pgcrypto';
    RAISE NOTICE 'Note: PGVector NOT installed (admin cluster uses standard PostgreSQL)';
    RAISE NOTICE '=====================================';
END $$;
