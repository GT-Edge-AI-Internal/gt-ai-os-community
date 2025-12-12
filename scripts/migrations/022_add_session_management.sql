-- Migration: 022_add_session_management.sql
-- Description: Server-side session tracking for OWASP/NIST compliance
-- Date: 2025-12-08
-- Issue: #264 - Session timeout warning not appearing
--
-- Timeout Configuration:
--   Idle Timeout: 4 hours (240 minutes) - covers meetings, lunch, context-switching
--   Absolute Timeout: 8 hours (maximum session lifetime) - full work day
--   Warning Threshold: 5 minutes before idle expiry

-- Active sessions table for server-side session tracking
-- This is the authoritative source of truth for session validity,
-- not the JWT expiration time alone.
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 of session token (never store plaintext)

    -- Session timing (NIST SP 800-63B compliant)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    absolute_expires_at TIMESTAMP WITH TIME ZONE NOT NULL,  -- 8 hours from creation

    -- Session metadata for security auditing
    ip_address VARCHAR(45),  -- IPv6 compatible (max 45 chars)
    user_agent TEXT,
    tenant_id INTEGER REFERENCES tenants(id),

    -- Session state
    is_active BOOLEAN NOT NULL DEFAULT true,
    revoked_at TIMESTAMP WITH TIME ZONE,
    revoke_reason VARCHAR(50),  -- 'logout', 'idle_timeout', 'absolute_timeout', 'admin_revoke', 'password_change', 'cleanup_stale'
    ended_at TIMESTAMP WITH TIME ZONE,  -- When session ended (any reason: logout, timeout, etc.)
    app_type VARCHAR(20) NOT NULL DEFAULT 'control_panel'  -- 'control_panel' or 'tenant_app'
);

-- Indexes for session lookup and cleanup
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(session_token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity_at);
CREATE INDEX IF NOT EXISTS idx_sessions_absolute_expires ON sessions(absolute_expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_sessions_tenant_id ON sessions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sessions_ended_at ON sessions(ended_at);
CREATE INDEX IF NOT EXISTS idx_sessions_app_type ON sessions(app_type);

-- Function to clean up expired sessions (run periodically via cron or scheduled task)
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    rows_affected INTEGER := 0;
    idle_rows INTEGER := 0;
    idle_timeout_minutes INTEGER := 240;  -- 4 hours
    absolute_cutoff TIMESTAMP WITH TIME ZONE;
    idle_cutoff TIMESTAMP WITH TIME ZONE;
BEGIN
    absolute_cutoff := CURRENT_TIMESTAMP;
    idle_cutoff := CURRENT_TIMESTAMP - (idle_timeout_minutes * INTERVAL '1 minute');

    -- Mark sessions as inactive if absolute timeout exceeded
    UPDATE sessions
    SET is_active = false,
        revoked_at = CURRENT_TIMESTAMP,
        ended_at = CURRENT_TIMESTAMP,
        revoke_reason = 'absolute_timeout'
    WHERE is_active = true
      AND absolute_expires_at < absolute_cutoff;

    GET DIAGNOSTICS rows_affected = ROW_COUNT;

    -- Mark sessions as inactive if idle timeout exceeded
    UPDATE sessions
    SET is_active = false,
        revoked_at = CURRENT_TIMESTAMP,
        ended_at = CURRENT_TIMESTAMP,
        revoke_reason = 'idle_timeout'
    WHERE is_active = true
      AND last_activity_at < idle_cutoff;

    GET DIAGNOSTICS idle_rows = ROW_COUNT;
    rows_affected := rows_affected + idle_rows;

    RETURN rows_affected;
END;
$$ LANGUAGE plpgsql;

-- Function to get session status (for internal API validation)
CREATE OR REPLACE FUNCTION get_session_status(p_token_hash VARCHAR(64))
RETURNS TABLE (
    is_valid BOOLEAN,
    expiry_reason VARCHAR(50),
    seconds_until_idle_timeout INTEGER,
    seconds_until_absolute_timeout INTEGER,
    user_id INTEGER,
    tenant_id INTEGER
) AS $$
DECLARE
    v_session RECORD;
    v_idle_timeout_minutes INTEGER := 240;  -- 4 hours
    v_warning_threshold_minutes INTEGER := 5;
    v_idle_expires_at TIMESTAMP WITH TIME ZONE;
    v_seconds_until_idle INTEGER;
    v_seconds_until_absolute INTEGER;
BEGIN
    -- Find the session
    SELECT s.* INTO v_session
    FROM sessions s
    WHERE s.session_token_hash = p_token_hash
      AND s.is_active = true;

    -- Session not found or inactive
    IF NOT FOUND THEN
        RETURN QUERY SELECT
            false::BOOLEAN,
            NULL::VARCHAR(50),
            NULL::INTEGER,
            NULL::INTEGER,
            NULL::INTEGER,
            NULL::INTEGER;
        RETURN;
    END IF;

    -- Calculate expiration times
    v_idle_expires_at := v_session.last_activity_at + (v_idle_timeout_minutes * INTERVAL '1 minute');

    -- Check absolute timeout first
    IF CURRENT_TIMESTAMP >= v_session.absolute_expires_at THEN
        -- Mark session as expired
        UPDATE sessions
        SET is_active = false,
            revoked_at = CURRENT_TIMESTAMP,
            ended_at = CURRENT_TIMESTAMP,
            revoke_reason = 'absolute_timeout'
        WHERE session_token_hash = p_token_hash;

        RETURN QUERY SELECT
            false::BOOLEAN,
            'absolute'::VARCHAR(50),
            NULL::INTEGER,
            NULL::INTEGER,
            v_session.user_id,
            v_session.tenant_id;
        RETURN;
    END IF;

    -- Check idle timeout
    IF CURRENT_TIMESTAMP >= v_idle_expires_at THEN
        -- Mark session as expired
        UPDATE sessions
        SET is_active = false,
            revoked_at = CURRENT_TIMESTAMP,
            ended_at = CURRENT_TIMESTAMP,
            revoke_reason = 'idle_timeout'
        WHERE session_token_hash = p_token_hash;

        RETURN QUERY SELECT
            false::BOOLEAN,
            'idle'::VARCHAR(50),
            NULL::INTEGER,
            NULL::INTEGER,
            v_session.user_id,
            v_session.tenant_id;
        RETURN;
    END IF;

    -- Session is valid - calculate remaining times
    v_seconds_until_idle := EXTRACT(EPOCH FROM (v_idle_expires_at - CURRENT_TIMESTAMP))::INTEGER;
    v_seconds_until_absolute := EXTRACT(EPOCH FROM (v_session.absolute_expires_at - CURRENT_TIMESTAMP))::INTEGER;

    RETURN QUERY SELECT
        true::BOOLEAN,
        NULL::VARCHAR(50),
        v_seconds_until_idle,
        v_seconds_until_absolute,
        v_session.user_id,
        v_session.tenant_id;
END;
$$ LANGUAGE plpgsql;

-- Function to update session activity (called on each authenticated request)
CREATE OR REPLACE FUNCTION update_session_activity(p_token_hash VARCHAR(64))
RETURNS BOOLEAN AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    UPDATE sessions
    SET last_activity_at = CURRENT_TIMESTAMP
    WHERE session_token_hash = p_token_hash
      AND is_active = true;

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated > 0;
END;
$$ LANGUAGE plpgsql;

-- Function to revoke a session
CREATE OR REPLACE FUNCTION revoke_session(p_token_hash VARCHAR(64), p_reason VARCHAR(50) DEFAULT 'logout')
RETURNS BOOLEAN AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    UPDATE sessions
    SET is_active = false,
        revoked_at = CURRENT_TIMESTAMP,
        ended_at = CURRENT_TIMESTAMP,
        revoke_reason = p_reason
    WHERE session_token_hash = p_token_hash
      AND is_active = true;

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated > 0;
END;
$$ LANGUAGE plpgsql;

-- Function to revoke all sessions for a user (e.g., on password change)
CREATE OR REPLACE FUNCTION revoke_all_user_sessions(p_user_id INTEGER, p_reason VARCHAR(50) DEFAULT 'password_change')
RETURNS INTEGER AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    UPDATE sessions
    SET is_active = false,
        revoked_at = CURRENT_TIMESTAMP,
        ended_at = CURRENT_TIMESTAMP,
        revoke_reason = p_reason
    WHERE user_id = p_user_id
      AND is_active = true;

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated;
END;
$$ LANGUAGE plpgsql;

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Migration 022: Created sessions table and session management functions for OWASP/NIST compliance';
END $$;
