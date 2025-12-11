-- GT 2.0 Tenant Cluster Role Creation Script
-- Creates PostgreSQL roles for tenant cluster (including replication)
-- Runs in tenant postgres container only

-- Enable logging
\set ON_ERROR_STOP on
\set ECHO all

-- Create replication user for High Availability
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'replicator') THEN
        CREATE ROLE replicator WITH REPLICATION PASSWORD 'tenant_replicator_dev_password' LOGIN;
        RAISE NOTICE 'Created replicator role for HA cluster';
    ELSE
        RAISE NOTICE 'Replicator role already exists';
    END IF;
END $$;

-- Create application user for tenant backend connections (legacy)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gt2_app') THEN
        CREATE ROLE gt2_app LOGIN PASSWORD 'gt2_app_password';
        RAISE NOTICE 'Created gt2_app role for tenant backend';
    ELSE
        RAISE NOTICE 'gt2_app role already exists';
    END IF;
END $$;

-- Create tenant user for tenant database operations (current)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gt2_tenant_user') THEN
        CREATE ROLE gt2_tenant_user LOGIN PASSWORD 'gt2_tenant_dev_password';
        RAISE NOTICE 'Created gt2_tenant_user role for tenant operations';
    ELSE
        RAISE NOTICE 'gt2_tenant_user role already exists';
    END IF;
END $$;

-- Set default search_path for gt2_tenant_user role
-- This ensures all connections automatically use tenant_test_company schema
ALTER ROLE gt2_tenant_user SET search_path TO tenant_test_company, public;

-- Grant database connection permissions (only on gt2_tenants which exists in tenant container)
GRANT CONNECT ON DATABASE gt2_tenants TO gt2_app;
GRANT CONNECT ON DATABASE gt2_tenants TO gt2_tenant_user;
GRANT CONNECT ON DATABASE gt2_tenants TO replicator;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE '=== GT 2.0 TENANT CLUSTER ROLE CREATION ===';
    RAISE NOTICE 'Roles created:';
    RAISE NOTICE '  - replicator (for HA replication)';
    RAISE NOTICE '  - gt2_app (tenant backend - legacy)';
    RAISE NOTICE '  - gt2_tenant_user (tenant operations - current)';
    RAISE NOTICE 'Permissions granted on:';
    RAISE NOTICE '  - gt2_tenants database';
    RAISE NOTICE '==========================================';
END $$;
