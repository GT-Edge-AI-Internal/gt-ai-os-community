-- Migration 025: Fix NVIDIA model names to match API format
--
-- Problem: Model names stored with incorrect format (e.g., nvidia/meta-llama-3.1-8b-instruct)
-- Solution: Update to match NVIDIA NIM API expected format (e.g., meta/llama-3.1-8b-instruct)
--
-- NVIDIA NIM API model naming:
-- - Models from Meta: meta/llama-3.1-8b-instruct (NOT nvidia/meta-llama-*)
-- - Models from NVIDIA: nvidia/llama-3.1-nemotron-70b-instruct
-- - Models from Mistral: mistralai/mistral-large-3-instruct
-- - Models from DeepSeek: deepseek-ai/deepseek-v3
-- - Models from OpenAI-compatible: openai/gpt-oss-120b (already correct in groq provider)

-- Idempotency: Only update if old format exists
DO $$
BEGIN
    -- Fix Meta Llama models (remove nvidia/ prefix for meta models)
    UPDATE model_configs
    SET model_id = 'meta/llama-3.1-8b-instruct'
    WHERE model_id = 'nvidia/meta-llama-3.1-8b-instruct' AND provider = 'nvidia';

    UPDATE model_configs
    SET model_id = 'meta/llama-3.1-70b-instruct'
    WHERE model_id = 'nvidia/meta-llama-3.1-70b-instruct' AND provider = 'nvidia';

    UPDATE model_configs
    SET model_id = 'meta/llama-3.1-405b-instruct'
    WHERE model_id = 'nvidia/meta-llama-3.1-405b-instruct' AND provider = 'nvidia';

    UPDATE model_configs
    SET model_id = 'meta/llama-3.3-70b-instruct'
    WHERE model_id = 'nvidia/meta-llama-3.3-70b-instruct' AND provider = 'nvidia';

    -- Fix DeepSeek models
    UPDATE model_configs
    SET model_id = 'deepseek-ai/deepseek-v3'
    WHERE model_id = 'nvidia/deepseek-ai-deepseek-v3' AND provider = 'nvidia';

    UPDATE model_configs
    SET model_id = 'deepseek-ai/deepseek-r1'
    WHERE model_id = 'nvidia/deepseek-ai-deepseek-r1' AND provider = 'nvidia';

    -- Fix Mistral models
    UPDATE model_configs
    SET model_id = 'mistralai/mistral-large-3-instruct'
    WHERE model_id = 'nvidia/mistralai-mistral-large-3-instruct' AND provider = 'nvidia';

    -- Fix Moonshot/Kimi models
    UPDATE model_configs
    SET model_id = 'moonshot-ai/kimi-k2-instruct'
    WHERE model_id = 'nvidia/moonshot-ai-kimi-k2-instruct' AND provider = 'nvidia';

    -- Fix Qwen models
    UPDATE model_configs
    SET model_id = 'qwen/qwen3-235b-a22b-fp8-instruct'
    WHERE model_id = 'nvidia/qwen-qwen3-235b-a22b-fp8-instruct' AND provider = 'nvidia';

    -- Fix OpenAI-compatible models (for NVIDIA provider)
    UPDATE model_configs
    SET model_id = 'openai/gpt-oss-120b'
    WHERE model_id = 'nvidia/openai-gpt-oss-120b' AND provider = 'nvidia';

    UPDATE model_configs
    SET model_id = 'openai/gpt-oss-20b'
    WHERE model_id = 'nvidia/openai-gpt-oss-20b' AND provider = 'nvidia';

    -- Also update tenant_model_configs to match (if they reference old model_ids)
    UPDATE tenant_model_configs
    SET model_id = 'meta/llama-3.1-8b-instruct'
    WHERE model_id = 'nvidia/meta-llama-3.1-8b-instruct';

    UPDATE tenant_model_configs
    SET model_id = 'meta/llama-3.1-70b-instruct'
    WHERE model_id = 'nvidia/meta-llama-3.1-70b-instruct';

    UPDATE tenant_model_configs
    SET model_id = 'meta/llama-3.1-405b-instruct'
    WHERE model_id = 'nvidia/meta-llama-3.1-405b-instruct';

    UPDATE tenant_model_configs
    SET model_id = 'meta/llama-3.3-70b-instruct'
    WHERE model_id = 'nvidia/meta-llama-3.3-70b-instruct';

    UPDATE tenant_model_configs
    SET model_id = 'deepseek-ai/deepseek-v3'
    WHERE model_id = 'nvidia/deepseek-ai-deepseek-v3';

    UPDATE tenant_model_configs
    SET model_id = 'deepseek-ai/deepseek-r1'
    WHERE model_id = 'nvidia/deepseek-ai-deepseek-r1';

    UPDATE tenant_model_configs
    SET model_id = 'mistralai/mistral-large-3-instruct'
    WHERE model_id = 'nvidia/mistralai-mistral-large-3-instruct';

    UPDATE tenant_model_configs
    SET model_id = 'moonshot-ai/kimi-k2-instruct'
    WHERE model_id = 'nvidia/moonshot-ai-kimi-k2-instruct';

    UPDATE tenant_model_configs
    SET model_id = 'qwen/qwen3-235b-a22b-fp8-instruct'
    WHERE model_id = 'nvidia/qwen-qwen3-235b-a22b-fp8-instruct';

    UPDATE tenant_model_configs
    SET model_id = 'openai/gpt-oss-120b'
    WHERE model_id = 'nvidia/openai-gpt-oss-120b';

    UPDATE tenant_model_configs
    SET model_id = 'openai/gpt-oss-20b'
    WHERE model_id = 'nvidia/openai-gpt-oss-20b';

    RAISE NOTICE 'Migration 025: Fixed NVIDIA model names to match API format';
END $$;

-- Log migration completion
INSERT INTO system_versions (version, component, description, applied_at)
VALUES ('025', 'model_configs', 'Fixed NVIDIA model names to match API format', NOW())
ON CONFLICT DO NOTHING;
