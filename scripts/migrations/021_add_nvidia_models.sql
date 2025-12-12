-- Migration: 021_add_nvidia_models.sql
-- Description: Add NVIDIA NIM models to model_configs table
-- Date: 2025-12-08
-- Issue: #266 - Add NVIDIA API endpoint support
-- Reference: https://build.nvidia.com/models

-- NVIDIA NIM Models (build.nvidia.com)
-- Pricing: Estimated based on third-party providers and model size (Dec 2025)
-- Models selected: SOTA reasoning, coding, and general-purpose LLMs

INSERT INTO model_configs (
    model_id,
    name,
    version,
    provider,
    model_type,
    endpoint,
    context_window,
    max_tokens,
    cost_per_million_input,
    cost_per_million_output,
    capabilities,
    is_active,
    description,
    created_at,
    updated_at,
    request_count,
    error_count,
    success_rate,
    avg_latency_ms,
    health_status
)
VALUES
    -- ==========================================
    -- NVIDIA Llama Nemotron Family (Flagship)
    -- ==========================================

    -- Llama 3.3 Nemotron Super 49B v1 - Latest flagship reasoning model
    (
        'nvidia/llama-3.3-nemotron-super-49b-v1',
        'NVIDIA Llama 3.3 Nemotron Super 49B',
        '1.0',
        'nvidia',
        'llm',
        'https://integrate.api.nvidia.com/v1/chat/completions',
        131072,
        8192,
        0.5,
        1.5,
        '{"streaming": true, "function_calling": true, "reasoning": true}',
        true,
        'NVIDIA flagship reasoning model - best accuracy/throughput on single GPU',
        NOW(),
        NOW(),
        0,
        0,
        100.0,
        0,
        'unknown'
    ),
    -- Llama 3.1 Nemotron Ultra 253B - Maximum accuracy
    (
        'nvidia/llama-3.1-nemotron-ultra-253b-v1',
        'NVIDIA Llama 3.1 Nemotron Ultra 253B',
        '1.0',
        'nvidia',
        'llm',
        'https://integrate.api.nvidia.com/v1/chat/completions',
        131072,
        8192,
        0.6,
        1.8,
        '{"streaming": true, "function_calling": true, "reasoning": true}',
        true,
        'Maximum agentic accuracy for scientific reasoning, math, and coding',
        NOW(),
        NOW(),
        0,
        0,
        100.0,
        0,
        'unknown'
    ),
    -- Nemotron Nano 8B - Edge/PC deployment
    (
        'nvidia/llama-3.1-nemotron-nano-8b-v1',
        'NVIDIA Llama 3.1 Nemotron Nano 8B',
        '1.0',
        'nvidia',
        'llm',
        'https://integrate.api.nvidia.com/v1/chat/completions',
        131072,
        8192,
        0.02,
        0.06,
        '{"streaming": true, "function_calling": true}',
        true,
        'Cost-effective model optimized for edge devices and low latency',
        NOW(),
        NOW(),
        0,
        0,
        100.0,
        0,
        'unknown'
    ),

    -- ==========================================
    -- Meta Llama 3.3 (via NVIDIA NIM)
    -- ==========================================

    -- Llama 3.3 70B Instruct - Latest Llama
    (
        'nvidia/meta-llama-3.3-70b-instruct',
        'NVIDIA Meta Llama 3.3 70B Instruct',
        '1.0',
        'nvidia',
        'llm',
        'https://integrate.api.nvidia.com/v1/chat/completions',
        128000,
        4096,
        0.13,
        0.4,
        '{"streaming": true, "function_calling": true}',
        true,
        'Latest Meta Llama 3.3 - excellent for instruction following',
        NOW(),
        NOW(),
        0,
        0,
        100.0,
        0,
        'unknown'
    ),

    -- ==========================================
    -- DeepSeek Models (via NVIDIA NIM)
    -- ==========================================

    -- DeepSeek V3 - Hybrid inference with Think/Non-Think modes
    (
        'nvidia/deepseek-ai-deepseek-v3',
        'NVIDIA DeepSeek V3',
        '1.0',
        'nvidia',
        'llm',
        'https://integrate.api.nvidia.com/v1/chat/completions',
        128000,
        8192,
        0.5,
        1.5,
        '{"streaming": true, "function_calling": true, "reasoning": true}',
        true,
        'Hybrid LLM with Think/Non-Think modes, 128K context, strong tool use',
        NOW(),
        NOW(),
        0,
        0,
        100.0,
        0,
        'unknown'
    ),
    -- DeepSeek R1 - Enhanced reasoning
    (
        'nvidia/deepseek-ai-deepseek-r1',
        'NVIDIA DeepSeek R1',
        '1.0',
        'nvidia',
        'llm',
        'https://integrate.api.nvidia.com/v1/chat/completions',
        128000,
        8192,
        0.6,
        2.4,
        '{"streaming": true, "function_calling": true, "reasoning": true}',
        true,
        'Enhanced reasoning model - reduced hallucination, strong math/coding',
        NOW(),
        NOW(),
        0,
        0,
        100.0,
        0,
        'unknown'
    ),

    -- ==========================================
    -- Kimi K2 (Moonshot AI via NVIDIA NIM)
    -- ==========================================

    (
        'nvidia/moonshot-ai-kimi-k2-instruct',
        'NVIDIA Kimi K2 Instruct',
        '1.0',
        'nvidia',
        'llm',
        'https://integrate.api.nvidia.com/v1/chat/completions',
        128000,
        8192,
        0.4,
        1.2,
        '{"streaming": true, "function_calling": true, "reasoning": true}',
        true,
        'Long context window with enhanced reasoning capabilities',
        NOW(),
        NOW(),
        0,
        0,
        100.0,
        0,
        'unknown'
    ),

    -- ==========================================
    -- Mistral Models (via NVIDIA NIM)
    -- ==========================================

    -- Mistral Large 3 - State-of-the-art MoE
    (
        'nvidia/mistralai-mistral-large-3-instruct',
        'NVIDIA Mistral Large 3 Instruct',
        '1.0',
        'nvidia',
        'llm',
        'https://integrate.api.nvidia.com/v1/chat/completions',
        128000,
        8192,
        0.8,
        2.4,
        '{"streaming": true, "function_calling": true}',
        true,
        'State-of-the-art general purpose MoE model',
        NOW(),
        NOW(),
        0,
        0,
        100.0,
        0,
        'unknown'
    ),

    -- ==========================================
    -- Qwen Models (via NVIDIA NIM)
    -- ==========================================

    -- Qwen 3 - Ultra-long context (131K with YaRN extension)
    (
        'nvidia/qwen-qwen3-235b-a22b-fp8-instruct',
        'NVIDIA Qwen 3 235B Instruct',
        '1.0',
        'nvidia',
        'llm',
        'https://integrate.api.nvidia.com/v1/chat/completions',
        131072,
        8192,
        0.7,
        2.1,
        '{"streaming": true, "function_calling": true}',
        true,
        'Ultra-long context AI with strong multilingual support',
        NOW(),
        NOW(),
        0,
        0,
        100.0,
        0,
        'unknown'
    ),

    -- ==========================================
    -- Meta Llama 3.1 (via NVIDIA NIM)
    -- ==========================================

    -- Llama 3.1 405B - Largest open model
    (
        'nvidia/meta-llama-3.1-405b-instruct',
        'NVIDIA Meta Llama 3.1 405B Instruct',
        '1.0',
        'nvidia',
        'llm',
        'https://integrate.api.nvidia.com/v1/chat/completions',
        128000,
        4096,
        1.0,
        3.0,
        '{"streaming": true, "function_calling": true}',
        true,
        'Largest open-source LLM - exceptional quality across all tasks',
        NOW(),
        NOW(),
        0,
        0,
        100.0,
        0,
        'unknown'
    ),
    -- Llama 3.1 70B
    (
        'nvidia/meta-llama-3.1-70b-instruct',
        'NVIDIA Meta Llama 3.1 70B Instruct',
        '1.0',
        'nvidia',
        'llm',
        'https://integrate.api.nvidia.com/v1/chat/completions',
        128000,
        4096,
        0.13,
        0.4,
        '{"streaming": true, "function_calling": true}',
        true,
        'Excellent balance of quality and speed',
        NOW(),
        NOW(),
        0,
        0,
        100.0,
        0,
        'unknown'
    ),
    -- Llama 3.1 8B - Fast and efficient
    (
        'nvidia/meta-llama-3.1-8b-instruct',
        'NVIDIA Meta Llama 3.1 8B Instruct',
        '1.0',
        'nvidia',
        'llm',
        'https://integrate.api.nvidia.com/v1/chat/completions',
        128000,
        4096,
        0.02,
        0.06,
        '{"streaming": true, "function_calling": true}',
        true,
        'Fast and cost-effective for simpler tasks',
        NOW(),
        NOW(),
        0,
        0,
        100.0,
        0,
        'unknown'
    ),

    -- ==========================================
    -- OpenAI GPT-OSS Models (via NVIDIA NIM)
    -- Released August 2025 - Apache 2.0 License
    -- ==========================================

    -- GPT-OSS 120B via NVIDIA NIM - Production flagship, MoE architecture (117B params, 5.7B active)
    (
        'nvidia/openai-gpt-oss-120b',
        'NVIDIA OpenAI GPT-OSS 120B',
        '1.0',
        'nvidia',
        'llm',
        'https://integrate.api.nvidia.com/v1/chat/completions',
        128000,
        8192,
        0.7,
        2.1,
        '{"streaming": true, "function_calling": true, "reasoning": true, "tool_use": true}',
        true,
        'OpenAI flagship open model via NVIDIA NIM - production-grade reasoning, fits single H100 GPU',
        NOW(),
        NOW(),
        0,
        0,
        100.0,
        0,
        'unknown'
    ),
    -- GPT-OSS 20B via NVIDIA NIM - Lightweight MoE for edge/local (21B params, 4B active)
    (
        'nvidia/openai-gpt-oss-20b',
        'NVIDIA OpenAI GPT-OSS 20B',
        '1.0',
        'nvidia',
        'llm',
        'https://integrate.api.nvidia.com/v1/chat/completions',
        128000,
        8192,
        0.15,
        0.45,
        '{"streaming": true, "function_calling": true, "reasoning": true, "tool_use": true}',
        true,
        'OpenAI lightweight open model via NVIDIA NIM - low latency, runs in 16GB VRAM',
        NOW(),
        NOW(),
        0,
        0,
        100.0,
        0,
        'unknown'
    )

ON CONFLICT (model_id) DO UPDATE SET
    name = EXCLUDED.name,
    version = EXCLUDED.version,
    provider = EXCLUDED.provider,
    endpoint = EXCLUDED.endpoint,
    context_window = EXCLUDED.context_window,
    max_tokens = EXCLUDED.max_tokens,
    cost_per_million_input = EXCLUDED.cost_per_million_input,
    cost_per_million_output = EXCLUDED.cost_per_million_output,
    capabilities = EXCLUDED.capabilities,
    is_active = EXCLUDED.is_active,
    description = EXCLUDED.description,
    updated_at = NOW();

-- Assign NVIDIA models to all existing tenants with 1000 RPM rate limits
-- Note: model_config_id (UUID) is the foreign key, model_id kept for convenience
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
ON CONFLICT (tenant_id, model_config_id) DO UPDATE SET
    rate_limits = EXCLUDED.rate_limits;

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Migration 021: Added NVIDIA NIM models (Nemotron, Llama 3.3, DeepSeek, Kimi K2, Mistral, Qwen, OpenAI GPT-OSS) to model_configs and assigned to tenants';
END $$;
