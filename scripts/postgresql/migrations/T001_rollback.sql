-- Rollback Migration T001: Rename 'tenants' table back to 'teams'
-- Date: November 6, 2025
--
-- This script reverses the T001_rename_teams_to_tenants.sql migration
-- Use only if you need to rollback the migration for any reason
--
-- NO DATA LOSS - purely structural rename back to original state
-- IDEMPOTENT: Can be run multiple times safely

SET search_path TO tenant_test_company, public;

BEGIN;

-- Idempotency wrapper: Only run if rollback hasn't been applied yet
DO $$
DECLARE
    teams_exists BOOLEAN;
    tenants_exists BOOLEAN;
BEGIN
    -- Check current state
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

    IF NOT teams_exists AND tenants_exists THEN
        RAISE NOTICE 'Rollback T001: Reverting tenants → teams rename...';

        -- Step 1: Rename the table back
        ALTER TABLE tenants RENAME TO teams;

        -- Step 2: Rename foreign key columns back
        ALTER TABLE users RENAME COLUMN tenant_id TO team_id;
        ALTER TABLE agents RENAME COLUMN tenant_id TO team_id;
        ALTER TABLE datasets RENAME COLUMN tenant_id TO team_id;
        ALTER TABLE conversations RENAME COLUMN tenant_id TO team_id;
        ALTER TABLE documents RENAME COLUMN tenant_id TO team_id;
        ALTER TABLE document_chunks RENAME COLUMN tenant_id TO team_id;

        -- Step 3: Rename foreign key constraints back
        ALTER TABLE users RENAME CONSTRAINT users_tenant_id_fkey TO users_team_id_fkey;
        ALTER TABLE agents RENAME CONSTRAINT agents_tenant_id_fkey TO agents_team_id_fkey;
        ALTER TABLE datasets RENAME CONSTRAINT datasets_tenant_id_fkey TO datasets_team_id_fkey;
        ALTER TABLE conversations RENAME CONSTRAINT conversations_tenant_id_fkey TO conversations_team_id_fkey;
        ALTER TABLE documents RENAME CONSTRAINT documents_tenant_id_fkey TO documents_team_id_fkey;
        ALTER TABLE document_chunks RENAME CONSTRAINT document_chunks_tenant_id_fkey TO document_chunks_team_id_fkey;

        -- Step 4: Rename indexes back
        ALTER INDEX IF EXISTS idx_tenants_domain RENAME TO idx_teams_domain;
        ALTER INDEX IF EXISTS idx_users_tenant_id RENAME TO idx_users_team_id;
        ALTER INDEX IF EXISTS idx_agents_tenant_id RENAME TO idx_agents_team_id;
        ALTER INDEX IF EXISTS idx_datasets_tenant_id RENAME TO idx_datasets_team_id;
        ALTER INDEX IF EXISTS idx_conversations_tenant_id RENAME TO idx_conversations_team_id;
        ALTER INDEX IF EXISTS idx_documents_tenant_id RENAME TO idx_documents_team_id;
        ALTER INDEX IF EXISTS idx_document_chunks_tenant_id RENAME TO idx_document_chunks_team_id;

        RAISE NOTICE '✅ Rollback T001 completed successfully!';
        RAISE NOTICE '  - Table renamed: tenants → teams';
        RAISE NOTICE '  - Columns renamed: tenant_id → team_id (6 tables)';
        RAISE NOTICE '  - Constraints renamed: 6 foreign keys';
        RAISE NOTICE '  - Indexes renamed: 7 indexes';

    ELSIF teams_exists AND NOT tenants_exists THEN
        RAISE NOTICE '✅ Rollback T001 already applied (teams table exists, tenants table not found)';
    ELSE
        RAISE WARNING '⚠️  Rollback T001 cannot determine state: teams=%,tenants=%', teams_exists, tenants_exists;
    END IF;
END $$;

COMMIT;

-- Verification
DO $$
DECLARE
    team_count INTEGER;
    user_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO team_count FROM teams;
    SELECT COUNT(*) INTO user_count FROM users;

    RAISE NOTICE 'Rollback T001 verification:';
    RAISE NOTICE '  Teams: % rows', team_count;
    RAISE NOTICE '  Users: % rows', user_count;
END $$;
