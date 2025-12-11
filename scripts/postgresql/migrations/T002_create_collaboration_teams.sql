-- Migration T002: Create User Collaboration Teams Tables
-- Date: November 6, 2025
--
-- PURPOSE:
-- Creates tables for user collaboration teams (different from tenant metadata).
-- Users can create teams, invite members, and share agents/datasets with team members.
--
-- TABLES CREATED:
-- 1. teams - User collaboration teams (NOT tenant metadata)
-- 2. team_memberships - Team members with two-tier permissions
--
-- PERMISSION MODEL:
-- Tier 1 (Team-level): 'read' (access resources) or 'share' (access + share own resources)
-- Tier 2 (Resource-level): Per-user permissions stored in JSONB {"agent:uuid": "read|edit"}
--
-- IDEMPOTENT: Can be run multiple times safely
-- DEPENDS ON: T001_rename_teams_to_tenants.sql (must run first)

-- Note: When run via docker exec, we're already connected to gt2_tenants

SET search_path TO tenant_test_company, public;

BEGIN;

-- Table 1: User Collaboration Teams
-- This is the NEW teams table for user collaboration (replaces old misnamed tenant table)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'tenant_test_company'
        AND table_name = 'teams'
    ) THEN
        CREATE TABLE teams (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            description TEXT,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,  -- Tenant isolation
            owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,     -- Team owner
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        RAISE NOTICE '✅ Created teams table for user collaboration';
    ELSE
        RAISE NOTICE '✅ Teams table already exists';
    END IF;
END $$;

-- Table 2: Team Memberships with Two-Tier Permissions
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'tenant_test_company'
        AND table_name = 'team_memberships'
    ) THEN
        CREATE TABLE team_memberships (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

            -- Tier 1: Team-level permission (set by team owner)
            team_permission VARCHAR(20) NOT NULL DEFAULT 'read'
                CHECK (team_permission IN ('read', 'share')),
            -- 'read' = can access resources shared to this team
            -- 'share' = can access resources AND share own resources to this team

            -- Tier 2: Resource-level permissions (set by resource sharer when sharing)
            -- JSONB structure: {"agent:uuid": "read|edit", "dataset:uuid": "read|edit"}
            resource_permissions JSONB DEFAULT '{}',

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(team_id, user_id)  -- Prevent duplicate memberships
        );

        RAISE NOTICE '✅ Created team_memberships table';
    ELSE
        RAISE NOTICE '✅ Team_memberships table already exists';
    END IF;
END $$;

-- Performance indexes
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_indexes
        WHERE schemaname = 'tenant_test_company'
        AND indexname = 'idx_teams_owner_id'
    ) THEN
        CREATE INDEX idx_teams_owner_id ON teams(owner_id);
        RAISE NOTICE '✅ Created index: idx_teams_owner_id';
    END IF;

    IF NOT EXISTS (
        SELECT FROM pg_indexes
        WHERE schemaname = 'tenant_test_company'
        AND indexname = 'idx_teams_tenant_id'
    ) THEN
        CREATE INDEX idx_teams_tenant_id ON teams(tenant_id);
        RAISE NOTICE '✅ Created index: idx_teams_tenant_id';
    END IF;

    IF NOT EXISTS (
        SELECT FROM pg_indexes
        WHERE schemaname = 'tenant_test_company'
        AND indexname = 'idx_team_memberships_team_id'
    ) THEN
        CREATE INDEX idx_team_memberships_team_id ON team_memberships(team_id);
        RAISE NOTICE '✅ Created index: idx_team_memberships_team_id';
    END IF;

    IF NOT EXISTS (
        SELECT FROM pg_indexes
        WHERE schemaname = 'tenant_test_company'
        AND indexname = 'idx_team_memberships_user_id'
    ) THEN
        CREATE INDEX idx_team_memberships_user_id ON team_memberships(user_id);
        RAISE NOTICE '✅ Created index: idx_team_memberships_user_id';
    END IF;

    IF NOT EXISTS (
        SELECT FROM pg_indexes
        WHERE schemaname = 'tenant_test_company'
        AND indexname = 'idx_team_memberships_resources'
    ) THEN
        CREATE INDEX idx_team_memberships_resources ON team_memberships USING gin(resource_permissions);
        RAISE NOTICE '✅ Created index: idx_team_memberships_resources';
    END IF;
END $$;

-- Function: Auto-unshare resources when user loses 'share' permission
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE n.nspname = 'tenant_test_company'
        AND p.proname = 'auto_unshare_on_permission_downgrade'
    ) THEN
        CREATE FUNCTION auto_unshare_on_permission_downgrade()
        RETURNS TRIGGER AS $func$
        BEGIN
            -- If team_permission changed from 'share' to 'read'
            IF OLD.team_permission = 'share' AND NEW.team_permission = 'read' THEN
                -- Clear all resource permissions for this user
                -- (they can no longer share resources, so remove what they shared)
                NEW.resource_permissions := '{}'::jsonb;

                RAISE NOTICE 'Auto-unshared all resources for user % in team % due to permission downgrade',
                             NEW.user_id, NEW.team_id;
            END IF;

            RETURN NEW;
        END;
        $func$ LANGUAGE plpgsql;

        RAISE NOTICE '✅ Created function: auto_unshare_on_permission_downgrade';
    ELSE
        RAISE NOTICE '✅ Function auto_unshare_on_permission_downgrade already exists';
    END IF;
END $$;

-- Trigger: Apply auto-unshare logic
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_trigger
        WHERE tgname = 'trigger_auto_unshare'
    ) THEN
        CREATE TRIGGER trigger_auto_unshare
        BEFORE UPDATE OF team_permission ON team_memberships
        FOR EACH ROW
        EXECUTE FUNCTION auto_unshare_on_permission_downgrade();

        RAISE NOTICE '✅ Created trigger: trigger_auto_unshare';
    ELSE
        RAISE NOTICE '✅ Trigger trigger_auto_unshare already exists';
    END IF;
END $$;

-- Grant permissions
DO $$
BEGIN
    GRANT SELECT, INSERT, UPDATE, DELETE ON teams TO gt2_tenant_user;
    GRANT SELECT, INSERT, UPDATE, DELETE ON team_memberships TO gt2_tenant_user;
    RAISE NOTICE '✅ Granted permissions to gt2_tenant_user';
EXCEPTION
    WHEN undefined_object THEN
        RAISE NOTICE '⚠️  Role gt2_tenant_user does not exist (ok for fresh installs)';
END $$;

COMMIT;

-- Final verification
DO $$
DECLARE
    teams_count INTEGER;
    memberships_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO teams_count FROM teams;
    SELECT COUNT(*) INTO memberships_count FROM team_memberships;

    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ Migration T002 completed successfully!';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Tables created:';
    RAISE NOTICE '  - teams (user collaboration): % rows', teams_count;
    RAISE NOTICE '  - team_memberships: % rows', memberships_count;
    RAISE NOTICE 'Indexes: 5 created';
    RAISE NOTICE 'Functions: 1 created';
    RAISE NOTICE 'Triggers: 1 created';
    RAISE NOTICE '========================================';
END $$;
