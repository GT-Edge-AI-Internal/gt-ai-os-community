-- Migration 013: Rename cost columns from per_1k to per_million
-- This is idempotent - only runs if old columns exist

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'model_configs'
               AND column_name = 'cost_per_1k_input') THEN
        ALTER TABLE model_configs RENAME COLUMN cost_per_1k_input TO cost_per_million_input;
        ALTER TABLE model_configs RENAME COLUMN cost_per_1k_output TO cost_per_million_output;
        RAISE NOTICE 'Renamed cost columns from per_1k to per_million';
    ELSE
        RAISE NOTICE 'Cost columns already renamed or do not exist';
    END IF;
END $$;
