-- Migration: 027_assign_nvidia_models_to_tenants.sql
-- Description: Ensure NVIDIA models are assigned to all tenants (fix for partial 021 migration)
-- Date: 2025-12-08
-- Issue: Deploy.sh updates add models but don't assign to existing tenants

-- Assign NVIDIA models to all existing tenants with 1000 RPM rate limits
-- This is idempotent - ON CONFLICT DO NOTHING means it won't duplicate
INSERT INTO tenant_model_configs (tenant_id, model_config_id, model_id, is_enabled, priority, rate_limits, created_at, updated_at)
SELECT
    t.id,
    m.id,        -- UUID foreign key (auto-generated in model_configs)
    m.model_id,  -- String identifier (kept for easier queries)
    true,
    5,
    '{"max_requests_per_hour": 1000, "max_tokens_per_request": 4000, "concurrent_requests": 5, "max_cost_per_hour": 10.0, "requests_per_minute": 1000, "tokens_per_minute": 100000, "max_concurrent": 10}'::json,
    NOW(),
    NOW()
FROM tenants t
CROSS JOIN model_configs m
WHERE m.provider = 'nvidia'
  AND m.is_active = true
ON CONFLICT (tenant_id, model_config_id) DO NOTHING;

-- Log migration completion
DO $$
DECLARE
    assigned_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO assigned_count
    FROM tenant_model_configs tmc
    JOIN model_configs mc ON mc.id = tmc.model_config_id
    WHERE mc.provider = 'nvidia';

    RAISE NOTICE 'Migration 027: Ensured NVIDIA models are assigned to all tenants (% total assignments)', assigned_count;
END $$;
