-- Migration 026: Fix NVIDIA model_ids to exact NVIDIA NIM API format
--
-- Verified against docs.api.nvidia.com and build.nvidia.com (December 2025)
--
-- Issues found:
-- 1. moonshot-ai/kimi-k2-instruct -> should be moonshotai/kimi-k2-instruct (no hyphen)
-- 2. mistralai/mistral-large-3-instruct -> model doesn't exist, should be mistralai/mistral-large
-- 3. deepseek-ai/deepseek-v3 -> model doesn't exist on NVIDIA, should be deepseek-ai/deepseek-v3.1
-- 4. qwen/qwen3-235b-a22b-fp8-instruct -> should be qwen/qwen3-235b-a22b (no fp8-instruct suffix)
--
-- Note: These are the model_id strings passed to NVIDIA's API, not the names shown to users

DO $$
BEGIN
    -- Fix Kimi K2: moonshot-ai -> moonshotai (NVIDIA uses no hyphen)
    UPDATE model_configs
    SET model_id = 'moonshotai/kimi-k2-instruct'
    WHERE model_id = 'moonshot-ai/kimi-k2-instruct' AND provider = 'nvidia';

    -- Fix Mistral Large 3: Use the correct model name from NVIDIA
    -- The full name is mistralai/mistral-large or mistralai/mistral-large-3-675b-instruct-2512
    UPDATE model_configs
    SET model_id = 'mistralai/mistral-large'
    WHERE model_id = 'mistralai/mistral-large-3-instruct' AND provider = 'nvidia';

    -- Fix DeepSeek V3: NVIDIA only has v3.1, not plain v3
    UPDATE model_configs
    SET model_id = 'deepseek-ai/deepseek-v3.1'
    WHERE model_id = 'deepseek-ai/deepseek-v3' AND provider = 'nvidia';

    -- Fix Qwen 3 235B: Remove fp8-instruct suffix
    UPDATE model_configs
    SET model_id = 'qwen/qwen3-235b-a22b'
    WHERE model_id = 'qwen/qwen3-235b-a22b-fp8-instruct' AND provider = 'nvidia';

    -- Also update tenant_model_configs to match
    UPDATE tenant_model_configs
    SET model_id = 'moonshotai/kimi-k2-instruct'
    WHERE model_id = 'moonshot-ai/kimi-k2-instruct';

    UPDATE tenant_model_configs
    SET model_id = 'mistralai/mistral-large'
    WHERE model_id = 'mistralai/mistral-large-3-instruct';

    UPDATE tenant_model_configs
    SET model_id = 'deepseek-ai/deepseek-v3.1'
    WHERE model_id = 'deepseek-ai/deepseek-v3';

    UPDATE tenant_model_configs
    SET model_id = 'qwen/qwen3-235b-a22b'
    WHERE model_id = 'qwen/qwen3-235b-a22b-fp8-instruct';

    RAISE NOTICE 'Migration 026: Fixed NVIDIA model_ids to match exact API format';
END $$;

-- Log migration completion
INSERT INTO system_versions (version, component, description, applied_at)
VALUES ('026', 'model_configs', 'Fixed NVIDIA model_ids to exact API format', NOW())
ON CONFLICT DO NOTHING;
