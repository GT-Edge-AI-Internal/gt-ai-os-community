-- Migration 011: Add system management tables for version tracking, updates, and backups
-- Idempotent: Uses CREATE TABLE IF NOT EXISTS and exception handling for enums

-- Create enum types (safe to recreate)
DO $$ BEGIN
    CREATE TYPE updatestatus AS ENUM ('pending', 'in_progress', 'completed', 'failed', 'rolled_back');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE backuptype AS ENUM ('manual', 'pre_update', 'scheduled');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- System versions table - tracks installed system versions
CREATE TABLE IF NOT EXISTS system_versions (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) NOT NULL UNIQUE DEFAULT gen_random_uuid()::text,
    version VARCHAR(50) NOT NULL,
    installed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    installed_by VARCHAR(255),
    is_current BOOLEAN NOT NULL DEFAULT true,
    release_notes TEXT,
    git_commit VARCHAR(40)
);
CREATE INDEX IF NOT EXISTS ix_system_versions_id ON system_versions(id);
CREATE INDEX IF NOT EXISTS ix_system_versions_version ON system_versions(version);

-- Update jobs table - tracks update execution
CREATE TABLE IF NOT EXISTS update_jobs (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) NOT NULL UNIQUE DEFAULT gen_random_uuid()::text,
    target_version VARCHAR(50) NOT NULL,
    status updatestatus NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    current_stage VARCHAR(100),
    logs JSONB NOT NULL DEFAULT '[]'::jsonb,
    error_message TEXT,
    backup_id INTEGER,
    started_by VARCHAR(255),
    rollback_reason TEXT
);
CREATE INDEX IF NOT EXISTS ix_update_jobs_id ON update_jobs(id);
CREATE INDEX IF NOT EXISTS ix_update_jobs_uuid ON update_jobs(uuid);
CREATE INDEX IF NOT EXISTS ix_update_jobs_status ON update_jobs(status);

-- Backup records table - tracks system backups
CREATE TABLE IF NOT EXISTS backup_records (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) NOT NULL UNIQUE DEFAULT gen_random_uuid()::text,
    backup_type backuptype NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    size_bytes BIGINT,
    location VARCHAR(500) NOT NULL,
    version VARCHAR(50),
    components JSONB NOT NULL DEFAULT '{}'::jsonb,
    checksum VARCHAR(64),
    created_by VARCHAR(255),
    description TEXT,
    is_valid BOOLEAN NOT NULL DEFAULT true,
    expires_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS ix_backup_records_id ON backup_records(id);
CREATE INDEX IF NOT EXISTS ix_backup_records_uuid ON backup_records(uuid);

-- Seed initial version (idempotent - only inserts if no current version exists)
INSERT INTO system_versions (uuid, version, installed_by, is_current)
SELECT 'initial-version-uuid', 'v2.0.31', 'system', true
WHERE NOT EXISTS (SELECT 1 FROM system_versions WHERE is_current = true);
