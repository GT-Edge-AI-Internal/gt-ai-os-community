-- Migration 019: Add embedding usage tracking table
-- Supports #241 (Embedding Model Pricing)

CREATE TABLE IF NOT EXISTS public.embedding_usage_logs (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    tokens_used INTEGER NOT NULL,
    embedding_count INTEGER NOT NULL,
    model VARCHAR(100) DEFAULT 'BAAI/bge-m3',
    cost_cents DECIMAL(10,4) NOT NULL,
    request_id VARCHAR(100),
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_embedding_usage_tenant_timestamp
ON public.embedding_usage_logs(tenant_id, timestamp);
