"""
Backup Service - Manages system backups and restoration
"""
import os
import asyncio
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from fastapi import HTTPException, status
import structlog

from app.models.system import BackupRecord, BackupType

logger = structlog.get_logger()


class BackupService:
    """Service for creating and managing system backups"""

    BACKUP_SCRIPT = "/app/scripts/backup/backup-compose.sh"
    RESTORE_SCRIPT = "/app/scripts/backup/restore-compose.sh"
    BACKUP_DIR = os.getenv("GT2_BACKUP_DIR", "/app/backups")

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_backup(
        self,
        backup_type: str = "manual",
        description: str = None,
        created_by: str = None
    ) -> Dict[str, Any]:
        """Create a new system backup"""
        try:
            # Validate backup type
            if backup_type not in ["manual", "pre_update", "scheduled"]:
                raise ValueError(f"Invalid backup type: {backup_type}")

            # Ensure backup directory exists
            os.makedirs(self.BACKUP_DIR, exist_ok=True)

            # Generate backup filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"gt2_backup_{timestamp}.tar.gz"
            backup_path = os.path.join(self.BACKUP_DIR, backup_filename)

            # Get current version
            current_version = await self._get_current_version()

            # Create backup record
            backup_record = BackupRecord(
                backup_type=BackupType[backup_type],
                location=backup_path,
                version=current_version,
                description=description or f"{backup_type.replace('_', ' ').title()} backup",
                created_by=created_by,
                components=self._get_backup_components()
            )

            self.db.add(backup_record)
            await self.db.commit()
            await self.db.refresh(backup_record)

            # Run backup script in background
            asyncio.create_task(
                self._run_backup_process(backup_record.uuid, backup_path)
            )

            logger.info(f"Backup job {backup_record.uuid} created")

            return backup_record.to_dict()

        except Exception as e:
            logger.error(f"Failed to create backup: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create backup: {str(e)}"
            )

    async def list_backups(
        self,
        limit: int = 50,
        offset: int = 0,
        backup_type: str = None
    ) -> Dict[str, Any]:
        """List available backups"""
        try:
            # Build query
            query = select(BackupRecord)

            if backup_type:
                query = query.where(BackupRecord.backup_type == BackupType[backup_type])

            query = query.order_by(desc(BackupRecord.created_at)).limit(limit).offset(offset)

            result = await self.db.execute(query)
            backups = result.scalars().all()

            # Get total count
            count_query = select(BackupRecord)
            if backup_type:
                count_query = count_query.where(BackupRecord.backup_type == BackupType[backup_type])

            count_result = await self.db.execute(count_query)
            total = len(count_result.scalars().all())

            # Calculate total storage used by backups
            backup_list = [b.to_dict() for b in backups]
            storage_used = sum(b.get("size", 0) or 0 for b in backup_list)

            return {
                "backups": backup_list,
                "total": total,
                "limit": limit,
                "offset": offset,
                "storage_used": storage_used
            }

        except Exception as e:
            logger.error(f"Failed to list backups: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list backups: {str(e)}"
            )

    async def get_backup(self, backup_id: str) -> Dict[str, Any]:
        """Get details of a specific backup"""
        stmt = select(BackupRecord).where(BackupRecord.uuid == backup_id)
        result = await self.db.execute(stmt)
        backup = result.scalar_one_or_none()

        if not backup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup {backup_id} not found"
            )

        # Check if file actually exists
        file_exists = os.path.exists(backup.location)

        backup_dict = backup.to_dict()
        backup_dict["file_exists"] = file_exists

        return backup_dict

    async def restore_backup(
        self,
        backup_id: str,
        components: List[str] = None
    ) -> Dict[str, Any]:
        """Restore from a backup"""
        # Get backup record
        stmt = select(BackupRecord).where(BackupRecord.uuid == backup_id)
        result = await self.db.execute(stmt)
        backup = result.scalar_one_or_none()

        if not backup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup {backup_id} not found"
            )

        if not backup.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Backup is marked as invalid and cannot be restored"
            )

        # Check if backup file exists
        if not os.path.exists(backup.location):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup file not found on disk"
            )

        # Verify checksum if available
        if backup.checksum:
            calculated_checksum = await self._calculate_checksum(backup.location)
            if calculated_checksum != backup.checksum:
                backup.is_valid = False
                await self.db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Backup checksum mismatch - file may be corrupted"
                )

        # Run restore in background
        asyncio.create_task(self._run_restore_process(backup.location, components))

        return {
            "message": "Restore initiated",
            "backup_id": backup_id,
            "version": backup.version,
            "components": components or list(backup.components.keys())
        }

    async def delete_backup(self, backup_id: str) -> Dict[str, Any]:
        """Delete a backup"""
        stmt = select(BackupRecord).where(BackupRecord.uuid == backup_id)
        result = await self.db.execute(stmt)
        backup = result.scalar_one_or_none()

        if not backup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup {backup_id} not found"
            )

        # Delete file from disk
        try:
            if os.path.exists(backup.location):
                os.remove(backup.location)
                logger.info(f"Deleted backup file: {backup.location}")
        except Exception as e:
            logger.warning(f"Failed to delete backup file: {str(e)}")

        # Delete database record
        await self.db.delete(backup)
        await self.db.commit()

        return {
            "message": "Backup deleted",
            "backup_id": backup_id
        }

    async def _run_backup_process(self, backup_uuid: str, backup_path: str):
        """Background task to create backup"""
        try:
            # Reload backup record
            stmt = select(BackupRecord).where(BackupRecord.uuid == backup_uuid)
            result = await self.db.execute(stmt)
            backup = result.scalar_one_or_none()

            if not backup:
                logger.error(f"Backup {backup_uuid} not found")
                return

            logger.info(f"Starting backup process: {backup_uuid}")

            # Run backup script
            process = await asyncio.create_subprocess_exec(
                self.BACKUP_SCRIPT,
                backup_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                # Success - calculate file size and checksum
                if os.path.exists(backup_path):
                    backup.size_bytes = os.path.getsize(backup_path)
                    backup.checksum = await self._calculate_checksum(backup_path)
                    logger.info(f"Backup completed: {backup_uuid} ({backup.size_bytes} bytes)")
                else:
                    backup.is_valid = False
                    logger.error(f"Backup file not created: {backup_path}")
            else:
                # Failure
                backup.is_valid = False
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Backup failed: {error_msg}")

            await self.db.commit()

        except Exception as e:
            logger.error(f"Backup process error: {str(e)}")
            # Mark backup as invalid
            stmt = select(BackupRecord).where(BackupRecord.uuid == backup_uuid)
            result = await self.db.execute(stmt)
            backup = result.scalar_one_or_none()
            if backup:
                backup.is_valid = False
                await self.db.commit()

    async def _run_restore_process(self, backup_path: str, components: List[str] = None):
        """Background task to restore from backup"""
        try:
            logger.info(f"Starting restore process from: {backup_path}")

            # Build restore command
            cmd = [self.RESTORE_SCRIPT, backup_path]
            if components:
                cmd.extend(components)

            # Run restore script
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info("Restore completed successfully")
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Restore failed: {error_msg}")

        except Exception as e:
            logger.error(f"Restore process error: {str(e)}")

    async def _get_current_version(self) -> str:
        """Get current system version"""
        try:
            from app.models.system import SystemVersion

            stmt = select(SystemVersion.version).where(
                SystemVersion.is_current == True
            ).order_by(desc(SystemVersion.installed_at)).limit(1)

            result = await self.db.execute(stmt)
            version = result.scalar_one_or_none()

            return version or "unknown"
        except Exception:
            return "unknown"

    def _get_backup_components(self) -> Dict[str, bool]:
        """Get list of components to backup"""
        return {
            "databases": True,
            "docker_volumes": True,
            "configs": True,
            "logs": False  # Logs typically excluded to save space
        }

    async def _calculate_checksum(self, filepath: str) -> str:
        """Calculate SHA256 checksum of a file"""
        try:
            sha256_hash = hashlib.sha256()
            with open(filepath, "rb") as f:
                # Read file in chunks to handle large files
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate checksum: {str(e)}")
            return ""
