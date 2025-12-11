-- Migration T004: Update validate_resource_share Trigger Function
-- Purpose: Allow team owners and admins to share resources without requiring team membership
-- Dependencies: T003_team_resource_shares.sql
-- Author: GT 2.0 Development Team
-- Date: 2025-01-07
--
-- Changes:
-- - Add team owner bypass check (owners don't need team membership)
-- - Add admin/developer role bypass check (admins can share to any team)
-- - Preserve original team membership + share permission check for regular users
--
-- This migration is idempotent via CREATE OR REPLACE FUNCTION

SET search_path TO tenant_test_company;

CREATE OR REPLACE FUNCTION validate_resource_share()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    user_team_permission VARCHAR(20);
    is_team_owner BOOLEAN;
    user_role VARCHAR(50);
    user_tenant_id UUID;
    team_tenant_id UUID;
BEGIN
    -- Check if user is team owner
    SELECT (owner_id = NEW.shared_by), tenant_id INTO is_team_owner, team_tenant_id
    FROM teams
    WHERE id = NEW.team_id;

    -- Allow team owners to share
    IF is_team_owner THEN
        RETURN NEW;
    END IF;

    -- Check if user is admin/developer (bypass membership requirement)
    SELECT u.user_type, u.tenant_id INTO user_role, user_tenant_id
    FROM users u
    WHERE u.id = NEW.shared_by;

    -- Allow admins/developers in the same tenant
    IF user_role IN ('admin', 'developer', 'super_admin') AND user_tenant_id = team_tenant_id THEN
        RETURN NEW;
    END IF;

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
$$;

-- Verification: Check that the function exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE n.nspname = 'tenant_test_company'
          AND p.proname = 'validate_resource_share'
    ) THEN
        RAISE NOTICE 'SUCCESS: T004 migration completed - validate_resource_share function updated';
    ELSE
        RAISE EXCEPTION 'FAILED: T004 migration - validate_resource_share function not found';
    END IF;
END $$;
