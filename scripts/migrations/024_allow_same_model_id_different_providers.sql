-- Migration: 024_allow_same_model_id_different_providers.sql
-- Description: Allow same model_id with different providers
-- The unique constraint should be on (model_id, provider) not just model_id
-- This allows the same model to be registered from multiple providers (e.g., Groq and NVIDIA)
-- Author: Claude Code
-- Date: 2025-12-08

-- ============================================================================
-- STEP 1: Drop the unique constraint on model_id alone
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'model_configs_model_id_unique'
        AND table_name = 'model_configs'
        AND table_schema = 'public'
    ) THEN
        ALTER TABLE model_configs DROP CONSTRAINT model_configs_model_id_unique;
        RAISE NOTICE 'Dropped unique constraint model_configs_model_id_unique';
    ELSE
        RAISE NOTICE 'Constraint model_configs_model_id_unique does not exist';
    END IF;
END $$;

-- ============================================================================
-- STEP 2: Add new unique constraint on (model_id, provider)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'model_configs_model_id_provider_unique'
        AND table_name = 'model_configs'
        AND table_schema = 'public'
    ) THEN
        ALTER TABLE model_configs ADD CONSTRAINT model_configs_model_id_provider_unique UNIQUE (model_id, provider);
        RAISE NOTICE 'Added unique constraint on (model_id, provider)';
    ELSE
        RAISE NOTICE 'Constraint model_configs_model_id_provider_unique already exists';
    END IF;
END $$;

-- ============================================================================
-- VERIFICATION
-- ============================================================================
SELECT 'model_configs constraints after migration:' AS info;
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'model_configs' AND table_schema = 'public'
ORDER BY constraint_type, constraint_name;
