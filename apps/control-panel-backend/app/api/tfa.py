"""
Two-Factor Authentication API endpoints

Handles TFA enable, disable, verification, and status operations.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Cookie
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import uuid
import base64
import io

from app.core.database import get_db
from app.core.auth import get_current_user, JWTHandler
from app.models.user import User
from app.models.audit import AuditLog
from app.models.tfa_rate_limit import TFAVerificationRateLimit
from app.models.used_temp_token import UsedTempToken
from app.core.tfa import get_tfa_manager

logger = structlog.get_logger()
router = APIRouter(prefix="/tfa", tags=["tfa"])


# Pydantic models
class TFAEnableResponse(BaseModel):
    success: bool
    message: str
    qr_code_uri: str
    manual_entry_key: str


class TFAVerifySetupRequest(BaseModel):
    code: str


class TFAVerifySetupResponse(BaseModel):
    success: bool
    message: str


class TFADisableRequest(BaseModel):
    password: str


class TFADisableResponse(BaseModel):
    success: bool
    message: str


class TFAVerifyLoginRequest(BaseModel):
    code: str  # Only code needed - temp_token from session cookie


class TFAVerifyLoginResponse(BaseModel):
    success: bool
    access_token: Optional[str] = None
    expires_in: Optional[int] = None
    user: Optional[dict] = None
    message: Optional[str] = None


class TFAStatusResponse(BaseModel):
    tfa_enabled: bool
    tfa_required: bool
    tfa_status: str


class TFASessionDataResponse(BaseModel):
    user_email: str
    tfa_configured: bool
    qr_code_uri: Optional[str] = None
    manual_entry_key: Optional[str] = None


# Endpoints
@router.get("/session-data", response_model=TFASessionDataResponse)
async def get_tfa_session_data(
    tfa_session: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Get TFA setup data from server-side session.
    Session ID from HTTP-only cookie.
    Used by /verify-tfa page to fetch QR code on mount.
    """
    if not tfa_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No TFA session found"
        )

    # Get session from database
    result = await db.execute(
        select(UsedTempToken).where(UsedTempToken.token_id == tfa_session)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TFA session"
        )

    # Check expiry
    if datetime.now(timezone.utc) > session.expires_at:
        await db.delete(session)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="TFA session expired"
        )

    # Check if already used
    if session.used_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="TFA session already used"
        )

    logger.info(
        "TFA session data retrieved",
        session_id=tfa_session,
        user_id=session.user_id,
        tfa_configured=session.tfa_configured
    )

    return TFASessionDataResponse(
        user_email=session.user_email,
        tfa_configured=session.tfa_configured,
        qr_code_uri=None,  # Security: Don't expose QR code data URI - use blob endpoint
        manual_entry_key=session.manual_entry_key
    )


@router.get("/session-qr-code")
async def get_tfa_session_qr_code(
    tfa_session: Optional[str] = Cookie(None, alias="tfa_session"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get TFA QR code as PNG blob (secure: never exposes TOTP secret to JavaScript).
    Session ID from HTTP-only cookie.
    Returns raw PNG bytes with image/png content type.
    """
    if not tfa_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No TFA session found"
        )

    # Get session from database
    result = await db.execute(
        select(UsedTempToken).where(UsedTempToken.token_id == tfa_session)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TFA session"
        )

    # Check expiry
    if datetime.now(timezone.utc) > session.expires_at:
        await db.delete(session)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="TFA session expired"
        )

    # Check if already used
    if session.used_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="TFA session already used"
        )

    # Check if QR code exists (only for setup flow)
    if not session.qr_code_uri:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No QR code available for this session"
        )

    # Extract base64 PNG data from data URI
    # Format: data:image/png;base64,iVBORw0KGgoAAAANS...
    if not session.qr_code_uri.startswith("data:image/png;base64,"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid QR code format"
        )

    base64_data = session.qr_code_uri.split(",", 1)[1]
    png_bytes = base64.b64decode(base64_data)

    logger.info(
        "TFA QR code blob retrieved",
        session_id=tfa_session,
        user_id=session.user_id,
        size_bytes=len(png_bytes)
    )

    # Return raw PNG bytes
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


#
@router.post("/enable", response_model=TFAEnableResponse)
async def enable_tfa(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Enable TFA for current user (user-initiated from settings)
    Generates TOTP secret and returns QR code for scanning
    """
    try:
        # Check if already enabled
        if current_user.tfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TFA is already enabled for this account"
            )

        # Get tenant name for QR code branding
        tenant_name = None
        if current_user.tenant_id:
            from app.models.tenant import Tenant
            tenant_result = await db.execute(
                select(Tenant).where(Tenant.id == current_user.tenant_id)
            )
            tenant = tenant_result.scalar_one_or_none()
            if tenant:
                tenant_name = tenant.name

        # Validate tenant name exists (fail fast - no fallback)
        if not tenant_name:
            logger.error("Tenant name not configured", user_id=current_user.id, tenant_id=current_user.tenant_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Tenant configuration error: tenant name not set"
            )

        # Get TFA manager
        tfa_manager = get_tfa_manager()

        # Setup TFA: generate secret, encrypt, create QR code with tenant branding
        encrypted_secret, qr_code_uri, manual_entry_key = tfa_manager.setup_new_tfa(current_user.email, tenant_name)

        # Save encrypted secret to user (but don't enable yet - wait for verification)
        current_user.tfa_secret = encrypted_secret
        await db.commit()

        # Create audit log
        audit_log = AuditLog.create_log(
            action="user.tfa_setup_initiated",
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            details={"email": current_user.email},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        db.add(audit_log)
        await db.commit()

        logger.info("TFA setup initiated", user_id=current_user.id, email=current_user.email)

        return TFAEnableResponse(
            success=True,
            message="Scan QR code with Google Authenticator and enter the code to complete setup",
            qr_code_uri=qr_code_uri,
            manual_entry_key=manual_entry_key
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("TFA enable error", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enable TFA"
        )


@router.post("/verify-setup", response_model=TFAVerifySetupResponse)
async def verify_setup(
    verify_data: TFAVerifySetupRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify initial TFA setup code and enable TFA
    """
    try:
        # Check if TFA secret exists
        if not current_user.tfa_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TFA setup not initiated. Call /tfa/enable first."
            )

        # Check if already enabled
        if current_user.tfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TFA is already enabled"
            )

        # Get TFA manager
        tfa_manager = get_tfa_manager()

        # Decrypt secret
        secret = tfa_manager.decrypt_secret(current_user.tfa_secret)

        # Verify code
        if not tfa_manager.verify_totp(secret, verify_data.code):
            logger.warning("TFA setup verification failed", user_id=current_user.id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code"
            )

        # Enable TFA
        current_user.tfa_enabled = True
        await db.commit()

        # Create audit log
        audit_log = AuditLog.create_log(
            action="user.tfa_enabled",
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            details={"email": current_user.email},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        db.add(audit_log)
        await db.commit()

        logger.info("TFA enabled successfully", user_id=current_user.id, email=current_user.email)

        return TFAVerifySetupResponse(
            success=True,
            message="Two-Factor Authentication enabled successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("TFA verify setup error", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify TFA setup"
        )


@router.post("/disable", response_model=TFADisableResponse)
async def disable_tfa(
    disable_data: TFADisableRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Disable TFA for current user (requires password confirmation)
    Only allowed if TFA is not required by admin
    """
    try:
        # Check if TFA is required by admin
        if current_user.tfa_required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot disable TFA - it is required by your administrator"
            )

        # Check if TFA is enabled
        if not current_user.tfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TFA is not enabled"
            )

        # Verify password
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        if not pwd_context.verify(disable_data.password, current_user.hashed_password):
            logger.warning("TFA disable failed - invalid password", user_id=current_user.id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password"
            )

        # Disable TFA and clear secret
        current_user.tfa_enabled = False
        current_user.tfa_secret = None
        await db.commit()

        # Create audit log
        audit_log = AuditLog.create_log(
            action="user.tfa_disabled",
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            details={"email": current_user.email},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        db.add(audit_log)
        await db.commit()

        logger.info("TFA disabled successfully", user_id=current_user.id, email=current_user.email)

        return TFADisableResponse(
            success=True,
            message="Two-Factor Authentication disabled successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("TFA disable error", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable TFA"
        )


@router.post("/verify-login", response_model=TFAVerifyLoginResponse)
async def verify_login(
    verify_data: TFAVerifyLoginRequest,
    request: Request,
    tfa_session: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify TFA code during login and issue final JWT
    Handles both setup (State 2) and verification (State 3)
    Uses session cookie to get temp_token (server-side session)
    """
    try:
        # Get session from cookie
        if not tfa_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No TFA session found"
            )

        # Get session from database
        result = await db.execute(
            select(UsedTempToken).where(UsedTempToken.token_id == tfa_session)
        )
        session = result.scalar_one_or_none()

        if not session or not session.temp_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid TFA session"
            )

        # Check expiry
        if datetime.now(timezone.utc) > session.expires_at:
            await db.delete(session)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="TFA session expired"
            )

        # Check if already used
        if session.used_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="TFA session already used"
            )

        # Get user_id and token_id from session
        user_id = session.user_id
        token_id = session.token_id

        # Check for replay attack
        if await UsedTempToken.is_token_used(token_id, db):
            logger.warning("Temp token replay attempt detected", user_id=user_id, token_id=token_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has already been used"
            )

        # Check rate limiting
        if await TFAVerificationRateLimit.is_rate_limited(user_id, db):
            logger.warning("TFA verification rate limited", user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please wait 60 seconds and try again."
            )

        # Record attempt for rate limiting
        await TFAVerificationRateLimit.record_attempt(user_id, db)

        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )

        # Check if TFA secret exists
        if not user.tfa_secret:
            logger.error("TFA secret missing during verification", user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TFA not properly configured"
            )

        # Get TFA manager
        tfa_manager = get_tfa_manager()

        # Decrypt secret
        secret = tfa_manager.decrypt_secret(user.tfa_secret)

        # Verify TOTP code
        if not tfa_manager.verify_totp(secret, verify_data.code):
            logger.warning("TFA verification failed", user_id=user_id)

            # Create audit log for failed attempt
            audit_log = AuditLog.create_log(
                action="user.tfa_verification_failed",
                user_id=user_id,
                tenant_id=user.tenant_id,
                details={"email": user.email},
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent")
            )
            db.add(audit_log)
            await db.commit()

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code"
            )

        # If TFA was enforced but not enabled, enable it now
        if user.tfa_required and not user.tfa_enabled:
            user.tfa_enabled = True
            logger.info("TFA auto-enabled after mandatory setup", user_id=user_id)

        # Mark session as used
        session.used_at = datetime.now(timezone.utc)
        await db.commit()

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)

        # Get tenant context
        from app.models.tenant import Tenant
        if user.tenant_id:
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
            current_tenant_context = {
                "id": None,
                "domain": "none",
                "name": "No Tenant",
                "role": user.user_type
            }
            available_tenants = []

        # Create final JWT token
        token = JWTHandler.create_access_token(
            user_id=user.id,
            user_email=user.email,
            user_type=user.user_type,
            current_tenant=current_tenant_context,
            available_tenants=available_tenants,
            capabilities=user.capabilities or []
        )

        # Create audit log for successful verification
        audit_log = AuditLog.create_log(
            action="user.tfa_verification_success",
            user_id=user_id,
            tenant_id=user.tenant_id,
            details={"email": user.email},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        db.add(audit_log)
        await db.commit()

        logger.info("TFA verification successful", user_id=user_id, email=user.email)

        # Return response with user object for frontend validation
        from fastapi.responses import JSONResponse
        response = JSONResponse(content={
            "success": True,
            "access_token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "user_type": user.user_type,
                "tenant_id": user.tenant_id,
                "capabilities": user.capabilities or [],
                "tfa_setup_pending": False
            }
        })

        # Delete TFA session cookie
        response.delete_cookie(key="tfa_session")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("TFA verify login error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify TFA code"
        )


@router.get("/status", response_model=TFAStatusResponse)
async def get_tfa_status(
    current_user: User = Depends(get_current_user)
):
    """Get TFA status for current user"""
    return TFAStatusResponse(
        tfa_enabled=current_user.tfa_enabled,
        tfa_required=current_user.tfa_required,
        tfa_status=current_user.tfa_status
    )
