-- Remove ip_address column from password_reset_rate_limits
-- Migration: 008_remove_ip_address_from_rate_limits
-- Date: October 7, 2025
-- Database: gt2_admin (Control Panel)
--
-- Description:
--   Removes ip_address column that was incorrectly added by Alembic auto-migration
--   Application only uses email-based rate limiting, not IP-based
--
-- Usage:
--   psql -U postgres -d gt2_admin -f 008_remove_ip_address_from_rate_limits.sql
--
--   OR via Docker:
--   docker exec -i gentwo-controlpanel-postgres psql -U postgres -d gt2_admin < 008_remove_ip_address_from_rate_limits.sql

BEGIN;

-- Remove ip_address column if it exists
DO $$
BEGIN
    IF EXISTS (
        SELECT FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'password_reset_rate_limits'
        AND column_name = 'ip_address'
    ) THEN
        ALTER TABLE password_reset_rate_limits DROP COLUMN ip_address CASCADE;
        RAISE NOTICE 'Removed ip_address column from password_reset_rate_limits';
    ELSE
        RAISE NOTICE 'Column ip_address does not exist, skipping';
    END IF;
END
$$;

-- Mark migration as applied in Alembic version table (if it exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alembic_version') THEN
        INSERT INTO alembic_version (version_num)
        VALUES ('008_remove_ip')
        ON CONFLICT (version_num) DO NOTHING;
        RAISE NOTICE 'Marked migration in alembic_version table';
    ELSE
        RAISE NOTICE 'No alembic_version table found (skipping)';
    END IF;
END
$$;

COMMIT;

-- Verify table structure
\d password_reset_rate_limits

\echo 'Migration 008_remove_ip_address_from_rate_limits completed successfully'
