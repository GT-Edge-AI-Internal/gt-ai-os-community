"""
User management API endpoints
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from pydantic import BaseModel, Field, EmailStr, validator
from passlib.context import CryptContext
import logging
import uuid
import csv
import io

from app.core.database import get_db
from app.core.auth import JWTHandler, get_current_user
from app.models.user import User
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# GT AI OS Community Edition - Hardcoded user limit
MAX_USERS_COMMUNITY = 5


def get_default_capabilities(user_type: str) -> List[Dict[str, Any]]:
    """
    Get default capabilities based on user type.
    Returns a list of capability objects with resource, actions, and constraints.
    """
    if user_type == "super_admin":
        return [{"resource": "*", "actions": ["*"], "constraints": {}}]
    elif user_type == "tenant_admin":
        return [{"resource": "*", "actions": ["*"], "constraints": {}}]
    else:  # tenant_user
        return [
            {"resource": "agents", "actions": ["read", "create", "edit", "delete", "execute"], "constraints": {}},
            {"resource": "conversations", "actions": ["read", "create", "delete"], "constraints": {}},
            {"resource": "documents", "actions": ["read", "upload", "delete"], "constraints": {}},
            {"resource": "datasets", "actions": ["read", "create", "upload", "delete"], "constraints": {}}
        ]


async def delete_user_from_tenant_database(user_email: str, tenant_domain: str) -> None:
    """
    Delete a user from the tenant database.
    Removes the user record from tenant_<domain>.users table.
    """
    import asyncpg
    import os

    # Get tenant database connection info
    db_host = os.getenv("TENANT_POSTGRES_HOST", "tenant-postgres-primary")
    db_port = 5432  # Internal container port
    db_user = os.getenv("TENANT_POSTGRES_USER", "gt2_tenant_user")
    db_password = os.getenv("TENANT_POSTGRES_PASSWORD", "gt2_tenant_dev_password")
    db_name = os.getenv("TENANT_POSTGRES_DB", "gt2_tenants")

    # Clean tenant domain for schema name
    clean_domain = tenant_domain.replace('-', '_').replace('.', '_').lower()
    schema_name = f"tenant_{clean_domain}"

    try:
        # Connect to tenant database
        conn = await asyncpg.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name
        )

        try:
            # Delete user from tenant database
            delete_query = f"DELETE FROM {schema_name}.users WHERE email = $1"
            result = await conn.execute(delete_query, user_email)

            logger.info(f"Deleted user {user_email} from {schema_name}.users: {result}")

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"Error deleting user from tenant database: {e}")
        raise


async def sync_user_to_tenant_database(user: User, tenant_domain: str) -> None:
    """
    Sync a Control Panel user to the tenant database.
    Creates a corresponding user record in tenant_<domain>.users table.
    """
    import asyncpg
    import os

    # Get tenant database connection info
    db_host = os.getenv("TENANT_POSTGRES_HOST", "tenant-postgres-primary")
    db_port = 5432  # Internal container port
    db_user = os.getenv("TENANT_POSTGRES_USER", "gt2_tenant_user")
    db_password = os.getenv("TENANT_POSTGRES_PASSWORD", "gt2_tenant_dev_password")
    db_name = os.getenv("TENANT_POSTGRES_DB", "gt2_tenants")

    # Clean tenant domain for schema name
    clean_domain = tenant_domain.replace('-', '_').replace('.', '_').lower()
    schema_name = f"tenant_{clean_domain}"

    try:
        # Connect to tenant database
        conn = await asyncpg.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name
        )

        try:
            # Get the tenant ID for this tenant schema
            tenant_query = f"SELECT id FROM {schema_name}.tenants LIMIT 1"
            tenant_id = await conn.fetchval(tenant_query)

            if not tenant_id:
                logger.error(f"No tenant found in {schema_name}.tenants")
                return

            # Map user_type to tenant role
            role_mapping = {
                "super_admin": "admin",
                "tenant_admin": "admin",
                "tenant_user": "analyst"  # Default role for regular users
            }
            role = role_mapping.get(user.user_type, "student")

            # Create user in tenant database (or update if exists)
            insert_query = f"""
                INSERT INTO {schema_name}.users (email, username, full_name, tenant_id, role, is_active)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (email, tenant_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    full_name = EXCLUDED.full_name,
                    role = EXCLUDED.role,
                    is_active = EXCLUDED.is_active,
                    updated_at = NOW()
                RETURNING id
            """

            user_uuid = await conn.fetchval(
                insert_query,
                user.email,
                user.email.split('@')[0],  # username from email
                user.full_name,
                tenant_id,
                role,
                user.is_active
            )

            logger.info(f"Synced user {user.email} to {schema_name}.users with UUID {user_uuid}")

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"Error syncing user to tenant database: {e}")
        raise


# Pydantic models
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=100)
    user_type: str = Field(default="tenant_user")
    tenant_id: Optional[int] = None
    capabilities: Optional[List[str]] = Field(default_factory=list)
    tfa_required: Optional[bool] = Field(default=False)  # Admin can enforce TFA

    @validator('user_type')
    def validate_user_type(cls, v):
        valid_types = ["super_admin", "tenant_admin", "tenant_user"]
        if v not in valid_types:
            raise ValueError(f'User type must be one of: {", ".join(valid_types)}')
        return v

    @validator('email', pre=True)
    def normalize_email(cls, v):
        """Normalize email to lowercase for case-insensitive matching"""
        return v.lower() if v else v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    user_type: Optional[str] = None
    capabilities: Optional[List[str]] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=1, max_length=100)
    tfa_required: Optional[bool] = None  # Admin can enforce/remove TFA requirement
    tfa_enabled: Optional[bool] = None  # Admin can disable TFA for recovery
    tfa_secret: Optional[str] = None  # Admin can clear TFA secret for recovery

    @validator('user_type')
    def validate_user_type(cls, v):
        if v is not None:
            valid_types = ["super_admin", "tenant_admin", "tenant_user"]
            if v not in valid_types:
                raise ValueError(f'User type must be one of: {", ".join(valid_types)}')
        return v

    @validator('email', pre=True)
    def normalize_email(cls, v):
        """Normalize email to lowercase for case-insensitive matching"""
        return v.lower() if v else v


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=1, max_length=100)


class UserResponse(BaseModel):
    id: int
    uuid: str
    email: str
    full_name: str
    user_type: str
    tenant_id: Optional[int]
    tenant_name: Optional[str]
    capabilities: List[Any]  # Can be strings or complex capability objects
    is_active: bool
    tfa_enabled: bool
    tfa_required: bool
    tfa_status: str  # "disabled", "enabled", "enforced"
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    limit: int


class BulkUploadError(BaseModel):
    row: int
    email: str
    reason: str


class BulkUploadResponse(BaseModel):
    success_count: int
    failed_count: int
    total_rows: int
    errors: List[BulkUploadError]


class BulkTFARequest(BaseModel):
    user_ids: List[int]


class BulkTFAError(BaseModel):
    user_id: int
    email: str
    reason: str


class BulkTFAResponse(BaseModel):
    success_count: int
    failed_count: int
    errors: List[BulkTFAError]


@router.get("/", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=10000),
    search: Optional[str] = None,
    tenant_id: Optional[int] = None,
    user_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List users with pagination and filtering"""
    try:
        # Build base query
        query = select(User)
        
        # Apply permission filters
        if current_user.user_type == "tenant_admin":
            # Tenant admins can only see users in their tenant
            query = query.where(User.tenant_id == current_user.tenant_id)
        elif current_user.user_type == "tenant_user":
            # Regular users can only see themselves
            query = query.where(User.id == current_user.id)
        # Super admins and GT admins can see all users
        
        # Apply filters
        conditions = []
        if search:
            conditions.append(
                or_(
                    User.email.ilike(f"%{search}%"),
                    User.full_name.ilike(f"%{search}%")
                )
            )
        
        if tenant_id is not None:
            conditions.append(User.tenant_id == tenant_id)
        
        if user_type:
            conditions.append(User.user_type == user_type)
        
        if is_active is not None:
            conditions.append(User.is_active == is_active)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Get total count
        count_query = select(func.count()).select_from(User)
        if current_user.user_type == "tenant_admin":
            count_query = count_query.where(User.tenant_id == current_user.tenant_id)
        elif current_user.user_type == "tenant_user":
            count_query = count_query.where(User.id == current_user.id)
        
        if conditions:
            count_query = count_query.where(and_(*conditions))
        
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(User.created_at.desc())
        
        # Execute query
        result = await db.execute(query)
        users = result.scalars().all()
        
        # Get tenant names
        user_responses = []
        for user in users:
            tenant_name = None
            if user.tenant_id:
                tenant_result = await db.execute(
                    select(Tenant.name).where(Tenant.id == user.tenant_id)
                )
                tenant_name = tenant_result.scalar()
            
            user_dict = {
                "id": user.id,
                "uuid": user.uuid,
                "email": user.email,
                "full_name": user.full_name,
                "user_type": user.user_type,
                "tenant_id": user.tenant_id,
                "tenant_name": tenant_name,
                "capabilities": user.capabilities or [],
                "is_active": user.is_active,
                "tfa_enabled": user.tfa_enabled,
                "tfa_required": user.tfa_required,
                "tfa_status": user.tfa_status,
                "last_login_at": user.last_login_at,
                "created_at": user.created_at,
                "updated_at": user.updated_at
            }
            user_responses.append(UserResponse(**user_dict))
        
        return UserListResponse(
            users=user_responses,
            total=total,
            page=page,
            limit=limit
        )
        
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific user by ID"""
    try:
        # Check permissions
        if current_user.user_type == "tenant_user" and current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        # Get user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check tenant access
        if current_user.user_type == "tenant_admin" and user.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access users from other tenants"
            )
        
        # Get tenant name
        tenant_name = None
        if user.tenant_id:
            tenant_result = await db.execute(
                select(Tenant.name).where(Tenant.id == user.tenant_id)
            )
            tenant_name = tenant_result.scalar()
        
        return UserResponse(
            id=user.id,
            uuid=user.uuid,
            email=user.email,
            full_name=user.full_name,
            user_type=user.user_type,
            tenant_id=user.tenant_id,
            tenant_name=tenant_name,
            capabilities=user.capabilities or [],
            is_active=user.is_active,
            tfa_enabled=user.tfa_enabled,
            tfa_required=user.tfa_required,
            tfa_status=user.tfa_status,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user"
        )


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new user"""
    try:
        # Permission checks
        if current_user.user_type == "tenant_admin":
            # Tenant admins can only create users in their tenant
            if user_data.tenant_id != current_user.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot create users in other tenants"
                )
            # Tenant admins cannot create super admins or GT admins
            if user_data.user_type == "super_admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot create admin users"
                )
        elif current_user.user_type == "tenant_user":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to create users"
            )

        # Check user limit for Community Edition
        user_count_result = await db.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        current_user_count = user_count_result.scalar() or 0

        if current_user_count >= MAX_USERS_COMMUNITY:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"GT AI OS Community is limited to {MAX_USERS_COMMUNITY} users. "
                       "Contact GT Edge AI for Enterprise licensing."
            )

        # Check if email already exists
        existing = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        hashed_password = pwd_context.hash(user_data.password)

        # Set default capabilities if none provided
        default_capabilities = user_data.capabilities or []
        if not default_capabilities:
            default_capabilities = get_default_capabilities(user_data.user_type)

        # Create user
        user = User(
            uuid=str(uuid.uuid4()),
            email=user_data.email,
            full_name=user_data.full_name,
            hashed_password=hashed_password,
            user_type=user_data.user_type,
            tenant_id=user_data.tenant_id,
            capabilities=default_capabilities,
            is_active=True,
            tfa_required=user_data.tfa_required  # Admin can enforce TFA on user creation
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Get tenant information
        tenant_name = None
        tenant_domain = None
        if user.tenant_id:
            tenant_result = await db.execute(
                select(Tenant).where(Tenant.id == user.tenant_id)
            )
            tenant = tenant_result.scalar()
            if tenant:
                tenant_name = tenant.name
                tenant_domain = tenant.domain

                # Automatically create user in tenant database
                try:
                    await sync_user_to_tenant_database(user, tenant_domain)
                    logger.info(f"Successfully synced user {user.email} to tenant database {tenant_domain}")
                except Exception as e:
                    logger.warning(f"Failed to sync user {user.email} to tenant database {tenant_domain}: {e}")
                    # Don't fail user creation if tenant sync fails
        
        return UserResponse(
            id=user.id,
            uuid=user.uuid,
            email=user.email,
            full_name=user.full_name,
            user_type=user.user_type,
            tenant_id=user.tenant_id,
            tenant_name=tenant_name,
            capabilities=user.capabilities,
            is_active=user.is_active,
            tfa_enabled=user.tfa_enabled,
            tfa_required=user.tfa_required,
            tfa_status=user.tfa_status,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a user"""
    try:
        # Get user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Permission checks
        if current_user.user_type == "tenant_admin":
            if user.tenant_id != current_user.tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot update users from other tenants"
                )
            # Tenant admins cannot change user type to admin
            if user_update.user_type == "super_admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot promote users to admin"
                )
        elif current_user.user_type == "tenant_user":
            if user.id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Can only update your own profile"
                )
            # Regular users cannot change their user type
            if user_update.user_type is not None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot change user type"
                )

        # Check if email is being changed and if it's already taken
        if user_update.email and user_update.email != user.email:
            existing = await db.execute(
                select(User).where(User.email == user_update.email)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )

        # Update fields
        update_data = user_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            # Hash password if it's being updated
            if field == 'password' and value is not None:
                user.hashed_password = pwd_context.hash(value)
            elif field != 'password':  # Don't set password field directly
                setattr(user, field, value)

        user.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(user)

        # Sync role changes to tenant database immediately
        if user.tenant_id and user_update.user_type is not None:
            try:
                tenant_result = await db.execute(
                    select(Tenant).where(Tenant.id == user.tenant_id)
                )
                tenant = tenant_result.scalar()
                if tenant:
                    await sync_user_to_tenant_database(user, tenant.domain)
                    logger.info(f"Role updated in tenant database for {user.email}")
            except Exception as e:
                logger.warning(f"Failed to sync role to tenant database: {e}")

        # Get tenant name
        tenant_name = None
        if user.tenant_id:
            tenant_result = await db.execute(
                select(Tenant.name).where(Tenant.id == user.tenant_id)
            )
            tenant_name = tenant_result.scalar()
        
        return UserResponse(
            id=user.id,
            uuid=user.uuid,
            email=user.email,
            full_name=user.full_name,
            user_type=user.user_type,
            tenant_id=user.tenant_id,
            tenant_name=tenant_name,
            capabilities=user.capabilities or [],
            is_active=user.is_active,
            tfa_enabled=user.tfa_enabled,
            tfa_required=user.tfa_required,
            tfa_status=user.tfa_status,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Permanently delete a user"""
    try:
        # Permission checks - only super_admin can permanently delete users
        if current_user.user_type != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admins can delete users"
            )

        # Get user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Cannot delete yourself
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )

        # Delete from tenant database first if user has a tenant
        if user.tenant_id:
            try:
                # Get tenant domain
                tenant_result = await db.execute(
                    select(Tenant).where(Tenant.id == user.tenant_id)
                )
                tenant = tenant_result.scalar()
                if tenant:
                    await delete_user_from_tenant_database(user.email, tenant.domain)
                    logger.info(f"Deleted user {user.email} from tenant database {tenant.domain}")
            except Exception as e:
                logger.warning(f"Failed to delete user {user.email} from tenant database: {e}")
                # Continue with control panel deletion even if tenant deletion fails

        # Permanently delete user from control panel
        await db.delete(user)
        await db.commit()

        logger.info(f"User {user.email} (ID: {user.id}) permanently deleted by {current_user.email}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )


@router.post("/bulk-upload", response_model=BulkUploadResponse)
async def bulk_upload_users(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bulk upload users from CSV file"""
    try:
        # Permission check: only super_admin can bulk upload
        if current_user.user_type != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admins can bulk upload users"
            )

        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a CSV"
            )

        # Read CSV file
        contents = await file.read()
        csv_content = contents.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_content))

        # Validate CSV headers
        required_fields = {'email', 'full_name', 'password', 'user_type'}
        if not required_fields.issubset(set(csv_reader.fieldnames or [])):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSV must contain these columns: {', '.join(required_fields)}"
            )

        # Check if bulk upload would exceed Community limit
        user_count_result = await db.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        current_user_count = user_count_result.scalar() or 0

        # Count non-header rows
        csv_content_for_count = contents.decode('utf-8')
        rows_to_add = len(csv_content_for_count.strip().split('\n')) - 1  # Exclude header row

        if current_user_count + rows_to_add > MAX_USERS_COMMUNITY:
            available_slots = MAX_USERS_COMMUNITY - current_user_count
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"GT AI OS Community is limited to {MAX_USERS_COMMUNITY} users. "
                       f"Currently {current_user_count} users exist, only {available_slots} slots available. "
                       "Contact GT Edge AI for Enterprise licensing."
            )

        success_count = 0
        failed_count = 0
        errors = []
        row_num = 1  # Start at 1 for header
        created_users = []  # Track successfully created users for tenant sync

        for row in csv_reader:
            row_num += 1
            email = row.get('email', '').strip().lower()
            full_name = row.get('full_name', '').strip()
            password = row.get('password', '').strip()
            user_type = row.get('user_type', '').strip()
            tenant_id_str = row.get('tenant_id', '').strip()
            tfa_required_str = row.get('tfa_required', '').strip().lower()

            try:
                # Validate required fields
                if not email or not full_name or not password or not user_type:
                    errors.append(BulkUploadError(
                        row=row_num,
                        email=email or 'N/A',
                        reason="Missing required field(s)"
                    ))
                    failed_count += 1
                    continue

                # Validate user_type
                valid_types = ["super_admin", "tenant_admin", "tenant_user"]
                if user_type not in valid_types:
                    errors.append(BulkUploadError(
                        row=row_num,
                        email=email,
                        reason=f"Invalid user_type. Must be one of: {', '.join(valid_types)}"
                    ))
                    failed_count += 1
                    continue

                # Validate password is not empty
                if not password:
                    errors.append(BulkUploadError(
                        row=row_num,
                        email=email,
                        reason="Password cannot be empty"
                    ))
                    failed_count += 1
                    continue

                # Parse tenant_id
                tenant_id = None
                if tenant_id_str:
                    try:
                        tenant_id = int(tenant_id_str)
                    except ValueError:
                        errors.append(BulkUploadError(
                            row=row_num,
                            email=email,
                            reason="Invalid tenant_id (must be a number)"
                        ))
                        failed_count += 1
                        continue

                # Validate tenant requirement for non-super_admin
                if user_type != "super_admin" and not tenant_id:
                    errors.append(BulkUploadError(
                        row=row_num,
                        email=email,
                        reason="tenant_id required for non-super_admin users"
                    ))
                    failed_count += 1
                    continue

                # Check if email already exists
                existing = await db.execute(
                    select(User).where(User.email == email)
                )
                if existing.scalar_one_or_none():
                    errors.append(BulkUploadError(
                        row=row_num,
                        email=email,
                        reason="Email already exists"
                    ))
                    failed_count += 1
                    continue

                # Verify tenant exists if provided
                if tenant_id:
                    tenant_check = await db.execute(
                        select(Tenant).where(Tenant.id == tenant_id)
                    )
                    if not tenant_check.scalar_one_or_none():
                        errors.append(BulkUploadError(
                            row=row_num,
                            email=email,
                            reason=f"Tenant with ID {tenant_id} not found"
                        ))
                        failed_count += 1
                        continue

                # Parse tfa_required (optional field)
                tfa_required = False
                if tfa_required_str:
                    if tfa_required_str in ('true', '1', 'yes', 'y'):
                        tfa_required = True
                    elif tfa_required_str in ('false', '0', 'no', 'n', ''):
                        tfa_required = False
                    else:
                        errors.append(BulkUploadError(
                            row=row_num,
                            email=email,
                            reason=f"Invalid tfa_required value: '{tfa_required_str}'. Use: true/false, 1/0, yes/no"
                        ))
                        failed_count += 1
                        continue

                # Hash password
                hashed_password = pwd_context.hash(password)

                # Get default capabilities based on user type
                default_capabilities = get_default_capabilities(user_type)

                # Create user
                user = User(
                    uuid=str(uuid.uuid4()),
                    email=email,
                    full_name=full_name,
                    hashed_password=hashed_password,
                    user_type=user_type,
                    tenant_id=tenant_id,
                    capabilities=default_capabilities,
                    is_active=True,
                    tfa_required=tfa_required
                )

                db.add(user)
                created_users.append((user, tenant_id))  # Track for tenant sync
                success_count += 1

            except Exception as e:
                logger.error(f"Error processing row {row_num}: {str(e)}")
                errors.append(BulkUploadError(
                    row=row_num,
                    email=email or 'N/A',
                    reason=f"Unexpected error: {str(e)}"
                ))
                failed_count += 1
                continue

        # Commit all successful user creations
        await db.commit()

        # Sync users to tenant databases
        for user_obj, tenant_id in created_users:
            if tenant_id:
                try:
                    # Refresh user to get the committed ID
                    await db.refresh(user_obj)

                    # Get tenant domain
                    tenant_result = await db.execute(
                        select(Tenant).where(Tenant.id == tenant_id)
                    )
                    tenant = tenant_result.scalar()
                    if tenant:
                        await sync_user_to_tenant_database(user_obj, tenant.domain)
                        logger.info(f"Synced bulk user {user_obj.email} to tenant database {tenant.domain}")
                except Exception as e:
                    logger.warning(f"Failed to sync bulk user {user_obj.email} to tenant database: {e}")
                    # Don't fail bulk upload if tenant sync fails

        total_rows = row_num - 1  # Subtract header row

        logger.info(f"Bulk upload completed: {success_count} success, {failed_count} failed")

        return BulkUploadResponse(
            success_count=success_count,
            failed_count=failed_count,
            total_rows=total_rows,
            errors=errors
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk upload: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process bulk upload: {str(e)}"
        )


@router.post("/bulk/reset-tfa", response_model=BulkTFAResponse)
async def bulk_reset_tfa(
    request: BulkTFARequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reset TFA for multiple users (clears tfa_secret and sets tfa_enabled=false)"""
    try:
        # Permission check: only super_admin can bulk reset TFA
        if current_user.user_type != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admins can bulk reset TFA"
            )

        if not request.user_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user IDs provided"
            )

        success_count = 0
        failed_count = 0
        errors = []

        for user_id in request.user_ids:
            try:
                # Get user
                result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    errors.append(BulkTFAError(
                        user_id=user_id,
                        email="Unknown",
                        reason="User not found"
                    ))
                    failed_count += 1
                    continue

                # Reset TFA
                user.tfa_enabled = False
                user.tfa_secret = None
                success_count += 1

                logger.info(f"Reset TFA for user {user.email} (ID: {user.id}) by {current_user.email}")

            except Exception as e:
                logger.error(f"Error resetting TFA for user {user_id}: {str(e)}")
                errors.append(BulkTFAError(
                    user_id=user_id,
                    email=user.email if 'user' in locals() else "Unknown",
                    reason=f"Unexpected error: {str(e)}"
                ))
                failed_count += 1
                continue

        # Commit all changes
        await db.commit()

        logger.info(f"Bulk TFA reset completed: {success_count} success, {failed_count} failed")

        return BulkTFAResponse(
            success_count=success_count,
            failed_count=failed_count,
            errors=errors
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk TFA reset: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset TFA: {str(e)}"
        )


@router.post("/bulk/enforce-tfa", response_model=BulkTFAResponse)
async def bulk_enforce_tfa(
    request: BulkTFARequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Enforce TFA for multiple users (sets tfa_required=true)"""
    try:
        # Permission check: only super_admin can bulk enforce TFA
        if current_user.user_type != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admins can bulk enforce TFA"
            )

        if not request.user_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user IDs provided"
            )

        success_count = 0
        failed_count = 0
        errors = []

        for user_id in request.user_ids:
            try:
                # Get user
                result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    errors.append(BulkTFAError(
                        user_id=user_id,
                        email="Unknown",
                        reason="User not found"
                    ))
                    failed_count += 1
                    continue

                # Enforce TFA
                user.tfa_required = True
                success_count += 1

                logger.info(f"Enforced TFA for user {user.email} (ID: {user.id}) by {current_user.email}")

            except Exception as e:
                logger.error(f"Error enforcing TFA for user {user_id}: {str(e)}")
                errors.append(BulkTFAError(
                    user_id=user_id,
                    email=user.email if 'user' in locals() else "Unknown",
                    reason=f"Unexpected error: {str(e)}"
                ))
                failed_count += 1
                continue

        # Commit all changes
        await db.commit()

        logger.info(f"Bulk TFA enforcement completed: {success_count} success, {failed_count} failed")

        return BulkTFAResponse(
            success_count=success_count,
            failed_count=failed_count,
            errors=errors
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk TFA enforcement: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enforce TFA: {str(e)}"
        )


@router.post("/bulk/disable-tfa", response_model=BulkTFAResponse)
async def bulk_disable_tfa(
    request: BulkTFARequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Disable TFA requirement for multiple users (sets tfa_required=false)"""
    try:
        # Permission check: only super_admin can bulk disable TFA
        if current_user.user_type != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admins can bulk disable TFA"
            )

        if not request.user_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user IDs provided"
            )

        success_count = 0
        failed_count = 0
        errors = []

        for user_id in request.user_ids:
            try:
                # Get user
                result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    errors.append(BulkTFAError(
                        user_id=user_id,
                        email="Unknown",
                        reason="User not found"
                    ))
                    failed_count += 1
                    continue

                # Disable TFA requirement
                user.tfa_required = False
                success_count += 1

                logger.info(f"Disabled TFA requirement for user {user.email} (ID: {user.id}) by {current_user.email}")

            except Exception as e:
                logger.error(f"Error disabling TFA for user {user_id}: {str(e)}")
                errors.append(BulkTFAError(
                    user_id=user_id,
                    email=user.email if 'user' in locals() else "Unknown",
                    reason=f"Unexpected error: {str(e)}"
                ))
                failed_count += 1
                continue

        # Commit all changes
        await db.commit()

        logger.info(f"Bulk TFA disable completed: {success_count} success, {failed_count} failed")

        return BulkTFAResponse(
            success_count=success_count,
            failed_count=failed_count,
            errors=errors
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk TFA disable: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable TFA: {str(e)}"
        )