"""
Unit Tests for Dataset Sharing System

Tests hierarchical sharing, permission management, and access control
with tenant isolation and capability-based security.
"""

import pytest
import tempfile
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from app.services.dataset_sharing import (
    DatasetSharingService, DatasetShare, DatasetInfo, SharingPermission
)
from app.services.access_controller import AccessController
from app.models.access_group import AccessGroup


class TestDatasetShare:
    """Test DatasetShare data structure"""
    
    def test_dataset_share_creation(self):
        """Test dataset share creation and serialization"""
        share = DatasetShare(
            dataset_id="dataset_123",
            owner_id="owner@example.com",
            access_group=AccessGroup.TEAM,
            team_members=["user1@example.com", "user2@example.com"],
            team_permissions={
                "user1@example.com": SharingPermission.READ,
                "user2@example.com": SharingPermission.WRITE
            }
        )
        
        assert share.dataset_id == "dataset_123"
        assert share.owner_id == "owner@example.com"
        assert share.access_group == AccessGroup.TEAM
        assert len(share.team_members) == 2
        assert share.team_permissions["user1@example.com"] == SharingPermission.READ
        assert share.is_active == True
    
    def test_dataset_share_serialization(self):
        """Test dataset share to/from dict conversion"""
        original = DatasetShare(
            dataset_id="test_dataset",
            owner_id="test@example.com",
            access_group=AccessGroup.ORGANIZATION,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        
        # Convert to dict and back
        share_dict = original.to_dict()
        restored = DatasetShare.from_dict(share_dict)
        
        assert restored.dataset_id == original.dataset_id
        assert restored.owner_id == original.owner_id
        assert restored.access_group == original.access_group
        assert restored.id == original.id
        assert restored.expires_at == original.expires_at
    
    def test_sharing_permission_hierarchy(self):
        """Test permission hierarchy logic"""
        service = DatasetSharingService("test.com", Mock())
        
        # Read permission satisfies read requirement
        assert service._has_permission(SharingPermission.READ, SharingPermission.READ) == True
        
        # Write permission satisfies read requirement
        assert service._has_permission(SharingPermission.WRITE, SharingPermission.READ) == True
        
        # Admin permission satisfies all requirements
        assert service._has_permission(SharingPermission.ADMIN, SharingPermission.READ) == True
        assert service._has_permission(SharingPermission.ADMIN, SharingPermission.WRITE) == True
        assert service._has_permission(SharingPermission.ADMIN, SharingPermission.ADMIN) == True
        
        # Read permission does not satisfy write requirement
        assert service._has_permission(SharingPermission.READ, SharingPermission.WRITE) == False
        
        # Write permission does not satisfy admin requirement
        assert service._has_permission(SharingPermission.WRITE, SharingPermission.ADMIN) == False


class TestDatasetSharingService:
    """Test Dataset Sharing Service functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def access_controller(self):
        """Mock access controller"""
        controller = Mock(spec=AccessController)
        controller.tenant_domain = "test.com"
        controller.update_resource_access = AsyncMock()
        return controller
    
    @pytest.fixture
    def sharing_service(self, temp_dir, access_controller):
        """Create sharing service with temporary storage"""
        service = DatasetSharingService("test.com", access_controller)
        service.base_path = temp_dir
        service.shares_path = temp_dir / "shares"
        service.datasets_path = temp_dir / "datasets"
        service._ensure_directories()
        return service
    
    @pytest.fixture
    def mock_capability_token(self):
        """Mock capability token verification"""
        with patch('app.services.dataset_sharing.verify_capability_token') as mock_verify:
            mock_verify.return_value = {
                "tenant_id": "test.com",
                "sub": "test@example.com",
                "capabilities": ["dataset:share", "dataset:manage"]
            }
            yield "mock_token"
    
    @pytest.mark.asyncio
    async def test_share_dataset_team(self, sharing_service, mock_capability_token):
        """Test sharing dataset with team"""
        team_members = ["member1@example.com", "member2@example.com"]
        team_permissions = {
            "member1@example.com": SharingPermission.READ,
            "member2@example.com": SharingPermission.WRITE
        }
        
        # Mock dataset resource loading
        sharing_service._load_dataset_resource = AsyncMock(return_value=Mock(
            owner_id="owner@example.com"
        ))
        
        share = await sharing_service.share_dataset(
            dataset_id="dataset_123",
            owner_id="owner@example.com",
            access_group=AccessGroup.TEAM,
            team_members=team_members,
            team_permissions=team_permissions,
            capability_token=mock_capability_token
        )
        
        assert share.dataset_id == "dataset_123"
        assert share.owner_id == "owner@example.com"
        assert share.access_group == AccessGroup.TEAM
        assert share.team_members == team_members
        assert share.team_permissions["member1@example.com"] == SharingPermission.READ
        assert share.team_permissions["member2@example.com"] == SharingPermission.WRITE
        
        # Check file was created
        share_file = sharing_service.shares_path / "dataset_123.json"
        assert share_file.exists()
    
    @pytest.mark.asyncio
    async def test_share_dataset_organization(self, sharing_service, mock_capability_token):
        """Test sharing dataset with organization"""
        # Mock dataset resource loading
        sharing_service._load_dataset_resource = AsyncMock(return_value=Mock(
            owner_id="owner@example.com"
        ))
        
        share = await sharing_service.share_dataset(
            dataset_id="dataset_456",
            owner_id="owner@example.com",
            access_group=AccessGroup.ORGANIZATION,
            capability_token=mock_capability_token
        )
        
        assert share.access_group == AccessGroup.ORGANIZATION
        assert share.team_members == []
        assert share.team_permissions == {}
        assert share.is_active == True
    
    @pytest.mark.asyncio
    async def test_share_dataset_with_expiration(self, sharing_service, mock_capability_token):
        """Test sharing dataset with expiration"""
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        # Mock dataset resource loading
        sharing_service._load_dataset_resource = AsyncMock(return_value=Mock(
            owner_id="owner@example.com"
        ))
        
        share = await sharing_service.share_dataset(
            dataset_id="dataset_789",
            owner_id="owner@example.com",
            access_group=AccessGroup.TEAM,
            team_members=["user@example.com"],
            expires_at=expires_at,
            capability_token=mock_capability_token
        )
        
        assert share.expires_at == expires_at
        assert share.is_active == True
    
    @pytest.mark.asyncio
    async def test_check_dataset_access_owner(self, sharing_service):
        """Test dataset access check for owner"""
        # Create and store a share
        share = DatasetShare(
            dataset_id="owner_dataset",
            owner_id="owner@example.com",
            access_group=AccessGroup.INDIVIDUAL
        )
        await sharing_service._store_share(share)
        
        allowed, reason = await sharing_service.check_dataset_access(
            dataset_id="owner_dataset",
            user_id="owner@example.com",
            permission=SharingPermission.ADMIN
        )
        
        assert allowed == True
        assert "Owner access" in reason
    
    @pytest.mark.asyncio
    async def test_check_dataset_access_team_member(self, sharing_service):
        """Test dataset access check for team member"""
        # Create and store a team share
        share = DatasetShare(
            dataset_id="team_dataset",
            owner_id="owner@example.com",
            access_group=AccessGroup.TEAM,
            team_members=["member@example.com"],
            team_permissions={"member@example.com": SharingPermission.WRITE}
        )
        await sharing_service._store_share(share)
        
        # Test read access (should succeed)
        allowed, reason = await sharing_service.check_dataset_access(
            dataset_id="team_dataset",
            user_id="member@example.com",
            permission=SharingPermission.READ
        )
        assert allowed == True
        assert "Team member" in reason
        
        # Test write access (should succeed)
        allowed, reason = await sharing_service.check_dataset_access(
            dataset_id="team_dataset",
            user_id="member@example.com",
            permission=SharingPermission.WRITE
        )
        assert allowed == True
        
        # Test admin access (should fail)
        allowed, reason = await sharing_service.check_dataset_access(
            dataset_id="team_dataset",
            user_id="member@example.com",
            permission=SharingPermission.ADMIN
        )
        assert allowed == False
        assert "Insufficient permission" in reason
    
    @pytest.mark.asyncio
    async def test_check_dataset_access_organization(self, sharing_service):
        """Test dataset access check for organization sharing"""
        # Create and store an organization share
        share = DatasetShare(
            dataset_id="org_dataset",
            owner_id="owner@example.com",
            access_group=AccessGroup.ORGANIZATION
        )
        await sharing_service._store_share(share)
        
        # Mock valid tenant user
        sharing_service._is_valid_tenant_user = AsyncMock(return_value=True)
        
        # Test read access (should succeed)
        allowed, reason = await sharing_service.check_dataset_access(
            dataset_id="org_dataset",
            user_id="any_user@example.com",
            permission=SharingPermission.READ
        )
        assert allowed == True
        assert "Organization-wide read access" in reason
        
        # Test write access (should fail)
        allowed, reason = await sharing_service.check_dataset_access(
            dataset_id="org_dataset",
            user_id="any_user@example.com",
            permission=SharingPermission.WRITE
        )
        assert allowed == False
        assert "read-only" in reason
    
    @pytest.mark.asyncio
    async def test_check_dataset_access_expired(self, sharing_service):
        """Test dataset access check for expired share"""
        # Create expired share
        share = DatasetShare(
            dataset_id="expired_dataset",
            owner_id="owner@example.com",
            access_group=AccessGroup.TEAM,
            team_members=["member@example.com"],
            expires_at=datetime.utcnow() - timedelta(days=1)  # Expired yesterday
        )
        await sharing_service._store_share(share)
        
        allowed, reason = await sharing_service.check_dataset_access(
            dataset_id="expired_dataset",
            user_id="member@example.com",
            permission=SharingPermission.READ
        )
        
        assert allowed == False
        assert "expired" in reason
    
    @pytest.mark.asyncio
    async def test_check_dataset_access_not_team_member(self, sharing_service):
        """Test dataset access check for non-team member"""
        # Create team share
        share = DatasetShare(
            dataset_id="team_only_dataset",
            owner_id="owner@example.com",
            access_group=AccessGroup.TEAM,
            team_members=["member@example.com"]
        )
        await sharing_service._store_share(share)
        
        allowed, reason = await sharing_service.check_dataset_access(
            dataset_id="team_only_dataset",
            user_id="outsider@example.com",
            permission=SharingPermission.READ
        )
        
        assert allowed == False
        assert "Not a team member" in reason
    
    @pytest.mark.asyncio
    async def test_revoke_dataset_sharing(self, sharing_service, mock_capability_token):
        """Test revoking dataset sharing"""
        # Create and store a share
        share = DatasetShare(
            dataset_id="revoke_dataset",
            owner_id="owner@example.com",
            access_group=AccessGroup.TEAM,
            team_members=["member@example.com"]
        )
        await sharing_service._store_share(share)
        
        success = await sharing_service.revoke_dataset_sharing(
            dataset_id="revoke_dataset",
            owner_id="owner@example.com",
            capability_token=mock_capability_token
        )
        
        assert success == True
        
        # Load and verify share was revoked
        revoked_share = await sharing_service._load_share("revoke_dataset")
        assert revoked_share.access_group == AccessGroup.INDIVIDUAL
        assert revoked_share.team_members == []
        assert revoked_share.is_active == False
    
    @pytest.mark.asyncio
    async def test_update_team_permissions(self, sharing_service, mock_capability_token):
        """Test updating team member permissions"""
        # Create and store a team share
        share = DatasetShare(
            dataset_id="update_perms_dataset",
            owner_id="owner@example.com",
            access_group=AccessGroup.TEAM,
            team_members=["member@example.com"],
            team_permissions={"member@example.com": SharingPermission.READ}
        )
        await sharing_service._store_share(share)
        
        success = await sharing_service.update_team_permissions(
            dataset_id="update_perms_dataset",
            owner_id="owner@example.com",
            user_id="member@example.com",
            permission=SharingPermission.ADMIN,
            capability_token=mock_capability_token
        )
        
        assert success == True
        
        # Load and verify permission was updated
        updated_share = await sharing_service._load_share("update_perms_dataset")
        assert updated_share.team_permissions["member@example.com"] == SharingPermission.ADMIN
    
    @pytest.mark.asyncio
    async def test_list_accessible_datasets(self, sharing_service, mock_capability_token):
        """Test listing accessible datasets"""
        # Create multiple shares with different access patterns
        shares = [
            DatasetShare(
                dataset_id="owned_dataset",
                owner_id="user@example.com",
                access_group=AccessGroup.INDIVIDUAL
            ),
            DatasetShare(
                dataset_id="team_dataset",
                owner_id="other@example.com",
                access_group=AccessGroup.TEAM,
                team_members=["user@example.com"]
            ),
            DatasetShare(
                dataset_id="org_dataset",
                owner_id="another@example.com",
                access_group=AccessGroup.ORGANIZATION
            )
        ]
        
        for share in shares:
            await sharing_service._store_share(share)
        
        # Mock dataset info loading
        sharing_service._load_dataset_info = AsyncMock(side_effect=lambda dataset_id: DatasetInfo(
            id=dataset_id,
            name=f"Dataset {dataset_id}",
            description="Test dataset",
            owner_id="test_owner",
            document_count=10,
            size_bytes=1024,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ))
        
        # Mock tenant user validation
        sharing_service._is_valid_tenant_user = AsyncMock(return_value=True)
        
        datasets = await sharing_service.list_accessible_datasets(
            user_id="user@example.com",
            capability_token=mock_capability_token,
            include_owned=True,
            include_shared=True
        )
        
        # Should include owned dataset, team dataset, and org dataset
        dataset_ids = [d.id for d in datasets]
        assert "owned_dataset" in dataset_ids
        assert "team_dataset" in dataset_ids
        assert "org_dataset" in dataset_ids
    
    @pytest.mark.asyncio
    async def test_get_sharing_statistics(self, sharing_service, mock_capability_token):
        """Test getting sharing statistics"""
        # Create multiple shares for user
        shares = [
            DatasetShare(
                dataset_id="owned1",
                owner_id="user@example.com",
                access_group=AccessGroup.INDIVIDUAL
            ),
            DatasetShare(
                dataset_id="owned2",
                owner_id="user@example.com",
                access_group=AccessGroup.TEAM,
                team_members=["member1@example.com", "member2@example.com"]
            ),
            DatasetShare(
                dataset_id="owned3",
                owner_id="user@example.com",
                access_group=AccessGroup.ORGANIZATION
            ),
            DatasetShare(
                dataset_id="shared_with_user",
                owner_id="other@example.com",
                access_group=AccessGroup.TEAM,
                team_members=["user@example.com"]
            )
        ]
        
        for share in shares:
            await sharing_service._store_share(share)
        
        # Mock tenant user validation
        sharing_service._is_valid_tenant_user = AsyncMock(return_value=True)
        
        stats = await sharing_service.get_sharing_statistics(
            user_id="user@example.com",
            capability_token=mock_capability_token
        )
        
        assert stats["owned_datasets"] == 3
        assert stats["shared_with_me"] == 1
        assert stats["sharing_breakdown"][AccessGroup.INDIVIDUAL] == 1
        assert stats["sharing_breakdown"][AccessGroup.TEAM] == 1
        assert stats["sharing_breakdown"][AccessGroup.ORGANIZATION] == 1
        assert stats["total_team_members"] == 2  # From owned2
    
    @pytest.mark.asyncio
    async def test_sharing_permission_errors(self, sharing_service, mock_capability_token):
        """Test permission errors in sharing operations"""
        # Test sharing non-existent dataset
        sharing_service._load_dataset_resource = AsyncMock(return_value=None)
        
        with pytest.raises(PermissionError):
            await sharing_service.share_dataset(
                dataset_id="nonexistent",
                owner_id="user@example.com",
                access_group=AccessGroup.TEAM,
                capability_token=mock_capability_token
            )
        
        # Test sharing dataset owned by different user
        sharing_service._load_dataset_resource = AsyncMock(return_value=Mock(
            owner_id="different_owner@example.com"
        ))
        
        with pytest.raises(PermissionError):
            await sharing_service.share_dataset(
                dataset_id="not_owned",
                owner_id="user@example.com",
                access_group=AccessGroup.TEAM,
                capability_token=mock_capability_token
            )
    
    @pytest.mark.asyncio
    async def test_team_sharing_validation(self, sharing_service, mock_capability_token):
        """Test team sharing validation"""
        # Mock dataset resource loading
        sharing_service._load_dataset_resource = AsyncMock(return_value=Mock(
            owner_id="owner@example.com"
        ))
        
        # Test team sharing without team members
        with pytest.raises(ValueError, match="Team members required"):
            await sharing_service.share_dataset(
                dataset_id="team_dataset",
                owner_id="owner@example.com",
                access_group=AccessGroup.TEAM,
                team_members=None,
                capability_token=mock_capability_token
            )
        
        # Test team sharing with empty team members
        with pytest.raises(ValueError, match="Team members required"):
            await sharing_service.share_dataset(
                dataset_id="team_dataset",
                owner_id="owner@example.com",
                access_group=AccessGroup.TEAM,
                team_members=[],
                capability_token=mock_capability_token
            )
    
    @pytest.mark.asyncio
    async def test_share_storage_and_loading(self, sharing_service):
        """Test share storage and loading persistence"""
        share = DatasetShare(
            dataset_id="storage_test",
            owner_id="owner@example.com",
            access_group=AccessGroup.TEAM,
            team_members=["member@example.com"],
            team_permissions={"member@example.com": SharingPermission.WRITE},
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        
        # Store share
        await sharing_service._store_share(share)
        
        # Load share
        loaded_share = await sharing_service._load_share("storage_test")
        
        assert loaded_share is not None
        assert loaded_share.dataset_id == share.dataset_id
        assert loaded_share.owner_id == share.owner_id
        assert loaded_share.access_group == share.access_group
        assert loaded_share.team_members == share.team_members
        assert loaded_share.team_permissions == share.team_permissions
        assert loaded_share.expires_at == share.expires_at
        
        # Test loading non-existent share
        missing_share = await sharing_service._load_share("nonexistent")
        assert missing_share is None