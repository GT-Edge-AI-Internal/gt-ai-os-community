-- Add frontend_url column to tenants table
-- Migration: 006_add_tenant_frontend_url
-- Date: October 6, 2025

BEGIN;

-- Add frontend_url column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'tenants' 
        AND column_name = 'frontend_url'
    ) THEN
        ALTER TABLE tenants ADD COLUMN frontend_url VARCHAR(255);
        RAISE NOTICE 'Added frontend_url column to tenants table';
    ELSE
        RAISE NOTICE 'Column frontend_url already exists in tenants table';
    END IF;
END
$$;

-- Mark migration as applied in Alembic version table (if it exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alembic_version') THEN
        INSERT INTO alembic_version (version_num)
        VALUES ('006_frontend_url')
        ON CONFLICT (version_num) DO NOTHING;
        RAISE NOTICE 'Marked migration in alembic_version table';
    ELSE
        RAISE NOTICE 'No alembic_version table found (skipping)';
    END IF;
END
$$;

COMMIT;

-- Verify column was added
\echo 'Migration 006_add_tenant_frontend_url completed successfully'
