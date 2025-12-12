-- GT 2.0 Tenant Database Creation Script
-- Creates database for tenant cluster only
-- This MUST run first (00-prefix ensures execution order)

-- Enable logging
\set ON_ERROR_STOP on
\set ECHO all

-- Create gt2_tenants database for tenant data storage
SELECT 'CREATE DATABASE gt2_tenants'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'gt2_tenants')\gexec

-- Log database creation completion
DO $$
BEGIN
    RAISE NOTICE '=== GT 2.0 TENANT DATABASE CREATION ===';
    RAISE NOTICE 'Database created successfully:';
    RAISE NOTICE '- gt2_tenants (tenant data storage with PGVector)';
    RAISE NOTICE '=======================================';
END $$;
