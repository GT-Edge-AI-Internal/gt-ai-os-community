-- Migration: 023_add_uuid_primary_key_to_model_configs.sql
-- Description: Add UUID primary key to model_configs table instead of using model_id string
-- This fixes the database design issue where model_id (a human-readable string) was used as primary key
-- Author: Claude Code
-- Date: 2025-12-08

-- ============================================================================
-- STEP 1: Ensure uuid-ossp extension is available
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- STEP 2: Add new UUID 'id' column to model_configs
-- ============================================================================
DO $$
BEGIN
    -- Check if 'id' column already exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'model_configs' AND column_name = 'id' AND table_schema = 'public'
    ) THEN
        -- Add the new UUID column
        ALTER TABLE model_configs ADD COLUMN id UUID DEFAULT uuid_generate_v4();

        -- Populate UUIDs for all existing rows
        UPDATE model_configs SET id = uuid_generate_v4() WHERE id IS NULL;

        -- Make id NOT NULL
        ALTER TABLE model_configs ALTER COLUMN id SET NOT NULL;

        RAISE NOTICE 'Added id column to model_configs';
    ELSE
        RAISE NOTICE 'id column already exists in model_configs';
    END IF;
END $$;

-- ============================================================================
-- STEP 3: Add new UUID 'model_config_id' column to tenant_model_configs
-- ============================================================================
DO $$
BEGIN
    -- Check if 'model_config_id' column already exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tenant_model_configs' AND column_name = 'model_config_id' AND table_schema = 'public'
    ) THEN
        -- Add the new UUID column
        ALTER TABLE tenant_model_configs ADD COLUMN model_config_id UUID;

        RAISE NOTICE 'Added model_config_id column to tenant_model_configs';
    ELSE
        RAISE NOTICE 'model_config_id column already exists in tenant_model_configs';
    END IF;
END $$;

-- ============================================================================
-- STEP 4: Populate model_config_id based on model_id mapping
-- ============================================================================
UPDATE tenant_model_configs tmc
SET model_config_id = mc.id
FROM model_configs mc
WHERE tmc.model_id = mc.model_id
AND tmc.model_config_id IS NULL;

-- ============================================================================
-- STEP 5: Drop the old foreign key constraint
-- ============================================================================
DO $$
BEGIN
    -- Drop foreign key if it exists
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'tenant_model_configs_model_id_fkey'
        AND table_name = 'tenant_model_configs'
        AND table_schema = 'public'
    ) THEN
        ALTER TABLE tenant_model_configs DROP CONSTRAINT tenant_model_configs_model_id_fkey;
        RAISE NOTICE 'Dropped old foreign key constraint tenant_model_configs_model_id_fkey';
    ELSE
        RAISE NOTICE 'Foreign key constraint tenant_model_configs_model_id_fkey does not exist';
    END IF;
END $$;

-- ============================================================================
-- STEP 6: Drop old unique constraint on (tenant_id, model_id)
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'unique_tenant_model'
        AND table_name = 'tenant_model_configs'
        AND table_schema = 'public'
    ) THEN
        ALTER TABLE tenant_model_configs DROP CONSTRAINT unique_tenant_model;
        RAISE NOTICE 'Dropped old unique constraint unique_tenant_model';
    ELSE
        RAISE NOTICE 'Unique constraint unique_tenant_model does not exist';
    END IF;
END $$;

-- ============================================================================
-- STEP 7: Drop the old primary key on model_configs.model_id
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'model_configs_pkey'
        AND constraint_type = 'PRIMARY KEY'
        AND table_name = 'model_configs'
        AND table_schema = 'public'
    ) THEN
        ALTER TABLE model_configs DROP CONSTRAINT model_configs_pkey;
        RAISE NOTICE 'Dropped old primary key model_configs_pkey';
    ELSE
        RAISE NOTICE 'Primary key model_configs_pkey does not exist';
    END IF;
END $$;

-- ============================================================================
-- STEP 8: Add new primary key on model_configs.id
-- ============================================================================
DO $$
BEGIN
    -- Check if primary key already exists on id column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_name = 'model_configs'
        AND tc.constraint_type = 'PRIMARY KEY'
        AND kcu.column_name = 'id'
        AND tc.table_schema = 'public'
    ) THEN
        ALTER TABLE model_configs ADD CONSTRAINT model_configs_pkey PRIMARY KEY (id);
        RAISE NOTICE 'Added new primary key on model_configs.id';
    ELSE
        RAISE NOTICE 'Primary key on model_configs.id already exists';
    END IF;
END $$;

-- ============================================================================
-- STEP 9: Add unique constraint on model_configs.model_id
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'model_configs_model_id_unique'
        AND table_name = 'model_configs'
        AND table_schema = 'public'
    ) THEN
        ALTER TABLE model_configs ADD CONSTRAINT model_configs_model_id_unique UNIQUE (model_id);
        RAISE NOTICE 'Added unique constraint on model_configs.model_id';
    ELSE
        RAISE NOTICE 'Unique constraint on model_configs.model_id already exists';
    END IF;
END $$;

-- ============================================================================
-- STEP 10: Make model_config_id NOT NULL and add foreign key
-- ============================================================================
DO $$
BEGIN
    -- Make model_config_id NOT NULL (only if all values are populated)
    IF EXISTS (
        SELECT 1 FROM tenant_model_configs WHERE model_config_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Cannot make model_config_id NOT NULL: some values are NULL. Run the UPDATE first.';
    END IF;

    -- Alter column to NOT NULL
    ALTER TABLE tenant_model_configs ALTER COLUMN model_config_id SET NOT NULL;
    RAISE NOTICE 'Set model_config_id to NOT NULL';
EXCEPTION
    WHEN others THEN
        RAISE NOTICE 'Could not set model_config_id to NOT NULL: %', SQLERRM;
END $$;

-- ============================================================================
-- STEP 11: Add foreign key from tenant_model_configs.model_config_id to model_configs.id
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'tenant_model_configs_model_config_id_fkey'
        AND table_name = 'tenant_model_configs'
        AND table_schema = 'public'
    ) THEN
        ALTER TABLE tenant_model_configs
        ADD CONSTRAINT tenant_model_configs_model_config_id_fkey
        FOREIGN KEY (model_config_id) REFERENCES model_configs(id) ON DELETE CASCADE;
        RAISE NOTICE 'Added foreign key on tenant_model_configs.model_config_id';
    ELSE
        RAISE NOTICE 'Foreign key tenant_model_configs_model_config_id_fkey already exists';
    END IF;
END $$;

-- ============================================================================
-- STEP 12: Add new unique constraint on (tenant_id, model_config_id)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'unique_tenant_model_config'
        AND table_name = 'tenant_model_configs'
        AND table_schema = 'public'
    ) THEN
        ALTER TABLE tenant_model_configs
        ADD CONSTRAINT unique_tenant_model_config UNIQUE (tenant_id, model_config_id);
        RAISE NOTICE 'Added unique constraint unique_tenant_model_config';
    ELSE
        RAISE NOTICE 'Unique constraint unique_tenant_model_config already exists';
    END IF;
END $$;

-- ============================================================================
-- STEP 13: Add index on model_configs.model_id for fast lookups
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'model_configs'
        AND indexname = 'ix_model_configs_model_id'
        AND schemaname = 'public'
    ) THEN
        CREATE INDEX ix_model_configs_model_id ON model_configs(model_id);
        RAISE NOTICE 'Created index ix_model_configs_model_id';
    ELSE
        RAISE NOTICE 'Index ix_model_configs_model_id already exists';
    END IF;
END $$;

-- ============================================================================
-- STEP 14: Add index on tenant_model_configs.model_config_id
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'tenant_model_configs'
        AND indexname = 'ix_tenant_model_configs_model_config_id'
        AND schemaname = 'public'
    ) THEN
        CREATE INDEX ix_tenant_model_configs_model_config_id ON tenant_model_configs(model_config_id);
        RAISE NOTICE 'Created index ix_tenant_model_configs_model_config_id';
    ELSE
        RAISE NOTICE 'Index ix_tenant_model_configs_model_config_id already exists';
    END IF;
END $$;

-- ============================================================================
-- VERIFICATION: Show final schema
-- ============================================================================
SELECT 'model_configs schema:' AS info;
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'model_configs' AND table_schema = 'public'
ORDER BY ordinal_position;

SELECT 'tenant_model_configs schema:' AS info;
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'tenant_model_configs' AND table_schema = 'public'
ORDER BY ordinal_position;

SELECT 'model_configs constraints:' AS info;
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'model_configs' AND table_schema = 'public';

SELECT 'tenant_model_configs constraints:' AS info;
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'tenant_model_configs' AND table_schema = 'public';
