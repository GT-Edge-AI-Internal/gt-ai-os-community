"""
GT 2.0 Session Validation Middleware

OWASP/NIST Compliant Server-Side Session Validation (Issue #264)
- Validates session_id from JWT against server-side session state
- Updates session activity on every authenticated request
- Adds X-Session-Warning header when < 5 minutes remaining
- Returns 401 with X-Session-Expired header when session is invalid
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import httpx
import logging
import jwt
from app.core.config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)


class SessionValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate server-side sessions on every authenticated request.

    The server-side session is the authoritative source of truth for session validity.
    JWT expiration is secondary - the session can expire before the JWT does.

    Response Headers:
    - X-Session-Warning: <seconds> - Added when session is about to expire
    - X-Session-Expired: idle|absolute - Added on 401 when session expired
    """

    def __init__(self, app, control_panel_url: str = None, service_auth_token: str = None):
        super().__init__(app)
        self.control_panel_url = control_panel_url or settings.control_panel_url or "http://control-panel-backend:8001"
        self.service_auth_token = service_auth_token or settings.service_auth_token or "internal-service-token"

    async def dispatch(self, request: Request, call_next):
        """Process request and validate server-side session"""

        # Skip session validation for public endpoints
        skip_paths = [
            "/health",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/auth/password-reset",
            "/api/v1/public",
            "/docs",
            "/openapi.json",
            "/redoc"
        ]

        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)

        # Extract JWT from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return await call_next(request)

        token = auth_header.split(" ")[1]

        # Decode JWT to get session_id (without verification - that's done elsewhere)
        try:
            # We just need to extract the session_id claim
            # Full JWT verification happens in the auth dependency
            payload = jwt.decode(token, options={"verify_signature": False})
            session_id = payload.get("session_id")
        except jwt.InvalidTokenError:
            # Let the normal auth flow handle invalid tokens
            return await call_next(request)

        # If no session_id in JWT, skip session validation (backwards compatibility)
        # This allows old tokens without session_id to work until they expire
        if not session_id:
            logger.debug("No session_id in JWT, skipping server-side validation")
            return await call_next(request)

        # Validate session with control panel
        validation_result = await self._validate_session(session_id)

        if validation_result is None:
            # Control panel unavailable - FAIL CLOSED for security (OWASP best practice)
            # Reject the request rather than allowing potentially expired sessions through
            logger.error("Session validation failed - control panel unavailable, rejecting request")
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Session validation service unavailable",
                    "code": "SESSION_VALIDATION_UNAVAILABLE"
                },
                headers={"X-Session-Warning": "validation-unavailable"}
            )

        if not validation_result.get("is_valid", False):
            # Session is invalid - return 401 with expiry reason
            # Ensure expiry_reason is never None (causes header encode error)
            expiry_reason = validation_result.get("expiry_reason") or "unknown"
            logger.info(f"Session expired: {expiry_reason}")

            return JSONResponse(
                status_code=401,
                content={
                    "detail": f"Session expired ({expiry_reason})",
                    "code": "SESSION_EXPIRED",
                    "expiry_reason": expiry_reason
                },
                headers={"X-Session-Expired": expiry_reason}
            )

        # Session is valid - process request
        response = await call_next(request)

        # Add warning header if session is about to expire
        if validation_result.get("show_warning", False):
            seconds_remaining = validation_result.get("seconds_remaining", 0)
            response.headers["X-Session-Warning"] = str(seconds_remaining)
            logger.debug(f"Session warning: {seconds_remaining}s remaining")

        return response

    async def _validate_session(self, session_token: str) -> dict | None:
        """
        Validate session with control panel internal API.

        Returns:
            dict with is_valid, expiry_reason, seconds_remaining, show_warning
            or None if control panel is unavailable
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{self.control_panel_url}/internal/sessions/validate",
                    json={"session_token": session_token},
                    headers={
                        "X-Service-Auth": self.service_auth_token,
                        "X-Service-Name": "tenant-backend"
                    }
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Session validation failed: {response.status_code} - {response.text}")
                    return None

        except httpx.RequestError as e:
            logger.error(f"Session validation request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during session validation: {e}")
            return None
