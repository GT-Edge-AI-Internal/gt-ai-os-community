-- Migration T003: Team Resource Sharing System
-- Purpose: Enable multi-team resource sharing for agents and datasets
-- Dependencies: T002_create_collaboration_teams.sql
-- Author: GT 2.0 Development Team
-- Date: 2025-01-07

-- Set schema for tenant isolation
SET search_path TO tenant_test_company;

-- ============================================================================
-- SECTION 1: Junction Table for Many-to-Many Resource Sharing
-- ============================================================================

CREATE TABLE IF NOT EXISTS team_resource_shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    resource_type VARCHAR(20) NOT NULL CHECK (resource_type IN ('agent', 'dataset')),
    resource_id UUID NOT NULL,
    shared_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),

    -- Ensure each resource can only be shared once per team
    UNIQUE(team_id, resource_type, resource_id)
);

COMMENT ON TABLE team_resource_shares IS 'Junction table for sharing agents/datasets with collaboration teams';
COMMENT ON COLUMN team_resource_shares.resource_type IS 'Type of resource: agent or dataset';
COMMENT ON COLUMN team_resource_shares.resource_id IS 'UUID of the agent or dataset being shared';
COMMENT ON COLUMN team_resource_shares.shared_by IS 'User who shared this resource with the team';

-- ============================================================================
-- SECTION 2: Performance Indexes
-- ============================================================================

-- Index for finding all teams a resource is shared with
CREATE INDEX idx_trs_resource ON team_resource_shares(resource_type, resource_id);

-- Index for finding all resources shared with a team
CREATE INDEX idx_trs_team ON team_resource_shares(team_id);

-- Index for finding resources shared by a specific user
CREATE INDEX idx_trs_shared_by ON team_resource_shares(shared_by);

-- Composite index for common access checks
CREATE INDEX idx_trs_lookup ON team_resource_shares(team_id, resource_type, resource_id);

-- ============================================================================
-- SECTION 3: Helper View #1 - Individual User Resource Access
-- ============================================================================
-- Purpose: Flatten team memberships + resource shares for fast permission checks
-- Usage: Check if specific user has access to specific resource

CREATE VIEW user_resource_access AS
SELECT
    tm.user_id,
    trs.resource_type,
    trs.resource_id,
    tm.resource_permissions->(trs.resource_type || ':' || trs.resource_id::text) as permission,
    tm.team_id,
    tm.team_permission,
    trs.shared_by,
    trs.created_at
FROM team_memberships tm
JOIN team_resource_shares trs ON tm.team_id = trs.team_id
WHERE tm.resource_permissions ? (trs.resource_type || ':' || trs.resource_id::text);

COMMENT ON VIEW user_resource_access IS 'Flattened view of user access to resources via team memberships';

-- Note: Indexes on views are not supported in standard PostgreSQL
-- For performance, consider creating a materialized view if needed

-- ============================================================================
-- SECTION 4: Helper View #2 - Aggregated User Accessible Resources
-- ============================================================================
-- Purpose: Aggregate resources by user for efficient listing
-- Usage: Get all agents/datasets accessible to a user (for list views)

CREATE VIEW user_accessible_resources AS
SELECT
    tm.user_id,
    trs.resource_type,
    trs.resource_id,
    MAX(CASE
        WHEN tm.resource_permissions->(trs.resource_type || ':' || trs.resource_id::text) = '"edit"'::jsonb
        THEN 'edit'
        WHEN tm.resource_permissions->(trs.resource_type || ':' || trs.resource_id::text) = '"read"'::jsonb
        THEN 'read'
        ELSE 'none'
    END) as best_permission,
    COUNT(DISTINCT tm.team_id) as shared_in_teams,
    ARRAY_AGG(DISTINCT tm.team_id) as team_ids,
    MIN(trs.created_at) as first_shared_at
FROM team_memberships tm
JOIN team_resource_shares trs ON tm.team_id = trs.team_id
WHERE tm.resource_permissions ? (trs.resource_type || ':' || trs.resource_id::text)
GROUP BY tm.user_id, trs.resource_type, trs.resource_id;

COMMENT ON VIEW user_accessible_resources IS 'Aggregated view showing all resources accessible to each user with best permission level';

-- Note: Indexes on views are not supported in standard PostgreSQL
-- For performance, consider creating a materialized view if needed

-- ============================================================================
-- SECTION 5: Cascade Cleanup Trigger
-- ============================================================================
-- Purpose: When a resource is unshared from a team, clean up member permissions
-- Note: The ON DELETE CASCADE on team_resource_shares already handles team deletion

CREATE OR REPLACE FUNCTION cleanup_resource_permissions()
RETURNS TRIGGER AS $$
BEGIN
    -- Remove the resource permission key from all team members
    UPDATE team_memberships
    SET resource_permissions = resource_permissions - (OLD.resource_type || ':' || OLD.resource_id::text)
    WHERE team_id = OLD.team_id
      AND resource_permissions ? (OLD.resource_type || ':' || OLD.resource_id::text);

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_cleanup_resource_permissions
    BEFORE DELETE ON team_resource_shares
    FOR EACH ROW
    EXECUTE FUNCTION cleanup_resource_permissions();

COMMENT ON FUNCTION cleanup_resource_permissions IS 'Removes resource permission entries from team members when resource is unshared';

-- ============================================================================
-- SECTION 6: Validation Function
-- ============================================================================
-- Purpose: Validate that a user has 'share' permission before sharing resources

CREATE OR REPLACE FUNCTION validate_resource_share()
RETURNS TRIGGER AS $$
DECLARE
    user_team_permission VARCHAR(20);
BEGIN
    -- Check if the user has 'share' permission on the team
    SELECT team_permission INTO user_team_permission
    FROM team_memberships
    WHERE team_id = NEW.team_id
      AND user_id = NEW.shared_by;

    IF user_team_permission IS NULL THEN
        RAISE EXCEPTION 'User % is not a member of team %', NEW.shared_by, NEW.team_id;
    END IF;

    IF user_team_permission != 'share' THEN
        RAISE EXCEPTION 'User % does not have share permission on team %', NEW.shared_by, NEW.team_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_validate_resource_share
    BEFORE INSERT ON team_resource_shares
    FOR EACH ROW
    EXECUTE FUNCTION validate_resource_share();

COMMENT ON FUNCTION validate_resource_share IS 'Ensures only users with share permission can share resources to teams';

-- ============================================================================
-- SECTION 6B: Sync JSONB Permissions When Resource Shared
-- ============================================================================
-- Purpose: Automatically update team_memberships.resource_permissions when
--          a resource is shared to a team. This ensures database-level consistency.

CREATE OR REPLACE FUNCTION sync_resource_permissions_on_share()
RETURNS TRIGGER AS $$
BEGIN
    -- Note: This trigger is called AFTER validation, so we know the share is valid
    -- The actual permission levels (read/edit) are set by the application layer
    -- This trigger just ensures the resource key exists in the JSONB
    --
    -- The application will call a separate function to set individual user permissions
    -- after this trigger runs. This is a two-step process:
    -- 1. This trigger: Ensure resource is known to the team
    -- 2. Application: Set per-user permissions via update_member_resource_permission()

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Note: We're keeping this trigger simple for now. The application layer handles
-- per-user permission assignment. A future optimization could move all permission
-- logic into triggers, but that requires storing default permissions in team_resource_shares.

COMMENT ON FUNCTION sync_resource_permissions_on_share IS 'Placeholder for future JSONB sync automation';

-- ============================================================================
-- SECTION 7: Helper Functions for Application Layer
-- ============================================================================

-- Function to get all resources shared with a team
CREATE OR REPLACE FUNCTION get_team_resources(p_team_id UUID, p_resource_type VARCHAR DEFAULT NULL)
RETURNS TABLE (
    resource_id UUID,
    resource_type VARCHAR,
    shared_by UUID,
    created_at TIMESTAMP,
    member_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        trs.resource_id,
        trs.resource_type,
        trs.shared_by,
        trs.created_at,
        COUNT(DISTINCT tm.user_id) as member_count
    FROM team_resource_shares trs
    JOIN team_memberships tm ON tm.team_id = trs.team_id
    WHERE trs.team_id = p_team_id
      AND (p_resource_type IS NULL OR trs.resource_type = p_resource_type)
      AND tm.resource_permissions ? (trs.resource_type || ':' || trs.resource_id::text)
    GROUP BY trs.resource_id, trs.resource_type, trs.shared_by, trs.created_at
    ORDER BY trs.created_at DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_team_resources IS 'Get all resources shared with a team, optionally filtered by resource type';

-- Function to check if a user has permission on a resource
CREATE OR REPLACE FUNCTION check_user_resource_permission(
    p_user_id UUID,
    p_resource_type VARCHAR,
    p_resource_id UUID,
    p_required_permission VARCHAR DEFAULT 'read'
)
RETURNS BOOLEAN AS $$
DECLARE
    user_permission VARCHAR;
BEGIN
    -- Get the user's permission from any team that has this resource
    SELECT (ura.permission::text)
    INTO user_permission
    FROM user_resource_access ura
    WHERE ura.user_id = p_user_id
      AND ura.resource_type = p_resource_type
      AND ura.resource_id = p_resource_id
    LIMIT 1;

    -- If no permission found, return false
    IF user_permission IS NULL THEN
        RETURN FALSE;
    END IF;

    -- Remove quotes from JSONB string value
    user_permission := TRIM(BOTH '"' FROM user_permission);

    -- Check permission level
    IF p_required_permission = 'read' THEN
        RETURN user_permission IN ('read', 'edit');
    ELSIF p_required_permission = 'edit' THEN
        RETURN user_permission = 'edit';
    ELSE
        RETURN FALSE;
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION check_user_resource_permission IS 'Check if user has required permission (read/edit) on a resource';

-- ============================================================================
-- SECTION 8: Migration Data (if needed)
-- ============================================================================

-- If there are any existing agents/datasets with visibility='team',
-- they would need to be migrated here. Since this is a fresh feature,
-- no data migration is needed.

-- ============================================================================
-- SECTION 9: Grant Permissions
-- ============================================================================

-- Grant appropriate permissions to application roles
-- Note: Adjust role names based on your PostgreSQL setup

-- GRANT SELECT, INSERT, UPDATE, DELETE ON team_resource_shares TO gt2_tenant_user;
-- GRANT SELECT ON user_resource_access TO gt2_tenant_user;
-- GRANT SELECT ON user_accessible_resources TO gt2_tenant_user;
-- GRANT EXECUTE ON FUNCTION get_team_resources TO gt2_tenant_user;
-- GRANT EXECUTE ON FUNCTION check_user_resource_permission TO gt2_tenant_user;

-- ============================================================================
-- SECTION 10: Verification Queries
-- ============================================================================

-- Verify table was created
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'team_resource_shares') THEN
        RAISE NOTICE 'SUCCESS: team_resource_shares table created';
    ELSE
        RAISE EXCEPTION 'FAILURE: team_resource_shares table not found';
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.views WHERE table_name = 'user_resource_access') THEN
        RAISE NOTICE 'SUCCESS: user_resource_access view created';
    ELSE
        RAISE EXCEPTION 'FAILURE: user_resource_access view not found';
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.views WHERE table_name = 'user_accessible_resources') THEN
        RAISE NOTICE 'SUCCESS: user_accessible_resources view created';
    ELSE
        RAISE EXCEPTION 'FAILURE: user_accessible_resources view not found';
    END IF;

    RAISE NOTICE 'Migration T003 completed successfully!';
END $$;
