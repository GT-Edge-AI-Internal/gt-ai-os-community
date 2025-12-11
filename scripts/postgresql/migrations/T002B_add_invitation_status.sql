-- Migration: Add invitation status tracking to team_memberships
-- Created: 2025-01-07
-- Purpose: Enable team invitation accept/decline workflow

SET search_path TO tenant_test_company, public;

-- Add status tracking columns
ALTER TABLE team_memberships
  ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'accepted'
    CHECK (status IN ('pending', 'accepted', 'declined'));

ALTER TABLE team_memberships
  ADD COLUMN IF NOT EXISTS invited_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE team_memberships
  ADD COLUMN IF NOT EXISTS responded_at TIMESTAMPTZ;

-- Update existing memberships to 'accepted' status
-- This ensures backward compatibility with existing data
UPDATE team_memberships
SET status = 'accepted', invited_at = created_at
WHERE status IS NULL;

-- Create index for efficient pending invitation queries
CREATE INDEX IF NOT EXISTS idx_team_memberships_status
  ON team_memberships(user_id, status);

CREATE INDEX IF NOT EXISTS idx_team_memberships_team_status
  ON team_memberships(team_id, status);

-- Add comment for documentation
COMMENT ON COLUMN team_memberships.status IS 'Invitation status: pending (invited), accepted (active member), declined (rejected invitation)';
COMMENT ON COLUMN team_memberships.invited_at IS 'Timestamp when invitation was sent';
COMMENT ON COLUMN team_memberships.responded_at IS 'Timestamp when invitation was accepted or declined';
