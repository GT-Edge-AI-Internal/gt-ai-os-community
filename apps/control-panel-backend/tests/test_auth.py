"""
Unit tests for authentication API endpoints
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from app.models.user import User


@pytest.mark.unit
class TestAuthAPI:
    """Test authentication API endpoints."""

    async def test_login_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test successful user login."""
        login_data = {
            "email": test_user.email,
            "password": "testpassword123"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == test_user.email
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 24 * 3600

    async def test_login_invalid_email(self, client: AsyncClient):
        """Test login with non-existent email."""
        login_data = {
            "email": "nonexistent@test.com",
            "password": "password123"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        data = response.json()
        assert not data["success"]
        assert "Invalid email or password" in data["error"]["message"]

    async def test_login_invalid_password(
        self,
        client: AsyncClient,
        test_user: User
    ):
        """Test login with incorrect password."""
        login_data = {
            "email": test_user.email,
            "password": "wrongpassword"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        data = response.json()
        assert not data["success"]
        assert "Invalid email or password" in data["error"]["message"]

    async def test_login_inactive_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User
    ):
        """Test login with inactive user."""
        # Deactivate user
        test_user.is_active = False
        await db_session.commit()
        
        login_data = {
            "email": test_user.email,
            "password": "testpassword123"
        }
        
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401

    async def test_login_invalid_data(self, client: AsyncClient):
        """Test login with invalid request data."""
        # Missing password
        login_data = {"email": "test@example.com"}
        
        response = await client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 422  # Validation error

    async def test_get_current_user_info(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User
    ):
        """Test getting current user information."""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"]
        assert data["data"]["email"] == test_user.email
        assert data["data"]["user_type"] == test_user.user_type

    async def test_get_current_user_no_token(self, client: AsyncClient):
        """Test getting current user without authentication token."""
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401

    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test getting current user with invalid token."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401

    async def test_logout_success(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test successful logout."""
        response = await client.post("/api/v1/auth/logout", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"]
        assert "Logged out successfully" in data["message"]

    async def test_change_password_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User
    ):
        """Test successful password change."""
        password_data = {
            "current_password": "testpassword123",
            "new_password": "NewSecurePassword123!"
        }
        
        response = await client.post(
            "/api/v1/auth/change-password",
            json=password_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"]
        assert "Password changed successfully" in data["message"]

    async def test_change_password_wrong_current(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test password change with wrong current password."""
        password_data = {
            "current_password": "wrongpassword",
            "new_password": "NewSecurePassword123!"
        }
        
        response = await client.post(
            "/api/v1/auth/change-password",
            json=password_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.json()
        assert not data["success"]
        assert "Current password is incorrect" in data["error"]["message"]

    async def test_change_password_weak_password(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """Test password change with weak new password."""
        password_data = {
            "current_password": "testpassword123",
            "new_password": "weak"
        }
        
        response = await client.post(
            "/api/v1/auth/change-password",
            json=password_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.json()
        assert not data["success"]
        assert "Password validation failed" in data["error"]["message"]

    async def test_verify_token_valid(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User
    ):
        """Test token verification with valid token."""
        response = await client.get("/api/v1/auth/verify-token", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"]
        assert data["data"]["valid"] is True
        assert data["data"]["user"]["email"] == test_user.email

    async def test_verify_token_invalid(self, client: AsyncClient):
        """Test token verification with invalid token."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = await client.get("/api/v1/auth/verify-token", headers=headers)
        
        assert response.status_code == 401

    @patch('app.api.auth.AuditLog')
    async def test_login_audit_logging(
        self,
        mock_audit_log,
        client: AsyncClient,
        test_user: User
    ):
        """Test that login attempts are properly logged."""
        login_data = {
            "email": test_user.email,
            "password": "testpassword123"
        }
        
        await client.post("/api/v1/auth/login", json=login_data)
        
        # Verify audit log was called
        mock_audit_log.create_log.assert_called()
        call_args = mock_audit_log.create_log.call_args
        assert call_args[1]["action"] == "user.login"
        assert call_args[1]["user_id"] == test_user.id