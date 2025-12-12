-- GT 2.0 Admin Database Creation Script
-- Creates databases for admin/control panel cluster only
-- This MUST run first (00-prefix ensures execution order)

-- Enable logging
\set ON_ERROR_STOP on
\set ECHO all

-- Create gt2_admin database for control panel
SELECT 'CREATE DATABASE gt2_admin'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'gt2_admin')\gexec

-- Create gt2_control_panel database for control panel backend
SELECT 'CREATE DATABASE gt2_control_panel'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'gt2_control_panel')\gexec

-- Log database creation completion
DO $$
BEGIN
    RAISE NOTICE '=== GT 2.0 ADMIN DATABASE CREATION ===';
    RAISE NOTICE 'Databases created successfully:';
    RAISE NOTICE '- gt2_admin (control panel metadata)';
    RAISE NOTICE '- gt2_control_panel (control panel backend)';
    RAISE NOTICE 'Note: gt2_tenants created in tenant cluster separately';
    RAISE NOTICE '======================================';
END $$;