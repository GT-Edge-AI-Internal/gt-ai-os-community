-- GT 2.0 Test Data Creation Script
-- Creates test tenant and gtadmin@test.com user for development/testing
-- This is the ONLY place where the test user should be created

-- Enable logging
\set ON_ERROR_STOP on
\set ECHO all

-- Create test tenant
INSERT INTO public.tenants (
    uuid,
    name,
    domain,
    template,
    status,
    max_users,
    resource_limits,
    namespace,
    subdomain,
    optics_enabled,
    created_at,
    updated_at
) VALUES (
    'test-tenant-uuid-001',
    'GT AI OS',
    'test-company',
    'enterprise',
    'active',
    100,
    '{"cpu": "4000m", "memory": "8Gi", "storage": "50Gi"}',
    'gt-test',
    'test',
    false,  -- Optics disabled by default (enable via Control Panel)
    NOW(),
    NOW()
) ON CONFLICT (domain) DO UPDATE SET
    name = EXCLUDED.name,
    template = EXCLUDED.template,
    status = EXCLUDED.status,
    max_users = EXCLUDED.max_users,
    resource_limits = EXCLUDED.resource_limits,
    namespace = EXCLUDED.namespace,
    subdomain = EXCLUDED.subdomain,
    optics_enabled = EXCLUDED.optics_enabled,
    updated_at = NOW();

-- Create test super admin user
-- Password: Test@123
-- Hash generated with: python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('Test@123'))"
INSERT INTO public.users (
    uuid,
    email,
    full_name,
    hashed_password,
    user_type,
    tenant_id,
    capabilities,
    is_active,
    created_at,
    updated_at
) VALUES (
    'test-admin-uuid-001',
    'gtadmin@test.com',
    'GT Admin Test User',
    '$2b$12$otRZHfXz7GJUjA.ULeIc4ev612FSAK3tDcOYZdZCJ219j7WFNjFye',
    'super_admin',
    (SELECT id FROM public.tenants WHERE domain = 'test-company'),
    '[{"resource": "*", "actions": ["*"], "constraints": {}}]',
    true,
    NOW(),
    NOW()
) ON CONFLICT (email) DO UPDATE SET
    hashed_password = EXCLUDED.hashed_password,
    user_type = EXCLUDED.user_type,
    tenant_id = EXCLUDED.tenant_id,
    capabilities = EXCLUDED.capabilities,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- ===================================================================
-- MODEL CONFIGURATIONS
-- ===================================================================

-- Insert LLM model configurations
INSERT INTO public.model_configs (
    model_id, name, version, provider, model_type, endpoint,
    context_window, max_tokens, capabilities,
    cost_per_million_input, cost_per_million_output,
    is_active, health_status, request_count, error_count,
    success_rate, avg_latency_ms,
    tenant_restrictions, required_capabilities,
    created_at, updated_at
) VALUES
-- Groq Llama 3.1 8B Instant (fast, cheap)
('llama-3.1-8b-instant', 'Groq Llama 3.1 8b Instant', '1.0', 'groq', 'llm',
 'https://api.groq.com/openai/v1/chat/completions',
 131072, 131072,
 '{"reasoning": false, "function_calling": false, "vision": false, "audio": false, "streaming": false, "multilingual": false}'::json,
 0.05, 0.08, true, 'unknown', 0, 0, 100, 0,
 '{"global_access": true}'::json, '[]'::json,
 NOW(), NOW()),

-- Groq Llama 3.3 70B Versatile (best quality)
('llama-3.3-70b-versatile', 'Groq Llama 3.3 70b Versatile', '1.0', 'groq', 'llm',
 'https://api.groq.com/openai/v1/chat/completions',
 131072, 32768,
 '{"reasoning": false, "function_calling": false, "vision": false, "audio": false, "streaming": false, "multilingual": false}'::json,
 0.59, 0.79, true, 'unknown', 0, 0, 100, 0,
 '{"global_access": true}'::json, '[]'::json,
 NOW(), NOW()),

-- Groq Compound AI Search (blended: GPT-OSS-120B + Llama 4 Scout)
('groq/compound', 'Groq Compound AI Search', '1.0', 'groq', 'llm',
 'https://api.groq.com/openai/v1/chat/completions',
 131072, 8192,
 '{"reasoning": false, "function_calling": false, "vision": false, "audio": false, "streaming": false, "multilingual": false}'::json,
 0.13, 0.47, true, 'unknown', 0, 0, 100, 0,
 '{"global_access": true}'::json, '[]'::json,
 NOW(), NOW()),

-- Groq Compound Mini AI Search (blended: GPT-OSS-120B + Llama 3.3 70B)
('groq/compound-mini', 'Groq Compound Mini AI Search', '1.0', 'groq', 'llm',
 'https://api.groq.com/openai/v1/chat/completions',
 131072, 8192,
 '{"reasoning": false, "function_calling": false, "vision": false, "audio": false, "streaming": false, "multilingual": false}'::json,
 0.37, 0.695, true, 'unknown', 0, 0, 100, 0,
 '{"global_access": true}'::json, '[]'::json,
 NOW(), NOW()),

-- Groq OpenAI GPT OSS 120B (large OSS)
('openai/gpt-oss-120b', 'Groq Open AI GPT OSS 120b', '1.0', 'groq', 'llm',
 'https://api.groq.com/openai/v1/chat/completions',
 131072, 32000,
 '{"reasoning": false, "function_calling": false, "vision": false, "audio": false, "streaming": false, "multilingual": false}'::json,
 0.15, 0.60, true, 'unknown', 0, 0, 100, 0,
 '{"global_access": true}'::json, '[]'::json,
 NOW(), NOW()),

-- Groq OpenAI GPT OSS 20B (medium OSS)
('openai/gpt-oss-20b', 'Groq Open AI GPT OSS 20b', '1.0', 'groq', 'llm',
 'https://api.groq.com/openai/v1/chat/completions',
 131072, 65536,
 '{"reasoning": false, "function_calling": false, "vision": false, "audio": false, "streaming": false, "multilingual": false}'::json,
 0.075, 0.30, true, 'unknown', 0, 0, 100, 0,
 '{"global_access": true}'::json, '[]'::json,
 NOW(), NOW()),

-- Groq Meta Llama 4 Maverick 17B (17Bx128E MoE)
('meta-llama/llama-4-maverick-17b-128e-instruct', 'Groq Meta Llama 4 Maverick 17b 128 MOE Instruct', '1.0', 'groq', 'llm',
 'https://api.groq.com/openai/v1/chat/completions',
 131072, 8192,
 '{"reasoning": false, "function_calling": false, "vision": false, "audio": false, "streaming": false, "multilingual": false}'::json,
 0.20, 0.60, true, 'unknown', 0, 0, 100, 0,
 '{"global_access": true}'::json, '[]'::json,
 NOW(), NOW()),

-- Moonshot AI Kimi K2 (1T parameters, 256k context)
('moonshotai/kimi-k2-instruct-0905', 'Moonshot AI Kimi K2 instruct 0905', '1.0', 'groq', 'llm',
 'https://api.groq.com/openai/v1/chat/completions',
 262144, 16384,
 '{"reasoning": false, "function_calling": false, "vision": false, "audio": false, "streaming": false, "multilingual": false}'::json,
 1.00, 3.00, true, 'unknown', 0, 0, 100, 0,
 '{"global_access": true}'::json, '[]'::json,
 NOW(), NOW()),

-- Groq Llama Guard 4 12B (safety/moderation model)
('meta-llama/llama-guard-4-12b', 'Groq Llama Guard 4 12B', '1.0', 'groq', 'llm',
 'https://api.groq.com/openai/v1/chat/completions',
 131072, 8192,
 '{"reasoning": false, "function_calling": false, "vision": false, "audio": false, "streaming": false, "multilingual": false}'::json,
 0.20, 0.20, true, 'unknown', 0, 0, 100, 0,
 '{"global_access": true}'::json, '[]'::json,
 NOW(), NOW()),

-- BGE-M3 Multilingual Embedding Model (embeddings, input only)
('BAAI/bge-m3', 'BGE-M3 Multilingual Embedding', '1.0', 'external', 'embedding',
 'http://gentwo-vllm-embeddings:8000/v1/embeddings',
 8192, 8193,
 '{"multilingual": true, "reasoning": false, "function_calling": false, "vision": false, "audio": false, "streaming": false}'::json,
 0.01, 0.00, true, 'unknown', 0, 0, 100, 0,
 '{"global_access": true}'::json, '[]'::json,
 NOW(), NOW())

ON CONFLICT (model_id) DO UPDATE SET
    name = EXCLUDED.name,
    version = EXCLUDED.version,
    provider = EXCLUDED.provider,
    model_type = EXCLUDED.model_type,
    endpoint = EXCLUDED.endpoint,
    context_window = EXCLUDED.context_window,
    max_tokens = EXCLUDED.max_tokens,
    capabilities = EXCLUDED.capabilities,
    cost_per_million_input = EXCLUDED.cost_per_million_input,
    cost_per_million_output = EXCLUDED.cost_per_million_output,
    is_active = EXCLUDED.is_active,
    tenant_restrictions = EXCLUDED.tenant_restrictions,
    required_capabilities = EXCLUDED.required_capabilities,
    updated_at = NOW();

-- ===================================================================
-- TENANT MODEL ACCESS
-- ===================================================================

-- Enable all models for test tenant with 10,000 requests/min rate limit
INSERT INTO public.tenant_model_configs (
    tenant_id, model_id, is_enabled, tenant_capabilities,
    rate_limits, usage_constraints, priority,
    created_at, updated_at
) VALUES
((SELECT id FROM public.tenants WHERE domain = 'test-company'), 'llama-3.1-8b-instant', true, '{}'::json,
 '{"requests_per_minute": 10000}'::json, '{}'::json, 5, NOW(), NOW()),

((SELECT id FROM public.tenants WHERE domain = 'test-company'), 'llama-3.3-70b-versatile', true, '{}'::json,
 '{"requests_per_minute": 10000}'::json, '{}'::json, 5, NOW(), NOW()),

((SELECT id FROM public.tenants WHERE domain = 'test-company'), 'groq/compound', true, '{}'::json,
 '{"requests_per_minute": 10000}'::json, '{}'::json, 5, NOW(), NOW()),

((SELECT id FROM public.tenants WHERE domain = 'test-company'), 'groq/compound-mini', true, '{}'::json,
 '{"requests_per_minute": 10000}'::json, '{}'::json, 5, NOW(), NOW()),

((SELECT id FROM public.tenants WHERE domain = 'test-company'), 'openai/gpt-oss-120b', true, '{}'::json,
 '{"requests_per_minute": 10000}'::json, '{}'::json, 5, NOW(), NOW()),

((SELECT id FROM public.tenants WHERE domain = 'test-company'), 'openai/gpt-oss-20b', true, '{}'::json,
 '{"requests_per_minute": 10000}'::json, '{}'::json, 5, NOW(), NOW()),

((SELECT id FROM public.tenants WHERE domain = 'test-company'), 'meta-llama/llama-4-maverick-17b-128e-instruct', true, '{}'::json,
 '{"requests_per_minute": 10000}'::json, '{}'::json, 5, NOW(), NOW()),

((SELECT id FROM public.tenants WHERE domain = 'test-company'), 'moonshotai/kimi-k2-instruct-0905', true, '{}'::json,
 '{"requests_per_minute": 10000}'::json, '{}'::json, 5, NOW(), NOW()),

((SELECT id FROM public.tenants WHERE domain = 'test-company'), 'meta-llama/llama-guard-4-12b', true, '{}'::json,
 '{"requests_per_minute": 10000}'::json, '{}'::json, 5, NOW(), NOW()),

((SELECT id FROM public.tenants WHERE domain = 'test-company'), 'BAAI/bge-m3', true, '{}'::json,
 '{"requests_per_minute": 10000}'::json, '{}'::json, 5, NOW(), NOW())

ON CONFLICT (tenant_id, model_id) DO UPDATE SET
    is_enabled = EXCLUDED.is_enabled,
    rate_limits = EXCLUDED.rate_limits,
    updated_at = NOW();

-- Log completion
DO $$
DECLARE
    tenant_count INTEGER;
    user_count INTEGER;
    model_count INTEGER;
    tenant_model_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO tenant_count FROM public.tenants WHERE domain = 'test-company';
    SELECT COUNT(*) INTO user_count FROM public.users WHERE email = 'gtadmin@test.com';
    SELECT COUNT(*) INTO model_count FROM public.model_configs;
    SELECT COUNT(*) INTO tenant_model_count FROM public.tenant_model_configs WHERE tenant_id = (SELECT id FROM public.tenants WHERE domain = 'test-company');

    RAISE NOTICE '=== GT 2.0 TEST DATA CREATION ===';
    RAISE NOTICE 'Test tenant created: % (domain: test-company)', tenant_count;
    RAISE NOTICE 'Test user created: % (email: gtadmin@test.com)', user_count;
    RAISE NOTICE 'Login credentials:';
    RAISE NOTICE '  Email: gtadmin@test.com';
    RAISE NOTICE '  Password: Test@123';
    RAISE NOTICE '';
    RAISE NOTICE 'LLM Models configured: %', model_count;
    RAISE NOTICE 'Tenant model access enabled: %', tenant_model_count;
    RAISE NOTICE 'Rate limit: 10,000 requests/minute per model';
    RAISE NOTICE '====================================';
END $$;
