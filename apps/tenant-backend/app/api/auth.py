"""
Authentication API endpoints for GT 2.0 Tenant Backend

Handles JWT authentication via Control Panel Backend.
No mocks - following GT 2.0 philosophy of building on real foundations.
"""

import httpx
from datetime import datetime
from typing import Dict, Any, Optional, Union
from fastapi import APIRouter, HTTPException, Depends, Header, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import jwt
import logging

from app.core.config import get_settings
from app.core.security import create_capability_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["authentication"])
security = HTTPBearer(auto_error=False)
settings = get_settings()


# Development authentication function will be defined after class definitions


# Pydantic models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict
    tenant: Optional[dict] = None


class TFASetupResponse(BaseModel):
    """Response when TFA is enforced but not yet configured
    Session data (QR code, temp token) stored server-side in HTTP-only cookie"""
    requires_tfa: bool = True
    tfa_configured: bool = False


class TFAVerificationResponse(BaseModel):
    """Response when TFA is configured and verification is required
    Session data (temp token) stored server-side in HTTP-only cookie"""
    requires_tfa: bool = True
    tfa_configured: bool = True


class UserInfo(BaseModel):
    id: int
    email: str
    full_name: str
    user_type: str
    tenant_id: Optional[int]
    capabilities: list
    is_active: bool


# No development authentication function - violates No Mocks principle
# All authentication MUST go through Control Panel Backend


async def get_tenant_user_uuid_by_email(email: str) -> Optional[str]:
    """
    Query tenant database to get user UUID by email.
    This maps Control Panel users to tenant-specific UUIDs for resource access.
    """
    try:
        from app.core.postgresql_client import get_postgresql_client

        client = await get_postgresql_client()
        if not client or not client._initialized:
            logger.warning("PostgreSQL client not initialized, cannot query tenant user")
            return None

        # Query tenant schema for user by email
        query = f"""
            SELECT id FROM {client.schema_name}.users
            WHERE email = $1
            LIMIT 1
        """

        async with client._pool.acquire() as conn:
            user_uuid = await conn.fetchval(query, email)

        if user_uuid:
            logger.info(f"Found tenant user UUID {user_uuid} for email {email}")
            return str(user_uuid)
        else:
            logger.warning(f"No tenant user found for email {email}")
            return None

    except Exception as e:
        logger.error(f"Error querying tenant user by email {email}: {e}")
        return None


async def verify_token_with_control_panel(token: str) -> Dict[str, Any]:
    """
    Verify JWT token with Control Panel Backend.
    This ensures consistency across the entire GT 2.0 platform.
    No fallbacks - if Control Panel is unavailable, authentication fails.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.control_panel_url}/api/v1/verify-token",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("data", {}).get("valid"):
                    return data["data"]

            return {"valid": False, "error": "Invalid token"}

    except httpx.RequestError as e:
        logger.error(f"Control Panel unavailable for token verification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )


async def get_current_user(
    authorization: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    Extract current user from JWT token.
    Validates with Control Panel for consistency.
    No fallbacks - authentication is required.
    """
    if not authorization or not authorization.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.credentials
    validation = await verify_token_with_control_panel(token)

    if not validation.get("valid"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=validation.get("error", "Invalid authentication token"),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_data = validation.get("user", {})
    user_type = user_data.get("user_type", "")

    # For super_admin users, allow access to any tenant backend
    # They will assume the tenant context of the backend they're accessing
    if user_type == "super_admin":
        logger.info(f"Super admin user {user_data.get('email')} accessing tenant backend {settings.tenant_id}")

        # Override user data with tenant backend context and admin capabilities
        user_data.update({
            'tenant_id': settings.tenant_id,
            'tenant_domain': settings.tenant_domain,
            'tenant_name': f'Tenant {settings.tenant_domain}',
            'tenant_role': 'super_admin',
            'capabilities': [
                {'resource': '*', 'actions': ['*'], 'constraints': {}}
            ]
        })
    # Tenant ID validation removed - any authenticated Control Panel user can access any tenant

    return user_data


@router.post("/auth/login", response_model=Union[LoginResponse, TFASetupResponse, TFAVerificationResponse])
async def login(
    login_data: LoginRequest,
    request: Request,
    response: Response
):
    """
    Authenticate user via Control Panel Backend.
    This ensures a single source of truth for user authentication.
    No fallbacks - if Control Panel is unavailable, login fails.
    """
    try:
        # Forward authentication request to Control Panel
        async with httpx.AsyncClient() as client:
            cp_response = await client.post(
                f"{settings.control_panel_url}/api/v1/login",
                json={
                    "email": login_data.email,
                    "password": login_data.password
                },
                headers={
                    "X-Forwarded-For": request.client.host if request.client else "unknown",
                    "User-Agent": request.headers.get("user-agent", "unknown"),
                    "X-App-Type": "tenant_app"  # Distinguish from control_panel sessions
                },
                timeout=10.0
            )

            if cp_response.status_code == 200:
                data = cp_response.json()

                # Forward Set-Cookie headers from Control Panel to client
                if "set-cookie" in cp_response.headers:
                    response.headers["set-cookie"] = cp_response.headers["set-cookie"]

                # Check if this is a TFA response (setup or verification)
                if data.get("requires_tfa"):
                    logger.info(
                        f"TFA required for user {data.get('user_email')}: "
                        f"configured={data.get('tfa_configured')}"
                    )

                    # Return TFA response directly without modification
                    if data.get("tfa_configured"):
                        # TFA verification required
                        return TFAVerificationResponse(**data)
                    else:
                        # TFA setup required
                        return TFASetupResponse(**data)

                # Handle normal login response (no TFA required)
                user = data.get("user", {})
                user_type = user.get("user_type", "")

                # For super_admin users, allow access to any tenant backend
                # They will assume the tenant context of the backend they're accessing
                if user_type == "super_admin":
                    logger.info(f"Super admin user {user.get('email')} accessing tenant backend {settings.tenant_id}")
                    # Admin users can access any tenant backend - no tenant validation needed
                # Tenant ID validation removed - any authenticated Control Panel user can access any tenant

                logger.info(
                    f"User login successful: {user.get('email')} (ID: {user.get('id')})"
                )

                # Use the original Control Panel JWT token - do not replace with tenant UUID token
                # UUID mapping will be handled at the service level when accessing tenant resources
                access_token = data["access_token"]
                logger.info(f"Using original Control Panel JWT for user {user.get('email')}")

                # Get user's role from tenant database for frontend
                from app.core.permissions import get_user_role
                from app.core.postgresql_client import get_postgresql_client

                pg_client = await get_postgresql_client()
                tenant_role = await get_user_role(pg_client, user.get('email'), settings.tenant_domain)

                # Add tenant role to user object for frontend
                user['role'] = tenant_role
                logger.info(f"Added tenant role '{tenant_role}' to user {user.get('email')}")

                # Create tenant context for frontend
                tenant_info = {
                    "id": settings.tenant_id,
                    "domain": settings.tenant_domain,
                    "name": f"Tenant {settings.tenant_domain}"
                }

                return LoginResponse(
                    access_token=access_token,
                    expires_in=data.get("expires_in", 86400),
                    user=user,
                    tenant=tenant_info
                )

            elif response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            else:
                logger.error(
                    f"Control Panel login failed: {response.status_code} - {response.text}"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Authentication service error"
                )

    except httpx.RequestError as e:
        logger.error(f"Control Panel connection failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/auth/refresh")
async def refresh_token(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Refresh authentication token.
    For now, returns the same token (Control Panel tokens have 24hr expiry).
    """
    # Get current token
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    
    # In a production system, we'd generate a new token here
    # For now, return the existing token since Control Panel tokens last 24 hours
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 86400,  # 24 hours
        "user": current_user
    }


@router.post("/auth/logout")
async def logout(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Logout user (forward to Control Panel for audit logging).
    """
    try:
        # Get token from request
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
        if token:
            # Forward logout to Control Panel for audit logging
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.control_panel_url}/api/v1/auth/logout",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-Forwarded-For": request.client.host if request.client else "unknown",
                        "User-Agent": request.headers.get("user-agent", "unknown")
                    },
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    logger.info(
                        f"User logout successful: {current_user.get('email')} (ID: {current_user.get('id')})"
                    )
        
        # Always return success for logout
        return {"success": True, "message": "Logged out successfully"}
                
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        # Always return success for logout
        return {"success": True, "message": "Logged out successfully"}


@router.get("/auth/me")
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get current user information.
    """
    return {
        "success": True,
        "data": current_user
    }


@router.get("/auth/verify")
async def verify_token(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Verify if token is valid.
    """
    return {
        "success": True,
        "valid": True,
        "user": current_user
    }


# ============================================================================
# PASSWORD RESET PROXY ENDPOINTS
# ============================================================================

@router.post("/auth/request-password-reset")
async def request_password_reset_proxy(
    data: dict,
    request: Request
):
    """
    Proxy password reset request to Control Panel Backend.
    Forwards client IP for rate limiting.
    """
    try:
        # Get client IP for rate limiting
        client_ip = request.client.host if request.client else "unknown"

        # Forward to Control Panel Backend
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.control_panel_url}/api/auth/request-password-reset",
                json=data,
                headers={
                    "X-Forwarded-For": client_ip,
                    "User-Agent": request.headers.get("user-agent", "unknown")
                },
                timeout=10.0
            )

            return response.json()

    except httpx.RequestError as e:
        logger.error(f"Failed to forward password reset request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset service unavailable"
        )
    except Exception as e:
        logger.error(f"Password reset request error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset request failed"
        )


@router.post("/auth/reset-password")
async def reset_password_proxy(data: dict):
    """
    Proxy password reset to Control Panel Backend.
    """
    try:
        # Forward to Control Panel Backend
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.control_panel_url}/api/auth/reset-password",
                json=data,
                timeout=10.0
            )

            # Return response with original status code
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=response.json().get("detail", "Password reset failed")
                )

            return response.json()

    except httpx.RequestError as e:
        logger.error(f"Failed to forward password reset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset service unavailable"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed"
        )


@router.get("/auth/verify-reset-token")
async def verify_reset_token_proxy(token: str):
    """
    Proxy token verification to Control Panel Backend.
    """
    try:
        # Forward to Control Panel Backend
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.control_panel_url}/api/auth/verify-reset-token",
                params={"token": token},
                timeout=10.0
            )

            return response.json()

    except httpx.RequestError as e:
        logger.error(f"Failed to verify reset token: {str(e)}")
        return {"valid": False, "error": "Token verification service unavailable"}
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return {"valid": False, "error": "Token verification failed"}


# ============================================================================
# TFA PROXY ENDPOINTS
# ============================================================================

@router.get("/auth/tfa/session-data")
async def get_tfa_session_data(request: Request, response: Response):
    """
    Proxy TFA session data request to Control Panel Backend.
    Forwards cookies for session validation.
    """
    try:
        # Get cookies from request
        cookie_header = request.headers.get("cookie", "")

        # Forward to Control Panel Backend
        async with httpx.AsyncClient() as client:
            cp_response = await client.get(
                f"{settings.control_panel_url}/api/v1/tfa/session-data",
                headers={
                    "Cookie": cookie_header,
                    "X-Forwarded-For": request.client.host if request.client else "unknown",
                    "User-Agent": request.headers.get("user-agent", "unknown")
                },
                timeout=10.0
            )

            if cp_response.status_code != 200:
                raise HTTPException(
                    status_code=cp_response.status_code,
                    detail=cp_response.json().get("detail", "Failed to get TFA session data")
                )

            return cp_response.json()

    except httpx.RequestError as e:
        logger.error(f"Failed to get TFA session data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TFA service unavailable"
        )


@router.get("/auth/tfa/session-qr-code")
async def get_tfa_session_qr_code(request: Request):
    """
    Proxy TFA QR code blob request to Control Panel Backend.
    Forwards cookies for session validation.
    Returns PNG image blob (never exposes TOTP secret to JavaScript).
    """
    try:
        # Get cookies from request
        cookie_header = request.headers.get("cookie", "")

        # Forward to Control Panel Backend
        async with httpx.AsyncClient() as client:
            cp_response = await client.get(
                f"{settings.control_panel_url}/api/v1/tfa/session-qr-code",
                headers={
                    "Cookie": cookie_header,
                    "X-Forwarded-For": request.client.host if request.client else "unknown",
                    "User-Agent": request.headers.get("user-agent", "unknown")
                },
                timeout=10.0
            )

            if cp_response.status_code != 200:
                raise HTTPException(
                    status_code=cp_response.status_code,
                    detail="Failed to get TFA QR code"
                )

            # Return raw PNG bytes with image/png content type
            from fastapi.responses import Response
            return Response(
                content=cp_response.content,
                media_type="image/png",
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )

    except httpx.RequestError as e:
        logger.error(f"Failed to get TFA QR code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TFA service unavailable"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TFA session data error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get TFA session data"
        )


@router.post("/auth/tfa/verify-login")
async def verify_tfa_login_proxy(
    data: dict,
    request: Request,
    response: Response
):
    """
    Proxy TFA verification to Control Panel Backend.
    Forwards cookies for session validation.
    """
    try:
        # Get cookies from request
        cookie_header = request.headers.get("cookie", "")

        # Forward to Control Panel Backend
        async with httpx.AsyncClient() as client:
            cp_response = await client.post(
                f"{settings.control_panel_url}/api/v1/tfa/verify-login",
                json=data,
                headers={
                    "Cookie": cookie_header,
                    "X-Forwarded-For": request.client.host if request.client else "unknown",
                    "User-Agent": request.headers.get("user-agent", "unknown")
                },
                timeout=10.0
            )

            # Forward Set-Cookie headers (cookie deletion after verification)
            if "set-cookie" in cp_response.headers:
                response.headers["set-cookie"] = cp_response.headers["set-cookie"]

            if cp_response.status_code != 200:
                raise HTTPException(
                    status_code=cp_response.status_code,
                    detail=cp_response.json().get("detail", "TFA verification failed")
                )

            return cp_response.json()

    except httpx.RequestError as e:
        logger.error(f"Failed to verify TFA: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TFA service unavailable"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TFA verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="TFA verification failed"
        )


# ============================================================================
# SESSION STATUS ENDPOINT (Issue #264)
# ============================================================================

class SessionStatusResponse(BaseModel):
    """Response for session status check"""
    is_valid: bool
    seconds_remaining: int  # Seconds until idle timeout
    show_warning: bool  # True if < 5 minutes remaining
    absolute_seconds_remaining: Optional[int] = None  # Seconds until absolute timeout


@router.get("/auth/session/status", response_model=SessionStatusResponse)
async def get_session_status(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get current session status for frontend session monitoring.

    Proxies request to Control Panel Backend which is the authoritative
    source for session state. This endpoint replaces the complex react-idle-timer
    approach with a simple polling mechanism.

    Frontend calls this every 60 seconds to check session health.

    Returns:
    - is_valid: Whether session is currently valid
    - seconds_remaining: Seconds until idle timeout (30 min from last activity)
    - show_warning: True if warning should be shown (< 5 min remaining)
    - absolute_seconds_remaining: Seconds until absolute timeout (8 hours from login)
    """
    try:
        # Get token from request
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No token provided"
            )

        # Forward to Control Panel Backend (authoritative session source)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.control_panel_url}/api/v1/session/status",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": request.headers.get("user-agent", "unknown")
                },
                timeout=5.0  # Short timeout for health check
            )

            if response.status_code == 200:
                data = response.json()
                return SessionStatusResponse(
                    is_valid=data.get("is_valid", True),
                    seconds_remaining=data.get("seconds_remaining", 1800),
                    show_warning=data.get("show_warning", False),
                    absolute_seconds_remaining=data.get("absolute_seconds_remaining")
                )

            elif response.status_code == 401:
                # Session expired - return invalid status
                return SessionStatusResponse(
                    is_valid=False,
                    seconds_remaining=0,
                    show_warning=False,
                    absolute_seconds_remaining=None
                )

            else:
                # Unexpected response - return safe defaults
                logger.warning(
                    f"Unexpected session status response: {response.status_code}"
                )
                return SessionStatusResponse(
                    is_valid=True,
                    seconds_remaining=1800,  # 30 minutes default
                    show_warning=False,
                    absolute_seconds_remaining=None
                )

    except httpx.RequestError as e:
        # Control Panel unavailable - FAIL CLOSED for security
        logger.error(f"Session status check failed - Control Panel unavailable: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session validation service unavailable"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session status proxy error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session status check failed"
        )