"""
System management models for version tracking, updates, and backups
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, Enum as SQLEnum, BigInteger
from sqlalchemy.sql import func
import uuid
import enum

from app.core.database import Base


class UpdateStatus(str, enum.Enum):
    """Update job status states"""
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    rolled_back = "rolled_back"


class BackupType(str, enum.Enum):
    """Backup types"""
    manual = "manual"
    pre_update = "pre_update"
    scheduled = "scheduled"


class SystemVersion(Base):
    """Track installed system versions"""

    __tablename__ = "system_versions"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    version = Column(String(50), nullable=False, index=True)
    installed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    installed_by = Column(String(255), nullable=True)  # User email or "system"
    is_current = Column(Boolean, default=True, nullable=False)
    release_notes = Column(Text, nullable=True)
    git_commit = Column(String(40), nullable=True)

    def __repr__(self):
        return f"<SystemVersion(id={self.id}, version='{self.version}', current={self.is_current})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "uuid": self.uuid,
            "version": self.version,
            "installed_at": self.installed_at.isoformat() if self.installed_at else None,
            "installed_by": self.installed_by,
            "is_current": self.is_current,
            "release_notes": self.release_notes,
            "git_commit": self.git_commit
        }


class UpdateJob(Base):
    """Track update job execution"""

    __tablename__ = "update_jobs"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True)
    target_version = Column(String(50), nullable=False)
    status = Column(SQLEnum(UpdateStatus), default=UpdateStatus.pending, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    current_stage = Column(String(100), nullable=True)  # e.g., "pulling_images", "backing_up", "migrating_db"
    logs = Column(JSON, default=list, nullable=False)  # Array of log entries with timestamps
    error_message = Column(Text, nullable=True)
    backup_id = Column(Integer, nullable=True)  # Reference to pre-update backup
    started_by = Column(String(255), nullable=True)  # User email
    rollback_reason = Column(Text, nullable=True)

    def __repr__(self):
        return f"<UpdateJob(id={self.id}, version='{self.target_version}', status='{self.status}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "uuid": self.uuid,
            "target_version": self.target_version,
            "status": self.status.value if isinstance(self.status, UpdateStatus) else self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_stage": self.current_stage,
            "logs": self.logs or [],
            "error_message": self.error_message,
            "backup_id": self.backup_id,
            "started_by": self.started_by,
            "rollback_reason": self.rollback_reason
        }

    def add_log(self, message: str, level: str = "info"):
        """Add a log entry"""
        if self.logs is None:
            self.logs = []
        self.logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message
        })


class BackupRecord(Base):
    """Track system backups"""

    __tablename__ = "backup_records"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True)
    backup_type = Column(SQLEnum(BackupType), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    size_bytes = Column(BigInteger, nullable=True)  # Size of backup archive
    location = Column(String(500), nullable=False)  # Full path to backup file
    version = Column(String(50), nullable=True)  # System version at backup time
    components = Column(JSON, default=dict, nullable=False)  # Which components backed up
    checksum = Column(String(64), nullable=True)  # SHA256 checksum
    created_by = Column(String(255), nullable=True)  # User email or "system"
    description = Column(Text, nullable=True)
    is_valid = Column(Boolean, default=True, nullable=False)  # False if corrupted
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Retention policy

    def __repr__(self):
        return f"<BackupRecord(id={self.id}, type='{self.backup_type}', version='{self.version}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "uuid": self.uuid,
            "backup_type": self.backup_type.value if isinstance(self.backup_type, BackupType) else self.backup_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "size_bytes": self.size_bytes,
            "size": self.size_bytes,  # Alias for frontend compatibility
            "size_mb": round(self.size_bytes / (1024 * 1024), 2) if self.size_bytes else None,
            "location": self.location,
            "version": self.version,
            "components": self.components or {},
            "checksum": self.checksum,
            "created_by": self.created_by,
            "description": self.description,
            "is_valid": self.is_valid,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "download_url": f"/api/v1/system/backups/{self.uuid}/download" if self.is_valid else None
        }
