"""
Dataset Sharing Service for GT 2.0

Implements hierarchical dataset sharing with perfect tenant isolation.
Enables secure data collaboration while maintaining ownership and access control.
"""

import os
import stat
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

from app.models.access_group import AccessGroup, Resource
from app.services.access_controller import AccessController
from app.core.security import verify_capability_token

logger = logging.getLogger(__name__)


class SharingPermission(Enum):
    """Sharing permission levels"""
    READ = "read"           # Can view and search dataset
    WRITE = "write"         # Can add documents
    ADMIN = "admin"         # Can modify sharing settings


@dataclass
class DatasetShare:
    """Dataset sharing configuration"""
    id: str = field(default_factory=lambda: str(uuid4()))
    dataset_id: str = ""
    owner_id: str = ""
    access_group: AccessGroup = AccessGroup.INDIVIDUAL
    team_members: List[str] = field(default_factory=list)
    team_permissions: Dict[str, SharingPermission] = field(default_factory=dict)
    shared_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "dataset_id": self.dataset_id,
            "owner_id": self.owner_id,
            "access_group": self.access_group.value,
            "team_members": self.team_members,
            "team_permissions": {k: v.value for k, v in self.team_permissions.items()},
            "shared_at": self.shared_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetShare":
        """Create from dictionary"""
        return cls(
            id=data.get("id", str(uuid4())),
            dataset_id=data["dataset_id"],
            owner_id=data["owner_id"],
            access_group=AccessGroup(data["access_group"]),
            team_members=data.get("team_members", []),
            team_permissions={
                k: SharingPermission(v) for k, v in data.get("team_permissions", {}).items()
            },
            shared_at=datetime.fromisoformat(data["shared_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            is_active=data.get("is_active", True)
        )


@dataclass
class DatasetInfo:
    """Dataset information for sharing"""
    id: str
    name: str
    description: str
    owner_id: str
    document_count: int
    size_bytes: int
    created_at: datetime
    updated_at: datetime
    tags: List[str] = field(default_factory=list)


class DatasetSharingService:
    """
    Service for hierarchical dataset sharing with capability-based access control.
    
    Features:
    - Individual, Team, and Organization level sharing
    - Granular permission management (read, write, admin)
    - Time-based expiration of shares
    - Perfect tenant isolation through file-based storage
    - Event emission for sharing activities
    """
    
    def __init__(self, tenant_domain: str, access_controller: AccessController):
        self.tenant_domain = tenant_domain
        self.access_controller = access_controller
        self.base_path = Path(f"/data/{tenant_domain}/dataset_sharing")
        self.shares_path = self.base_path / "shares"
        self.datasets_path = self.base_path / "datasets"
        
        # Ensure directories exist with proper permissions
        self._ensure_directories()
        
        logger.info(f"DatasetSharingService initialized for {tenant_domain}")
    
    def _ensure_directories(self):
        """Ensure sharing directories exist with proper permissions"""
        for path in [self.shares_path, self.datasets_path]:
            path.mkdir(parents=True, exist_ok=True)
            # Set permissions to 700 (owner only)
            os.chmod(path, stat.S_IRWXU)
    
    async def share_dataset(
        self,
        dataset_id: str,
        owner_id: str,
        access_group: AccessGroup,
        team_members: Optional[List[str]] = None,
        team_permissions: Optional[Dict[str, SharingPermission]] = None,
        expires_at: Optional[datetime] = None,
        capability_token: str = ""
    ) -> DatasetShare:
        """
        Share a dataset with specified access group.
        
        Args:
            dataset_id: Dataset to share
            owner_id: Owner of the dataset
            access_group: Level of sharing (Individual, Team, Organization)
            team_members: List of team members (if Team access)
            team_permissions: Permissions for each team member
            expires_at: Optional expiration time
            capability_token: JWT capability token
            
        Returns:
            DatasetShare configuration
        """
        # Verify capability token
        token_data = verify_capability_token(capability_token)
        if not token_data or token_data.get("tenant_id") != self.tenant_domain:
            raise PermissionError("Invalid capability token")
        
        # Verify ownership
        dataset_resource = await self._load_dataset_resource(dataset_id)
        if not dataset_resource or dataset_resource.owner_id != owner_id:
            raise PermissionError("Only dataset owner can modify sharing")
        
        # Validate team members for team sharing
        if access_group == AccessGroup.TEAM:
            if not team_members:
                raise ValueError("Team members required for team sharing")
            
            # Ensure all team members are valid users in tenant
            for member in team_members:
                if not await self._is_valid_tenant_user(member):
                    logger.warning(f"Invalid team member: {member}")
        
        # Create sharing configuration
        share = DatasetShare(
            dataset_id=dataset_id,
            owner_id=owner_id,
            access_group=access_group,
            team_members=team_members or [],
            team_permissions=team_permissions or {},
            expires_at=expires_at
        )
        
        # Set default permissions for team members
        if access_group == AccessGroup.TEAM:
            for member in share.team_members:
                if member not in share.team_permissions:
                    share.team_permissions[member] = SharingPermission.READ
        
        # Store sharing configuration
        await self._store_share(share)
        
        # Update dataset resource access group
        await self.access_controller.update_resource_access(
            owner_id, dataset_id, access_group, team_members
        )
        
        # Emit sharing event
        if hasattr(self.access_controller, 'event_bus'):
            await self.access_controller.event_bus.emit_event(
                "dataset.shared",
                owner_id,
                {
                    "dataset_id": dataset_id,
                    "access_group": access_group.value,
                    "team_members": team_members or [],
                    "expires_at": expires_at.isoformat() if expires_at else None
                }
            )
        
        logger.info(f"Dataset {dataset_id} shared as {access_group.value} by {owner_id}")
        return share
    
    async def get_dataset_sharing(
        self,
        dataset_id: str,
        user_id: str,
        capability_token: str
    ) -> Optional[DatasetShare]:
        """
        Get sharing configuration for a dataset.
        
        Args:
            dataset_id: Dataset ID
            user_id: Requesting user
            capability_token: JWT capability token
            
        Returns:
            DatasetShare if user has access, None otherwise
        """
        # Verify capability token
        token_data = verify_capability_token(capability_token)
        if not token_data or token_data.get("tenant_id") != self.tenant_domain:
            raise PermissionError("Invalid capability token")
        
        # Load sharing configuration
        share = await self._load_share(dataset_id)
        if not share:
            return None
        
        # Check if user has access to view sharing info
        if share.owner_id == user_id:
            return share  # Owner can always see
        
        if share.access_group == AccessGroup.TEAM and user_id in share.team_members:
            return share  # Team member can see
        
        if share.access_group == AccessGroup.ORGANIZATION:
            # All tenant users can see organization shares
            if await self._is_valid_tenant_user(user_id):
                return share
        
        return None
    
    async def check_dataset_access(
        self,
        dataset_id: str,
        user_id: str,
        permission: SharingPermission = SharingPermission.READ
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if user has specified permission on dataset.
        
        Args:
            dataset_id: Dataset to check
            user_id: User requesting access
            permission: Required permission level
            
        Returns:
            Tuple of (allowed, reason)
        """
        # Load sharing configuration
        share = await self._load_share(dataset_id)
        if not share or not share.is_active:
            return False, "Dataset not shared or sharing inactive"
        
        # Check expiration
        if share.expires_at and datetime.utcnow() > share.expires_at:
            return False, "Dataset sharing has expired"
        
        # Owner has all permissions
        if share.owner_id == user_id:
            return True, "Owner access"
        
        # Check access group permissions
        if share.access_group == AccessGroup.INDIVIDUAL:
            return False, "Private dataset"
        
        elif share.access_group == AccessGroup.TEAM:
            if user_id not in share.team_members:
                return False, "Not a team member"
            
            # Check specific permission
            user_permission = share.team_permissions.get(user_id, SharingPermission.READ)
            if self._has_permission(user_permission, permission):
                return True, f"Team member with {user_permission.value} permission"
            else:
                return False, f"Insufficient permission: has {user_permission.value}, needs {permission.value}"
        
        elif share.access_group == AccessGroup.ORGANIZATION:
            # Organization sharing is typically read-only
            if permission == SharingPermission.READ:
                if await self._is_valid_tenant_user(user_id):
                    return True, "Organization-wide read access"
            return False, "Organization access is read-only"
        
        return False, "Unknown access configuration"
    
    async def list_accessible_datasets(
        self,
        user_id: str,
        capability_token: str,
        include_owned: bool = True,
        include_shared: bool = True
    ) -> List[DatasetInfo]:
        """
        List datasets accessible to user.
        
        Args:
            user_id: User requesting list
            capability_token: JWT capability token
            include_owned: Include user's own datasets
            include_shared: Include datasets shared with user
            
        Returns:
            List of accessible datasets
        """
        # Verify capability token
        token_data = verify_capability_token(capability_token)
        if not token_data or token_data.get("tenant_id") != self.tenant_domain:
            raise PermissionError("Invalid capability token")
        
        accessible_datasets = []
        
        # Get all dataset shares
        all_shares = await self._list_all_shares()
        
        for share in all_shares:
            # Skip inactive or expired shares
            if not share.is_active:
                continue
            if share.expires_at and datetime.utcnow() > share.expires_at:
                continue
            
            # Check if user has access
            has_access = False
            
            if include_owned and share.owner_id == user_id:
                has_access = True
            elif include_shared:
                allowed, _ = await self.check_dataset_access(share.dataset_id, user_id)
                has_access = allowed
            
            if has_access:
                dataset_info = await self._load_dataset_info(share.dataset_id)
                if dataset_info:
                    accessible_datasets.append(dataset_info)
        
        return accessible_datasets
    
    async def revoke_dataset_sharing(
        self,
        dataset_id: str,
        owner_id: str,
        capability_token: str
    ) -> bool:
        """
        Revoke dataset sharing (make it private).
        
        Args:
            dataset_id: Dataset to make private
            owner_id: Owner of the dataset
            capability_token: JWT capability token
            
        Returns:
            True if revoked successfully
        """
        # Verify capability token
        token_data = verify_capability_token(capability_token)
        if not token_data or token_data.get("tenant_id") != self.tenant_domain:
            raise PermissionError("Invalid capability token")
        
        # Verify ownership
        share = await self._load_share(dataset_id)
        if not share or share.owner_id != owner_id:
            raise PermissionError("Only dataset owner can revoke sharing")
        
        # Update sharing to individual (private)
        share.access_group = AccessGroup.INDIVIDUAL
        share.team_members = []
        share.team_permissions = {}
        share.is_active = False
        
        # Store updated share
        await self._store_share(share)
        
        # Update resource access
        await self.access_controller.update_resource_access(
            owner_id, dataset_id, AccessGroup.INDIVIDUAL, []
        )
        
        # Emit revocation event
        if hasattr(self.access_controller, 'event_bus'):
            await self.access_controller.event_bus.emit_event(
                "dataset.sharing_revoked",
                owner_id,
                {"dataset_id": dataset_id}
            )
        
        logger.info(f"Dataset {dataset_id} sharing revoked by {owner_id}")
        return True
    
    async def update_team_permissions(
        self,
        dataset_id: str,
        owner_id: str,
        user_id: str,
        permission: SharingPermission,
        capability_token: str
    ) -> bool:
        """
        Update team member permissions for a dataset.
        
        Args:
            dataset_id: Dataset ID
            owner_id: Owner of the dataset
            user_id: Team member to update
            permission: New permission level
            capability_token: JWT capability token
            
        Returns:
            True if updated successfully
        """
        # Verify capability token
        token_data = verify_capability_token(capability_token)
        if not token_data or token_data.get("tenant_id") != self.tenant_domain:
            raise PermissionError("Invalid capability token")
        
        # Load and verify sharing
        share = await self._load_share(dataset_id)
        if not share or share.owner_id != owner_id:
            raise PermissionError("Only dataset owner can update permissions")
        
        if share.access_group != AccessGroup.TEAM:
            raise ValueError("Can only update permissions for team-shared datasets")
        
        if user_id not in share.team_members:
            raise ValueError("User is not a team member")
        
        # Update permission
        share.team_permissions[user_id] = permission
        
        # Store updated share
        await self._store_share(share)
        
        logger.info(f"Updated {user_id} permission to {permission.value} for dataset {dataset_id}")
        return True
    
    async def get_sharing_statistics(
        self,
        user_id: str,
        capability_token: str
    ) -> Dict[str, Any]:
        """
        Get sharing statistics for user.
        
        Args:
            user_id: User to get stats for
            capability_token: JWT capability token
            
        Returns:
            Statistics dictionary
        """
        # Verify capability token
        token_data = verify_capability_token(capability_token)
        if not token_data or token_data.get("tenant_id") != self.tenant_domain:
            raise PermissionError("Invalid capability token")
        
        stats = {
            "owned_datasets": 0,
            "shared_with_me": 0,
            "sharing_breakdown": {
                AccessGroup.INDIVIDUAL: 0,
                AccessGroup.TEAM: 0,
                AccessGroup.ORGANIZATION: 0
            },
            "total_team_members": 0,
            "expired_shares": 0
        }
        
        all_shares = await self._list_all_shares()
        
        for share in all_shares:
            # Count owned datasets
            if share.owner_id == user_id:
                stats["owned_datasets"] += 1
                stats["sharing_breakdown"][share.access_group] += 1
                stats["total_team_members"] += len(share.team_members)
                
                # Count expired shares
                if share.expires_at and datetime.utcnow() > share.expires_at:
                    stats["expired_shares"] += 1
            
            # Count datasets shared with user
            elif user_id in share.team_members or share.access_group == AccessGroup.ORGANIZATION:
                if share.is_active and (not share.expires_at or datetime.utcnow() <= share.expires_at):
                    stats["shared_with_me"] += 1
        
        return stats
    
    def _has_permission(self, user_permission: SharingPermission, required: SharingPermission) -> bool:
        """Check if user permission satisfies required permission"""
        permission_hierarchy = {
            SharingPermission.READ: 1,
            SharingPermission.WRITE: 2,
            SharingPermission.ADMIN: 3
        }
        
        return permission_hierarchy[user_permission] >= permission_hierarchy[required]
    
    async def _store_share(self, share: DatasetShare):
        """Store sharing configuration to file system"""
        share_file = self.shares_path / f"{share.dataset_id}.json"
        
        with open(share_file, "w") as f:
            json.dump(share.to_dict(), f, indent=2)
        
        # Set secure permissions
        os.chmod(share_file, stat.S_IRUSR | stat.S_IWUSR)  # 600
    
    async def _load_share(self, dataset_id: str) -> Optional[DatasetShare]:
        """Load sharing configuration from file system"""
        share_file = self.shares_path / f"{dataset_id}.json"
        
        if not share_file.exists():
            return None
        
        try:
            with open(share_file, "r") as f:
                data = json.load(f)
                return DatasetShare.from_dict(data)
        except Exception as e:
            logger.error(f"Error loading share for dataset {dataset_id}: {e}")
            return None
    
    async def _list_all_shares(self) -> List[DatasetShare]:
        """List all sharing configurations"""
        shares = []
        
        if self.shares_path.exists():
            for share_file in self.shares_path.glob("*.json"):
                try:
                    with open(share_file, "r") as f:
                        data = json.load(f)
                        shares.append(DatasetShare.from_dict(data))
                except Exception as e:
                    logger.error(f"Error loading share file {share_file}: {e}")
        
        return shares
    
    async def _load_dataset_resource(self, dataset_id: str) -> Optional[Resource]:
        """Load dataset resource (implementation would query storage)"""
        # Placeholder - would integrate with actual resource storage
        return Resource(
            id=dataset_id,
            name=f"Dataset {dataset_id}",
            resource_type="dataset",
            owner_id="mock_owner",
            tenant_domain=self.tenant_domain,
            access_group=AccessGroup.INDIVIDUAL
        )
    
    async def _load_dataset_info(self, dataset_id: str) -> Optional[DatasetInfo]:
        """Load dataset information (implementation would query storage)"""
        # Placeholder - would integrate with actual dataset storage
        return DatasetInfo(
            id=dataset_id,
            name=f"Dataset {dataset_id}",
            description="Mock dataset for testing",
            owner_id="mock_owner",
            document_count=10,
            size_bytes=1024000,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            tags=["test", "mock"]
        )
    
    async def _is_valid_tenant_user(self, user_id: str) -> bool:
        """Check if user is valid in tenant (implementation would query user store)"""
        # Placeholder - would integrate with actual user management
        return "@" in user_id and user_id.endswith((".com", ".org", ".edu"))