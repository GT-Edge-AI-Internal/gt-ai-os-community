#!/bin/bash
# GT 2.0 - Setup Model Configurations
# Enables tenant model configs for fresh deployments

set -e

echo "🚀 GT 2.0 Model Configuration Setup"
echo "==================================="

# Check if databases are ready
echo "⏳ Waiting for databases..."
sleep 5

# Setup model configs in control panel
echo "📦 Setting up model configurations..."

docker exec gentwo-controlpanel-postgres psql -U postgres -d gt2_admin << 'EOF'
-- Clear existing demo configs for tenant 1
DELETE FROM tenant_model_configs WHERE tenant_id = 1;

-- Insert your current model configs
INSERT INTO tenant_model_configs (tenant_id, model_id, is_enabled, rate_limits, usage_constraints, priority, created_at, updated_at) VALUES
(1, 'groq/compound', true, '{"max_requests_per_hour": 1000, "max_tokens_per_request": 4000, "concurrent_requests": 5, "max_cost_per_hour": 10.0, "requests_per_minute": 100, "tokens_per_minute": 100000, "max_concurrent": 10}', '{}', 5, NOW(), NOW()),
(1, 'llama-3.1-8b-instant', true, '{"max_requests_per_hour": 1000, "max_tokens_per_request": 4000, "concurrent_requests": 5, "max_cost_per_hour": 10.0, "requests_per_minute": 100, "tokens_per_minute": 100000, "max_concurrent": 10}', '{}', 5, NOW(), NOW()),
(1, 'moonshotai/kimi-k2-instruct-0905', true, '{"max_requests_per_hour": 1000, "max_tokens_per_request": 4000, "concurrent_requests": 5, "max_cost_per_hour": 10.0, "requests_per_minute": 100, "tokens_per_minute": 100000, "max_concurrent": 10}', '{}', 5, NOW(), NOW()),
(1, 'llama-3.3-70b-versatile', true, '{"max_requests_per_hour": 1000, "max_tokens_per_request": 4000, "concurrent_requests": 5, "max_cost_per_hour": 10.0, "requests_per_minute": 10000, "tokens_per_minute": 100000, "max_concurrent": 10}', '{}', 5, NOW(), NOW()),
(1, 'openai/gpt-oss-120b', true, '{"max_requests_per_hour": 1000, "max_tokens_per_request": 4000, "concurrent_requests": 5, "max_cost_per_hour": 10.0, "requests_per_minute": 10000, "tokens_per_minute": 100000, "max_concurrent": 10}', '{}', 5, NOW(), NOW())
ON CONFLICT (tenant_id, model_id) DO UPDATE SET
  is_enabled = EXCLUDED.is_enabled,
  rate_limits = EXCLUDED.rate_limits,
  updated_at = NOW();

SELECT COUNT(*) || ' model configs configured' FROM tenant_model_configs WHERE tenant_id = 1;
EOF

echo "   ✓ Model configs ready"

echo ""
echo "✅ Model configuration complete!"
echo ""
echo "Summary:"
echo "  - 5 tenant model configurations enabled"
echo ""
echo "Your environment is ready to use!"
