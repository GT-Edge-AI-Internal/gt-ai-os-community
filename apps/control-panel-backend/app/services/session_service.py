"""
GT 2.0 Session Management Service

OWASP/NIST Compliant Server-Side Session Management (Issue #264)
- Server-side session tracking is authoritative
- Idle timeout: 4 hours (enterprise-friendly)
- Absolute timeout: 8 hours (full work day)
- Warning threshold: 5 minutes before expiry
- Session tokens are SHA-256 hashed before storage
"""

from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import and_
import secrets
import hashlib
import logging

from app.models.session import Session

logger = logging.getLogger(__name__)


class SessionService:
    """
    Service for OWASP/NIST compliant session management.

    Key features:
    - Server-side session state is the single source of truth
    - Session tokens hashed with SHA-256 (never stored in plaintext)
    - Idle timeout tracked via last_activity_at
    - Absolute timeout prevents indefinite session extension
    - Warning signals sent when approaching expiry
    """

    # Session timeout configuration (Enterprise-friendly)
    IDLE_TIMEOUT_MINUTES = 240  # 4 hours - covers meetings, lunch, context-switching
    ABSOLUTE_TIMEOUT_HOURS = 8  # Maximum session lifetime (full work day)
    WARNING_THRESHOLD_MINUTES = 5  # Send warning 5 min before idle expiry

    def __init__(self, db: DBSession):
        self.db = db

    @staticmethod
    def generate_session_token() -> str:
        """
        Generate a cryptographically secure session token.

        Uses secrets.token_urlsafe for CSPRNG (Cryptographically Secure
        Pseudo-Random Number Generator). 32 bytes = 256 bits of entropy.
        """
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token: str) -> str:
        """
        Hash session token with SHA-256 for secure storage.

        OWASP: Never store session tokens in plaintext.
        """
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def create_session(
        self,
        user_id: int,
        tenant_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        app_type: str = 'control_panel'
    ) -> Tuple[str, datetime]:
        """
        Create a new server-side session.

        Args:
            user_id: The authenticated user's ID
            tenant_id: Optional tenant context
            ip_address: Client IP for security auditing
            user_agent: Client user agent for security auditing
            app_type: 'control_panel' or 'tenant_app' to distinguish session source

        Returns:
            Tuple of (session_token, absolute_expires_at)
            The token should be included in JWT claims.
        """
        # Generate session token (this gets sent to client in JWT)
        session_token = self.generate_session_token()
        token_hash = self.hash_token(session_token)

        # Calculate absolute expiration
        now = datetime.now(timezone.utc)
        absolute_expires_at = now + timedelta(hours=self.ABSOLUTE_TIMEOUT_HOURS)

        # Create session record
        session = Session(
            user_id=user_id,
            session_token_hash=token_hash,
            absolute_expires_at=absolute_expires_at,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent and len(user_agent) > 500 else user_agent,
            tenant_id=tenant_id,
            is_active=True,
            app_type=app_type
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        logger.info(f"Created session for user_id={user_id}, tenant_id={tenant_id}, app_type={app_type}, expires={absolute_expires_at}")

        return session_token, absolute_expires_at

    def validate_session(self, session_token: str) -> Tuple[bool, Optional[str], Optional[int], Optional[Dict[str, Any]]]:
        """
        Validate a session and return status information.

        This is the core validation method called on every authenticated request.

        Args:
            session_token: The plaintext session token from JWT

        Returns:
            Tuple of (is_valid, expiry_reason, seconds_until_idle_expiry, session_info)
            - is_valid: Whether the session is currently valid
            - expiry_reason: 'idle' or 'absolute' if expired, None if valid
            - seconds_until_idle_expiry: Seconds until idle timeout (for warning)
            - session_info: Dict with user_id, tenant_id if valid
        """
        token_hash = self.hash_token(session_token)

        # Find active session
        session = self.db.query(Session).filter(
            and_(
                Session.session_token_hash == token_hash,
                Session.is_active == True
            )
        ).first()

        if not session:
            logger.debug(f"Session not found or inactive for token hash prefix: {token_hash[:8]}...")
            return False, 'not_found', None, None

        now = datetime.now(timezone.utc)

        # Ensure session timestamps are timezone-aware for comparison
        absolute_expires = session.absolute_expires_at
        if absolute_expires.tzinfo is None:
            absolute_expires = absolute_expires.replace(tzinfo=timezone.utc)

        last_activity = session.last_activity_at
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)

        # Check absolute timeout first (cannot be extended)
        if now >= absolute_expires:
            self._revoke_session_internal(session, 'absolute_timeout')
            logger.info(f"Session expired (absolute) for user_id={session.user_id}")
            return False, 'absolute', None, {'user_id': session.user_id, 'tenant_id': session.tenant_id}

        # Check idle timeout
        idle_expires_at = last_activity + timedelta(minutes=self.IDLE_TIMEOUT_MINUTES)
        if now >= idle_expires_at:
            self._revoke_session_internal(session, 'idle_timeout')
            logger.info(f"Session expired (idle) for user_id={session.user_id}")
            return False, 'idle', None, {'user_id': session.user_id, 'tenant_id': session.tenant_id}

        # Session is valid - calculate time until idle expiry
        seconds_until_idle = int((idle_expires_at - now).total_seconds())

        # Also check seconds until absolute expiry (use whichever is sooner)
        seconds_until_absolute = int((absolute_expires - now).total_seconds())
        seconds_remaining = min(seconds_until_idle, seconds_until_absolute)

        return True, None, seconds_remaining, {
            'user_id': session.user_id,
            'tenant_id': session.tenant_id,
            'session_id': str(session.id)
        }

    def update_activity(self, session_token: str) -> bool:
        """
        Update the last_activity_at timestamp for a session.

        This should be called on every authenticated request to track idle time.

        Args:
            session_token: The plaintext session token from JWT

        Returns:
            True if session was updated, False if session not found/inactive
        """
        token_hash = self.hash_token(session_token)

        result = self.db.query(Session).filter(
            and_(
                Session.session_token_hash == token_hash,
                Session.is_active == True
            )
        ).update({
            Session.last_activity_at: datetime.now(timezone.utc)
        })

        self.db.commit()

        if result > 0:
            logger.debug(f"Updated activity for session hash prefix: {token_hash[:8]}...")
            return True
        return False

    def revoke_session(self, session_token: str, reason: str = 'logout') -> bool:
        """
        Revoke a session (e.g., on logout).

        Args:
            session_token: The plaintext session token
            reason: Revocation reason ('logout', 'admin_revoke', etc.)

        Returns:
            True if session was revoked, False if not found
        """
        token_hash = self.hash_token(session_token)

        session = self.db.query(Session).filter(
            and_(
                Session.session_token_hash == token_hash,
                Session.is_active == True
            )
        ).first()

        if not session:
            return False

        self._revoke_session_internal(session, reason)
        logger.info(f"Session revoked for user_id={session.user_id}, reason={reason}")
        return True

    def revoke_all_user_sessions(self, user_id: int, reason: str = 'password_change') -> int:
        """
        Revoke all active sessions for a user.

        This should be called on password change, account lockout, etc.

        Args:
            user_id: The user whose sessions to revoke
            reason: Revocation reason

        Returns:
            Number of sessions revoked
        """
        now = datetime.now(timezone.utc)

        result = self.db.query(Session).filter(
            and_(
                Session.user_id == user_id,
                Session.is_active == True
            )
        ).update({
            Session.is_active: False,
            Session.revoked_at: now,
            Session.ended_at: now,  # Always set ended_at when session ends
            Session.revoke_reason: reason
        })

        self.db.commit()

        if result > 0:
            logger.info(f"Revoked {result} sessions for user_id={user_id}, reason={reason}")

        return result

    def get_active_sessions_for_user(self, user_id: int) -> list:
        """
        Get all active sessions for a user.

        Useful for "active sessions" UI where users can see/revoke their sessions.

        Args:
            user_id: The user to query

        Returns:
            List of session dictionaries (without sensitive data)
        """
        sessions = self.db.query(Session).filter(
            and_(
                Session.user_id == user_id,
                Session.is_active == True
            )
        ).all()

        return [s.to_dict() for s in sessions]

    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions (for scheduled maintenance).

        This marks expired sessions as inactive rather than deleting them
        to preserve audit trail.

        Returns:
            Number of sessions cleaned up
        """
        now = datetime.now(timezone.utc)
        idle_cutoff = now - timedelta(minutes=self.IDLE_TIMEOUT_MINUTES)

        # Mark absolute-expired sessions
        absolute_count = self.db.query(Session).filter(
            and_(
                Session.is_active == True,
                Session.absolute_expires_at < now
            )
        ).update({
            Session.is_active: False,
            Session.revoked_at: now,
            Session.ended_at: now,  # Always set ended_at when session ends
            Session.revoke_reason: 'absolute_timeout'
        })

        # Mark idle-expired sessions
        idle_count = self.db.query(Session).filter(
            and_(
                Session.is_active == True,
                Session.last_activity_at < idle_cutoff
            )
        ).update({
            Session.is_active: False,
            Session.revoked_at: now,
            Session.ended_at: now,  # Always set ended_at when session ends
            Session.revoke_reason: 'idle_timeout'
        })

        self.db.commit()

        total = absolute_count + idle_count
        if total > 0:
            logger.info(f"Cleaned up {total} expired sessions (absolute={absolute_count}, idle={idle_count})")

        return total

    def _revoke_session_internal(self, session: Session, reason: str) -> None:
        """Internal helper to revoke a session."""
        now = datetime.now(timezone.utc)
        session.is_active = False
        session.revoked_at = now
        session.ended_at = now  # Always set ended_at when session ends
        session.revoke_reason = reason
        self.db.commit()

    def should_show_warning(self, seconds_remaining: int) -> bool:
        """
        Check if a warning should be shown to the user.

        Args:
            seconds_remaining: Seconds until session expiry

        Returns:
            True if warning should be shown (< 5 minutes remaining)
        """
        return seconds_remaining <= (self.WARNING_THRESHOLD_MINUTES * 60)
