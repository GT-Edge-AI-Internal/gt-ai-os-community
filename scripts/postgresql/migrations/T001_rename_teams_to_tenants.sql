-- Migration T001: Rename 'teams' table to 'tenants' for semantic clarity
-- Date: November 6, 2025
--
-- RATIONALE:
-- The 'teams' table is misnamed - it stores TENANT metadata (one row per tenant),
-- not user collaboration teams. This rename eliminates confusion and frees up the
-- 'teams' name for actual user collaboration features.
--
-- IMPACT:
-- - Renames table: teams → tenants
-- - Renames all foreign key columns: team_id → tenant_id
-- - Updates all constraints and indexes
-- - NO DATA LOSS - purely structural rename
--
-- IDEMPOTENT: Can be run multiple times safely
-- ROLLBACK: See rollback script: T001_rollback.sql

-- Note: When run via docker exec, we're already connected to gt2_tenants
-- So we don't use \c command here

SET search_path TO tenant_test_company, public;

BEGIN;

-- Idempotency wrapper: Only run if migration hasn't been applied yet
DO $$
DECLARE
    teams_exists BOOLEAN;
    tenants_exists BOOLEAN;
BEGIN
    -- Check if old 'teams' table exists and new 'tenants' table doesn't
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'tenant_test_company'
        AND table_name = 'teams'
    ) INTO teams_exists;

    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'tenant_test_company'
        AND table_name = 'tenants'
    ) INTO tenants_exists;

    IF teams_exists AND NOT tenants_exists THEN
        RAISE NOTICE 'Migration T001: Applying teams → tenants rename...';

        -- Step 1: Rename the table
        ALTER TABLE teams RENAME TO tenants;

        -- Step 2: Rename foreign key columns in all dependent tables
        ALTER TABLE users RENAME COLUMN team_id TO tenant_id;
        ALTER TABLE agents RENAME COLUMN team_id TO tenant_id;
        ALTER TABLE datasets RENAME COLUMN team_id TO tenant_id;
        ALTER TABLE conversations RENAME COLUMN team_id TO tenant_id;
        ALTER TABLE documents RENAME COLUMN team_id TO tenant_id;
        ALTER TABLE document_chunks RENAME COLUMN team_id TO tenant_id;

        -- Step 3: Rename foreign key constraints
        ALTER TABLE users RENAME CONSTRAINT users_team_id_fkey TO users_tenant_id_fkey;
        ALTER TABLE agents RENAME CONSTRAINT agents_team_id_fkey TO agents_tenant_id_fkey;
        ALTER TABLE datasets RENAME CONSTRAINT datasets_team_id_fkey TO datasets_tenant_id_fkey;
        ALTER TABLE conversations RENAME CONSTRAINT conversations_team_id_fkey TO conversations_tenant_id_fkey;
        ALTER TABLE documents RENAME CONSTRAINT documents_team_id_fkey TO documents_tenant_id_fkey;
        ALTER TABLE document_chunks RENAME CONSTRAINT document_chunks_team_id_fkey TO document_chunks_tenant_id_fkey;

        -- Step 4: Rename indexes
        ALTER INDEX IF EXISTS idx_teams_domain RENAME TO idx_tenants_domain;
        ALTER INDEX IF EXISTS idx_users_team_id RENAME TO idx_users_tenant_id;
        ALTER INDEX IF EXISTS idx_agents_team_id RENAME TO idx_agents_tenant_id;
        ALTER INDEX IF EXISTS idx_datasets_team_id RENAME TO idx_datasets_tenant_id;
        ALTER INDEX IF EXISTS idx_conversations_team_id RENAME TO idx_conversations_tenant_id;
        ALTER INDEX IF EXISTS idx_documents_team_id RENAME TO idx_documents_tenant_id;
        ALTER INDEX IF EXISTS idx_document_chunks_team_id RENAME TO idx_document_chunks_tenant_id;

        RAISE NOTICE '✅ Migration T001 applied successfully!';
        RAISE NOTICE '  - Table renamed: teams → tenants';
        RAISE NOTICE '  - Columns renamed: team_id → tenant_id (6 tables)';
        RAISE NOTICE '  - Constraints renamed: 6 foreign keys';
        RAISE NOTICE '  - Indexes renamed: 7 indexes';

    ELSIF NOT teams_exists AND tenants_exists THEN
        RAISE NOTICE '✅ Migration T001 already applied (tenants table exists, teams table renamed)';
    ELSIF teams_exists AND tenants_exists THEN
        RAISE WARNING '⚠️  Migration T001 in inconsistent state: both teams and tenants tables exist!';
        RAISE WARNING '    Manual intervention may be required.';
    ELSE
        RAISE WARNING '⚠️  Migration T001 cannot run: neither teams nor tenants table exists!';
        RAISE WARNING '    Check if schema is properly initialized.';
    END IF;
END $$;

COMMIT;

-- Verification query
DO $$
DECLARE
    tenant_count INTEGER;
    user_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO tenant_count FROM tenants;
    SELECT COUNT(*) INTO user_count FROM users;

    RAISE NOTICE 'Migration T001 verification:';
    RAISE NOTICE '  Tenants: % rows', tenant_count;
    RAISE NOTICE '  Users: % rows', user_count;
END $$;
