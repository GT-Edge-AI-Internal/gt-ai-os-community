"""Add user-tenant assignments for multi-tenant user management

Revision ID: 005_add_user_tenant_assignments
Revises: 004_add_license_billing_tables
Create Date: 2025-09-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005_add_user_tenant_assignments'
down_revision: Union[str, None] = '004_add_license_billing_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade to add user-tenant assignments table and update user table"""
    
    # Create user_tenant_assignments table
    op.create_table(
        'user_tenant_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        
        # Tenant-specific user profile
        sa.Column('tenant_user_role', sa.String(20), nullable=False, default='tenant_user'),
        sa.Column('tenant_display_name', sa.String(100), nullable=True),
        sa.Column('tenant_email', sa.String(255), nullable=True),
        sa.Column('tenant_department', sa.String(100), nullable=True),
        sa.Column('tenant_title', sa.String(100), nullable=True),
        
        # Tenant-specific authentication (optional)
        sa.Column('tenant_password_hash', sa.String(255), nullable=True),
        sa.Column('requires_2fa', sa.Boolean(), nullable=False, default=False),
        sa.Column('last_password_change', sa.DateTime(timezone=True), nullable=True),
        
        # Tenant-specific permissions and limits
        sa.Column('tenant_capabilities', sa.JSON(), nullable=False, default=list),
        sa.Column('resource_limits', sa.JSON(), nullable=False, default=dict),
        
        # Status and activity tracking
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_primary_tenant', sa.Boolean(), nullable=False, default=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_accessed', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        
        # Invitation tracking
        sa.Column('invited_by', sa.Integer(), nullable=True),
        sa.Column('invitation_accepted_at', sa.DateTime(timezone=True), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        
        # Foreign key constraints
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id']),
        
        # Indexes (created separately with CONCURRENTLY for zero downtime)
        # sa.Index('ix_user_tenant_assignments_user_id', 'user_id'),
        # sa.Index('ix_user_tenant_assignments_tenant_id', 'tenant_id'),
        # sa.Index('ix_user_tenant_assignments_tenant_email', 'tenant_email'),
        
        # Unique constraint
        sa.UniqueConstraint('user_id', 'tenant_id', name='unique_user_tenant_assignment')
    )
    
    # Add current_tenant_id to users table (remove old tenant_id later)
    op.add_column('users', sa.Column('current_tenant_id', sa.Integer(), nullable=True))
    
    # Create index for current_tenant_id (using CONCURRENTLY for zero downtime)
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_users_current_tenant_id ON users(current_tenant_id)")
    
    # Create indexes for user_tenant_assignments table (using CONCURRENTLY for zero downtime)
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_user_tenant_assignments_user_id ON user_tenant_assignments(user_id)")
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_user_tenant_assignments_tenant_id ON user_tenant_assignments(tenant_id)")
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_user_tenant_assignments_tenant_email ON user_tenant_assignments(tenant_email)")
    
    # Data migration: Convert existing users.tenant_id to user_tenant_assignments
    # This is a raw SQL operation to handle the data migration
    
    connection = op.get_bind()
    
    # Step 1: Get all existing users with tenant_id
    result = connection.execute(sa.text("""
        SELECT id, tenant_id, user_type, email, full_name, capabilities
        FROM users 
        WHERE tenant_id IS NOT NULL
    """))
    
    users_to_migrate = result.fetchall()
    
    # Step 2: Create user_tenant_assignments for each user
    for user in users_to_migrate:
        user_id, tenant_id, user_type, email, full_name, capabilities = user
        
        # Set default resource limits based on user type
        resource_limits = {
            "max_conversations": 1000 if user_type == "super_admin" else 100,
            "max_datasets": 100 if user_type == "super_admin" else 10,
            "max_agents": 200 if user_type == "super_admin" else 20,
            "daily_api_calls": 10000 if user_type == "super_admin" else 1000
        }
        
        # Convert old capabilities to tenant_capabilities
        tenant_capabilities = capabilities if capabilities else []
        
        # Insert user_tenant_assignment
        connection.execute(sa.text("""
            INSERT INTO user_tenant_assignments (
                user_id, tenant_id, tenant_user_role, tenant_display_name, 
                tenant_email, tenant_capabilities, resource_limits, 
                is_active, is_primary_tenant, joined_at, created_at, updated_at
            ) VALUES (
                :user_id, :tenant_id, :user_type, :full_name,
                :email, :tenant_capabilities, :resource_limits,
                true, true, now(), now(), now()
            )
        """), {
            'user_id': user_id,
            'tenant_id': tenant_id,
            'user_type': user_type,
            'full_name': full_name,
            'email': email,
            'tenant_capabilities': sa.dialects.postgresql.JSON().literal_processor(dialect=connection.dialect)(tenant_capabilities),
            'resource_limits': sa.dialects.postgresql.JSON().literal_processor(dialect=connection.dialect)(resource_limits)
        })
        
        # Update user's current_tenant_id to their primary tenant
        connection.execute(sa.text("""
            UPDATE users 
            SET current_tenant_id = :tenant_id 
            WHERE id = :user_id
        """), {'tenant_id': tenant_id, 'user_id': user_id})
    
    # Step 3: Remove old tenant_id column from users (this is irreversible)
    # First remove the foreign key constraint
    op.drop_constraint('users_tenant_id_fkey', 'users', type_='foreignkey')
    
    # Then drop the column
    op.drop_column('users', 'tenant_id')


def downgrade() -> None:
    """Downgrade: Remove user-tenant assignments and restore single tenant_id"""
    
    # Re-add tenant_id column to users
    op.add_column('users', sa.Column('tenant_id', sa.Integer(), nullable=True))
    
    # Re-create foreign key constraint
    op.create_foreign_key('users_tenant_id_fkey', 'users', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')
    
    # Data migration back: Convert user_tenant_assignments to users.tenant_id
    connection = op.get_bind()
    
    # Get primary tenant assignments for each user
    result = connection.execute(sa.text("""
        SELECT user_id, tenant_id, tenant_capabilities
        FROM user_tenant_assignments 
        WHERE is_primary_tenant = true AND is_active = true
    """))
    
    assignments_to_migrate = result.fetchall()
    
    # Update users table with their primary tenant
    for assignment in assignments_to_migrate:
        user_id, tenant_id, tenant_capabilities = assignment
        
        connection.execute(sa.text("""
            UPDATE users 
            SET tenant_id = :tenant_id, 
                capabilities = :capabilities
            WHERE id = :user_id
        """), {
            'tenant_id': tenant_id,
            'user_id': user_id,
            'capabilities': sa.dialects.postgresql.JSON().literal_processor(dialect=connection.dialect)(tenant_capabilities or [])
        })
    
    # Drop current_tenant_id column and index
    op.drop_index('ix_users_current_tenant_id', 'users')
    op.drop_column('users', 'current_tenant_id')
    
    # Drop user_tenant_assignments table
    op.drop_table('user_tenant_assignments')