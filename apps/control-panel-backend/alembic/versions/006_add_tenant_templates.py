"""add tenant templates table

Revision ID: 006_add_tenant_templates
Revises: 005_add_user_tenant_assignments
Create Date: 2025-09-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '006_add_tenant_templates'
down_revision = '005_add_user_tenant_assignments'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tenant_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_data', JSONB, nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tenant_templates_id'), 'tenant_templates', ['id'], unique=False)
    op.create_index(op.f('ix_tenant_templates_name'), 'tenant_templates', ['name'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_tenant_templates_name'), table_name='tenant_templates')
    op.drop_index(op.f('ix_tenant_templates_id'), table_name='tenant_templates')
    op.drop_table('tenant_templates')