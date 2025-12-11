"""
Unit Tests for Access Groups System

Tests the access control model, service, and API endpoints.
Ensures perfect tenant isolation and proper permission cascading.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import os
import stat

from app.models.access_group import (
    AccessGroup, TenantStructure, User, Resource,
    ResourceCreate, ResourceUpdate, AccessGroupModel
)
from app.services.access_controller import AccessController, AccessControlMiddleware


class TestAccessGroupModels:
    """Test access group data models"""
    
    def test_tenant_structure_creation(self):
        """Test creating tenant structure"""
        tenant = TenantStructure(
            tenant_domain="customer1.com",
            tenant_id="tenant-123",
            users=[],
            created_at=datetime.utcnow(),
            settings={"max_users": 100}
        )
        
        assert tenant.tenant_domain == "customer1.com"
        assert tenant.tenant_id == "tenant-123"
        assert len(tenant.users) == 0
        assert tenant.settings["max_users"] == 100
    
    def test_user_creation_and_access(self):
        """Test user creation and resource access checks"""
        user = User(
            id="alice@customer1.com",
            email="alice@customer1.com",
            full_name="Alice Smith",
            role="developer",
            tenant_domain="customer1.com",
            owned_resources=[],
            created_at=datetime.utcnow()
        )
        
        # Test owner access
        resource = Resource(
            id="res-123",
            name="Test Resource",
            resource_type="dataset",
            owner_id="alice@customer1.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.INDIVIDUAL,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={}
        )
        
        assert user.can_access_resource(resource) == True
        assert user.can_modify_resource(resource) == True
    
    def test_resource_access_groups(self):
        """Test different access group behaviors"""
        owner = User(
            id="owner@customer1.com",
            email="owner@customer1.com",
            full_name="Owner User",
            role="admin",
            tenant_domain="customer1.com",
            owned_resources=[],
            created_at=datetime.utcnow()
        )
        
        other_user = User(
            id="other@customer1.com",
            email="other@customer1.com",
            full_name="Other User",
            role="developer",
            tenant_domain="customer1.com",
            owned_resources=[],
            created_at=datetime.utcnow()
        )
        
        # Individual access - only owner
        individual_resource = Resource(
            id="res-1",
            name="Private Resource",
            resource_type="agent",
            owner_id="owner@customer1.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.INDIVIDUAL,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={}
        )
        
        assert owner.can_access_resource(individual_resource) == True
        assert other_user.can_access_resource(individual_resource) == False
        
        # Team access - owner and team members
        team_resource = Resource(
            id="res-2",
            name="Team Resource",
            resource_type="dataset",
            owner_id="owner@customer1.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.TEAM,
            team_members=["other@customer1.com"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={}
        )
        
        assert owner.can_access_resource(team_resource) == True
        assert other_user.can_access_resource(team_resource) == True
        
        # Organization access - everyone
        org_resource = Resource(
            id="res-3",
            name="Org Resource",
            resource_type="document",
            owner_id="owner@customer1.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.ORGANIZATION,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={}
        )
        
        assert owner.can_access_resource(org_resource) == True
        assert other_user.can_access_resource(org_resource) == True
        
        # Only owner can modify
        assert owner.can_modify_resource(org_resource) == True
        assert other_user.can_modify_resource(org_resource) == False
    
    def test_resource_team_member_management(self):
        """Test adding and removing team members"""
        resource = Resource(
            id="res-123",
            name="Team Resource",
            resource_type="workflow",
            owner_id="owner@customer1.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.TEAM,
            team_members=["alice@customer1.com"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={}
        )
        
        # Add team member
        resource.add_team_member("bob@customer1.com")
        assert "bob@customer1.com" in resource.team_members
        assert len(resource.team_members) == 2
        
        # Remove team member
        resource.remove_team_member("alice@customer1.com")
        assert "alice@customer1.com" not in resource.team_members
        assert len(resource.team_members) == 1
        
        # Change to individual access clears team members
        resource.update_access_group(AccessGroup.INDIVIDUAL)
        assert len(resource.team_members) == 0
    
    def test_file_permissions(self):
        """Test file permission settings"""
        resource = Resource(
            id="res-123",
            name="File Resource",
            resource_type="document",
            owner_id="owner@customer1.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.ORGANIZATION,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={}
        )
        
        # All resources should have 700 permissions for security
        assert resource.get_file_permissions() == "700"


class TestAccessController:
    """Test access controller service"""
    
    @pytest.fixture
    def controller(self, tmp_path):
        """Create access controller with temp directory"""
        with patch("app.services.access_controller.Path") as mock_path:
            mock_path.return_value = tmp_path / "customer1.com"
            controller = AccessController("customer1.com")
            controller.base_path = tmp_path / "customer1.com"
            return controller
    
    @pytest.mark.asyncio
    async def test_check_permission_owner(self, controller):
        """Test owner has all permissions"""
        resource = Resource(
            id="res-123",
            name="Test Resource",
            resource_type="dataset",
            owner_id="alice@customer1.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.INDIVIDUAL,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={}
        )
        
        # Owner should have all permissions
        allowed, reason = await controller.check_permission(
            "alice@customer1.com", resource, "read"
        )
        assert allowed == True
        assert reason == "Owner access granted"
        
        allowed, reason = await controller.check_permission(
            "alice@customer1.com", resource, "write"
        )
        assert allowed == True
        assert reason == "Owner access granted"
        
        allowed, reason = await controller.check_permission(
            "alice@customer1.com", resource, "delete"
        )
        assert allowed == True
        assert reason == "Owner access granted"
    
    @pytest.mark.asyncio
    async def test_check_permission_team_access(self, controller):
        """Test team member permissions"""
        resource = Resource(
            id="res-123",
            name="Team Resource",
            resource_type="workflow",
            owner_id="owner@customer1.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.TEAM,
            team_members=["alice@customer1.com", "bob@customer1.com"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={}
        )
        
        # Team member should have read access
        allowed, reason = await controller.check_permission(
            "alice@customer1.com", resource, "read"
        )
        assert allowed == True
        assert reason == "Team member read access"
        
        # Team member should NOT have write access
        allowed, reason = await controller.check_permission(
            "alice@customer1.com", resource, "write"
        )
        assert allowed == False
        assert reason == "Only owner can modify"
        
        # Non-team member should NOT have access
        allowed, reason = await controller.check_permission(
            "charlie@customer1.com", resource, "read"
        )
        assert allowed == False
        assert reason == "Not a team member"
    
    @pytest.mark.asyncio
    async def test_check_permission_organization_access(self, controller):
        """Test organization-wide permissions"""
        resource = Resource(
            id="res-123",
            name="Org Resource",
            resource_type="document",
            owner_id="owner@customer1.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.ORGANIZATION,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={}
        )
        
        # Any user in tenant should have read access
        allowed, reason = await controller.check_permission(
            "anyone@customer1.com", resource, "read"
        )
        assert allowed == True
        assert reason == "Organization-wide read access"
        
        # But only owner can write
        allowed, reason = await controller.check_permission(
            "anyone@customer1.com", resource, "write"
        )
        assert allowed == False
        assert reason == "Only owner can modify"
    
    @pytest.mark.asyncio
    async def test_cross_tenant_isolation(self, controller):
        """Test cross-tenant access is blocked"""
        resource = Resource(
            id="res-123",
            name="Other Tenant Resource",
            resource_type="dataset",
            owner_id="owner@customer2.com",
            tenant_domain="customer2.com",  # Different tenant!
            access_group=AccessGroup.ORGANIZATION,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={}
        )
        
        # Should block cross-tenant access
        allowed, reason = await controller.check_permission(
            "alice@customer1.com", resource, "read"
        )
        assert allowed == False
        assert reason == "Cross-tenant access denied"
    
    @pytest.mark.asyncio
    async def test_create_resource_with_file_storage(self, controller, tmp_path):
        """Test creating resource with file storage"""
        controller.base_path = tmp_path
        
        with patch("app.services.access_controller.verify_capability_token") as mock_verify:
            mock_verify.return_value = {"tenant_id": "customer1.com"}
            
            resource_data = ResourceCreate(
                name="Test Dataset",
                resource_type="dataset",
                access_group=AccessGroup.TEAM,
                team_members=["alice@customer1.com"],
                metadata={"description": "Test dataset"}
            )
            
            resource = await controller.create_resource(
                user_id="owner@customer1.com",
                resource_data=resource_data,
                capability_token="valid-token"
            )
            
            assert resource.name == "Test Dataset"
            assert resource.owner_id == "owner@customer1.com"
            assert resource.access_group == AccessGroup.TEAM
            assert resource.file_path is not None
            
            # Check file was created with proper permissions
            file_path = Path(resource.file_path)
            assert file_path.exists()
            
            # Check directory permissions (should be 700)
            dir_path = file_path.parent
            dir_stat = os.stat(dir_path)
            assert oct(dir_stat.st_mode)[-3:] == "700"
    
    @pytest.mark.asyncio
    async def test_update_resource_access(self, controller):
        """Test updating resource access group"""
        resource = Resource(
            id="res-123",
            name="Test Resource",
            resource_type="agent",
            owner_id="owner@customer1.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.INDIVIDUAL,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={}
        )
        
        with patch.object(controller, '_load_resource', return_value=resource):
            with patch.object(controller, '_update_file_permissions'):
                updated = await controller.update_resource_access(
                    user_id="owner@customer1.com",
                    resource_id="res-123",
                    new_access_group=AccessGroup.TEAM,
                    team_members=["alice@customer1.com", "bob@customer1.com"]
                )
                
                assert updated.access_group == AccessGroup.TEAM
                assert len(updated.team_members) == 2
                assert "alice@customer1.com" in updated.team_members


class TestAccessControlMiddleware:
    """Test access control middleware"""
    
    @pytest.fixture
    def middleware(self):
        """Create middleware instance"""
        return AccessControlMiddleware("customer1.com")
    
    @pytest.mark.asyncio
    async def test_verify_request_valid(self, middleware):
        """Test valid request verification"""
        resource = Resource(
            id="res-123",
            name="Test Resource",
            resource_type="dataset",
            owner_id="alice@customer1.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.INDIVIDUAL,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={}
        )
        
        with patch("app.services.access_controller.verify_capability_token") as mock_verify:
            mock_verify.return_value = {"tenant_id": "customer1.com"}
            
            with patch.object(middleware.controller, '_load_resource', return_value=resource):
                # Owner should be allowed
                result = await middleware.verify_request(
                    user_id="alice@customer1.com",
                    resource_id="res-123",
                    action="read",
                    capability_token="valid-token"
                )
                assert result == True
    
    @pytest.mark.asyncio
    async def test_verify_request_denied(self, middleware):
        """Test request denial for unauthorized access"""
        resource = Resource(
            id="res-123",
            name="Private Resource",
            resource_type="agent",
            owner_id="owner@customer1.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.INDIVIDUAL,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={}
        )
        
        with patch("app.services.access_controller.verify_capability_token") as mock_verify:
            mock_verify.return_value = {"tenant_id": "customer1.com"}
            
            with patch.object(middleware.controller, '_load_resource', return_value=resource):
                # Non-owner should be denied
                with pytest.raises(PermissionError) as exc:
                    await middleware.verify_request(
                        user_id="other@customer1.com",
                        resource_id="res-123",
                        action="read",
                        capability_token="valid-token"
                    )
                assert "Access denied" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_verify_request_invalid_token(self, middleware):
        """Test request denial for invalid token"""
        with patch("app.services.access_controller.verify_capability_token") as mock_verify:
            mock_verify.return_value = None  # Invalid token
            
            with pytest.raises(PermissionError) as exc:
                await middleware.verify_request(
                    user_id="alice@customer1.com",
                    resource_id="res-123",
                    action="read",
                    capability_token="invalid-token"
                )
            assert "Invalid capability token" in str(exc.value)
    
    @pytest.mark.asyncio
    async def test_verify_request_tenant_mismatch(self, middleware):
        """Test request denial for tenant mismatch"""
        with patch("app.services.access_controller.verify_capability_token") as mock_verify:
            mock_verify.return_value = {"tenant_id": "customer2.com"}  # Wrong tenant!
            
            with pytest.raises(PermissionError) as exc:
                await middleware.verify_request(
                    user_id="alice@customer1.com",
                    resource_id="res-123",
                    action="read",
                    capability_token="wrong-tenant-token"
                )
            assert "Tenant mismatch" in str(exc.value)


class TestSecurityValidation:
    """Security-specific tests for access control"""
    
    def test_file_permissions_always_restrictive(self):
        """Ensure file permissions are always restrictive regardless of access group"""
        for access_group in [AccessGroup.INDIVIDUAL, AccessGroup.TEAM, AccessGroup.ORGANIZATION]:
            resource = Resource(
                id="res-123",
                name="Test Resource",
                resource_type="document",
                owner_id="owner@customer1.com",
                tenant_domain="customer1.com",
                access_group=access_group,
                team_members=["alice@customer1.com"] if access_group == AccessGroup.TEAM else [],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                metadata={}
            )
            
            # All files should have 700 permissions for OS-level security
            assert resource.get_file_permissions() == "700"
    
    def test_no_privilege_escalation(self):
        """Test that users cannot escalate privileges"""
        user = User(
            id="attacker@customer1.com",
            email="attacker@customer1.com",
            full_name="Attacker",
            role="student",  # Low privilege role
            tenant_domain="customer1.com",
            owned_resources=[],
            created_at=datetime.utcnow()
        )
        
        admin_resource = Resource(
            id="admin-res",
            name="Admin Resource",
            resource_type="configuration",
            owner_id="admin@customer1.com",
            tenant_domain="customer1.com",
            access_group=AccessGroup.INDIVIDUAL,
            team_members=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={"sensitive": True}
        )
        
        # Low privilege user cannot access admin resources
        assert user.can_access_resource(admin_resource) == False
        assert user.can_modify_resource(admin_resource) == False
    
    @pytest.mark.asyncio
    async def test_audit_logging(self, tmp_path):
        """Test that all access attempts are logged"""
        with patch("app.services.access_controller.logger") as mock_logger:
            controller = AccessController("customer1.com")
            controller.base_path = tmp_path
            
            resource = Resource(
                id="res-123",
                name="Sensitive Resource",
                resource_type="dataset",
                owner_id="owner@customer1.com",
                tenant_domain="customer2.com",  # Wrong tenant
                access_group=AccessGroup.ORGANIZATION,
                team_members=[],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                metadata={}
            )
            
            # Attempt cross-tenant access
            await controller.check_permission(
                "attacker@customer1.com", resource, "read"
            )
            
            # Should log the security violation
            mock_logger.warning.assert_called()
            call_args = str(mock_logger.warning.call_args)
            assert "Cross-tenant access attempt" in call_args