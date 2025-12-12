-- Migration: T006_auth_logs
-- Description: Add authentication logging for user logins, logouts, and failed attempts
-- Date: 2025-11-17
-- Issue: #152

-- This migration creates the auth_logs table to track authentication events
-- for observability and security auditing purposes.

BEGIN;

-- Apply to existing tenant schemas
DO $$
DECLARE
    tenant_schema TEXT;
BEGIN
    FOR tenant_schema IN
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name LIKE 'tenant_%' AND schema_name != 'tenant_template'
    LOOP
        -- Create auth_logs table
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.auth_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id TEXT NOT NULL,
                email TEXT NOT NULL,
                event_type TEXT NOT NULL CHECK (event_type IN (''login'', ''logout'', ''failed_login'')),
                success BOOLEAN NOT NULL DEFAULT true,
                failure_reason TEXT,
                ip_address TEXT,
                user_agent TEXT,
                tenant_domain TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                metadata JSONB DEFAULT ''{}''::jsonb
            )', tenant_schema);

        -- Create indexes
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_auth_logs_user_id ON %I.auth_logs(user_id)', tenant_schema);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_auth_logs_email ON %I.auth_logs(email)', tenant_schema);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_auth_logs_event_type ON %I.auth_logs(event_type)', tenant_schema);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_auth_logs_created_at ON %I.auth_logs(created_at DESC)', tenant_schema);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_auth_logs_tenant_domain ON %I.auth_logs(tenant_domain)', tenant_schema);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_auth_logs_event_created ON %I.auth_logs(event_type, created_at DESC)', tenant_schema);

        RAISE NOTICE 'Applied T006_auth_logs migration to schema: %', tenant_schema;
    END LOOP;
END $$;

COMMIT;

-- Verification query
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relname = 'auth_logs'
    AND n.nspname LIKE 'tenant_%'
ORDER BY n.nspname;
