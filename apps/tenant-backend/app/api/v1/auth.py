"""
Authentication endpoints for Tenant Backend

Real authentication that connects to Control Panel Backend.
No mocks - following GT 2.0 philosophy of building on real foundations.
"""

import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import jwt
import structlog

from app.core.config import get_settings
from app.core.security import create_capability_token
from app.core.database import get_postgresql_client

logger = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()
settings = get_settings()


# Auth logging helper function (Issue #152)
async def log_auth_event(
    event_type: str,
    email: str,
    user_id: str = None,
    success: bool = True,
    failure_reason: str = None,
    ip_address: str = None,
    user_agent: str = None,
    tenant_domain: str = None
):
    """
    Log authentication events to auth_logs table for security monitoring.

    Args:
        event_type: 'login', 'logout', or 'failed_login'
        email: User's email address
        user_id: User ID (optional for failed logins)
        success: Whether the auth attempt succeeded
        failure_reason: Reason for failure (if applicable)
        ip_address: IP address of the request
        user_agent: User agent string from request
        tenant_domain: Tenant domain for the auth event
    """
    try:
        if not tenant_domain:
            tenant_domain = settings.tenant_domain or "test-company"

        schema_name = f"tenant_{tenant_domain.replace('-', '_')}"

        client = await get_postgresql_client()
        query = f"""
            INSERT INTO {schema_name}.auth_logs (
                user_id,
                email,
                event_type,
                success,
                failure_reason,
                ip_address,
                user_agent,
                tenant_domain
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """

        await client.execute_command(
            query,
            user_id or "unknown",
            email,
            event_type,
            success,
            failure_reason,
            ip_address,
            user_agent,
            tenant_domain
        )

        logger.debug(
            "Auth event logged",
            event_type=event_type,
            email=email,
            success=success,
            tenant=tenant_domain
        )
    except Exception as e:
        # Don't fail the authentication if logging fails
        logger.error(f"Failed to log auth event: {e}", event_type=event_type, email=email)


# Pydantic models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class TokenValidation(BaseModel):
    valid: bool
    user: Optional[dict] = None
    error: Optional[str] = None


class UserInfo(BaseModel):
    id: int
    email: str
    full_name: str
    user_type: str
    tenant_id: Optional[int]
    capabilities: list
    is_active: bool


# Helper functions
async def development_login(login_data: LoginRequest) -> LoginResponse:
    """
    Development authentication that creates a valid JWT token
    for testing purposes when Control Panel is unavailable.
    """
    # Simple development authentication - check for test credentials
    test_users = {
        "gtadmin@test.com": {"password": "password", "role": "admin"},
        "admin@test.com": {"password": "password", "role": "admin"},
        "test@example.com": {"password": "password", "role": "developer"}
    }
    
    user_info = test_users.get(str(login_data.email).lower())
    if not user_info or login_data.password != user_info["password"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create capability token using GT 2.0 security
    # NIST compliant: 30 minutes idle timeout (Issue #242)
    token = create_capability_token(
        user_id=str(login_data.email),
        tenant_id="test-company",
        capabilities=[
            {"resource": "agents", "actions": ["read", "write", "delete"]},
            {"resource": "datasets", "actions": ["read", "write", "delete"]},
            {"resource": "conversations", "actions": ["read", "write", "delete"]}
        ],
        expires_hours=0.5  # 30 minutes (NIST compliant)
    )
    
    user_data = {
        "id": 1,
        "email": str(login_data.email),
        "full_name": "Test User",
        "role": user_info["role"],
        "tenant_id": "test-company",
        "tenant_domain": "test-company",
        "is_active": True
    }
    
    logger.info(
        "Development login successful",
        email=login_data.email,
        tenant_id="test-company"
    )
    
    return LoginResponse(
        access_token=token,
        expires_in=1800,  # 30 minutes (NIST compliant)
        user=user_data
    )
async def verify_token_with_control_panel(token: str) -> Dict[str, Any]:
    """
    Verify JWT token with Control Panel Backend.
    This ensures consistency across the entire GT 2.0 platform.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.control_panel_url}/api/v1/auth/verify-token",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("data", {}).get("valid"):
                    return data["data"]
            
            return {"valid": False, "error": "Invalid token"}
            
    except httpx.RequestError as e:
        logger.error("Failed to verify token with control panel", error=str(e))
        # Fallback to local verification if control panel is unreachable
        try:
            # Use same RSA keys as token creation for consistency
            from app.core.security import verify_capability_token
            payload = verify_capability_token(token)
            if payload:
                return {"valid": True, "user": payload}
            else:
                return {"valid": False, "error": "Invalid token"}
        except Exception as e:
            logger.error(f"Local token verification failed: {e}")
            return {"valid": False, "error": "Token verification failed"}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserInfo:
    """
    Get current user from JWT token.
    Validates with Control Panel for consistency.
    """
    token = credentials.credentials
    validation = await verify_token_with_control_panel(token)
    
    if not validation.get("valid"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=validation.get("error", "Invalid authentication token"),
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_data = validation.get("user", {})
    
    # Ensure user belongs to this tenant
    if settings.tenant_id and str(user_data.get("tenant_id")) != str(settings.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to this tenant"
        )
    
    return UserInfo(
        id=user_data.get("id"),
        email=user_data.get("email"),
        full_name=user_data.get("full_name"),
        user_type=user_data.get("user_type"),
        tenant_id=user_data.get("tenant_id"),
        capabilities=user_data.get("capabilities", []),
        is_active=user_data.get("is_active", True)
    )


# API endpoints
@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    request: Request
):
    """
    Authenticate user via Control Panel Backend.
    For development, falls back to test authentication.
    """
    logger.warning(f"Login attempt for {login_data.email}")
    logger.warning(f"Settings environment: {settings.environment}")
    try:
        # Try Control Panel first
        async with httpx.AsyncClient() as client:
            response = await client.post(
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
                timeout=5.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify user belongs to this tenant
                user = data.get("user", {})
                if settings.tenant_id and str(user.get("tenant_id")) != str(settings.tenant_id):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="User does not belong to this tenant"
                    )
                
                logger.info(
                    "User login successful via Control Panel",
                    user_id=user.get("id"),
                    email=user.get("email"),
                    tenant_id=user.get("tenant_id")
                )

                # Log successful login (Issue #152)
                await log_auth_event(
                    event_type="login",
                    email=user.get("email"),
                    user_id=str(user.get("id")),
                    success=True,
                    ip_address=request.client.host if request.client else "unknown",
                    user_agent=request.headers.get("user-agent", "unknown"),
                    tenant_domain=settings.tenant_domain
                )

                return LoginResponse(
                    access_token=data["access_token"],
                    expires_in=data.get("expires_in", 86400),
                    user=user
                )
            else:
                # Control Panel returned non-200, fall back to development auth
                logger.warning(f"Control Panel returned {response.status_code}, using development auth")
                logger.warning(f"Environment is: {settings.environment}")
                if settings.environment == "development":
                    logger.warning("Calling development_login fallback")
                    return await development_login(login_data)
                else:
                    logger.warning("Not in development mode, raising 401")

                    # Log failed login attempt (Issue #152)
                    await log_auth_event(
                        event_type="failed_login",
                        email=login_data.email,
                        success=False,
                        failure_reason="Invalid credentials",
                        ip_address=request.client.host if request.client else "unknown",
                        user_agent=request.headers.get("user-agent", "unknown"),
                        tenant_domain=settings.tenant_domain
                    )

                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid email or password"
                    )
                
    except (httpx.RequestError, httpx.TimeoutException) as e:
        logger.warning("Control Panel unavailable, using development auth", error=str(e))
        
        # Development fallback authentication
        if settings.environment == "development":
            return await development_login(login_data)
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login error", error=str(e))
        
        # Development fallback for any other errors
        if settings.environment == "development":
            logger.warning("Falling back to development auth due to error")
            return await development_login(login_data)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Login failed"
            )


@router.post("/logout")
async def logout(
    request: Request,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Logout user (forward to Control Panel for audit logging).
    """
    try:
        # Get token from request
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        
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
                    "User logout successful",
                    user_id=current_user.id,
                    email=current_user.email
                )
                return {"success": True, "message": "Logged out successfully"}
            else:
                # Log locally even if Control Panel fails
                logger.warning(
                    "Control Panel logout failed, but logging out locally",
                    user_id=current_user.id,
                    status_code=response.status_code
                )
                return {"success": True, "message": "Logged out successfully"}
                
    except Exception as e:
        logger.error("Logout error", error=str(e), user_id=current_user.id)
        # Always return success for logout
        return {"success": True, "message": "Logged out successfully"}


@router.get("/me")
async def get_current_user_info(current_user: UserInfo = Depends(get_current_user)):
    """
    Get current user information.
    """
    return {
        "success": True,
        "data": current_user.dict()
    }


@router.get("/verify")
async def verify_token(
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Verify if token is valid.
    """
    return {
        "success": True,
        "valid": True,
        "user": current_user.dict()
    }


@router.post("/refresh")
async def refresh_token(
    request: Request,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Refresh authentication token via Control Panel Backend.
    Proxies the refresh request to maintain consistent token lifecycle.
    """
    try:
        # Get current token
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No token provided"
            )

        # Forward to Control Panel Backend
        # Note: Control Panel auth endpoints are at /api/v1/* (not /api/v1/auth/*)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.control_panel_url}/api/v1/refresh",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": request.headers.get("user-agent", "unknown")
                },
                timeout=10.0
            )

            # Handle successful refresh
            if response.status_code == 200:
                data = response.json()
                logger.info(
                    "Token refresh successful",
                    user_id=current_user.id,
                    email=current_user.email
                )
                return {
                    "access_token": data.get("access_token", token),
                    "token_type": "bearer",
                    "expires_in": data.get("expires_in", 86400),
                    "user": current_user.dict()
                }

            # Handle refresh failure (expired or invalid token)
            elif response.status_code == 401:
                logger.warning(
                    "Token refresh failed - token expired or invalid",
                    user_id=current_user.id
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token refresh failed - please login again"
                )

            # Handle other errors
            else:
                logger.error(
                    "Token refresh unexpected response",
                    status_code=response.status_code,
                    user_id=current_user.id
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Token refresh failed"
                )

    except httpx.RequestError as e:
        logger.error("Failed to forward token refresh", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token refresh service unavailable"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Token refresh proxy error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


# Two-Factor Authentication Proxy Endpoints
@router.post("/tfa/enable")
async def enable_tfa_proxy(
    request: Request,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Proxy TFA enable request to Control Panel Backend.
    User-initiated from settings page.
    """
    try:
        # Get token from request
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

        # Forward to Control Panel Backend
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.control_panel_url}/api/v1/tfa/enable",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": request.headers.get("user-agent", "unknown")
                },
                timeout=10.0
            )

            # Return response with original status code
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=response.json().get("detail", "TFA enable failed")
                )

            return response.json()

    except httpx.RequestError as e:
        logger.error("Failed to forward TFA enable request", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TFA service unavailable"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("TFA enable proxy error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="TFA enable failed"
        )


@router.post("/tfa/verify-setup")
async def verify_setup_tfa_proxy(
    data: dict,
    request: Request,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Proxy TFA setup verification to Control Panel Backend.
    """
    try:
        # Get token from request
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

        # Forward to Control Panel Backend
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.control_panel_url}/api/v1/tfa/verify-setup",
                json=data,
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": request.headers.get("user-agent", "unknown")
                },
                timeout=10.0
            )

            # Return response with original status code
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=response.json().get("detail", "TFA verification failed")
                )

            return response.json()

    except httpx.RequestError as e:
        logger.error("Failed to forward TFA verify setup", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TFA service unavailable"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("TFA verify setup proxy error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="TFA verification failed"
        )


@router.post("/tfa/disable")
async def disable_tfa_proxy(
    data: dict,
    request: Request,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Proxy TFA disable request to Control Panel Backend.
    Requires password confirmation.
    """
    try:
        # Get token from request
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

        # Forward to Control Panel Backend
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.control_panel_url}/api/v1/tfa/disable",
                json=data,
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": request.headers.get("user-agent", "unknown")
                },
                timeout=10.0
            )

            # Return response with original status code
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=response.json().get("detail", "TFA disable failed")
                )

            return response.json()

    except httpx.RequestError as e:
        logger.error("Failed to forward TFA disable request", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TFA service unavailable"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("TFA disable proxy error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="TFA disable failed"
        )


@router.post("/tfa/verify-login")
async def verify_login_tfa_proxy(data: dict, request: Request):
    """
    Proxy TFA login verification to Control Panel Backend.
    Called after password verification with temp token + 6-digit code.
    """
    try:
        # Forward to Control Panel Backend
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.control_panel_url}/api/v1/tfa/verify-login",
                json=data,
                headers={
                    "X-Forwarded-For": request.client.host if request.client else "unknown",
                    "User-Agent": request.headers.get("user-agent", "unknown")
                },
                timeout=10.0
            )

            # Return response with original status code
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=response.json().get("detail", "TFA verification failed")
                )

            return response.json()

    except httpx.RequestError as e:
        logger.error("Failed to forward TFA verify login", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TFA service unavailable"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("TFA verify login proxy error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="TFA verification failed"
        )


@router.get("/tfa/status")
async def get_tfa_status_proxy(
    request: Request,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Proxy TFA status request to Control Panel Backend.
    """
    try:
        # Get token from request
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

        # Forward to Control Panel Backend
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.control_panel_url}/api/v1/tfa/status",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": request.headers.get("user-agent", "unknown")
                },
                timeout=10.0
            )

            return response.json()

    except httpx.RequestError as e:
        logger.error("Failed to get TFA status", error=str(e))
        return {"tfa_enabled": False, "tfa_required": False, "tfa_status": "disabled"}
    except Exception as e:
        logger.error("TFA status proxy error", error=str(e))
        return {"tfa_enabled": False, "tfa_required": False, "tfa_status": "disabled"}


class SessionStatusResponse(BaseModel):
    """Response for session status check"""
    is_valid: bool
    seconds_remaining: int  # Seconds until idle timeout
    show_warning: bool  # True if < 5 minutes remaining
    absolute_seconds_remaining: Optional[int] = None  # Seconds until absolute timeout


@router.get("/session/status", response_model=SessionStatusResponse)
async def get_session_status(
    request: Request,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Get current session status for frontend session monitoring.

    Proxies request to Control Panel Backend which is the authoritative
    source for session state. This endpoint replaces the complex react-idle-timer
    approach with a simple polling mechanism.

    Frontend calls this every 60 seconds to check session health.

    Returns:
    - is_valid: Whether session is currently valid
    - seconds_remaining: Seconds until idle timeout (4 hours from last activity)
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
                timeout=10.0  # Increased timeout for proxy/Cloudflare scenarios
            )

            if response.status_code == 200:
                data = response.json()
                return SessionStatusResponse(
                    is_valid=data.get("is_valid", True),
                    seconds_remaining=data.get("seconds_remaining", 14400),  # 4 hours default
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
                    "Unexpected session status response",
                    status_code=response.status_code,
                    user_id=current_user.id
                )
                return SessionStatusResponse(
                    is_valid=True,
                    seconds_remaining=14400,  # 4 hours default (matches IDLE_TIMEOUT_MINUTES)
                    show_warning=False,
                    absolute_seconds_remaining=None
                )

    except httpx.RequestError as e:
        # Control Panel unavailable - FAIL CLOSED for security
        # Return session invalid to force re-authentication
        logger.error(
            "Session status check failed - Control Panel unavailable",
            error=str(e),
            user_id=current_user.id
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session validation service unavailable"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Session status proxy error", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session status check failed"
        )
