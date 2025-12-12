-- Migration 018: Add budget and storage pricing fields to tenants
-- Supports #234 (Budget Limits), #218 (Storage Tier Pricing)
-- Updated: Removed warm tier, changed cold tier to allocation-based model

-- Budget fields
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS monthly_budget_cents INTEGER DEFAULT NULL;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS budget_warning_threshold INTEGER DEFAULT 80;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS budget_critical_threshold INTEGER DEFAULT 90;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS budget_enforcement_enabled BOOLEAN DEFAULT true;

-- Hot tier storage pricing overrides (NULL = use system defaults)
-- Default: $0.15/GiB/month (in cents per MiB: ~0.0146 cents/MiB)
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS storage_price_dataset_hot DECIMAL(10,4) DEFAULT NULL;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS storage_price_conversation_hot DECIMAL(10,4) DEFAULT NULL;

-- Cold tier: Allocation-based model
-- Monthly cost = allocated_tibs × price_per_tib
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS cold_storage_allocated_tibs DECIMAL(10,4) DEFAULT NULL;
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS cold_storage_price_per_tib DECIMAL(10,2) DEFAULT 10.00;
