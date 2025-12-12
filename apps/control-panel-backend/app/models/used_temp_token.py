"""
Used Temp Token Model for Replay Prevention and TFA Session Management

Tracks temporary tokens that have been used for TFA verification to prevent replay attacks.
Also serves as TFA session storage for server-side session management.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class UsedTempToken(Base):
    """
    Track used temporary tokens to prevent replay attacks.
    Also stores TFA session data for server-side session management.
    """

    __tablename__ = "used_temp_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token_id = Column(String(255), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)  # NULL until token is used
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # TFA Session Data (for server-side session management)
    user_email = Column(String(255), nullable=True)  # User email for TFA session
    tfa_configured = Column(Boolean, nullable=True)  # Whether TFA is already configured
    qr_code_uri = Column(Text, nullable=True)  # QR code data URI (only if setup needed)
    manual_entry_key = Column(String(255), nullable=True)  # Manual entry key (only if setup needed)
    temp_token = Column(Text, nullable=True)  # Actual JWT temp token for verification
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    user = relationship("User", foreign_keys=[user_id])

    @staticmethod
    async def is_token_used(token_id: str, db_session) -> bool:
        """
        Check if token has already been used (async)

        Note: A token is "used" if used_at is NOT NULL.
        Records with used_at=NULL are active TFA sessions, not used tokens.

        Args:
            token_id: Unique token identifier
            db_session: AsyncSession

        Returns:
            True if token has been used (used_at is set), False otherwise
        """
        from sqlalchemy import select

        result = await db_session.execute(
            select(UsedTempToken).where(
                UsedTempToken.token_id == token_id,
                UsedTempToken.used_at.isnot(None),  # Check if used_at is set
                UsedTempToken.expires_at > datetime.now(timezone.utc)
            )
        )
        record = result.scalar_one_or_none()

        return record is not None

    @staticmethod
    def create_tfa_session(
        token_id: str,
        user_id: int,
        user_email: str,
        tfa_configured: bool,
        temp_token: str,
        qr_code_uri: str = None,
        manual_entry_key: str = None,
        db_session = None,
        expires_minutes: int = 5
    ) -> 'UsedTempToken':
        """
        Create a new TFA session (server-side)

        Args:
            token_id: Unique token identifier (session ID)
            user_id: User ID
            user_email: User email
            tfa_configured: Whether TFA is already configured
            temp_token: JWT temp token for verification
            qr_code_uri: QR code data URI (if setup needed)
            manual_entry_key: Manual entry key (if setup needed)
            db_session: Database session
            expires_minutes: Minutes until expiry (default 5)

        Returns:
            Created session record
        """
        now = datetime.now(timezone.utc)
        record = UsedTempToken(
            token_id=token_id,
            user_id=user_id,
            user_email=user_email,
            tfa_configured=tfa_configured,
            temp_token=temp_token,
            qr_code_uri=qr_code_uri,
            manual_entry_key=manual_entry_key,
            created_at=now,
            used_at=None,  # Not used yet
            expires_at=now + timedelta(minutes=expires_minutes)
        )
        db_session.add(record)
        db_session.commit()
        return record

    @staticmethod
    def mark_token_used(token_id: str, user_id: int, db_session, expires_minutes: int = 5) -> None:
        """
        Mark token as used (backward compatibility for existing code)

        Args:
            token_id: Unique token identifier
            user_id: User ID
            db_session: Database session
            expires_minutes: Minutes until expiry (default 5)
        """
        now = datetime.now(timezone.utc)
        record = UsedTempToken(
            token_id=token_id,
            user_id=user_id,
            used_at=now,
            expires_at=now + timedelta(minutes=expires_minutes)
        )
        db_session.add(record)
        db_session.commit()

    @staticmethod
    def cleanup_expired(db_session) -> int:
        """
        Clean up expired token records

        Args:
            db_session: Database session

        Returns:
            Number of records deleted
        """
        now = datetime.now(timezone.utc)
        deleted = db_session.query(UsedTempToken).filter(
            UsedTempToken.expires_at < now
        ).delete()
        db_session.commit()
        return deleted

    def __repr__(self):
        return f"<UsedTempToken(token_id={self.token_id}, user_id={self.user_id}, used_at={self.used_at})>"
