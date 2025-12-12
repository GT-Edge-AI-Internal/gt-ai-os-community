"""
TFA Verification Rate Limiting Model

Tracks failed TFA verification attempts per user with 1-minute rolling windows.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import Column, Integer, DateTime, ForeignKey, select
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TFAVerificationRateLimit(Base):
    """Track TFA verification attempts per user (user-based rate limiting only)"""

    __tablename__ = "tfa_verification_rate_limits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    request_count = Column(Integer, nullable=False, default=1)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    user = relationship("User", foreign_keys=[user_id])

    @staticmethod
    async def is_rate_limited(user_id: int, db_session) -> bool:
        """
        Check if user is rate limited (5 attempts per 1 minute) - async

        Args:
            user_id: User ID to check
            db_session: AsyncSession

        Returns:
            True if rate limited, False otherwise
        """
        now = datetime.now(timezone.utc)

        # Find active rate limit record for this user
        result = await db_session.execute(
            select(TFAVerificationRateLimit).where(
                TFAVerificationRateLimit.user_id == user_id,
                TFAVerificationRateLimit.window_end > now
            )
        )
        record = result.scalar_one_or_none()

        if not record:
            return False

        # Check if limit exceeded (5 attempts per minute)
        return record.request_count >= 5

    @staticmethod
    async def record_attempt(user_id: int, db_session) -> None:
        """
        Record a TFA verification attempt for user - async

        Args:
            user_id: User ID
            db_session: AsyncSession
        """
        now = datetime.now(timezone.utc)

        # Find or create rate limit record
        result = await db_session.execute(
            select(TFAVerificationRateLimit).where(
                TFAVerificationRateLimit.user_id == user_id,
                TFAVerificationRateLimit.window_end > now
            )
        )
        record = result.scalar_one_or_none()

        if record:
            # Increment existing record
            record.request_count += 1
        else:
            # Create new record with 1-minute window
            record = TFAVerificationRateLimit(
                user_id=user_id,
                request_count=1,
                window_start=now,
                window_end=now + timedelta(minutes=1)
            )
            db_session.add(record)

        await db_session.commit()

    @staticmethod
    def cleanup_expired(db_session) -> int:
        """
        Clean up expired rate limit records

        Args:
            db_session: Database session

        Returns:
            Number of records deleted
        """
        now = datetime.utcnow()
        deleted = db_session.query(TFAVerificationRateLimit).filter(
            TFAVerificationRateLimit.window_end < now
        ).delete()
        db_session.commit()
        return deleted

    def __repr__(self):
        return f"<TFAVerificationRateLimit(user_id={self.user_id}, count={self.request_count}, window_end={self.window_end})>"
