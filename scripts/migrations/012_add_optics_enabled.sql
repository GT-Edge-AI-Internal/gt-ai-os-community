-- T008_optics_feature.sql
-- Add Optics cost tracking feature toggle for tenants
-- This enables the Optics tab in tenant observability for cost visibility

BEGIN;

-- Add optics_enabled column to tenants table in control panel database
-- This column controls whether the Optics cost tracking tab is visible for a tenant
ALTER TABLE public.tenants
ADD COLUMN IF NOT EXISTS optics_enabled BOOLEAN DEFAULT FALSE;

-- Add comment for documentation
COMMENT ON COLUMN public.tenants.optics_enabled IS
    'Enable Optics cost tracking tab in tenant observability dashboard';

-- Update existing test tenant to have optics enabled for demo purposes
UPDATE public.tenants
SET optics_enabled = TRUE
WHERE domain = 'test-company';

COMMIT;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE '=== T008 OPTICS FEATURE MIGRATION ===';
    RAISE NOTICE 'Added optics_enabled column to tenants table';
    RAISE NOTICE 'Default: FALSE (disabled)';
    RAISE NOTICE 'Test tenant (test-company): enabled';
    RAISE NOTICE '=====================================';
END $$;

-- Rollback (if needed):
-- BEGIN;
-- ALTER TABLE public.tenants DROP COLUMN IF EXISTS optics_enabled;
-- COMMIT;
