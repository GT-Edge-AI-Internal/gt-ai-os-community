"""
GT 2.0 Tenant Provisioning Service

Implements automated tenant infrastructure provisioning following GT 2.0 principles:
- File-based isolation with OS-level permissions
- Perfect tenant separation 
- Zero downtime deployment
- Self-contained security
"""

import os
import asyncio
import logging
# DuckDB removed - PostgreSQL + PGVector unified storage
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.tenant import Tenant
from app.core.config import get_settings
from app.services.message_bus import message_bus

logger = logging.getLogger(__name__)
settings = get_settings()


class TenantProvisioningService:
    """
    Service for automated tenant infrastructure provisioning.
    
    Follows GT 2.0 PostgreSQL + PGVector architecture principles:
    - PostgreSQL schema per tenant (MVCC concurrency)
    - PGVector embeddings per tenant (replaces ChromaDB)
    - Database-level tenant isolation with RLS
    - Encrypted data at rest
    """
    
    def __init__(self):
        self.base_data_path = Path("/data")
        self.message_bus = message_bus
        
    async def provision_tenant(self, tenant_id: int, db: AsyncSession) -> bool:
        """
        Complete tenant provisioning process.
        
        Args:
            tenant_id: Database ID of tenant to provision
            db: Database session
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get tenant details
            result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                logger.error(f"Tenant {tenant_id} not found")
                return False
            
            logger.info(f"Starting provisioning for tenant {tenant.domain}")
            
            # Step 1: Create tenant directory structure
            await self._create_directory_structure(tenant)
            
            # Step 2: Initialize PostgreSQL schema
            await self._initialize_database(tenant)
            
            # Step 3: Setup PGVector extensions (handled by schema creation)
            
            # Step 4: Create configuration files
            await self._create_configuration_files(tenant)
            
            # Step 5: Setup OS user (for production)
            await self._setup_os_user(tenant)
            
            # Step 6: Send provisioning message to tenant cluster
            await self._notify_tenant_cluster(tenant)
            
            # Step 7: Update tenant status
            await self._update_tenant_status(tenant_id, "active", db)
            
            logger.info(f"Tenant {tenant.domain} provisioned successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to provision tenant {tenant_id}: {e}")
            await self._update_tenant_status(tenant_id, "failed", db)
            return False
    
    async def _create_directory_structure(self, tenant: Tenant) -> None:
        """Create tenant directory structure with proper permissions"""
        tenant_path = self.base_data_path / tenant.domain
        
        # Create main directories
        directories = [
            tenant_path,
            tenant_path / "shared",
            tenant_path / "shared" / "models",
            tenant_path / "shared" / "configs", 
            tenant_path / "users",
            tenant_path / "sessions",
            tenant_path / "documents",
            tenant_path / "vector_storage",
            tenant_path / "backups"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            
        logger.info(f"Created directory structure for {tenant.domain}")
    
    async def _initialize_database(self, tenant: Tenant) -> None:
        """Initialize PostgreSQL schema for tenant"""
        schema_name = f"tenant_{tenant.domain.replace('-', '_').replace('.', '_')}"
        
        # PostgreSQL schema creation is handled by the main database migration scripts
        # Schema name follows pattern: tenant_{domain}
        
        logger.info(f"PostgreSQL schema initialization for {tenant.domain} handled by migration scripts")
        return True
    
    async def _setup_vector_storage(self, tenant: Tenant) -> None:
        """Setup PGVector extensions for tenant (handled by PostgreSQL migration)"""
        # PGVector extensions handled by PostgreSQL migration scripts
        # Vector storage is now unified within PostgreSQL schema
        
        logger.info(f"PGVector setup for {tenant.domain} handled by PostgreSQL migration scripts")
    
    async def _create_configuration_files(self, tenant: Tenant) -> None:
        """Create tenant-specific configuration files"""
        tenant_path = self.base_data_path / tenant.domain
        config_path = tenant_path / "shared" / "configs"
        
        # Main tenant configuration
        tenant_config = {
            "tenant_id": tenant.uuid,
            "tenant_domain": tenant.domain,
            "tenant_name": tenant.name,
            "template": tenant.template,
            "max_users": tenant.max_users,
            "resource_limits": tenant.resource_limits,
            "postgresql_schema": f"tenant_{tenant.domain.replace('-', '_').replace('.', '_')}",
            "vector_storage_path": str(tenant_path / "vector_storage"),
            "documents_path": str(tenant_path / "documents"),
            "created_at": datetime.utcnow().isoformat(),
            "encryption_enabled": True,
            "backup_enabled": True
        }
        
        config_file = config_path / "tenant_config.json"
        with open(config_file, 'w') as f:
            json.dump(tenant_config, f, indent=2)
        
        os.chmod(config_file, 0o600)
        
        # Environment file for tenant backend
        env_config = f"""
# GT 2.0 Tenant Configuration - {tenant.domain}
ENVIRONMENT=production
TENANT_ID={tenant.uuid}
TENANT_DOMAIN={tenant.domain}
DATABASE_URL=postgresql://gt2_tenant_user:gt2_tenant_dev_password@tenant-pgbouncer:5432/gt2_tenants
POSTGRES_SCHEMA=tenant_{tenant.domain.replace('-', '_').replace('.', '_')}
DOCUMENTS_PATH={tenant_path}/documents

# Security
SECRET_KEY=will_be_replaced_with_vault_key
ENCRYPT_DATA=true
SECURE_DELETE=true

# Resource Limits
MAX_USERS={tenant.max_users}
MAX_STORAGE_GB={tenant.resource_limits.get('max_storage_gb', 100)}
MAX_API_CALLS_PER_HOUR={tenant.resource_limits.get('max_api_calls_per_hour', 1000)}

# Integration
CONTROL_PANEL_URL=http://control-panel-backend:8001
RESOURCE_CLUSTER_URL=http://resource-cluster:8004
"""
        
        env_file = config_path / "tenant.env"
        with open(env_file, 'w') as f:
            f.write(env_config)
            
        os.chmod(env_file, 0o600)
        
        logger.info(f"Created configuration files for {tenant.domain}")
    
    async def _setup_os_user(self, tenant: Tenant) -> None:
        """Create OS user for tenant (production only)"""
        if settings.environment == "development":
            logger.info(f"Skipping OS user creation in development for {tenant.domain}")
            return
            
        try:
            # Create system user for tenant
            username = f"gt-{tenant.domain}"
            tenant_path = self.base_data_path / tenant.domain
            
            # Check if user already exists
            result = subprocess.run(
                ["id", username], 
                capture_output=True, 
                text=True
            )
            
            if result.returncode != 0:
                # Create user
                subprocess.run([
                    "useradd", 
                    "--system",
                    "--home-dir", str(tenant_path),
                    "--shell", "/usr/sbin/nologin",
                    "--comment", f"GT 2.0 Tenant {tenant.domain}",
                    username
                ], check=True)
                
                logger.info(f"Created OS user {username}")
            
            # Set ownership
            subprocess.run([
                "chown", "-R", f"{username}:{username}", str(tenant_path)
            ], check=True)
            
            logger.info(f"Set ownership for {tenant.domain}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to setup OS user for {tenant.domain}: {e}")
            # Don't fail the entire provisioning for this
    
    async def _notify_tenant_cluster(self, tenant: Tenant) -> None:
        """Send provisioning message to tenant cluster via RabbitMQ"""
        try:
            message = {
                "action": "tenant_provisioned",
                "tenant_id": tenant.uuid,
                "tenant_domain": tenant.domain,
                "namespace": tenant.namespace,
                "config_path": f"/data/{tenant.domain}/shared/configs/tenant_config.json",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.message_bus.send_tenant_command(
                command_type="tenant_provisioned",
                tenant_namespace=tenant.namespace,
                payload=message
            )
            
            logger.info(f"Sent provisioning notification for {tenant.domain}")
            
        except Exception as e:
            logger.error(f"Failed to notify tenant cluster for {tenant.domain}: {e}")
            # Don't fail provisioning for this
    
    async def _update_tenant_status(self, tenant_id: int, status: str, db: AsyncSession) -> None:
        """Update tenant status in database"""
        try:
            await db.execute(
                update(Tenant)
                .where(Tenant.id == tenant_id)
                .values(
                    status=status,
                    updated_at=datetime.utcnow()
                )
            )
            await db.commit()
            
        except Exception as e:
            logger.error(f"Failed to update tenant status: {e}")
    
    async def deprovision_tenant(self, tenant_id: int, db: AsyncSession) -> bool:
        """
        Safely deprovision tenant (archive data, don't delete).
        
        Args:
            tenant_id: Database ID of tenant to deprovision
            db: Database session
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get tenant details
            result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                logger.error(f"Tenant {tenant_id} not found")
                return False
            
            logger.info(f"Starting deprovisioning for tenant {tenant.domain}")
            
            # Step 1: Create backup
            await self._create_tenant_backup(tenant)
            
            # Step 2: Notify tenant cluster to stop services
            await self._notify_tenant_shutdown(tenant)
            
            # Step 3: Archive data (don't delete)
            await self._archive_tenant_data(tenant)
            
            # Step 4: Update status
            await self._update_tenant_status(tenant_id, "archived", db)
            
            logger.info(f"Tenant {tenant.domain} deprovisioned successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to deprovision tenant {tenant_id}: {e}")
            return False
    
    async def _create_tenant_backup(self, tenant: Tenant) -> None:
        """Create complete backup of tenant data"""
        tenant_path = self.base_data_path / tenant.domain
        backup_path = tenant_path / "backups" / f"full_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.tar.gz"
        
        # Create compressed backup
        subprocess.run([
            "tar", "-czf", str(backup_path),
            "-C", str(tenant_path.parent),
            tenant.domain,
            "--exclude", "backups"
        ], check=True)
        
        logger.info(f"Created backup for {tenant.domain}: {backup_path}")
    
    async def _notify_tenant_shutdown(self, tenant: Tenant) -> None:
        """Notify tenant cluster to shutdown services"""
        try:
            message = {
                "action": "tenant_shutdown",
                "tenant_id": tenant.uuid,
                "tenant_domain": tenant.domain,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.message_bus.send_tenant_command(
                command_type="tenant_shutdown",
                tenant_namespace=tenant.namespace,
                payload=message
            )
            
        except Exception as e:
            logger.error(f"Failed to notify tenant shutdown: {e}")
    
    async def _archive_tenant_data(self, tenant: Tenant) -> None:
        """Archive tenant data (rename directory)"""
        tenant_path = self.base_data_path / tenant.domain
        archive_path = self.base_data_path / f"{tenant.domain}_archived_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        if tenant_path.exists():
            tenant_path.rename(archive_path)
            logger.info(f"Archived tenant data: {archive_path}")


# Background task function for FastAPI
async def deploy_tenant_infrastructure(tenant_id: int) -> None:
    """Background task to deploy tenant infrastructure"""
    from app.core.database import get_db_session
    
    provisioning_service = TenantProvisioningService()
    
    async with get_db_session() as db:
        success = await provisioning_service.provision_tenant(tenant_id, db)
        
        if success:
            logger.info(f"Tenant {tenant_id} provisioned successfully")
        else:
            logger.error(f"Failed to provision tenant {tenant_id}")


async def archive_tenant_infrastructure(tenant_id: int) -> None:
    """Background task to archive tenant infrastructure"""
    from app.core.database import get_db_session
    
    provisioning_service = TenantProvisioningService()
    
    async with get_db_session() as db:
        success = await provisioning_service.deprovision_tenant(tenant_id, db)
        
        if success:
            logger.info(f"Tenant {tenant_id} archived successfully")
        else:
            logger.error(f"Failed to archive tenant {tenant_id}")