"""Add TFA session fields to used_temp_tokens

Revision ID: 009_add_tfa_session_fields
Revises: 008_add_totp_2fa
Create Date: 2025-10-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009_add_tfa_session_fields'
down_revision = '008_add_totp_2fa'
branch_labels = None
depends_on = None


def upgrade():
    # Add TFA session fields to used_temp_tokens table
    op.add_column('used_temp_tokens', sa.Column('user_email', sa.String(255), nullable=True))
    op.add_column('used_temp_tokens', sa.Column('tfa_configured', sa.Boolean(), nullable=True))
    op.add_column('used_temp_tokens', sa.Column('qr_code_uri', sa.Text(), nullable=True))
    op.add_column('used_temp_tokens', sa.Column('manual_entry_key', sa.String(255), nullable=True))
    op.add_column('used_temp_tokens', sa.Column('temp_token', sa.Text(), nullable=True))
    op.add_column('used_temp_tokens', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    # Modify used_at to be nullable (NULL until token is used)
    op.alter_column('used_temp_tokens', 'used_at',
                    existing_type=sa.DateTime(timezone=True),
                    nullable=True,
                    existing_server_default=sa.func.now())

    # Remove server default from used_at (manually set when used)
    op.alter_column('used_temp_tokens', 'used_at', server_default=None)


def downgrade():
    # Remove TFA session fields
    op.drop_column('used_temp_tokens', 'created_at')
    op.drop_column('used_temp_tokens', 'temp_token')
    op.drop_column('used_temp_tokens', 'manual_entry_key')
    op.drop_column('used_temp_tokens', 'qr_code_uri')
    op.drop_column('used_temp_tokens', 'tfa_configured')
    op.drop_column('used_temp_tokens', 'user_email')

    # Restore used_at to non-nullable with server default
    op.alter_column('used_temp_tokens', 'used_at',
                    existing_type=sa.DateTime(timezone=True),
                    nullable=False,
                    server_default=sa.func.now())
