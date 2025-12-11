"""
System Management API Endpoints
"""
import asyncio
import subprocess
import json
import shutil
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text
from pydantic import BaseModel, Field
import structlog

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.system import SystemVersion
from app.services.update_service import UpdateService
from app.services.backup_service import BackupService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/system", tags=["System Management"])


# Request/Response Models
class VersionResponse(BaseModel):
    """Response model for version information"""
    version: str
    installed_at: str
    installed_by: Optional[str]
    is_current: bool
    git_commit: Optional[str]


class SystemInfoResponse(BaseModel):
    """Response model for system information"""
    current_version: str
    version: str = ""  # Alias for frontend compatibility - will be set from current_version
    installation_date: str
    container_count: Optional[int] = None
    database_status: str = "healthy"


class CheckUpdateResponse(BaseModel):
    """Response model for update check"""
    update_available: bool
    available: bool = False  # Alias for frontend compatibility
    current_version: str
    latest_version: Optional[str]
    update_type: Optional[str] = None  # "major", "minor", or "patch"
    release_notes: Optional[str]
    published_at: Optional[str]
    released_at: Optional[str] = None  # Alias for frontend compatibility
    download_url: Optional[str]
    checked_at: str  # Timestamp when the check was performed


class ValidationCheckResult(BaseModel):
    """Individual validation check result"""
    name: str
    passed: bool
    message: str
    details: Dict[str, Any] = {}


class ValidateUpdateResponse(BaseModel):
    """Response model for update validation"""
    valid: bool
    checks: List[ValidationCheckResult]
    warnings: List[str] = []
    errors: List[str] = []


class ValidateUpdateRequest(BaseModel):
    """Request model for validating an update"""
    target_version: str = Field(..., description="Target version to validate")


class StartUpdateRequest(BaseModel):
    """Request model for starting an update"""
    target_version: str = Field(..., description="Version to update to")
    create_backup: bool = Field(default=True, description="Create backup before update")


class StartUpdateResponse(BaseModel):
    """Response model for starting an update"""
    update_id: str
    target_version: str
    message: str = "Update initiated"


class UpdateStatusResponse(BaseModel):
    """Response model for update status"""
    update_id: str
    target_version: str
    status: str
    started_at: str
    completed_at: Optional[str]
    current_stage: Optional[str]
    logs: List[Dict[str, Any]] = []
    error_message: Optional[str]
    backup_id: Optional[int]


class RollbackRequest(BaseModel):
    """Request model for rollback"""
    reason: Optional[str] = Field(None, description="Reason for rollback")


class BackupResponse(BaseModel):
    """Response model for backup information"""
    id: int
    uuid: str
    backup_type: str
    created_at: str
    size_mb: Optional[float]  # Keep for backward compatibility
    size: Optional[int] = None  # Size in bytes for frontend
    version: Optional[str]
    description: Optional[str]
    is_valid: bool
    download_url: Optional[str] = None  # Download URL if available


class CreateBackupRequest(BaseModel):
    """Request model for creating a backup"""
    backup_type: str = Field(default="manual", description="Type of backup")
    description: Optional[str] = Field(None, description="Backup description")


class RestoreBackupRequest(BaseModel):
    """Request model for restoring a backup"""
    backup_id: str = Field(..., description="UUID of backup to restore")
    components: Optional[List[str]] = Field(None, description="Components to restore")


class ContainerStatus(BaseModel):
    """Container status from Docker"""
    name: str
    cluster: str  # "admin", "tenant", "resource"
    state: str    # "running", "exited", "paused"
    health: str   # "healthy", "unhealthy", "starting", "none"
    uptime: str
    ports: List[str] = []


class DatabaseStats(BaseModel):
    """PostgreSQL database statistics"""
    connections_active: int
    connections_max: int
    cache_hit_ratio: float
    database_size: str
    transactions_committed: int


class ClusterSummary(BaseModel):
    """Cluster health summary"""
    name: str
    healthy: int
    unhealthy: int
    total: int


class SystemHealthDetailedResponse(BaseModel):
    """Detailed system health response"""
    overall_status: str
    containers: List[ContainerStatus]
    clusters: List[ClusterSummary]
    database: DatabaseStats
    version: str


# Helper Functions
async def _get_container_status() -> List[ContainerStatus]:
    """Get container status from Docker Compose"""
    try:
        # Run docker compose ps with JSON format
        process = await asyncio.create_subprocess_exec(
            "docker", "compose", "ps", "--format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/Users/hackweasel/Documents/GT-2.0"
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error("docker_compose_ps_failed", stderr=stderr.decode())
            return []

        # Parse JSON output (one JSON object per line)
        containers = []
        for line in stdout.decode().strip().split('\n'):
            if not line:
                continue

            try:
                container_data = json.loads(line)
                name = container_data.get("Name", "")
                state = container_data.get("State", "unknown")
                health = container_data.get("Health", "none")

                # Map container name to cluster
                cluster = "unknown"
                if "controlpanel" in name.lower():
                    cluster = "admin"
                elif "tenant" in name.lower() and "controlpanel" not in name.lower():
                    cluster = "tenant"
                elif "resource" in name.lower() or "vllm" in name.lower():
                    cluster = "resource"

                # Extract ports
                ports = []
                publishers = container_data.get("Publishers", [])
                if publishers:
                    for pub in publishers:
                        if pub.get("PublishedPort"):
                            ports.append(f"{pub.get('PublishedPort')}:{pub.get('TargetPort')}")

                # Get uptime from status
                status_text = container_data.get("Status", "")
                uptime = status_text if status_text else "unknown"

                containers.append(ContainerStatus(
                    name=name,
                    cluster=cluster,
                    state=state,
                    health=health if health else "none",
                    uptime=uptime,
                    ports=ports
                ))
            except json.JSONDecodeError as e:
                logger.warning("failed_to_parse_container_json", line=line, error=str(e))
                continue

        return containers

    except Exception as e:
        # Docker is not available inside the container - this is expected behavior
        logger.debug("docker_not_available", error=str(e))
        return []


async def _get_database_stats(db: AsyncSession) -> DatabaseStats:
    """Get PostgreSQL database statistics"""
    try:
        # Get connection and transaction stats
        stats_query = text("""
            SELECT
                numbackends as active_connections,
                xact_commit as transactions_committed,
                ROUND(100.0 * blks_hit / NULLIF(blks_read + blks_hit, 0), 1) as cache_hit_ratio
            FROM pg_stat_database
            WHERE datname = current_database()
        """)

        stats_result = await db.execute(stats_query)
        stats = stats_result.fetchone()

        # Get database size
        size_query = text("SELECT pg_size_pretty(pg_database_size(current_database()))")
        size_result = await db.execute(size_query)
        size = size_result.scalar()

        # Get max connections
        max_conn_query = text("SELECT current_setting('max_connections')::int")
        max_conn_result = await db.execute(max_conn_query)
        max_connections = max_conn_result.scalar()

        return DatabaseStats(
            connections_active=stats[0] if stats else 0,
            connections_max=max_connections if max_connections else 100,
            cache_hit_ratio=float(stats[2]) if stats and stats[2] else 0.0,
            database_size=size if size else "0 bytes",
            transactions_committed=stats[1] if stats else 0
        )

    except Exception as e:
        logger.error("failed_to_get_database_stats", error=str(e))
        # Return default stats on error
        return DatabaseStats(
            connections_active=0,
            connections_max=100,
            cache_hit_ratio=0.0,
            database_size="unknown",
            transactions_committed=0
        )


def _aggregate_clusters(containers: List[ContainerStatus]) -> List[ClusterSummary]:
    """Aggregate container health by cluster"""
    cluster_data = {}

    for container in containers:
        cluster_name = container.cluster

        if cluster_name not in cluster_data:
            cluster_data[cluster_name] = {"healthy": 0, "unhealthy": 0, "total": 0}

        cluster_data[cluster_name]["total"] += 1

        # Consider container healthy if running and health is healthy/none
        if container.state == "running" and container.health in ["healthy", "none"]:
            cluster_data[cluster_name]["healthy"] += 1
        else:
            cluster_data[cluster_name]["unhealthy"] += 1

    # Convert to ClusterSummary objects
    summaries = []
    for cluster_name, data in cluster_data.items():
        summaries.append(ClusterSummary(
            name=cluster_name,
            healthy=data["healthy"],
            unhealthy=data["unhealthy"],
            total=data["total"]
        ))

    return summaries


# Dependency for admin-only access
async def require_admin(current_user: User = Depends(get_current_user)):
    """Ensure user is a super admin"""
    if current_user.user_type != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required"
        )
    return current_user


# Version Endpoints
@router.get("/version", response_model=SystemInfoResponse)
async def get_system_version(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get current system version and information"""
    # Get current version
    stmt = select(SystemVersion).where(
        SystemVersion.is_current == True
    ).order_by(desc(SystemVersion.installed_at)).limit(1)

    result = await db.execute(stmt)
    current = result.scalar_one_or_none()

    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="System version not found. Please run database migrations: alembic upgrade head"
        )

    return SystemInfoResponse(
        current_version=current.version,
        version=current.version,  # Set version same as current_version for frontend compatibility
        installation_date=current.installed_at.isoformat(),
        database_status="healthy"
    )


@router.get("/health-detailed", response_model=SystemHealthDetailedResponse)
async def get_detailed_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get comprehensive system health with real container and database metrics"""
    # Get current version
    stmt = select(SystemVersion).where(
        SystemVersion.is_current == True
    ).order_by(desc(SystemVersion.installed_at)).limit(1)

    result = await db.execute(stmt)
    current_version = result.scalar_one_or_none()
    version_str = current_version.version if current_version else "unknown"

    # Gather system metrics concurrently
    containers = await _get_container_status()
    database_stats = await _get_database_stats(db)
    cluster_summaries = _aggregate_clusters(containers)

    # Determine overall status
    unhealthy_count = sum(cluster.unhealthy for cluster in cluster_summaries)
    overall_status = "healthy" if unhealthy_count == 0 else "degraded"

    return SystemHealthDetailedResponse(
        overall_status=overall_status,
        containers=containers,
        clusters=cluster_summaries,
        database=database_stats,
        version=version_str
    )


# Update Endpoints
@router.get("/check-update", response_model=CheckUpdateResponse)
async def check_for_updates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Check for available system updates"""
    service = UpdateService(db)
    return await service.check_for_updates()


@router.post("/validate-update", response_model=ValidateUpdateResponse)
async def validate_update(
    request: ValidateUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Run pre-update validation checks"""
    service = UpdateService(db)
    return await service.validate_update(request.target_version)


@router.post("/update", response_model=StartUpdateResponse)
async def start_update(
    request: StartUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Start system update process"""
    service = UpdateService(db)
    update_id = await service.execute_update(
        target_version=request.target_version,
        create_backup=request.create_backup,
        started_by=current_user.email
    )

    return StartUpdateResponse(
        update_id=update_id,
        target_version=request.target_version
    )


@router.get("/update/{update_id}/status", response_model=UpdateStatusResponse)
async def get_update_status(
    update_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get status of an update job"""
    service = UpdateService(db)
    status_data = await service.get_update_status(update_id)

    return UpdateStatusResponse(
        update_id=status_data["uuid"],
        target_version=status_data["target_version"],
        status=status_data["status"],
        started_at=status_data["started_at"],
        completed_at=status_data.get("completed_at"),
        current_stage=status_data.get("current_stage"),
        logs=status_data.get("logs", []),
        error_message=status_data.get("error_message"),
        backup_id=status_data.get("backup_id")
    )


@router.post("/update/{update_id}/rollback")
async def rollback_update(
    update_id: str,
    request: RollbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Rollback a failed update"""
    service = UpdateService(db)
    return await service.rollback(update_id, request.reason)


# Backup Endpoints
@router.get("/backups", response_model=Dict[str, Any])
async def list_backups(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    backup_type: Optional[str] = Query(default=None, description="Filter by backup type"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """List available backups with storage information"""
    service = BackupService(db)
    backup_data = await service.list_backups(limit=limit, offset=offset, backup_type=backup_type)

    # Add storage information
    backup_dir = service.BACKUP_DIR
    try:
        # Create backup directory if it doesn't exist
        os.makedirs(backup_dir, exist_ok=True)
        disk_usage = shutil.disk_usage(backup_dir)
        storage = {
            "used": backup_data.get("storage_used", 0),  # From service
            "total": disk_usage.total,
            "available": disk_usage.free
        }
    except Exception as e:
        logger.debug("backup_dir_unavailable", error=str(e))
        storage = {"used": 0, "total": 0, "available": 0}

    backup_data["storage"] = storage
    return backup_data


@router.post("/backups", response_model=BackupResponse)
async def create_backup(
    request: CreateBackupRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new system backup"""
    service = BackupService(db)
    backup_data = await service.create_backup(
        backup_type=request.backup_type,
        description=request.description,
        created_by=current_user.email
    )

    return BackupResponse(
        id=backup_data["id"],
        uuid=backup_data["uuid"],
        backup_type=backup_data["backup_type"],
        created_at=backup_data["created_at"],
        size_mb=backup_data.get("size_mb"),
        size=backup_data.get("size"),
        version=backup_data.get("version"),
        description=backup_data.get("description"),
        is_valid=backup_data["is_valid"],
        download_url=backup_data.get("download_url")
    )


@router.get("/backups/{backup_id}", response_model=BackupResponse)
async def get_backup(
    backup_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get details of a specific backup"""
    service = BackupService(db)
    backup_data = await service.get_backup(backup_id)

    return BackupResponse(
        id=backup_data["id"],
        uuid=backup_data["uuid"],
        backup_type=backup_data["backup_type"],
        created_at=backup_data["created_at"],
        size_mb=backup_data.get("size_mb"),
        size=backup_data.get("size"),
        version=backup_data.get("version"),
        description=backup_data.get("description"),
        is_valid=backup_data["is_valid"],
        download_url=backup_data.get("download_url")
    )


@router.delete("/backups/{backup_id}")
async def delete_backup(
    backup_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete a backup"""
    service = BackupService(db)
    return await service.delete_backup(backup_id)


@router.post("/restore")
async def restore_backup(
    request: RestoreBackupRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Restore system from a backup"""
    service = BackupService(db)
    return await service.restore_backup(
        backup_id=request.backup_id,
        components=request.components
    )
