"""
Unit tests for Model Management Service
"""
import pytest
import asyncio
import json
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from faker import Faker

from app.services.model_service import ModelService, ModelRegistryEntry

fake = Faker()


@pytest.fixture
def temp_db_path():
    """Create temporary database path for testing"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
        db_path = tmp.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def model_service(temp_db_path, mock_settings):
    """Create ModelService instance with temporary database"""
    service = ModelService()
    # Override the database path for testing
    service.db_path = temp_db_path
    service._init_database()
    return service


@pytest.fixture
def sample_model_data():
    """Sample model data matching the actual interface"""
    return {
        "model_id": "test-llama-70b",
        "name": "Test Llama 70B",
        "version": "1.0.0",
        "provider": "groq",
        "model_type": "llm",
        "description": "Test model for unit testing",
        "capabilities": {"streaming": True, "function_calling": True},
        "parameters": {"temperature": 0.7, "max_tokens": 8000},
        "endpoint_url": "https://api.groq.com/openai/v1",
        "max_tokens": 8000,
        "cost_per_1k_tokens": 0.59
    }


class TestModelService:
    """Test the ModelService class"""
    
    @pytest.mark.asyncio
    async def test_register_model_success(self, model_service, sample_model_data):
        """Test successful model registration"""
        # Register the model
        result = await model_service.register_model(**sample_model_data)
        
        assert result is not None
        assert result["id"] == sample_model_data["model_id"]
        assert result["name"] == sample_model_data["name"]
        assert result["provider"] == sample_model_data["provider"]
        assert result["capabilities"]["streaming"] is True
        assert result["performance"]["max_tokens"] == 8000
    
    @pytest.mark.asyncio
    async def test_register_model_updates_existing(self, model_service, sample_model_data):
        """Test that registering existing model updates it"""
        # Register model first time
        result1 = await model_service.register_model(**sample_model_data)
        assert result1 is not None
        
        # Register same model with updates
        updated_data = sample_model_data.copy()
        updated_data["version"] = "2.0.0"
        updated_data["description"] = "Updated description"
        
        result2 = await model_service.register_model(**updated_data)
        assert result2 is not None
        assert result2["version"] == "2.0.0"
        assert result2["description"] == "Updated description"
        
        # Verify only one model exists
        models = await model_service.list_models()
        model_ids = [m["id"] for m in models]
        assert model_ids.count(sample_model_data["model_id"]) == 1
    
    @pytest.mark.asyncio
    async def test_get_model_success(self, model_service, sample_model_data):
        """Test retrieving an existing model"""
        # Register model first
        await model_service.register_model(**sample_model_data)
        
        # Get the model
        model = await model_service.get_model(sample_model_data["model_id"])
        assert model is not None
        assert model["id"] == sample_model_data["model_id"]
        assert model["name"] == sample_model_data["name"]
        assert model["provider"] == sample_model_data["provider"]
    
    @pytest.mark.asyncio
    async def test_get_model_not_found(self, model_service):
        """Test getting non-existent model returns None"""
        model = await model_service.get_model("nonexistent-model")
        assert model is None
    
    @pytest.mark.asyncio
    async def test_list_models_empty(self, model_service):
        """Test listing models when none exist"""
        models = await model_service.list_models()
        assert models == []
    
    @pytest.mark.asyncio
    async def test_list_models_with_filters(self, model_service):
        """Test listing models with various filters"""
        # Register multiple models
        model1_data = {
            "model_id": "groq-llama-70b",
            "name": "Llama 70B",
            "version": "1.0.0",
            "provider": "groq",
            "model_type": "llm",
            "max_tokens": 8000,
            "cost_per_1k_tokens": 0.59
        }
        
        model2_data = {
            "model_id": "openai-gpt4",
            "name": "GPT-4",
            "version": "1.0.0", 
            "provider": "openai",
            "model_type": "llm",
            "max_tokens": 128000,
            "cost_per_1k_tokens": 30.0
        }
        
        model3_data = {
            "model_id": "openai-embedding",
            "name": "Text Embedding",
            "version": "1.0.0",
            "provider": "openai", 
            "model_type": "embedding",
            "max_tokens": 8000,
            "cost_per_1k_tokens": 0.1
        }
        
        await model_service.register_model(**model1_data)
        await model_service.register_model(**model2_data)
        await model_service.register_model(**model3_data)
        
        # Test filtering by provider
        groq_models = await model_service.list_models(provider="groq")
        assert len(groq_models) == 1
        assert groq_models[0]["id"] == "groq-llama-70b"
        
        openai_models = await model_service.list_models(provider="openai")
        assert len(openai_models) == 2
        
        # Test filtering by model type
        llm_models = await model_service.list_models(model_type="llm")
        assert len(llm_models) == 2
        
        embedding_models = await model_service.list_models(model_type="embedding")
        assert len(embedding_models) == 1
        assert embedding_models[0]["id"] == "openai-embedding"
    
    @pytest.mark.asyncio
    async def test_update_model_status(self, model_service, sample_model_data):
        """Test updating model deployment and health status"""
        # Register model first
        await model_service.register_model(**sample_model_data)
        
        # Update status
        result = await model_service.update_model_status(
            sample_model_data["model_id"],
            deployment_status="deploying",
            health_status="healthy"
        )
        assert result is True
        
        # Verify updates
        model = await model_service.get_model(sample_model_data["model_id"])
        assert model["status"]["deployment"] == "deploying"
        assert model["status"]["health"] == "healthy"
        assert model["status"]["last_health_check"] is not None
    
    @pytest.mark.asyncio
    async def test_update_status_nonexistent_model(self, model_service):
        """Test updating status of non-existent model fails"""
        result = await model_service.update_model_status(
            "nonexistent-model",
            deployment_status="deploying"
        )
        assert result is False
    
    @pytest.mark.asyncio
    async def test_track_model_usage_success(self, model_service, sample_model_data):
        """Test successful model usage tracking"""
        # Register model first
        await model_service.register_model(**sample_model_data)
        
        # Track successful usage
        await model_service.track_model_usage(
            model_id=sample_model_data["model_id"],
            success=True,
            latency_ms=1500.0
        )
        
        # Get model and check usage stats
        model = await model_service.get_model(sample_model_data["model_id"])
        assert model["usage"]["request_count"] == 1
        assert model["usage"]["error_count"] == 0
        assert model["usage"]["success_rate"] == 1.0
        assert model["performance"]["latency_p50_ms"] == 1500.0
    
    @pytest.mark.asyncio
    async def test_track_model_usage_failure(self, model_service, sample_model_data):
        """Test tracking failed model usage"""
        # Register model first
        await model_service.register_model(**sample_model_data)
        
        # Track failed usage
        await model_service.track_model_usage(
            model_id=sample_model_data["model_id"],
            success=False
        )
        
        # Get model and check failure stats
        model = await model_service.get_model(sample_model_data["model_id"])
        assert model["usage"]["request_count"] == 1
        assert model["usage"]["error_count"] == 1
        assert model["usage"]["success_rate"] == 0.0
    
    @pytest.mark.asyncio
    async def test_track_multiple_usage_updates_stats(self, model_service, sample_model_data):
        """Test that multiple usage tracking updates statistics correctly"""
        # Register model first
        await model_service.register_model(**sample_model_data)
        
        # Track multiple successful uses
        for i in range(5):
            await model_service.track_model_usage(
                model_id=sample_model_data["model_id"],
                success=True,
                latency_ms=1000.0 + (i * 100)  # 1000, 1100, 1200, 1300, 1400
            )
        
        # Track one failure
        await model_service.track_model_usage(
            model_id=sample_model_data["model_id"],
            success=False
        )
        
        # Verify aggregated stats
        model = await model_service.get_model(sample_model_data["model_id"])
        usage = model["usage"]
        
        assert usage["request_count"] == 6
        assert usage["error_count"] == 1
        assert usage["success_rate"] == pytest.approx(0.8333, rel=1e-3)  # 5/6
        
        # Latency should be updated with exponential moving average
        assert model["performance"]["latency_p50_ms"] > 1000.0
        assert model["performance"]["latency_p95_ms"] > 1000.0
    
    @pytest.mark.asyncio
    async def test_retire_model_success(self, model_service, sample_model_data):
        """Test successful model retirement"""
        # Register model first
        await model_service.register_model(**sample_model_data)
        
        # Retire model
        result = await model_service.retire_model(
            sample_model_data["model_id"],
            reason="Outdated model version"
        )
        assert result is True
        
        # Verify retirement
        model = await model_service.get_model(sample_model_data["model_id"])
        assert model["status"]["deployment"] == "retired"
        assert model["lifecycle"]["retired_at"] is not None
        assert "Retired: Outdated model version" in model["description"]
    
    @pytest.mark.asyncio
    async def test_retire_nonexistent_model_fails(self, model_service):
        """Test retiring non-existent model fails"""
        result = await model_service.retire_model("nonexistent-model")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_check_model_health_unknown_provider(self, model_service):
        """Test health check for unknown provider"""
        # Register model with unknown provider
        model_data = {
            "model_id": "unknown-model",
            "name": "Unknown Model",
            "version": "1.0.0",
            "provider": "unknown",
            "model_type": "llm"
        }
        
        await model_service.register_model(**model_data)
        
        # Check health
        health = await model_service.check_model_health("unknown-model")
        assert health["healthy"] is False
        assert "Unknown provider" in health["error"]
    
    @pytest.mark.asyncio
    async def test_check_model_health_not_found(self, model_service):
        """Test health check for non-existent model"""
        health = await model_service.check_model_health("nonexistent-model")
        assert health["healthy"] is False
        assert health["error"] == "Model not found"
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_groq_model_health_success(self, mock_httpx, model_service, sample_model_data):
        """Test successful Groq model health check"""
        # Register Groq model
        await model_service.register_model(**sample_model_data)
        
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "test-llama-70b"}]}
        
        mock_client = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_httpx.return_value.__aenter__.return_value = mock_client
        
        # Check health
        health = await model_service.check_model_health(sample_model_data["model_id"])
        
        assert health["healthy"] is True
        assert health["latency_ms"] >= 0
        assert health["provider"] == "groq"
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_groq_model_health_failure(self, mock_httpx, model_service, sample_model_data):
        """Test failed Groq model health check"""
        # Register Groq model
        await model_service.register_model(**sample_model_data)
        
        # Mock failed HTTP response
        mock_client = Mock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection timeout"))
        mock_httpx.return_value.__aenter__.return_value = mock_client
        
        # Check health
        health = await model_service.check_model_health(sample_model_data["model_id"])
        
        assert health["healthy"] is False
        assert "Connection timeout" in health["error"]
    
    @pytest.mark.asyncio
    async def test_concurrent_usage_tracking(self, model_service, sample_model_data):
        """Test concurrent usage tracking doesn't cause race conditions"""
        # Register model first
        await model_service.register_model(**sample_model_data)
        
        # Track usage concurrently
        async def track_usage(index):
            await model_service.track_model_usage(
                model_id=sample_model_data["model_id"],
                success=True,
                latency_ms=1000.0
            )
        
        # Run 10 concurrent usage tracking operations
        tasks = [track_usage(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        # Verify all usage was tracked correctly
        model = await model_service.get_model(sample_model_data["model_id"])
        usage = model["usage"]
        
        assert usage["request_count"] == 10
        assert usage["error_count"] == 0
        assert usage["success_rate"] == 1.0


@pytest.mark.integration
class TestModelServiceIntegration:
    """Integration tests for ModelService"""
    
    @pytest.mark.asyncio
    async def test_full_model_lifecycle(self, model_service, sample_model_data):
        """Test complete model lifecycle from registration to retirement"""
        model_id = sample_model_data["model_id"]
        
        # 1. Register model
        register_result = await model_service.register_model(**sample_model_data)
        assert register_result is not None
        assert register_result["id"] == model_id
        
        # 2. Verify registration
        model = await model_service.get_model(model_id)
        assert model is not None
        assert model["id"] == model_id
        
        # 3. Update status
        status_result = await model_service.update_model_status(
            model_id,
            deployment_status="available",
            health_status="healthy"
        )
        assert status_result is True
        
        # 4. Track usage over time
        for i in range(5):
            await model_service.track_model_usage(
                model_id=model_id,
                success=True,
                latency_ms=1000.0 + i * 100
            )
        
        # 5. Verify usage tracking
        updated_model = await model_service.get_model(model_id)
        assert updated_model["usage"]["request_count"] == 5
        assert updated_model["usage"]["success_rate"] == 1.0
        
        # 6. List models (should include our model)
        all_models = await model_service.list_models()
        model_ids = [m["id"] for m in all_models]
        assert model_id in model_ids
        
        # 7. Filter models by provider
        groq_models = await model_service.list_models(provider="groq")
        groq_model_ids = [m["id"] for m in groq_models]
        assert model_id in groq_model_ids
        
        # 8. Retire model
        retire_result = await model_service.retire_model(
            model_id,
            reason="End of lifecycle test"
        )
        assert retire_result is True
        
        # 9. Verify retirement
        retired_model = await model_service.get_model(model_id)
        assert retired_model["status"]["deployment"] == "retired"
        assert retired_model["lifecycle"]["retired_at"] is not None