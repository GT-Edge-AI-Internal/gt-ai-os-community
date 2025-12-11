"""add password reset rate limits table

Revision ID: 007_add_password_reset_rate_limits
Revises: 006_add_tenant_templates
Create Date: 2025-10-06

Email-based rate limiting only (no IP tracking)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '007_add_password_reset_rate_limits'
down_revision = '006_add_tenant_templates'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'password_reset_rate_limits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('request_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_password_reset_rate_limits_email'), 'password_reset_rate_limits', ['email'], unique=False)
    op.create_index(op.f('ix_password_reset_rate_limits_window_end'), 'password_reset_rate_limits', ['window_end'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_password_reset_rate_limits_window_end'), table_name='password_reset_rate_limits')
    op.drop_index(op.f('ix_password_reset_rate_limits_email'), table_name='password_reset_rate_limits')
    op.drop_table('password_reset_rate_limits')
