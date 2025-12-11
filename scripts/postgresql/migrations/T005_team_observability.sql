-- Migration T005: Team Observability System
-- Purpose: Add Observable member tracking for team-level activity monitoring
-- Dependencies: T003_team_resource_shares.sql
-- Author: GT 2.0 Development Team
-- Date: 2025-01-10

-- Set schema for tenant isolation
SET search_path TO tenant_test_company;

-- ============================================================================
-- SECTION 1: Add Observable Columns to team_memberships
-- ============================================================================

-- Add Observable status tracking columns
ALTER TABLE team_memberships
ADD COLUMN IF NOT EXISTS is_observable BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS observable_consent_status VARCHAR(20) DEFAULT 'none',
ADD COLUMN IF NOT EXISTS observable_consent_at TIMESTAMPTZ;

-- Add constraint for observable_consent_status values
ALTER TABLE team_memberships
ADD CONSTRAINT check_observable_consent_status
    CHECK (observable_consent_status IN ('none', 'pending', 'approved', 'revoked'));

COMMENT ON COLUMN team_memberships.is_observable IS 'Member consents to team managers viewing their activity';
COMMENT ON COLUMN team_memberships.observable_consent_status IS 'Consent workflow status: none, pending, approved, revoked';
COMMENT ON COLUMN team_memberships.observable_consent_at IS 'Timestamp when Observable status was approved';

-- ============================================================================
-- SECTION 2: Extend team_permission to Include Manager Role
-- ============================================================================

-- Drop existing constraint if it exists (handles both explicit and auto-generated names)
ALTER TABLE team_memberships DROP CONSTRAINT IF EXISTS check_team_permission;
ALTER TABLE team_memberships DROP CONSTRAINT IF EXISTS team_memberships_team_permission_check;

-- Add updated constraint with 'manager' role
ALTER TABLE team_memberships
ADD CONSTRAINT check_team_permission
    CHECK (team_permission IN ('read', 'share', 'manager'));

COMMENT ON COLUMN team_memberships.team_permission IS
    'Team role: read=Member (view only), share=Contributor (can share resources), manager=Manager (can manage members + view Observable activity)';

-- ============================================================================
-- SECTION 3: Update Auto-Unshare Trigger for Manager Role
-- ============================================================================

-- Update trigger function to handle 'manager' role
CREATE OR REPLACE FUNCTION auto_unshare_on_permission_downgrade()
RETURNS TRIGGER AS $$
BEGIN
    -- Clear resource_permissions when downgrading from share/manager to read
    -- Manager and Contributor (share) can share resources
    -- Member (read) cannot share resources
    IF OLD.team_permission IN ('share', 'manager')
       AND NEW.team_permission = 'read' THEN
        NEW.resource_permissions := '{}'::jsonb;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION auto_unshare_on_permission_downgrade IS
    'Clears resource_permissions when member is downgraded to read-only (Member role)';

-- ============================================================================
-- SECTION 4: Update Resource Share Validation for Manager Role
-- ============================================================================

-- Update validation function to allow managers to share
CREATE OR REPLACE FUNCTION validate_resource_share()
RETURNS TRIGGER AS $$
DECLARE
    user_team_permission VARCHAR(20);
    is_team_owner BOOLEAN;
    user_role VARCHAR(50);
BEGIN
    -- Get user's team permission
    SELECT team_permission INTO user_team_permission
    FROM team_memberships
    WHERE team_id = NEW.team_id
      AND user_id = NEW.shared_by;

    -- Check if user is the team owner
    SELECT EXISTS (
        SELECT 1 FROM teams
        WHERE id = NEW.team_id AND owner_id = NEW.shared_by
    ) INTO is_team_owner;

    -- Get user's system role for admin bypass
    SELECT role INTO user_role
    FROM users
    WHERE id = NEW.shared_by;

    -- Allow if: owner, or has share/manager permission, or is admin/developer
    IF is_team_owner THEN
        RETURN NEW;
    END IF;

    IF user_role IN ('admin', 'developer') THEN
        RETURN NEW;
    END IF;

    IF user_team_permission IS NULL THEN
        RAISE EXCEPTION 'User % is not a member of team %', NEW.shared_by, NEW.team_id;
    END IF;

    IF user_team_permission NOT IN ('share', 'manager') THEN
        RAISE EXCEPTION 'User % does not have permission to share resources (current permission: %)',
            NEW.shared_by, user_team_permission;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION validate_resource_share IS
    'Validates that only owners, managers, contributors (share), or admins can share resources to teams';

-- ============================================================================
-- SECTION 5: Performance Indexes
-- ============================================================================

-- Index for finding Observable members (used for activity queries)
CREATE INDEX IF NOT EXISTS idx_team_memberships_observable
    ON team_memberships(team_id, is_observable, observable_consent_status)
    WHERE is_observable = true AND observable_consent_status = 'approved';

-- Index for finding members by role (for permission checks)
CREATE INDEX IF NOT EXISTS idx_team_memberships_permission
    ON team_memberships(team_id, team_permission);

COMMENT ON INDEX idx_team_memberships_observable IS
    'Optimizes queries for Observable member activity (partial index for approved Observable members only)';
COMMENT ON INDEX idx_team_memberships_permission IS
    'Optimizes role-based permission checks (finding managers, contributors, etc.)';

-- ============================================================================
-- SECTION 6: Helper Function - Get Observable Members
-- ============================================================================

CREATE OR REPLACE FUNCTION get_observable_members(p_team_id UUID)
RETURNS TABLE (
    user_id UUID,
    user_email TEXT,
    user_name TEXT,
    observable_since TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        tm.user_id,
        u.email::text as user_email,
        u.full_name::text as user_name,
        tm.observable_consent_at
    FROM team_memberships tm
    JOIN users u ON tm.user_id = u.id
    WHERE tm.team_id = p_team_id
      AND tm.is_observable = true
      AND tm.observable_consent_status = 'approved'
      AND tm.status = 'accepted'
    ORDER BY tm.observable_consent_at DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_observable_members IS
    'Returns list of Observable team members with approved consent status';

-- ============================================================================
-- SECTION 7: Verification
-- ============================================================================

DO $$
DECLARE
    observable_count INTEGER;
    manager_count INTEGER;
BEGIN
    -- Verify Observable columns exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_memberships'
        AND column_name = 'is_observable'
    ) THEN
        RAISE EXCEPTION 'FAILURE: is_observable column not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_memberships'
        AND column_name = 'observable_consent_status'
    ) THEN
        RAISE EXCEPTION 'FAILURE: observable_consent_status column not created';
    END IF;

    -- Verify indexes
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_team_memberships_observable'
    ) THEN
        RAISE EXCEPTION 'FAILURE: idx_team_memberships_observable index not created';
    END IF;

    -- Count Observable members (should be 0 initially)
    SELECT COUNT(*) INTO observable_count
    FROM team_memberships
    WHERE is_observable = true;

    RAISE NOTICE 'SUCCESS: Observable columns added (current Observable members: %)', observable_count;
    RAISE NOTICE 'SUCCESS: team_permission constraint updated to support manager role';
    RAISE NOTICE 'SUCCESS: Indexes created for Observable queries';
    RAISE NOTICE 'Migration T005 completed successfully!';
END $$;
