-- GT 2.0 Admin Cluster Role Creation Script
-- Creates PostgreSQL roles for admin/control panel cluster
-- Runs in admin postgres container only

-- Enable logging
\set ON_ERROR_STOP on
\set ECHO all

-- Create admin user for control panel database
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gt2_admin') THEN
        CREATE ROLE gt2_admin LOGIN PASSWORD 'dev_password_change_in_prod';
        RAISE NOTICE 'Created gt2_admin role for control panel access';
    ELSE
        RAISE NOTICE 'gt2_admin role already exists';
    END IF;
END $$;

-- Grant database connection permissions (only on databases that exist in admin container)
GRANT CONNECT ON DATABASE gt2_admin TO gt2_admin;
GRANT CONNECT ON DATABASE gt2_control_panel TO gt2_admin;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE '=== GT 2.0 ADMIN CLUSTER ROLE CREATION ===';
    RAISE NOTICE 'Role created: gt2_admin';
    RAISE NOTICE 'Permissions granted on:';
    RAISE NOTICE '  - gt2_admin database';
    RAISE NOTICE '  - gt2_control_panel database';
    RAISE NOTICE '=========================================';
END $$;
