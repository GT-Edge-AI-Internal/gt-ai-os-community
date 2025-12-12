-- Migration 016: Add is_compound column to model_configs
-- Required for Compound model pass-through pricing
-- Date: 2025-12-02

-- Add column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'model_configs' AND column_name = 'is_compound'
    ) THEN
        ALTER TABLE public.model_configs
        ADD COLUMN is_compound BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- Mark compound models
UPDATE public.model_configs
SET is_compound = true
WHERE model_id LIKE '%compound%'
  AND is_compound IS NOT TRUE;

-- Verify
SELECT model_id, is_compound FROM public.model_configs WHERE model_id LIKE '%compound%';
