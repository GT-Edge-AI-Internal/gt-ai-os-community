-- Migration 010: Update Model Context Windows and Max Tokens
-- Ensures all models in model_configs have proper context_window and max_tokens set

-- Update models with missing context_window and max_tokens based on deployment configs
-- Reference: scripts/seed/groq-models.sql and actual Groq API specifications

DO $$
DECLARE
    updated_count INTEGER := 0;
BEGIN
    -- LLaMA 3.1 8B Instant
    UPDATE model_configs
    SET context_window = 131072,
        max_tokens = 32000,
        updated_at = NOW()
    WHERE model_id = 'llama-3.1-8b-instant'
    AND (context_window IS NULL OR max_tokens IS NULL);

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    IF updated_count > 0 THEN
        RAISE NOTICE 'Updated % records for llama-3.1-8b-instant', updated_count;
    END IF;

    -- LLaMA 3.3 70B Versatile
    UPDATE model_configs
    SET context_window = 131072,
        max_tokens = 32768,
        updated_at = NOW()
    WHERE model_id = 'llama-3.3-70b-versatile'
    AND (context_window IS NULL OR max_tokens IS NULL);

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    IF updated_count > 0 THEN
        RAISE NOTICE 'Updated % records for llama-3.3-70b-versatile', updated_count;
    END IF;

    -- Groq Compound
    UPDATE model_configs
    SET context_window = 131072,
        max_tokens = 8192,
        updated_at = NOW()
    WHERE model_id = 'groq/compound'
    AND (context_window IS NULL OR max_tokens IS NULL);

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    IF updated_count > 0 THEN
        RAISE NOTICE 'Updated % records for groq/compound', updated_count;
    END IF;

    -- Groq Compound Mini
    UPDATE model_configs
    SET context_window = 131072,
        max_tokens = 8192,
        updated_at = NOW()
    WHERE model_id = 'groq/compound-mini'
    AND (context_window IS NULL OR max_tokens IS NULL);

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    IF updated_count > 0 THEN
        RAISE NOTICE 'Updated % records for groq/compound-mini', updated_count;
    END IF;

    -- GPT OSS 120B
    UPDATE model_configs
    SET context_window = 131072,
        max_tokens = 65536,
        updated_at = NOW()
    WHERE model_id = 'openai/gpt-oss-120b'
    AND (context_window IS NULL OR max_tokens IS NULL);

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    IF updated_count > 0 THEN
        RAISE NOTICE 'Updated % records for openai/gpt-oss-120b', updated_count;
    END IF;

    -- GPT OSS 20B
    UPDATE model_configs
    SET context_window = 131072,
        max_tokens = 65536,
        updated_at = NOW()
    WHERE model_id = 'openai/gpt-oss-20b'
    AND (context_window IS NULL OR max_tokens IS NULL);

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    IF updated_count > 0 THEN
        RAISE NOTICE 'Updated % records for openai/gpt-oss-20b', updated_count;
    END IF;

    -- Meta LLaMA Guard 4 12B
    UPDATE model_configs
    SET context_window = 131072,
        max_tokens = 1024,
        updated_at = NOW()
    WHERE model_id = 'meta-llama/llama-guard-4-12b'
    AND (context_window IS NULL OR max_tokens IS NULL);

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    IF updated_count > 0 THEN
        RAISE NOTICE 'Updated % records for meta-llama/llama-guard-4-12b', updated_count;
    END IF;

    -- Meta LLaMA 4 Maverick 17B
    UPDATE model_configs
    SET context_window = 131072,
        max_tokens = 8192,
        updated_at = NOW()
    WHERE model_id = 'meta-llama/llama-4-maverick-17b-128e-instruct'
    AND (context_window IS NULL OR max_tokens IS NULL);

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    IF updated_count > 0 THEN
        RAISE NOTICE 'Updated % records for meta-llama/llama-4-maverick-17b-128e-instruct', updated_count;
    END IF;

    -- Moonshot AI Kimi K2 (checking for common variations)
    UPDATE model_configs
    SET context_window = 262144,
        max_tokens = 16384,
        updated_at = NOW()
    WHERE model_id IN ('moonshotai/kimi-k2-instruct-0905', 'kimi-k2-instruct-0905', 'moonshotai/kimi-k2')
    AND (context_window IS NULL OR max_tokens IS NULL);

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    IF updated_count > 0 THEN
        RAISE NOTICE 'Updated % records for moonshotai/kimi-k2-instruct-0905', updated_count;
    END IF;

    -- Whisper Large v3
    UPDATE model_configs
    SET context_window = 0,
        max_tokens = 0,
        updated_at = NOW()
    WHERE model_id = 'whisper-large-v3'
    AND (context_window IS NULL OR max_tokens IS NULL);

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    IF updated_count > 0 THEN
        RAISE NOTICE 'Updated % records for whisper-large-v3', updated_count;
    END IF;

    -- Whisper Large v3 Turbo
    UPDATE model_configs
    SET context_window = 0,
        max_tokens = 0,
        updated_at = NOW()
    WHERE model_id = 'whisper-large-v3-turbo'
    AND (context_window IS NULL OR max_tokens IS NULL);

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    IF updated_count > 0 THEN
        RAISE NOTICE 'Updated % records for whisper-large-v3-turbo', updated_count;
    END IF;

    RAISE NOTICE 'Migration 010 completed: Updated model context windows and max tokens';
END $$;

-- Display updated models
SELECT
    model_id,
    name,
    provider,
    model_type,
    context_window,
    max_tokens
FROM model_configs
WHERE provider = 'groq' OR model_id LIKE '%moonshot%' OR model_id LIKE '%kimi%'
ORDER BY model_id;
