-- Migration 015: Update Groq model pricing to December 2025 rates
-- Source: https://groq.com/pricing (verified Dec 2, 2025)
-- This migration updates ALL pricing values (not just NULL/0)

-- GPT OSS 120B 128k: Was $1.20/$1.20, now $0.15/$0.60
UPDATE model_configs
SET cost_per_million_input = 0.15, cost_per_million_output = 0.60, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%gpt-oss-120b%'
  AND model_id NOT LIKE '%safeguard%';

-- GPT OSS 20B 128k: Was $0.30/$0.30, now $0.075/$0.30
UPDATE model_configs
SET cost_per_million_input = 0.075, cost_per_million_output = 0.30, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%gpt-oss-20b%'
  AND model_id NOT LIKE '%safeguard%';

-- GPT OSS Safeguard 20B: $0.075/$0.30
UPDATE model_configs
SET cost_per_million_input = 0.075, cost_per_million_output = 0.30, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%gpt-oss-safeguard%';

-- Llama 4 Maverick (17Bx128E): Was $0.15/$0.25, now $0.20/$0.60
UPDATE model_configs
SET cost_per_million_input = 0.20, cost_per_million_output = 0.60, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%llama-4-maverick%';

-- Llama 4 Scout (17Bx16E): $0.11/$0.34 (new model)
UPDATE model_configs
SET cost_per_million_input = 0.11, cost_per_million_output = 0.34, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%llama-4-scout%';

-- Kimi K2: Was $0.30/$0.50, now $1.00/$3.00
UPDATE model_configs
SET cost_per_million_input = 1.00, cost_per_million_output = 3.00, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%kimi-k2%';

-- Llama Guard 4 12B: $0.20/$0.20
UPDATE model_configs
SET cost_per_million_input = 0.20, cost_per_million_output = 0.20, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%llama-guard%';

-- Groq Compound: Was $2.00/$2.00, now $2.50/$6.00 (estimated with tool costs)
UPDATE model_configs
SET cost_per_million_input = 2.50, cost_per_million_output = 6.00, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%compound%'
  AND model_id NOT LIKE '%mini%';

-- Groq Compound Mini: Was $0.80/$0.80, now $1.00/$2.50 (estimated with tool costs)
UPDATE model_configs
SET cost_per_million_input = 1.00, cost_per_million_output = 2.50, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%compound-mini%';

-- Qwen3 32B 131k: $0.29/$0.59 (new model)
UPDATE model_configs
SET cost_per_million_input = 0.29, cost_per_million_output = 0.59, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%qwen3-32b%';

-- LLaMA 3.1 8B Instant: $0.05/$0.08 (unchanged, ensure consistency)
UPDATE model_configs
SET cost_per_million_input = 0.05, cost_per_million_output = 0.08, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%llama-3.1-8b-instant%';

-- LLaMA 3.3 70B Versatile: $0.59/$0.79 (unchanged, ensure consistency)
UPDATE model_configs
SET cost_per_million_input = 0.59, cost_per_million_output = 0.79, updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%llama-3.3-70b-versatile%';

-- Report updated pricing
SELECT model_id, name, cost_per_million_input as input_per_1m, cost_per_million_output as output_per_1m
FROM model_configs
WHERE provider = 'groq'
ORDER BY cost_per_million_input DESC, model_id;
