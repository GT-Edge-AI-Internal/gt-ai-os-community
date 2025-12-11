"""
Authentication API endpoints
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import os
import json
import uuid

from app.core.database import get_db, get_sync_db
from app.core.config import settings
from app.models.user import User
from app.models.tenant import Tenant
from app.models.audit import AuditLog, AuditActions
from app.services.session_service import SessionService

logger = structlog.get_logger()
router = APIRouter()
security = HTTPBearer()


# Pydantic models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict
    tenant: dict


class TFASetupResponse(BaseModel):
    """Response when TFA is enforced but not yet configured"""
    requires_tfa: bool = True
    tfa_configured: bool = False
    temp_token: str
    qr_code_uri: str
    manual_entry_key: str
    user_email: str
    user_type: str


class TFAVerificationResponse(BaseModel):
    """Response when TFA is configured and verification is required"""
    requires_tfa: bool = True
    tfa_configured: bool = True
    temp_token: str
    user_email: str
    user_type: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class SwitchTenantRequest(BaseModel):
    tenant_id: int


class SwitchTenantResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    tenant: dict
    user: dict


class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


async def check_login_rate_limit(request: Request, db: AsyncSession) -> None:
    """
    Rate limit login attempts: 5 failed attempts per IP per 5 minutes
    Uses existing AuditLog table (no new tables needed)
    """
    client_ip = request.client.host if request.client else "unknown"
    five_min_ago = datetime.utcnow() - timedelta(minutes=5)

    # Count recent failed login attempts from this IP
    stmt = select(AuditLog).where(
        and_(
            AuditLog.action == AuditActions.USER_LOGIN_FAILED,
            AuditLog.ip_address == client_ip,
            AuditLog.created_at >= five_min_ago
        )
    )
    result = await db.execute(stmt)
    failed_attempts = len(result.scalars().all())

    if failed_attempts >= 5:
        logger.warning("Login rate limit exceeded", ip=client_ip, attempts=failed_attempts)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again in 5 minutes."
        )


# Helper functions
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    from app.core.auth import JWTHandler
    
    token = credentials.credentials
    payload = JWTHandler.decode_token(token)  # This will raise HTTPException if invalid
    
    # Get user from database  
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    stmt = select(User).where(User.id == int(user_id), User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current user and verify admin permissions"""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required"
        )
    return current_user


# API endpoints
@router.post("/login", response_model=Union[LoginResponse, TFASetupResponse, TFAVerificationResponse])
async def login(
    login_data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return JWT token"""
    # Check rate limit FIRST (before any processing)
    await check_login_rate_limit(request, db)

    from passlib.context import CryptContext
    from app.core.auth import JWTHandler

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # Get client IP and app type
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    # Determine app type from header (tenant_app sends this when proxying login)
    app_type = request.headers.get("x-app-type", "control_panel")

    try:
        # Find user by email
        stmt = select(User).where(User.email == login_data.email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            # Log failed login attempt
            audit_log = AuditLog.create_log(
                action=AuditActions.USER_LOGIN_FAILED,
                details={
                    "email": login_data.email,
                    "reason": "user_not_found_or_inactive"
                },
                ip_address=client_ip,
                user_agent=user_agent
            )
            db.add(audit_log)
            await db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Verify password
        if not pwd_context.verify(login_data.password, user.hashed_password):
            # Log failed login attempt
            audit_log = AuditLog.create_log(
                action=AuditActions.USER_LOGIN_FAILED,
                user_id=user.id,
                tenant_id=user.tenant_id,
                details={
                    "email": login_data.email,
                    "reason": "invalid_password"
                },
                ip_address=client_ip,
                user_agent=user_agent
            )
            db.add(audit_log)
            await db.commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # TFA Check: Handle 3 states
        # State 1: TFA Disabled (tfa_required=false, tfa_enabled=false) → Continue to JWT
        # State 2: TFA Enforced but Not Configured (tfa_required=true, tfa_enabled=false) → Mandatory TFA setup
        # State 3: TFA Configured (tfa_enabled=true) → Return temp token for verification

        if user.tfa_enabled:
            # State 3: TFA configured - return temp token for verification
            from app.models.used_temp_token import UsedTempToken
            from fastapi.responses import JSONResponse

            temp_token_id = str(uuid.uuid4())
            temp_payload = {
                "sub": str(user.id),
                "token_id": temp_token_id,
                "exp": datetime.utcnow() + timedelta(minutes=5),
                "iat": datetime.utcnow()
            }
            temp_token = JWTHandler.create_access_token(
                user_id=user.id,
                user_email=user.email,
                user_type=user.user_type,
                current_tenant={"temp": True},
                available_tenants=[],
                capabilities=[]
            )

            # Create server-side TFA session (no QR code needed)
            UsedTempToken.create_tfa_session(
                token_id=temp_token_id,
                user_id=user.id,
                user_email=user.email,
                tfa_configured=True,
                temp_token=temp_token,
                qr_code_uri=None,
                manual_entry_key=None,
                db_session=db,
                expires_minutes=5
            )

            logger.info(
                "TFA verification required",
                user_id=user.id,
                email=user.email
            )

            # Return minimal response with HTTP-only session cookie
            response = JSONResponse(content={
                "requires_tfa": True,
                "tfa_configured": True,
                "user_type": user.user_type
            })
            # Determine if connection is secure (HTTPS or behind HTTPS proxy)
            # This allows TFA to work via local IP (HTTP) while remaining secure over HTTPS
            is_secure = (
                request.url.scheme == "https" or
                request.headers.get("X-Forwarded-Proto", "").lower() == "https"
            )
            response.set_cookie(
                key="tfa_session",
                value=temp_token_id,
                httponly=True,
                secure=is_secure,  # Dynamic: HTTPS when available, HTTP for local dev
                samesite="lax",  # Allow safe navigations (redirects) - required for TFA flow
                max_age=300  # 5 minutes
            )
            return response

        elif user.tfa_required and not user.tfa_enabled:
            # State 2: TFA Enforced but Not Configured - MANDATORY SETUP
            from app.models.used_temp_token import UsedTempToken
            from fastapi.responses import JSONResponse
            from app.core.tfa import get_tfa_manager

            # Get tenant name for QR code branding
            tenant_name = None
            if user.tenant_id:
                tenant_result = await db.execute(
                    select(Tenant).where(Tenant.id == user.tenant_id)
                )
                tenant = tenant_result.scalar_one_or_none()
                if tenant:
                    tenant_name = tenant.name

            # Validate tenant name exists (fail fast - no fallback)
            if not tenant_name:
                logger.error("Tenant name not configured for mandatory TFA setup", user_id=user.id, tenant_id=user.tenant_id)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Tenant configuration error: tenant name not set"
                )

            # Get TFA manager
            tfa_manager = get_tfa_manager()

            # Setup TFA: generate secret, encrypt, create QR code with tenant branding
            encrypted_secret, qr_code_uri, manual_entry_key = tfa_manager.setup_new_tfa(user.email, tenant_name)

            # Save encrypted secret to user (but don't enable yet - wait for verification)
            user.tfa_secret = encrypted_secret
            await db.commit()

            # Create temp token for TFA setup session
            temp_token_id = str(uuid.uuid4())
            temp_token = JWTHandler.create_access_token(
                user_id=user.id,
                user_email=user.email,
                user_type=user.user_type,
                current_tenant={"temp": True},
                available_tenants=[],
                capabilities=[]
            )

            # Create server-side TFA session with QR code for setup
            UsedTempToken.create_tfa_session(
                token_id=temp_token_id,
                user_id=user.id,
                user_email=user.email,
                tfa_configured=False,  # Setup flow, not verification
                temp_token=temp_token,
                qr_code_uri=qr_code_uri,
                manual_entry_key=manual_entry_key,
                db_session=db,
                expires_minutes=5
            )

            # Create audit log
            audit_log = AuditLog.create_log(
                action="user.tfa_mandatory_setup_initiated",
                user_id=user.id,
                tenant_id=user.tenant_id,
                details={"email": user.email, "enforced": True},
                ip_address=client_ip,
                user_agent=user_agent
            )
            db.add(audit_log)
            await db.commit()

            logger.info(
                "Mandatory TFA setup required at login",
                user_id=user.id,
                email=user.email
            )

            # Return TFA setup response with HTTP-only session cookie
            response = JSONResponse(content={
                "requires_tfa": True,
                "tfa_configured": False,  # Indicates setup flow, not verification
                "user_type": user.user_type
            })
            # Determine if connection is secure (HTTPS or behind HTTPS proxy)
            # This allows TFA to work via local IP (HTTP) while remaining secure over HTTPS
            is_secure = (
                request.url.scheme == "https" or
                request.headers.get("X-Forwarded-Proto", "").lower() == "https"
            )
            response.set_cookie(
                key="tfa_session",
                value=temp_token_id,
                httponly=True,
                secure=is_secure,  # Dynamic: HTTPS when available, HTTP for local dev
                samesite="lax",  # Allow safe navigations (redirects) - required for TFA flow
                max_age=300  # 5 minutes
            )
            return response

        # State 1: TFA disabled - continue with normal JWT issuance
        # Get tenant context for JWT token
        # For all users, create simple context based on tenant_id field
        if user.tenant_id:
            # Get tenant info if available
            tenant_result = await db.execute(
                select(Tenant).where(Tenant.id == user.tenant_id)
            )
            tenant = tenant_result.scalar_one_or_none()

            current_tenant_context = {
                "id": str(user.tenant_id),
                "domain": tenant.domain if tenant else f"tenant_{user.tenant_id}",
                "name": tenant.name if tenant else f"Tenant {user.tenant_id}",
                "role": user.user_type,
                "display_name": user.full_name,
                "email": user.email,
                "is_primary": True
            }
            available_tenants = [current_tenant_context]
        else:
            # No tenant assigned
            current_tenant_context = {
                "id": None,
                "domain": "none",
                "name": "No Tenant",
                "role": user.user_type
            }
            available_tenants = []

        # Create server-side session (OWASP/NIST compliance - Issue #264)
        # This is the authoritative source of truth for session validity
        from sqlalchemy.orm import Session as SyncSession
        from app.core.database import sync_session_maker

        sync_db: SyncSession = sync_session_maker()
        try:
            session_service = SessionService(sync_db)
            session_token, absolute_expires_at = session_service.create_session(
                user_id=user.id,
                tenant_id=user.tenant_id,
                ip_address=client_ip,
                user_agent=user_agent,
                app_type=app_type  # 'control_panel' or 'tenant_app' based on X-App-Type header
            )
        finally:
            sync_db.close()

        # Create JWT token with tenant context, user capabilities, and session token
        token = JWTHandler.create_access_token(
            user_id=user.id,
            user_email=user.email,
            user_type=user.user_type,
            current_tenant=current_tenant_context,
            available_tenants=available_tenants,
            capabilities=user.capabilities or [],
            session_token=session_token  # Include session token for server-side validation
        )
        
        # Update last login time
        user.last_login_at = datetime.utcnow()
        
        # Log successful login
        audit_log = AuditLog.create_log(
            action=AuditActions.USER_LOGIN,
            user_id=user.id,
            tenant_id=user.tenant_id,
            details={"email": user.email},
            ip_address=client_ip,
            user_agent=user_agent
        )
        db.add(audit_log)
        await db.commit()
        
        logger.info(
            "User login successful",
            user_id=user.id,
            email=user.email,
            user_type=user.user_type,
            client_ip=client_ip,
            app_type=app_type
        )

        # Last login tracking simplified - just update user's last_login_at (already done above)

        return LoginResponse(
            access_token=token,
            expires_in=settings.JWT_EXPIRES_MINUTES * 60,  # 30 minutes (NIST compliant)
            user={
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "user_type": user.user_type,
                "current_tenant_id": user.current_tenant_id,
                "is_active": user.is_active,
                "available_tenants": available_tenants,
                "tfa_setup_pending": user.tfa_required and not user.tfa_enabled
            },
            tenant=current_tenant_context or {
                "id": None,
                "name": "No Tenant Access",
                "domain": "none",
                "subdomain": "none",
                "role": "none"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login error", error=str(e), email=login_data.email)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/switch-tenant", response_model=SwitchTenantResponse)
async def switch_tenant(
    switch_data: SwitchTenantRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Switch user's current tenant context"""
    from app.core.auth import JWTHandler
    
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    target_tenant_id = switch_data.tenant_id
    
    try:
        # Update user's current tenant
        current_user.current_tenant_id = target_tenant_id
        await db.commit()

        # Get new tenant context
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == target_tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()

        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant {target_tenant_id} not found"
            )

        new_tenant_context = {
            "id": str(target_tenant_id),
            "domain": tenant.domain,
            "name": tenant.name,
            "role": current_user.user_type,
            "display_name": current_user.full_name,
            "email": current_user.email,
            "is_primary": True
        }
        available_tenants = [new_tenant_context]

        # Create new JWT token with updated context and user capabilities
        token = JWTHandler.create_access_token(
            user_id=current_user.id,
            user_email=current_user.email,
            user_type=current_user.user_type,
            current_tenant=new_tenant_context,
            available_tenants=available_tenants,
            capabilities=current_user.capabilities or []
        )
        
        # Log tenant switch
        audit_log = AuditLog.create_log(
            action=AuditActions.USER_LOGIN,  # Using LOGIN as there's no TENANT_SWITCH action
            user_id=current_user.id,
            tenant_id=target_tenant_id,
            details={
                "email": current_user.email,
                "action": "tenant_switch",
                "new_tenant_id": target_tenant_id,
                "tenant_domain": new_tenant_context.get("domain") if new_tenant_context else None
            },
            ip_address=client_ip,
            user_agent=user_agent
        )
        db.add(audit_log)
        await db.commit()
        
        logger.info(
            "Tenant switch successful",
            user_id=current_user.id,
            email=current_user.email,
            new_tenant_id=target_tenant_id,
            tenant_domain=new_tenant_context.get("domain") if new_tenant_context else None,
            client_ip=client_ip
        )
        
        return SwitchTenantResponse(
            access_token=token,
            expires_in=settings.JWT_EXPIRES_MINUTES * 60,  # 30 minutes (NIST compliant)
            user={
                "id": current_user.id,
                "email": current_user.email,
                "full_name": current_user.full_name,
                "user_type": current_user.user_type,
                "current_tenant_id": current_user.current_tenant_id,
                "is_active": current_user.is_active,
                "available_tenants": available_tenants
            },
            tenant=new_tenant_context or {
                "id": target_tenant_id,
                "name": f"Tenant {target_tenant_id}",
                "domain": f"tenant_{target_tenant_id}",
                "role": "unknown"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Tenant switch error", error=str(e), user_id=current_user.id, target_tenant_id=target_tenant_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tenant switch failed"
        )


@router.get("/tenants")
async def get_available_tenants(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of tenants the current user has access to"""
    try:
        # Simplified: Get all active tenants (or just the user's tenant_id)
        available_tenants = []

        if current_user.tenant_id:
            tenant_result = await db.execute(
                select(Tenant).where(Tenant.id == current_user.tenant_id)
            )
            tenant = tenant_result.scalar_one_or_none()

            if tenant:
                available_tenants.append({
                    "id": str(tenant.id),
                    "domain": tenant.domain,
                    "name": tenant.name,
                    "role": current_user.user_type,
                    "is_primary": True,
                    "is_current": current_user.current_tenant_id == tenant.id,
                    "joined_at": current_user.created_at.isoformat() if current_user.created_at else None,
                    "last_accessed": current_user.last_login_at.isoformat() if current_user.last_login_at else None
                })

        return {
            "tenants": available_tenants,
            "current_tenant_id": current_user.current_tenant_id or current_user.tenant_id
        }

    except Exception as e:
        logger.error("Get available tenants error", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get available tenants"
        )


@router.get("/current-context")
async def get_current_context(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user and tenant context"""
    try:
        # Get tenant context
        current_tenant_context = None
        available_tenants = []

        if current_user.tenant_id:
            tenant_result = await db.execute(
                select(Tenant).where(Tenant.id == current_user.tenant_id)
            )
            tenant = tenant_result.scalar_one_or_none()

            if tenant:
                current_tenant_context = {
                    "id": str(tenant.id),
                    "domain": tenant.domain,
                    "name": tenant.name,
                    "role": current_user.user_type,
                    "display_name": current_user.full_name,
                    "email": current_user.email,
                    "is_primary": True
                }
                available_tenants = [current_tenant_context]

        return {
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "full_name": current_user.full_name,
                "user_type": current_user.user_type,
                "current_tenant_id": current_user.current_tenant_id or current_user.tenant_id,
                "is_active": current_user.is_active
            },
            "current_tenant": current_tenant_context,
            "available_tenants": available_tenants
        }

    except Exception as e:
        logger.error("Get current context error", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get current context"
        )


@router.post("/logout")
async def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Logout user and revoke server-side session (OWASP/NIST compliance - Issue #264)"""
    from app.core.auth import JWTHandler
    from app.core.database import sync_session_maker

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Revoke server-side session (Issue #264)
    try:
        token = credentials.credentials
        payload = JWTHandler.decode_token(token)
        session_token = payload.get("session_id")

        if session_token:
            sync_db = sync_session_maker()
            try:
                session_service = SessionService(sync_db)
                session_service.revoke_session(session_token, reason="logout")
                logger.info(
                    "Server-side session revoked on logout",
                    user_id=current_user.id
                )
            finally:
                sync_db.close()
    except Exception as e:
        # Don't fail logout if session revocation fails
        logger.warning(
            "Failed to revoke server-side session on logout",
            error=str(e),
            user_id=current_user.id
        )

    # Log logout
    audit_log = AuditLog.create_log(
        action=AuditActions.USER_LOGOUT,
        user_id=current_user.id,
        tenant_id=current_user.current_tenant_id,  # Use current_tenant_id instead of tenant_id
        details={"email": current_user.email},
        ip_address=client_ip,
        user_agent=user_agent
    )
    db.add(audit_log)
    await db.commit()

    logger.info(
        "User logout",
        user_id=current_user.id,
        email=current_user.email,
        client_ip=client_ip
    )

    return {"success": True, "message": "Logged out successfully"}


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Refresh JWT token with a new expiry time

    NIST/OWASP Compliant Session Management (Issue #242):
    - Extends idle timeout (exp) by 4 hours
    - Preserves absolute timeout (absolute_exp) - cannot be extended
    - If absolute timeout exceeded, rejects refresh and forces re-login
    """
    from app.core.auth import JWTHandler
    from app.core.config import settings
    from datetime import datetime, timezone

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        # Decode the current token to extract all claims
        token = credentials.credentials
        payload = JWTHandler.decode_token(token)

        # NIST/OWASP: Check absolute timeout (Issue #242)
        # If absolute_exp is exceeded, force re-authentication
        absolute_exp = payload.get("absolute_exp")
        if absolute_exp:
            now_timestamp = datetime.now(timezone.utc).timestamp()
            if now_timestamp >= absolute_exp:
                logger.warning(
                    "Token refresh rejected - absolute timeout exceeded",
                    user_id=current_user.id,
                    email=current_user.email,
                    absolute_exp=absolute_exp,
                    current_time=now_timestamp
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session expired. Please log in again.",
                    headers={"X-Session-Expired": "absolute"}
                )

        # Extract tenant context from the original token
        current_tenant = payload.get("current_tenant", {})
        available_tenants = payload.get("available_tenants", [])
        capabilities = payload.get("capabilities", [])

        # Extract session_token to preserve across refreshes (Issue #264)
        session_token = payload.get("session_id")

        # Extract original login time (iat) to preserve across refreshes
        original_iat = payload.get("iat")
        if isinstance(original_iat, (int, float)):
            original_iat = datetime.fromtimestamp(original_iat, tz=timezone.utc)

        # Create a new token with fresh idle timeout, preserving absolute timeout and session
        new_token = JWTHandler.create_access_token(
            user_id=current_user.id,
            user_email=current_user.email,
            user_type=current_user.user_type,
            current_tenant=current_tenant,
            available_tenants=available_tenants,
            capabilities=capabilities,
            # Preserve original login time and absolute expiry
            original_iat=original_iat,
            original_absolute_exp=absolute_exp,
            # Preserve session token for server-side validation (Issue #264)
            session_token=session_token
        )

        # Log token refresh for audit trail
        audit_log = AuditLog.create_log(
            action="user.token_refresh",
            user_id=current_user.id,
            tenant_id=current_user.current_tenant_id,
            details={
                "email": current_user.email,
                "tenant_domain": current_tenant.get("domain") if current_tenant else None,
                "absolute_exp_remaining_hours": round((absolute_exp - datetime.now(timezone.utc).timestamp()) / 3600, 2) if absolute_exp else None
            },
            ip_address=client_ip,
            user_agent=user_agent
        )
        db.add(audit_log)
        await db.commit()

        logger.info(
            "Token refresh successful",
            user_id=current_user.id,
            email=current_user.email,
            client_ip=client_ip,
            absolute_exp_remaining_hours=round((absolute_exp - datetime.now(timezone.utc).timestamp()) / 3600, 2) if absolute_exp else None
        )

        return RefreshTokenResponse(
            access_token=new_token,
            expires_in=settings.JWT_EXPIRES_MINUTES * 60  # 30 minutes in seconds
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Token refresh error", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return {
        "data": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "user_type": current_user.user_type,
            "tenant_id": current_user.tenant_id,
            "is_active": current_user.is_active
        }
    }


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password"""
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    try:
        # Verify current password
        if not pwd_context.verify(password_data.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Basic password validation (can be enhanced later)
        if len(password_data.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        # Hash new password
        new_hashed_password = pwd_context.hash(password_data.new_password)
        current_user.hashed_password = new_hashed_password

        # Revoke all sessions for this user (OWASP/NIST compliance - Issue #264)
        # Password change requires re-authentication on all devices
        from app.core.database import sync_session_maker
        try:
            sync_db = sync_session_maker()
            try:
                session_service = SessionService(sync_db)
                sessions_revoked = session_service.revoke_all_user_sessions(
                    current_user.id,
                    reason="password_change"
                )
                logger.info(
                    "Revoked all sessions on password change",
                    user_id=current_user.id,
                    sessions_revoked=sessions_revoked
                )
            finally:
                sync_db.close()
        except Exception as e:
            # Log but don't fail password change if session revocation fails
            logger.warning(
                "Failed to revoke sessions on password change",
                error=str(e),
                user_id=current_user.id
            )

        # Log password change
        audit_log = AuditLog.create_log(
            action="user.password_change",
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            details={"email": current_user.email},
            ip_address=client_ip,
            user_agent=user_agent
        )
        db.add(audit_log)
        await db.commit()

        logger.info(
            "Password changed successfully",
            user_id=current_user.id,
            email=current_user.email
        )

        return {"success": True, "message": "Password changed successfully. Please log in again."}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Password change error", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )


@router.get("/verify-token")
async def verify_token(current_user: User = Depends(get_current_user)):
    """Verify if token is valid"""
    return {
        "success": True,
        "data": {
            "valid": True,
            "user": current_user.to_dict()
        }
    }


class SessionStatusResponse(BaseModel):
    """Response for session status check"""
    is_valid: bool
    seconds_remaining: int  # Seconds until idle timeout
    show_warning: bool  # True if < 5 minutes remaining
    absolute_seconds_remaining: Optional[int] = None  # Seconds until absolute timeout


@router.get("/session/status", response_model=SessionStatusResponse)
async def get_session_status(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user)
):
    """
    Get current session status for frontend session monitoring.

    This endpoint replaces the complex react-idle-timer approach with a simple
    polling mechanism. Frontend calls this every 60 seconds to check session health.

    Returns:
    - is_valid: Whether session is currently valid
    - seconds_remaining: Seconds until idle timeout (4 hours from last activity)
    - show_warning: True if warning should be shown (< 5 min remaining)
    - absolute_seconds_remaining: Seconds until absolute timeout (8 hours from login)

    The middleware automatically updates last_activity_at on this request,
    effectively acting as a heartbeat.
    """
    from app.core.auth import JWTHandler
    from app.core.database import sync_session_maker

    try:
        token = credentials.credentials
        payload = JWTHandler.decode_token(token)
        session_token = payload.get("session_id")

        if not session_token:
            # Legacy token without session_id - return based on JWT exp only
            exp = payload.get("exp")
            absolute_exp = payload.get("absolute_exp")
            now = datetime.now(timezone.utc).timestamp()

            seconds_remaining = int(exp - now) if exp else 0
            absolute_seconds_remaining = int(absolute_exp - now) if absolute_exp else None

            return SessionStatusResponse(
                is_valid=seconds_remaining > 0,
                seconds_remaining=max(0, seconds_remaining),
                show_warning=0 < seconds_remaining <= 300,  # 5 minutes
                absolute_seconds_remaining=absolute_seconds_remaining
            )

        # Validate server-side session (authoritative)
        sync_db = sync_session_maker()
        try:
            session_service = SessionService(sync_db)
            is_valid, expiry_reason, seconds_remaining, session_info = session_service.validate_session(
                session_token
            )

            # Note: Middleware already updates activity, but we do it here too
            # to ensure this polling endpoint keeps session alive
            if is_valid:
                session_service.update_activity(session_token)

            # Calculate absolute timeout remaining from JWT
            absolute_exp = payload.get("absolute_exp")
            now = datetime.now(timezone.utc).timestamp()
            absolute_seconds_remaining = int(absolute_exp - now) if absolute_exp else None

            # Use the smaller of idle and absolute timeout for warning
            effective_seconds = seconds_remaining or 0
            if absolute_seconds_remaining and absolute_seconds_remaining < effective_seconds:
                effective_seconds = absolute_seconds_remaining

            return SessionStatusResponse(
                is_valid=is_valid,
                seconds_remaining=max(0, effective_seconds),
                show_warning=is_valid and 0 < effective_seconds <= 300,  # 5 minutes
                absolute_seconds_remaining=absolute_seconds_remaining
            )

        finally:
            sync_db.close()

    except Exception as e:
        logger.error("Session status check error", error=str(e), user_id=current_user.id)
        # On error, return a safe default that won't log user out immediately
        return SessionStatusResponse(
            is_valid=True,
            seconds_remaining=14400,  # 4 hours default (matches IDLE_TIMEOUT_MINUTES)
            show_warning=False,
            absolute_seconds_remaining=None
        )