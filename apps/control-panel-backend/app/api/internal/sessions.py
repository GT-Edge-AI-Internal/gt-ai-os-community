"""
Internal API for service-to-service session validation

OWASP/NIST Compliant Session Management (Issue #264):
- Server-side session state is the authoritative source of truth
- Called by tenant-backend on every authenticated request
- Returns session status, warning signals, and expiry information
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db, get_sync_db
from app.services.session_service import SessionService
from app.core.config import settings

router = APIRouter(prefix="/internal/sessions", tags=["Internal Sessions"])


async def verify_service_auth(
    x_service_auth: str = Header(None),
    x_service_name: str = Header(None)
) -> bool:
    """Verify service-to-service authentication"""

    if not x_service_auth or not x_service_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Service authentication required"
        )

    # Verify service token (in production, use proper service mesh auth)
    expected_token = settings.SERVICE_AUTH_TOKEN or "internal-service-token"
    if x_service_auth != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service authentication"
        )

    # Verify service is allowed
    allowed_services = ["resource-cluster", "tenant-backend"]
    if x_service_name not in allowed_services:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Service {x_service_name} not authorized"
        )

    return True


class SessionValidateRequest(BaseModel):
    """Request body for session validation"""
    session_token: str


class SessionValidateResponse(BaseModel):
    """Response for session validation"""
    is_valid: bool
    expiry_reason: Optional[str] = None  # 'idle' or 'absolute' if expired
    seconds_remaining: Optional[int] = None  # Seconds until expiry
    show_warning: bool = False  # True if < 5 minutes remaining
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None


class SessionRevokeRequest(BaseModel):
    """Request body for session revocation"""
    session_token: str
    reason: str = "logout"


class SessionRevokeResponse(BaseModel):
    """Response for session revocation"""
    success: bool


class SessionRevokeAllRequest(BaseModel):
    """Request body for revoking all user sessions"""
    user_id: int
    reason: str = "password_change"


class SessionRevokeAllResponse(BaseModel):
    """Response for revoking all user sessions"""
    sessions_revoked: int


@router.post("/validate", response_model=SessionValidateResponse)
def validate_session(
    request: SessionValidateRequest,
    db: SyncSession = Depends(get_sync_db),
    authorized: bool = Depends(verify_service_auth)
):
    """
    Validate a session and return status information.

    Called by tenant-backend on every authenticated request.

    Returns:
    - is_valid: Whether the session is currently valid
    - expiry_reason: 'idle' or 'absolute' if expired
    - seconds_remaining: Time until expiry (for warning calculation)
    - show_warning: True if warning should be shown (< 5 min remaining)
    - user_id, tenant_id: Session context if valid
    """
    session_service = SessionService(db)

    is_valid, expiry_reason, seconds_remaining, session_info = session_service.validate_session(
        request.session_token
    )

    # If valid, update activity timestamp
    if is_valid:
        session_service.update_activity(request.session_token)

    # Determine if warning should be shown
    show_warning = False
    if is_valid and seconds_remaining is not None:
        show_warning = session_service.should_show_warning(seconds_remaining)

    return SessionValidateResponse(
        is_valid=is_valid,
        expiry_reason=expiry_reason,
        seconds_remaining=seconds_remaining,
        show_warning=show_warning,
        user_id=session_info.get('user_id') if session_info else None,
        tenant_id=session_info.get('tenant_id') if session_info else None
    )


@router.post("/revoke", response_model=SessionRevokeResponse)
def revoke_session(
    request: SessionRevokeRequest,
    db: SyncSession = Depends(get_sync_db),
    authorized: bool = Depends(verify_service_auth)
):
    """
    Revoke a session (e.g., on logout).

    Called by tenant-backend or control-panel-backend when user logs out.
    """
    session_service = SessionService(db)
    success = session_service.revoke_session(request.session_token, request.reason)

    return SessionRevokeResponse(success=success)


@router.post("/revoke-all", response_model=SessionRevokeAllResponse)
def revoke_all_user_sessions(
    request: SessionRevokeAllRequest,
    db: SyncSession = Depends(get_sync_db),
    authorized: bool = Depends(verify_service_auth)
):
    """
    Revoke all sessions for a user.

    Called on password change, account lockout, etc.
    """
    session_service = SessionService(db)
    count = session_service.revoke_all_user_sessions(request.user_id, request.reason)

    return SessionRevokeAllResponse(sessions_revoked=count)


@router.post("/cleanup")
def cleanup_expired_sessions(
    db: SyncSession = Depends(get_sync_db),
    authorized: bool = Depends(verify_service_auth)
):
    """
    Clean up expired sessions.

    This endpoint can be called by a scheduled task to mark expired sessions
    as inactive. Not strictly required (validation does this anyway) but
    helps keep the database clean.
    """
    session_service = SessionService(db)
    count = session_service.cleanup_expired_sessions()

    return {"sessions_cleaned": count}
