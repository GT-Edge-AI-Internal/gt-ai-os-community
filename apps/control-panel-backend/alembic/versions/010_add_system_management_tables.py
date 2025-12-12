"""Add system management tables (versions, updates, backups)

Revision ID: 010_add_system_management_tables
Revises: 009_add_tfa_session_fields
Create Date: 2025-11-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = '010_add_system_management_tables'
down_revision = '009_add_tfa_session_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Create system_versions table
    op.create_table(
        'system_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', sa.String(36), nullable=False),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('installed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('installed_by', sa.String(255), nullable=True),
        sa.Column('is_current', sa.Boolean(), nullable=False, default=True),
        sa.Column('release_notes', sa.Text(), nullable=True),
        sa.Column('git_commit', sa.String(40), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uuid')
    )
    op.create_index('ix_system_versions_id', 'system_versions', ['id'])
    op.create_index('ix_system_versions_version', 'system_versions', ['version'])

    # Create update_jobs table
    op.create_table(
        'update_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', sa.String(36), nullable=False),
        sa.Column('target_version', sa.String(50), nullable=False),
        sa.Column('status', sa.Enum('pending', 'in_progress', 'completed', 'failed', 'rolled_back', name='updatestatus'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_stage', sa.String(100), nullable=True),
        sa.Column('logs', JSON, nullable=False, default=[]),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('backup_id', sa.Integer(), nullable=True),
        sa.Column('started_by', sa.String(255), nullable=True),
        sa.Column('rollback_reason', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uuid')
    )
    op.create_index('ix_update_jobs_id', 'update_jobs', ['id'])
    op.create_index('ix_update_jobs_uuid', 'update_jobs', ['uuid'])
    op.create_index('ix_update_jobs_status', 'update_jobs', ['status'])

    # Create backup_records table
    op.create_table(
        'backup_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', sa.String(36), nullable=False),
        sa.Column('backup_type', sa.Enum('manual', 'pre_update', 'scheduled', name='backuptype'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('location', sa.String(500), nullable=False),
        sa.Column('version', sa.String(50), nullable=True),
        sa.Column('components', JSON, nullable=False, default={}),
        sa.Column('checksum', sa.String(64), nullable=True),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=False, default=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uuid')
    )
    op.create_index('ix_backup_records_id', 'backup_records', ['id'])
    op.create_index('ix_backup_records_uuid', 'backup_records', ['uuid'])

    # Insert initial system version (v2.0.31 as per current deployment)
    op.execute("""
        INSERT INTO system_versions (uuid, version, installed_by, is_current, installed_at)
        VALUES (
            'initial-version-uuid',
            'v2.0.31',
            'system',
            true,
            NOW()
        )
    """)


def downgrade():
    # Drop tables
    op.drop_table('backup_records')
    op.drop_table('update_jobs')
    op.drop_table('system_versions')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS updatestatus')
    op.execute('DROP TYPE IF EXISTS backuptype')
