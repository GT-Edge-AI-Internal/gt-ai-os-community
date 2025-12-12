"""
Update Service - Manages system updates and version checking
"""
import os
import json
import asyncio
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from fastapi import HTTPException, status
import structlog

from app.models.system import SystemVersion, UpdateJob, UpdateStatus, BackupRecord
from app.services.backup_service import BackupService

logger = structlog.get_logger()


class UpdateService:
    """Service for checking and executing system updates"""

    GITHUB_API_BASE = "https://api.github.com"
    REPO_OWNER = "GT-Edge-AI-Internal"
    REPO_NAME = "gt-ai-os-community"
    DEPLOY_SCRIPT = "/app/scripts/deploy.sh"
    ROLLBACK_SCRIPT = "/app/scripts/rollback.sh"
    MIN_DISK_SPACE_GB = 5

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_for_updates(self) -> Dict[str, Any]:
        """Check GitHub for available updates"""
        try:
            # Get current version
            current_version = await self._get_current_version()

            # Query GitHub releases API
            url = f"{self.GITHUB_API_BASE}/repos/{self.REPO_OWNER}/{self.REPO_NAME}/releases/latest"

            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                response = await client.get(url)
                if response.status_code == 404:
                    logger.warning("No releases found in repository")
                    return {
                        "update_available": False,
                        "current_version": current_version,
                        "latest_version": None,
                        "release_notes": None,
                        "published_at": None,
                        "download_url": None,
                        "checked_at": datetime.utcnow().isoformat()
                    }

                if response.status_code != 200:
                    logger.error(f"GitHub API error: {response.status_code}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Unable to check for updates from GitHub"
                    )

                release_data = response.json()

            latest_version = release_data.get("tag_name", "").lstrip("v")
            release_notes = release_data.get("body", "")
            published_at = release_data.get("published_at")

            update_available = self._is_newer_version(latest_version, current_version)
            update_type = self._determine_update_type(latest_version, current_version) if update_available else None

            return {
                "update_available": update_available,
                "available": update_available,  # Alias for frontend compatibility
                "current_version": current_version,
                "latest_version": latest_version,
                "update_type": update_type,
                "release_notes": release_notes,
                "published_at": published_at,
                "released_at": published_at,  # Alias for frontend compatibility
                "download_url": release_data.get("html_url"),
                "checked_at": datetime.utcnow().isoformat()
            }

        except httpx.RequestError as e:
            logger.error(f"Network error checking for updates: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Network error while checking for updates"
            )
        except Exception as e:
            logger.error(f"Error checking for updates: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to check for updates: {str(e)}"
            )

    async def validate_update(self, target_version: str) -> Dict[str, Any]:
        """Run pre-update validation checks"""
        validation_results = {
            "valid": True,
            "checks": [],
            "warnings": [],
            "errors": []
        }

        # Check 1: Disk space
        disk_check = await self._check_disk_space()
        validation_results["checks"].append(disk_check)
        if not disk_check["passed"]:
            validation_results["valid"] = False
            validation_results["errors"].append(disk_check["message"])

        # Check 2: Container health
        container_check = await self._check_container_health()
        validation_results["checks"].append(container_check)
        if not container_check["passed"]:
            validation_results["valid"] = False
            validation_results["errors"].append(container_check["message"])

        # Check 3: Database connectivity
        db_check = await self._check_database_connectivity()
        validation_results["checks"].append(db_check)
        if not db_check["passed"]:
            validation_results["valid"] = False
            validation_results["errors"].append(db_check["message"])

        # Check 4: Recent backup exists
        backup_check = await self._check_recent_backup()
        validation_results["checks"].append(backup_check)
        if not backup_check["passed"]:
            validation_results["warnings"].append(backup_check["message"])

        # Check 5: No running updates
        running_update = await self._check_running_updates()
        if running_update:
            validation_results["valid"] = False
            validation_results["errors"].append(
                f"Update job {running_update} is already in progress"
            )

        return validation_results

    async def execute_update(
        self,
        target_version: str,
        create_backup: bool = True,
        started_by: str = None
    ) -> str:
        """Execute system update"""
        # Create update job
        update_job = UpdateJob(
            target_version=target_version,
            status=UpdateStatus.pending,
            started_by=started_by
        )
        update_job.add_log(f"Update to version {target_version} initiated", "info")

        self.db.add(update_job)
        await self.db.commit()
        await self.db.refresh(update_job)

        job_uuid = update_job.uuid

        # Start update in background
        asyncio.create_task(self._run_update_process(job_uuid, target_version, create_backup))

        logger.info(f"Update job {job_uuid} created for version {target_version}")

        return job_uuid

    async def get_update_status(self, update_id: str) -> Dict[str, Any]:
        """Get current status of an update job"""
        stmt = select(UpdateJob).where(UpdateJob.uuid == update_id)
        result = await self.db.execute(stmt)
        update_job = result.scalar_one_or_none()

        if not update_job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Update job {update_id} not found"
            )

        return update_job.to_dict()

    async def rollback(self, update_id: str, reason: str = None) -> Dict[str, Any]:
        """Rollback a failed update"""
        stmt = select(UpdateJob).where(UpdateJob.uuid == update_id)
        result = await self.db.execute(stmt)
        update_job = result.scalar_one_or_none()

        if not update_job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Update job {update_id} not found"
            )

        if update_job.status not in [UpdateStatus.failed, UpdateStatus.in_progress]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot rollback update in status: {update_job.status}"
            )

        update_job.rollback_reason = reason or "Manual rollback requested"
        update_job.add_log(f"Rollback initiated: {update_job.rollback_reason}", "warning")

        await self.db.commit()

        # Execute rollback in background
        asyncio.create_task(self._run_rollback_process(update_id))

        return {"message": "Rollback initiated", "update_id": update_id}

    async def _run_update_process(
        self,
        job_uuid: str,
        target_version: str,
        create_backup: bool
    ):
        """Background task to run update process"""
        try:
            # Reload job from database
            stmt = select(UpdateJob).where(UpdateJob.uuid == job_uuid)
            result = await self.db.execute(stmt)
            update_job = result.scalar_one_or_none()

            if not update_job:
                logger.error(f"Update job {job_uuid} not found")
                return

            update_job.status = UpdateStatus.in_progress
            await self.db.commit()

            # Stage 1: Create pre-update backup
            if create_backup:
                update_job.current_stage = "creating_backup"
                update_job.add_log("Creating pre-update backup", "info")
                await self.db.commit()

                backup_service = BackupService(self.db)
                backup_result = await backup_service.create_backup(
                    backup_type="pre_update",
                    description=f"Pre-update backup before upgrading to {target_version}"
                )
                update_job.backup_id = backup_result["id"]
                update_job.add_log(f"Backup created: {backup_result['uuid']}", "info")
                await self.db.commit()

            # Stage 2: Execute deploy script
            update_job.current_stage = "executing_update"
            update_job.add_log(f"Running deploy script for version {target_version}", "info")
            await self.db.commit()

            # Run deploy.sh script
            process = await asyncio.create_subprocess_exec(
                self.DEPLOY_SCRIPT,
                target_version,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                # Success
                update_job.status = UpdateStatus.completed
                update_job.current_stage = "completed"
                update_job.completed_at = datetime.utcnow()
                update_job.add_log(f"Update to {target_version} completed successfully", "info")

                # Record new version
                await self._record_version(target_version, update_job.started_by)
            else:
                # Failure
                update_job.status = UpdateStatus.failed
                update_job.current_stage = "failed"
                update_job.completed_at = datetime.utcnow()
                error_msg = stderr.decode() if stderr else "Unknown error"
                update_job.error_message = error_msg
                update_job.add_log(f"Update failed: {error_msg}", "error")

            await self.db.commit()

        except Exception as e:
            logger.error(f"Update process error: {str(e)}")
            stmt = select(UpdateJob).where(UpdateJob.uuid == job_uuid)
            result = await self.db.execute(stmt)
            update_job = result.scalar_one_or_none()

            if update_job:
                update_job.status = UpdateStatus.failed
                update_job.error_message = str(e)
                update_job.completed_at = datetime.utcnow()
                update_job.add_log(f"Update process exception: {str(e)}", "error")
                await self.db.commit()

    async def _run_rollback_process(self, job_uuid: str):
        """Background task to run rollback process"""
        try:
            stmt = select(UpdateJob).where(UpdateJob.uuid == job_uuid)
            result = await self.db.execute(stmt)
            update_job = result.scalar_one_or_none()

            if not update_job:
                logger.error(f"Update job {job_uuid} not found")
                return

            update_job.current_stage = "rolling_back"
            update_job.add_log("Executing rollback script", "warning")
            await self.db.commit()

            # Run rollback script
            process = await asyncio.create_subprocess_exec(
                self.ROLLBACK_SCRIPT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                update_job.status = UpdateStatus.rolled_back
                update_job.current_stage = "rolled_back"
                update_job.completed_at = datetime.utcnow()
                update_job.add_log("Rollback completed successfully", "info")
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                update_job.add_log(f"Rollback failed: {error_msg}", "error")

            await self.db.commit()

        except Exception as e:
            logger.error(f"Rollback process error: {str(e)}")

    async def _get_current_version(self) -> str:
        """Get currently installed version"""
        stmt = select(SystemVersion).where(
            SystemVersion.is_current == True
        ).order_by(desc(SystemVersion.installed_at)).limit(1)

        result = await self.db.execute(stmt)
        current = result.scalar_one_or_none()

        return current.version if current else "unknown"

    async def _record_version(self, version: str, installed_by: str):
        """Record new system version"""
        # Mark all versions as not current
        stmt = select(SystemVersion).where(SystemVersion.is_current == True)
        result = await self.db.execute(stmt)
        old_versions = result.scalars().all()

        for old_version in old_versions:
            old_version.is_current = False

        # Create new version record
        new_version = SystemVersion(
            version=version,
            installed_by=installed_by,
            is_current=True
        )
        self.db.add(new_version)
        await self.db.commit()

    def _is_newer_version(self, latest: str, current: str) -> bool:
        """Compare version strings"""
        try:
            latest_parts = [int(x) for x in latest.split(".")]
            current_parts = [int(x) for x in current.split(".")]

            # Pad shorter version with zeros
            max_len = max(len(latest_parts), len(current_parts))
            latest_parts += [0] * (max_len - len(latest_parts))
            current_parts += [0] * (max_len - len(current_parts))

            return latest_parts > current_parts
        except (ValueError, AttributeError):
            return False

    def _determine_update_type(self, latest: str, current: str) -> str:
        """Determine if update is major, minor, or patch"""
        try:
            latest_parts = [int(x) for x in latest.split(".")]
            current_parts = [int(x) for x in current.split(".")]

            # Pad to at least 3 parts for comparison
            while len(latest_parts) < 3:
                latest_parts.append(0)
            while len(current_parts) < 3:
                current_parts.append(0)

            if latest_parts[0] > current_parts[0]:
                return "major"
            elif latest_parts[1] > current_parts[1]:
                return "minor"
            else:
                return "patch"
        except (ValueError, IndexError, AttributeError):
            return "patch"

    async def _check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space"""
        try:
            stat = os.statvfs("/")
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            passed = free_gb >= self.MIN_DISK_SPACE_GB

            return {
                "name": "disk_space",
                "passed": passed,
                "message": f"Available disk space: {free_gb:.2f} GB (minimum: {self.MIN_DISK_SPACE_GB} GB)",
                "details": {"free_gb": round(free_gb, 2)}
            }
        except Exception as e:
            return {
                "name": "disk_space",
                "passed": False,
                "message": f"Failed to check disk space: {str(e)}",
                "details": {}
            }

    async def _check_container_health(self) -> Dict[str, Any]:
        """Check Docker container health"""
        try:
            # Run docker ps to check container status
            process = await asyncio.create_subprocess_exec(
                "docker", "ps", "--format", "{{.Names}}|{{.Status}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return {
                    "name": "container_health",
                    "passed": False,
                    "message": "Failed to check container status",
                    "details": {"error": stderr.decode()}
                }

            containers = stdout.decode().strip().split("\n")
            unhealthy = [c for c in containers if "unhealthy" in c.lower()]

            return {
                "name": "container_health",
                "passed": len(unhealthy) == 0,
                "message": f"Container health check: {len(containers)} running, {len(unhealthy)} unhealthy",
                "details": {"total": len(containers), "unhealthy": len(unhealthy)}
            }
        except Exception as e:
            return {
                "name": "container_health",
                "passed": False,
                "message": f"Failed to check container health: {str(e)}",
                "details": {}
            }

    async def _check_database_connectivity(self) -> Dict[str, Any]:
        """Check database connection"""
        try:
            await self.db.execute(select(1))
            return {
                "name": "database_connectivity",
                "passed": True,
                "message": "Database connection healthy",
                "details": {}
            }
        except Exception as e:
            return {
                "name": "database_connectivity",
                "passed": False,
                "message": f"Database connection failed: {str(e)}",
                "details": {}
            }

    async def _check_recent_backup(self) -> Dict[str, Any]:
        """Check if a recent backup exists"""
        try:
            from datetime import timedelta
            from app.models.system import BackupRecord

            one_day_ago = datetime.utcnow() - timedelta(days=1)
            stmt = select(BackupRecord).where(
                and_(
                    BackupRecord.created_at >= one_day_ago,
                    BackupRecord.is_valid == True
                )
            ).order_by(desc(BackupRecord.created_at)).limit(1)

            result = await self.db.execute(stmt)
            recent_backup = result.scalar_one_or_none()

            if recent_backup:
                return {
                    "name": "recent_backup",
                    "passed": True,
                    "message": f"Recent backup found: {recent_backup.uuid}",
                    "details": {"backup_id": recent_backup.id, "created_at": recent_backup.created_at.isoformat()}
                }
            else:
                return {
                    "name": "recent_backup",
                    "passed": False,
                    "message": "No backup found within last 24 hours",
                    "details": {}
                }
        except Exception as e:
            return {
                "name": "recent_backup",
                "passed": False,
                "message": f"Failed to check for recent backups: {str(e)}",
                "details": {}
            }

    async def _check_running_updates(self) -> Optional[str]:
        """Check for running update jobs"""
        stmt = select(UpdateJob.uuid).where(
            UpdateJob.status == UpdateStatus.in_progress
        ).limit(1)

        result = await self.db.execute(stmt)
        running = result.scalar_one_or_none()

        return running
