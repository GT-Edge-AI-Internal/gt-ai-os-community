"""add totp 2fa fields

Revision ID: 008_add_totp_2fa
Revises: 007_add_password_reset_rate_limits
Create Date: 2025-10-07

Adds TOTP Two-Factor Authentication support with optional and mandatory enforcement.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '008_add_totp_2fa'
down_revision = '007_add_password_reset_rate_limits'
branch_labels = None
depends_on = None


def upgrade():
    # Add TFA fields to users table
    op.add_column('users', sa.Column('tfa_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('tfa_secret', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('tfa_required', sa.Boolean(), nullable=False, server_default='false'))

    # Add indexes for query optimization
    op.create_index(op.f('ix_users_tfa_enabled'), 'users', ['tfa_enabled'], unique=False)
    op.create_index(op.f('ix_users_tfa_required'), 'users', ['tfa_required'], unique=False)

    # Create TFA verification rate limits table
    op.create_table(
        'tfa_verification_rate_limits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('request_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tfa_verification_rate_limits_user_id'), 'tfa_verification_rate_limits', ['user_id'], unique=False)
    op.create_index(op.f('ix_tfa_verification_rate_limits_window_end'), 'tfa_verification_rate_limits', ['window_end'], unique=False)

    # Create used temp tokens table for replay prevention
    op.create_table(
        'used_temp_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_id')
    )
    op.create_index(op.f('ix_used_temp_tokens_token_id'), 'used_temp_tokens', ['token_id'], unique=True)
    op.create_index(op.f('ix_used_temp_tokens_expires_at'), 'used_temp_tokens', ['expires_at'], unique=False)


def downgrade():
    # Drop used temp tokens table
    op.drop_index(op.f('ix_used_temp_tokens_expires_at'), table_name='used_temp_tokens')
    op.drop_index(op.f('ix_used_temp_tokens_token_id'), table_name='used_temp_tokens')
    op.drop_table('used_temp_tokens')

    # Drop TFA verification rate limits table
    op.drop_index(op.f('ix_tfa_verification_rate_limits_window_end'), table_name='tfa_verification_rate_limits')
    op.drop_index(op.f('ix_tfa_verification_rate_limits_user_id'), table_name='tfa_verification_rate_limits')
    op.drop_table('tfa_verification_rate_limits')

    # Drop TFA fields from users table
    op.drop_index(op.f('ix_users_tfa_required'), table_name='users')
    op.drop_index(op.f('ix_users_tfa_enabled'), table_name='users')
    op.drop_column('users', 'tfa_required')
    op.drop_column('users', 'tfa_secret')
    op.drop_column('users', 'tfa_enabled')
