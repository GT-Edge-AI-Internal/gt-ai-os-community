-- Migration 014: Backfill missing Groq model pricing
-- Updates models with NULL or 0 pricing to use standard Groq rates
-- Prices sourced from https://groq.com/pricing (verified Dec 2, 2025)
-- Idempotent - only updates rows that need fixing

-- Groq Compound (estimated: includes underlying model + tool costs)
UPDATE model_configs
SET cost_per_million_input = 2.50, cost_per_million_output = 6.00, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%compound'
  AND model_id NOT LIKE '%mini%'
  AND (cost_per_million_input IS NULL OR cost_per_million_input = 0
       OR cost_per_million_output IS NULL OR cost_per_million_output = 0);

-- Groq Compound Mini (estimated: includes underlying model + tool costs)
UPDATE model_configs
SET cost_per_million_input = 1.00, cost_per_million_output = 2.50, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%compound-mini%'
  AND (cost_per_million_input IS NULL OR cost_per_million_input = 0
       OR cost_per_million_output IS NULL OR cost_per_million_output = 0);

-- LLaMA 3.1 8B Instant
UPDATE model_configs
SET cost_per_million_input = 0.05, cost_per_million_output = 0.08, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%llama-3.1-8b-instant%'
  AND (cost_per_million_input IS NULL OR cost_per_million_input = 0
       OR cost_per_million_output IS NULL OR cost_per_million_output = 0);

-- LLaMA 3.3 70B Versatile
UPDATE model_configs
SET cost_per_million_input = 0.59, cost_per_million_output = 0.79, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%llama-3.3-70b-versatile%'
  AND (cost_per_million_input IS NULL OR cost_per_million_input = 0
       OR cost_per_million_output IS NULL OR cost_per_million_output = 0);

-- Meta Llama 4 Maverick 17B (17Bx128E MoE)
UPDATE model_configs
SET cost_per_million_input = 0.20, cost_per_million_output = 0.60, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%llama-4-maverick%'
  AND (cost_per_million_input IS NULL OR cost_per_million_input = 0
       OR cost_per_million_output IS NULL OR cost_per_million_output = 0);

-- Meta Llama 4 Scout 17B (17Bx16E MoE)
UPDATE model_configs
SET cost_per_million_input = 0.11, cost_per_million_output = 0.34, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%llama-4-scout%'
  AND (cost_per_million_input IS NULL OR cost_per_million_input = 0
       OR cost_per_million_output IS NULL OR cost_per_million_output = 0);

-- LLaMA Guard 4 12B
UPDATE model_configs
SET cost_per_million_input = 0.20, cost_per_million_output = 0.20, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%llama-guard%'
  AND (cost_per_million_input IS NULL OR cost_per_million_input = 0
       OR cost_per_million_output IS NULL OR cost_per_million_output = 0);

-- Moonshot AI Kimi K2 (1T params, 256k context)
UPDATE model_configs
SET cost_per_million_input = 1.00, cost_per_million_output = 3.00, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%kimi-k2%'
  AND (cost_per_million_input IS NULL OR cost_per_million_input = 0
       OR cost_per_million_output IS NULL OR cost_per_million_output = 0);

-- OpenAI GPT OSS 120B 128k
UPDATE model_configs
SET cost_per_million_input = 0.15, cost_per_million_output = 0.60, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%gpt-oss-120b%'
  AND (cost_per_million_input IS NULL OR cost_per_million_input = 0
       OR cost_per_million_output IS NULL OR cost_per_million_output = 0);

-- OpenAI GPT OSS 20B 128k
UPDATE model_configs
SET cost_per_million_input = 0.075, cost_per_million_output = 0.30, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%gpt-oss-20b%'
  AND model_id NOT LIKE '%safeguard%'
  AND (cost_per_million_input IS NULL OR cost_per_million_input = 0
       OR cost_per_million_output IS NULL OR cost_per_million_output = 0);

-- OpenAI GPT OSS Safeguard 20B
UPDATE model_configs
SET cost_per_million_input = 0.075, cost_per_million_output = 0.30, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%gpt-oss-safeguard%'
  AND (cost_per_million_input IS NULL OR cost_per_million_input = 0
       OR cost_per_million_output IS NULL OR cost_per_million_output = 0);

-- Qwen3 32B 131k
UPDATE model_configs
SET cost_per_million_input = 0.29, cost_per_million_output = 0.59, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%qwen3-32b%'
  AND (cost_per_million_input IS NULL OR cost_per_million_input = 0
       OR cost_per_million_output IS NULL OR cost_per_million_output = 0);

-- Report results
SELECT model_id, name, cost_per_million_input, cost_per_million_output
FROM model_configs
WHERE provider = 'groq'
ORDER BY model_id;
