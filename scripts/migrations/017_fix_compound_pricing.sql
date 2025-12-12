-- Migration 017: Fix Compound model pricing with correct blended rates
-- Source: https://groq.com/pricing (Dec 2025) + actual API response analysis
--
-- Compound uses GPT-OSS-120B ($0.15/$0.60) + Llama 4 Scout ($0.11/$0.34)
-- Blended 50/50: ($0.15+$0.11)/2 = $0.13 input, ($0.60+$0.34)/2 = $0.47 output
--
-- Compound Mini uses GPT-OSS-120B ($0.15/$0.60) + Llama 3.3 70B ($0.59/$0.79)
-- Blended 50/50: ($0.15+$0.59)/2 = $0.37 input, ($0.60+$0.79)/2 = $0.695 output

-- Fix Compound pricing (was incorrectly set to $2.50/$6.00)
UPDATE model_configs
SET cost_per_million_input = 0.13,
    cost_per_million_output = 0.47,
    updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%compound%'
  AND model_id NOT LIKE '%mini%';

-- Fix Compound Mini pricing (was incorrectly set to $1.00/$2.50)
UPDATE model_configs
SET cost_per_million_input = 0.37,
    cost_per_million_output = 0.695,
    updated_at = NOW()
WHERE provider = 'groq'
  AND model_id LIKE '%compound-mini%';

-- Report updated pricing
SELECT model_id, name, cost_per_million_input as input_per_1m, cost_per_million_output as output_per_1m
FROM model_configs
WHERE provider = 'groq' AND model_id LIKE '%compound%'
ORDER BY model_id;
