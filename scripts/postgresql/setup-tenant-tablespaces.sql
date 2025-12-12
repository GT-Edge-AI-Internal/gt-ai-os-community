-- GT 2.0 Tenant Tablespace Setup
-- Creates dedicated tablespaces for tenant data isolation on persistent volumes

-- Create tablespace directory if it doesn't exist (PostgreSQL will create it)
-- This tablespace will be on the dedicated tenant persistent volume
-- Note: CREATE TABLESPACE cannot be in DO block or EXECUTE, must be top-level SQL
-- Note: IF NOT EXISTS not supported until PostgreSQL 16, using conditional with DROP IF EXISTS

-- Drop and recreate to ensure clean state (safe for init scripts on fresh DB)
DROP TABLESPACE IF EXISTS tenant_test_company_ts;
CREATE TABLESPACE tenant_test_company_ts LOCATION '/var/lib/postgresql/tablespaces/tenant_test';

-- Set default tablespace for tenant schema (PostgreSQL doesn't support ALTER SCHEMA SET default_tablespace)
-- Instead, we'll set the default for the database connection when needed

-- Move existing tenant tables to the dedicated tablespace
-- This ensures all tenant data is stored on the tenant-specific persistent volume

-- Move users table
ALTER TABLE tenant_test_company.users SET TABLESPACE tenant_test_company_ts;

-- Move teams table  
ALTER TABLE tenant_test_company.teams SET TABLESPACE tenant_test_company_ts;

-- Move agents table
ALTER TABLE tenant_test_company.agents SET TABLESPACE tenant_test_company_ts;

-- Move conversations table
ALTER TABLE tenant_test_company.conversations SET TABLESPACE tenant_test_company_ts;

-- Move messages table
ALTER TABLE tenant_test_company.messages SET TABLESPACE tenant_test_company_ts;

-- Move documents table
ALTER TABLE tenant_test_company.documents SET TABLESPACE tenant_test_company_ts;

-- Move document_chunks table (contains PGVector embeddings)
ALTER TABLE tenant_test_company.document_chunks SET TABLESPACE tenant_test_company_ts;

-- Move datasets table
ALTER TABLE tenant_test_company.datasets SET TABLESPACE tenant_test_company_ts;

-- Move all indexes to the tenant tablespace as well
DO $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN 
        SELECT schemaname, indexname, tablename
        FROM pg_indexes 
        WHERE schemaname = 'tenant_test_company'
    LOOP
        BEGIN
            EXECUTE format('ALTER INDEX %I.%I SET TABLESPACE tenant_test_company_ts', 
                          rec.schemaname, rec.indexname);
            RAISE NOTICE 'Moved index %.% to tenant tablespace', rec.schemaname, rec.indexname;
        EXCEPTION
            WHEN OTHERS THEN
                RAISE WARNING 'Failed to move index %.%: %', rec.schemaname, rec.indexname, SQLERRM;
        END;
    END LOOP;
END $$;

-- Grant permissions for the tablespace
GRANT CREATE ON TABLESPACE tenant_test_company_ts TO gt2_tenant_user;

-- Display tablespace information
SELECT 
    spcname as tablespace_name,
    pg_tablespace_location(oid) as location,
    pg_size_pretty(pg_tablespace_size(spcname)) as size
FROM pg_tablespace 
WHERE spcname LIKE 'tenant_%';

-- Display tenant table locations
SELECT 
    schemaname,
    tablename,
    tablespace
FROM pg_tables 
WHERE schemaname = 'tenant_test_company'
ORDER BY tablename;

-- Display completion notice
DO $$
BEGIN
    RAISE NOTICE 'Tenant tablespace setup completed for test';
END $$;