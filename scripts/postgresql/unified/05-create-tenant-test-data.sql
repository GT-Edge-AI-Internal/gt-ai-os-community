-- GT 2.0 Tenant Test Data Creation Script
-- Creates test tenant and gtadmin@test.com user in tenant database
-- Mirrors the control panel test data for user sync compatibility

-- Enable logging
\set ON_ERROR_STOP on
\set ECHO all

-- Create test tenant in tenant schema
INSERT INTO tenant_test_company.tenants (
    domain,
    name,
    created_at,
    updated_at
) VALUES (
    'test-company',
    'HW Workstation Test Deployment',
    NOW(),
    NOW()
) ON CONFLICT (domain) DO UPDATE SET
    name = EXCLUDED.name,
    updated_at = NOW();

-- Create test super admin user in tenant schema
-- Role mapping: super_admin from control panel → 'admin' in tenant database
-- This mirrors what sync_user_to_tenant_database() does in control-panel-backend
INSERT INTO tenant_test_company.users (
    email,
    username,
    full_name,
    tenant_id,
    role,
    created_at,
    updated_at
) VALUES (
    'gtadmin@test.com',
    'gtadmin',
    'GT Admin',
    (SELECT id FROM tenant_test_company.tenants WHERE domain = 'test-company' LIMIT 1),
    'admin',
    NOW(),
    NOW()
) ON CONFLICT (email, tenant_id) DO UPDATE SET
    username = EXCLUDED.username,
    full_name = EXCLUDED.full_name,
    role = EXCLUDED.role,
    updated_at = NOW();

-- Log completion
DO $$
DECLARE
    tenant_count INTEGER;
    user_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO tenant_count FROM tenant_test_company.tenants WHERE domain = 'test-company';
    SELECT COUNT(*) INTO user_count FROM tenant_test_company.users WHERE email = 'gtadmin@test.com';

    RAISE NOTICE '=== GT 2.0 TENANT TEST DATA CREATION ===';
    RAISE NOTICE 'Test tenant created: % (domain: test-company)', tenant_count;
    RAISE NOTICE 'Test user created: % (email: gtadmin@test.com)', user_count;
    RAISE NOTICE 'User role: admin (mapped from super_admin)';
    RAISE NOTICE 'Note: User can now log into tenant app at localhost:3002';
    RAISE NOTICE '========================================';
END $$;
