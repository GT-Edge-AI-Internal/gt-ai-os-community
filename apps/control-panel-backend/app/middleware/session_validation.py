"""
GT 2.0 Control Panel Session Validation Middleware

OWASP/NIST Compliant Server-Side Session Validation (Issue #264)
- Validates session_id from JWT against server-side session state
- Updates session activity on every authenticated request
- Adds X-Session-Warning header when < 5 minutes remaining
- Returns 401 with X-Session-Expired header when session is invalid
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import jwt
import logging

from app.core.config import settings
from app.core.database import sync_session_maker
from app.services.session_service import SessionService

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

    # Paths that don't require session validation
    SKIP_PATHS = [
        "/health",
        "/ready",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/v1/login",
        "/api/v1/logout",
        "/api/auth/password-reset",
        "/api/auth/request-reset",
        "/api/auth/verify-reset-token",
        "/api/v1/public",
        "/api/v1/tfa/verify-login",
        "/api/v1/tfa/session-data",
        "/api/v1/tfa/session-qr-code",
        "/internal/",  # Internal service-to-service calls
    ]

    async def dispatch(self, request: Request, call_next):
        """Process request and validate server-side session"""

        # Skip session validation for public endpoints
        path = request.url.path
        if any(path.startswith(skip) for skip in self.SKIP_PATHS):
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
            session_token = payload.get("session_id")
        except jwt.InvalidTokenError:
            # Let the normal auth flow handle invalid tokens
            return await call_next(request)

        # If no session_id in JWT, skip session validation (backwards compatibility)
        # This allows old tokens without session_id to work until they expire
        if not session_token:
            logger.debug("No session_id in JWT, skipping server-side validation")
            return await call_next(request)

        # Validate session directly (we're in the control panel backend)
        db = sync_session_maker()
        try:
            session_service = SessionService(db)
            is_valid, expiry_reason, seconds_remaining, session_info = session_service.validate_session(
                session_token
            )

            if not is_valid:
                # Session is invalid - return 401 with expiry reason
                logger.info(f"Session expired: {expiry_reason}")
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": f"Session expired ({expiry_reason})",
                        "code": "SESSION_EXPIRED",
                        "expiry_reason": expiry_reason
                    },
                    headers={"X-Session-Expired": expiry_reason or "unknown"}
                )

            # Update session activity
            session_service.update_activity(session_token)

            # Check if we should show warning
            show_warning = session_service.should_show_warning(seconds_remaining) if seconds_remaining else False

        finally:
            db.close()

        # Session is valid - process request
        response = await call_next(request)

        # Add warning header if session is about to expire
        if show_warning and seconds_remaining:
            response.headers["X-Session-Warning"] = str(seconds_remaining)
            logger.debug(f"Session warning: {seconds_remaining}s remaining")

        return response
