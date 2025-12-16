-- Migration 028: Fix Groq Model Max Tokens
-- Corrects max_tokens for models that had incorrect values in test data

DO $$
DECLARE
    updated_count INTEGER := 0;
BEGIN
    -- LLaMA 3.1 8B Instant: max_tokens should be 32000 (was incorrectly 131072)
    UPDATE model_configs
    SET max_tokens = 32000,
        updated_at = NOW()
    WHERE model_id = 'llama-3.1-8b-instant'
    AND max_tokens != 32000;

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    IF updated_count > 0 THEN
        RAISE NOTICE 'Updated % records for llama-3.1-8b-instant max_tokens -> 32000', updated_count;
    END IF;

    -- LLaMA Guard 4 12B: max_tokens should be 1024 (was incorrectly 8192 in test data)
    UPDATE model_configs
    SET max_tokens = 1024,
        updated_at = NOW()
    WHERE model_id = 'meta-llama/llama-guard-4-12b'
    AND max_tokens != 1024;

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    IF updated_count > 0 THEN
        RAISE NOTICE 'Updated % records for llama-guard-4-12b max_tokens -> 1024', updated_count;
    END IF;

    RAISE NOTICE 'Migration 028 complete: Groq max_tokens corrected';
END $$;
