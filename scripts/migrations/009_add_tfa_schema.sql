-- Migration 009: Add Two-Factor Authentication Schema
-- Creates TFA fields in users table and supporting tables for rate limiting and token management

-- Add TFA fields to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS tfa_enabled BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS tfa_secret TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS tfa_required BOOLEAN NOT NULL DEFAULT false;

-- Add indexes for query optimization
CREATE INDEX IF NOT EXISTS ix_users_tfa_enabled ON users(tfa_enabled);
CREATE INDEX IF NOT EXISTS ix_users_tfa_required ON users(tfa_required);

-- Create TFA verification rate limits table
CREATE TABLE IF NOT EXISTS tfa_verification_rate_limits (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    request_count INTEGER NOT NULL DEFAULT 1,
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_tfa_verification_rate_limits_user_id ON tfa_verification_rate_limits(user_id);
CREATE INDEX IF NOT EXISTS ix_tfa_verification_rate_limits_window_end ON tfa_verification_rate_limits(window_end);

-- Create used temp tokens table for replay prevention
CREATE TABLE IF NOT EXISTS used_temp_tokens (
    id SERIAL PRIMARY KEY,
    token_id VARCHAR(255) NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_email VARCHAR(255),
    tfa_configured BOOLEAN,
    qr_code_uri TEXT,
    manual_entry_key VARCHAR(255),
    temp_token TEXT,
    used_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_used_temp_tokens_token_id ON used_temp_tokens(token_id);
CREATE INDEX IF NOT EXISTS ix_used_temp_tokens_expires_at ON used_temp_tokens(expires_at);
