"""
Unit tests for RAG Service with user-scoped datasets and vector operations
"""
import pytest
import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from faker import Faker

from app.services.rag_service import RAGService
from app.services.vector_store import VectorStoreService, VectorSearchResult
from app.core.resource_client import ResourceClusterClient
from app.models.document import Document, DocumentChunk, RAGDataset

fake = Faker()


@pytest.fixture
def mock_db_session():
    """Mock async database session"""
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_vector_store():
    """Mock Vector Store Service"""
    vector_store = Mock(spec=VectorStoreService)
    vector_store.create_user_collection = AsyncMock()
    vector_store.store_vectors = AsyncMock()
    vector_store.search = AsyncMock()
    vector_store.delete_collection = AsyncMock()
    vector_store.get_collection_stats = AsyncMock()
    vector_store.list_user_collections = AsyncMock()
    return vector_store


@pytest.fixture
def mock_resource_client():
    """Mock Resource Cluster Client"""
    client = Mock(spec=ResourceClusterClient)
    client.process_document = AsyncMock()
    client.generate_embeddings = AsyncMock()
    client.generate_query_embeddings = AsyncMock()
    return client


@pytest.fixture
def rag_service(mock_db_session, mock_vector_store, mock_resource_client):
    """Create RAG Service with mocked dependencies"""
    service = RAGService(mock_db_session)
    service.vector_store = mock_vector_store
    service.resource_client = mock_resource_client
    return service


@pytest.fixture
def sample_rag_dataset():
    """Sample RAG dataset"""
    dataset = Mock(spec=RAGDataset)
    dataset.id = "dataset-123"
    dataset.user_id = "user@example.com"
    dataset.dataset_name = "Research Papers"
    dataset.description = "Collection of AI research papers"
    dataset.chunking_strategy = "hybrid"
    dataset.embedding_model = "BAAI/bge-m3"
    dataset.document_count = 5
    dataset.chunk_count = 150
    dataset.vector_count = 150
    dataset.status = "active"
    dataset.created_at = datetime.utcnow() - timedelta(days=7)
    dataset.updated_at = datetime.utcnow()
    return dataset


@pytest.fixture
def sample_document():
    """Sample document"""
    document = Mock(spec=Document)
    document.id = 1
    document.uuid = "doc-uuid-123"
    document.filename = "research_paper.pdf"
    document.file_type = "application/pdf"
    document.file_size = 1024000  # 1MB
    document.processing_status = "completed"
    document.chunk_count = 25
    document.uploaded_by = "user@example.com"
    document.created_at = datetime.utcnow() - timedelta(hours=2)
    document.processed_at = datetime.utcnow() - timedelta(hours=1)
    return document


@pytest.fixture
def sample_chunks():
    """Sample document chunks"""
    chunks = []
    for i in range(3):
        chunk = {
            "text": f"This is chunk {i} of the document with important research content.",
            "metadata": {
                "page": i + 1,
                "section": f"Section {i + 1}",
                "chunk_type": "paragraph"
            }
        }
        chunks.append(chunk)
    return chunks


@pytest.fixture
def sample_embeddings():
    """Sample embedding vectors"""
    return [
        [0.1, 0.2, 0.3, 0.4, 0.5] * 100,  # 500-dim vector
        [0.2, 0.3, 0.4, 0.5, 0.6] * 100,
        [0.3, 0.4, 0.5, 0.6, 0.7] * 100
    ]


class TestRAGService:
    """Test the RAG Service class"""
    
    @pytest.mark.asyncio
    async def test_create_dataset_success(self, rag_service, mock_db_session, mock_vector_store):
        """Test successful dataset creation"""
        # Mock database operations
        created_dataset = Mock(spec=RAGDataset)
        created_dataset.id = "new-dataset-123"
        created_dataset.dataset_name = "New Dataset"
        created_dataset.user_id = "user@example.com"
        
        mock_db_session.add = Mock()
        mock_db_session.commit = AsyncMock()
        
        # Mock vector store collection creation
        mock_vector_store.create_user_collection.return_value = "user@example.com_New Dataset"
        
        with patch.object(rag_service.db, 'add') as mock_add:
            # Mock the dataset creation to set the ID
            def mock_add_side_effect(dataset):
                dataset.id = "new-dataset-123"
            mock_add.side_effect = mock_add_side_effect
            
            result = await rag_service.create_dataset(
                user_id="user@example.com",
                dataset_name="New Dataset",
                description="Test dataset",
                chunking_strategy="semantic"
            )
        
        # Verify database operations
        mock_add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        
        # Verify vector store collection creation
        mock_vector_store.create_user_collection.assert_called_once_with(
            user_id="user@example.com",
            collection_name="New Dataset",
            metadata={
                "dataset_id": "new-dataset-123",
                "created_at": pytest.approx(datetime.utcnow().isoformat(), abs=10),
                "chunking_strategy": "semantic"
            }
        )
        
        assert result == "new-dataset-123"
    
    @pytest.mark.asyncio
    async def test_create_dataset_rollback_on_error(self, rag_service, mock_db_session, mock_vector_store):
        """Test dataset creation rollback on error"""
        # Mock database error
        mock_db_session.commit.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            await rag_service.create_dataset(
                user_id="user@example.com",
                dataset_name="Failed Dataset"
            )
        
        # Verify rollback was called
        mock_db_session.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_upload_document_success(self, rag_service, mock_db_session, mock_resource_client, mock_vector_store, sample_rag_dataset, sample_chunks, sample_embeddings):
        """Test successful document upload and processing"""
        # Mock dataset retrieval
        mock_db_session.get.return_value = sample_rag_dataset
        
        # Mock document processing
        mock_resource_client.process_document.return_value = sample_chunks
        mock_resource_client.generate_embeddings.return_value = sample_embeddings
        
        # Mock database operations
        mock_db_session.add = Mock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.flush = AsyncMock()
        
        # Mock vector store operations
        mock_vector_store.store_vectors.return_value = True
        
        file_content = b"This is a test PDF document content."
        
        with patch.object(rag_service.db, 'add') as mock_add:
            # Mock document ID assignment
            def mock_add_side_effect(obj):
                if hasattr(obj, '__class__') and 'Document' in str(obj.__class__):
                    obj.id = 1
                elif hasattr(obj, '__class__') and 'DocumentChunk' in str(obj.__class__):
                    obj.embedding_id = hashlib.sha256(f"1:{0}".encode()).hexdigest()[:16]
            mock_add.side_effect = mock_add_side_effect
            
            result = await rag_service.upload_document(
                user_id="user@example.com",
                dataset_id="dataset-123",
                file_content=file_content,
                filename="test.pdf",
                file_type="application/pdf",
                metadata={"source": "research"}
            )
        
        # Verify Resource Cluster operations
        mock_resource_client.process_document.assert_called_once_with(
            content=file_content,
            document_type="application/pdf",
            chunking_strategy="hybrid"
        )
        
        mock_resource_client.generate_embeddings.assert_called_once_with(
            texts=[chunk["text"] for chunk in sample_chunks],
            tenant_id=rag_service.tenant_id
        )
        
        # Verify vector storage
        mock_vector_store.store_vectors.assert_called_once()
        store_call_args = mock_vector_store.store_vectors.call_args
        assert store_call_args[1]["user_id"] == "user@example.com"
        assert store_call_args[1]["collection_name"] == "Research Papers"
        assert len(store_call_args[1]["documents"]) == 3
        assert len(store_call_args[1]["embeddings"]) == 3
        
        # Verify database operations
        assert mock_add.call_count == 4  # 1 document + 3 chunks
        mock_db_session.commit.assert_called_once()
        
        # Verify dataset statistics updated
        assert sample_rag_dataset.document_count == 6  # was 5, now 6
        assert sample_rag_dataset.chunk_count == 153   # was 150, now 153
        
        assert result == 1
    
    @pytest.mark.asyncio
    async def test_upload_document_dataset_not_found(self, rag_service, mock_db_session):
        """Test document upload when dataset not found"""
        # Mock dataset not found
        mock_db_session.get.return_value = None
        
        with pytest.raises(ValueError, match="Dataset not found or access denied"):
            await rag_service.upload_document(
                user_id="user@example.com",
                dataset_id="nonexistent",
                file_content=b"test",
                filename="test.pdf",
                file_type="application/pdf"
            )
    
    @pytest.mark.asyncio
    async def test_upload_document_access_denied(self, rag_service, mock_db_session, sample_rag_dataset):
        """Test document upload with wrong user access"""
        # Mock dataset with different user
        sample_rag_dataset.user_id = "other@example.com"
        mock_db_session.get.return_value = sample_rag_dataset
        
        with pytest.raises(ValueError, match="Dataset not found or access denied"):
            await rag_service.upload_document(
                user_id="user@example.com",
                dataset_id="dataset-123",
                file_content=b"test",
                filename="test.pdf",
                file_type="application/pdf"
            )
    
    @pytest.mark.asyncio
    async def test_search_dataset_success(self, rag_service, mock_db_session, mock_resource_client, mock_vector_store, sample_rag_dataset):
        """Test successful dataset search"""
        # Mock dataset retrieval
        mock_db_session.get.return_value = sample_rag_dataset
        
        # Mock query embedding generation
        query_embedding = [0.1, 0.2, 0.3, 0.4, 0.5] * 100
        mock_resource_client.generate_query_embeddings.return_value = [query_embedding]
        
        # Mock vector search results
        search_results = [
            VectorSearchResult(
                document_id="chunk-1",
                text="This is the first relevant chunk about machine learning.",
                score=0.95,
                metadata={
                    "document_id": 1,
                    "chunk_index": 0,
                    "filename": "ml_paper.pdf",
                    "page": 1
                }
            ),
            VectorSearchResult(
                document_id="chunk-2",
                text="This is the second relevant chunk about neural networks.",
                score=0.87,
                metadata={
                    "document_id": 1,
                    "chunk_index": 1,
                    "filename": "ml_paper.pdf",
                    "page": 2
                }
            )
        ]
        mock_vector_store.search.return_value = search_results
        
        result = await rag_service.search_dataset(
            user_id="user@example.com",
            dataset_id="dataset-123",
            query="machine learning algorithms",
            top_k=5,
            filters={"page": 1}
        )
        
        # Verify query embedding generation
        mock_resource_client.generate_query_embeddings.assert_called_once_with(
            queries=["machine learning algorithms"],
            tenant_id=rag_service.tenant_id
        )
        
        # Verify vector store search
        mock_vector_store.search.assert_called_once_with(
            user_id="user@example.com",
            collection_name="Research Papers",
            query_embedding=query_embedding,
            top_k=5,
            filter_metadata={"page": 1}
        )
        
        # Verify result formatting
        assert len(result) == 2
        assert result[0]["text"] == "This is the first relevant chunk about machine learning."
        assert result[0]["score"] == 0.95
        assert result[0]["metadata"]["document_id"] == 1
        assert result[0]["metadata"]["filename"] == "ml_paper.pdf"
        assert result[1]["score"] == 0.87
    
    @pytest.mark.asyncio
    async def test_search_dataset_no_embeddings(self, rag_service, mock_db_session, mock_resource_client, sample_rag_dataset):
        """Test dataset search when no embeddings generated"""
        mock_db_session.get.return_value = sample_rag_dataset
        mock_resource_client.generate_query_embeddings.return_value = []
        
        result = await rag_service.search_dataset(
            user_id="user@example.com",
            dataset_id="dataset-123",
            query="empty query"
        )
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_conversation_context_success(self, rag_service, mock_db_session):
        """Test getting conversation context from multiple datasets"""
        # Mock dataset listing
        mock_result = Mock()
        mock_datasets = [
            Mock(id="dataset-1", user_id="user@example.com", status="active"),
            Mock(id="dataset-2", user_id="user@example.com", status="active")
        ]
        mock_result.scalars.return_value.all.return_value = mock_datasets
        mock_db_session.execute.return_value = mock_result
        
        # Mock search results from each dataset
        with patch.object(rag_service, 'search_dataset') as mock_search:
            mock_search.side_effect = [
                [
                    {
                        "text": "Context from dataset 1",
                        "score": 0.9,
                        "filename": "doc1.pdf",
                        "chunk_index": 0
                    }
                ],
                [
                    {
                        "text": "Context from dataset 2", 
                        "score": 0.8,
                        "filename": "doc2.pdf",
                        "chunk_index": 1
                    }
                ]
            ]
            
            context_string, citations = await rag_service.get_conversation_context(
                user_id="user@example.com",
                conversation_id="conv-123",
                query="What is machine learning?",
                max_context_size=3
            )
        
        # Verify search was called for both datasets
        assert mock_search.call_count == 2
        mock_search.assert_any_call(
            user_id="user@example.com",
            dataset_id="dataset-1",
            query="What is machine learning?",
            top_k=3
        )
        
        # Verify context formatting
        assert "[Context 1]:" in context_string
        assert "Context from dataset 1" in context_string
        assert "[Context 2]:" in context_string
        assert "Context from dataset 2" in context_string
        
        # Verify citations
        assert len(citations) == 2
        assert citations[0]["index"] == 1
        assert citations[0]["filename"] == "doc1.pdf"
        assert citations[0]["score"] == 0.9
        assert citations[1]["index"] == 2
        assert citations[1]["filename"] == "doc2.pdf"
        assert citations[1]["score"] == 0.8
    
    @pytest.mark.asyncio
    async def test_get_conversation_context_no_datasets(self, rag_service, mock_db_session):
        """Test conversation context when user has no datasets"""
        # Mock empty dataset list
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        context_string, citations = await rag_service.get_conversation_context(
            user_id="user@example.com",
            conversation_id="conv-123",
            query="What is machine learning?"
        )
        
        assert context_string == ""
        assert citations == []
    
    @pytest.mark.asyncio
    async def test_get_conversation_context_with_specific_datasets(self, rag_service):
        """Test conversation context with specific dataset IDs"""
        with patch.object(rag_service, 'search_dataset') as mock_search:
            mock_search.return_value = [
                {
                    "text": "Specific context",
                    "score": 0.95,
                    "filename": "specific.pdf",
                    "chunk_index": 0
                }
            ]
            
            context_string, citations = await rag_service.get_conversation_context(
                user_id="user@example.com",
                conversation_id="conv-123",
                query="Specific query",
                dataset_ids=["dataset-specific"]
            )
        
        # Should only search the specified dataset
        mock_search.assert_called_once_with(
            user_id="user@example.com",
            dataset_id="dataset-specific",
            query="Specific query",
            top_k=3
        )
        
        assert "Specific context" in context_string
        assert len(citations) == 1
    
    @pytest.mark.asyncio
    async def test_list_user_datasets_success(self, rag_service, mock_db_session, mock_vector_store):
        """Test listing user datasets with statistics"""
        # Mock database query
        mock_result = Mock()
        mock_datasets = [
            Mock(
                id="dataset-1",
                dataset_name="Research Papers",
                description="AI research collection",
                document_count=10,
                chunk_count=250,
                status="active",
                chunking_strategy="hybrid",
                created_at=datetime(2024, 1, 1),
                updated_at=datetime(2024, 1, 15)
            ),
            Mock(
                id="dataset-2",
                dataset_name="Technical Docs",
                description="Software documentation",
                document_count=5,
                chunk_count=100,
                status="processing",
                chunking_strategy="semantic",
                created_at=datetime(2024, 1, 10),
                updated_at=datetime(2024, 1, 12)
            )
        ]
        mock_result.scalars.return_value.all.return_value = mock_datasets
        mock_db_session.execute.return_value = mock_result
        
        # Mock vector store stats
        mock_vector_store.get_collection_stats.side_effect = [
            {"document_count": 250},
            {"document_count": 100}
        ]
        
        result = await rag_service.list_user_datasets("user@example.com")
        
        # Verify database query
        mock_db_session.execute.assert_called_once()
        
        # Verify vector store stats calls
        assert mock_vector_store.get_collection_stats.call_count == 2
        
        # Verify result structure
        assert len(result) == 2
        assert result[0]["id"] == "dataset-1"
        assert result[0]["name"] == "Research Papers"
        assert result[0]["description"] == "AI research collection"
        assert result[0]["document_count"] == 10
        assert result[0]["chunk_count"] == 250
        assert result[0]["vector_count"] == 250
        assert result[0]["status"] == "active"
        assert result[0]["chunking_strategy"] == "hybrid"
        
        assert result[1]["id"] == "dataset-2"
        assert result[1]["name"] == "Technical Docs"
        assert result[1]["status"] == "processing"
    
    @pytest.mark.asyncio
    async def test_delete_dataset_success(self, rag_service, mock_db_session, mock_vector_store, sample_rag_dataset):
        """Test successful dataset deletion"""
        # Mock dataset retrieval
        mock_db_session.get.return_value = sample_rag_dataset
        
        # Mock vector store deletion
        mock_vector_store.delete_collection.return_value = True
        
        # Mock database operations
        mock_db_session.delete = AsyncMock()
        mock_db_session.commit = AsyncMock()
        
        result = await rag_service.delete_dataset(
            user_id="user@example.com",
            dataset_id="dataset-123"
        )
        
        # Verify vector collection deletion
        mock_vector_store.delete_collection.assert_called_once_with(
            user_id="user@example.com",
            collection_name="Research Papers"
        )
        
        # Verify database deletion
        mock_db_session.delete.assert_called_once_with(sample_rag_dataset)
        mock_db_session.commit.assert_called_once()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_dataset_access_denied(self, rag_service, mock_db_session, sample_rag_dataset):
        """Test dataset deletion with wrong user access"""
        # Mock dataset with different user
        sample_rag_dataset.user_id = "other@example.com"
        mock_db_session.get.return_value = sample_rag_dataset
        
        with pytest.raises(ValueError, match="Dataset not found or access denied"):
            await rag_service.delete_dataset(
                user_id="user@example.com",
                dataset_id="dataset-123"
            )
    
    @pytest.mark.asyncio
    async def test_delete_dataset_rollback_on_error(self, rag_service, mock_db_session, mock_vector_store, sample_rag_dataset):
        """Test dataset deletion rollback on error"""
        mock_db_session.get.return_value = sample_rag_dataset
        mock_vector_store.delete_collection.side_effect = Exception("Vector store error")
        
        with pytest.raises(Exception, match="Vector store error"):
            await rag_service.delete_dataset(
                user_id="user@example.com",
                dataset_id="dataset-123"
            )
        
        mock_db_session.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_dataset_statistics_success(self, rag_service, mock_db_session, mock_vector_store, sample_rag_dataset):
        """Test getting detailed dataset statistics"""
        # Mock dataset retrieval
        mock_db_session.get.return_value = sample_rag_dataset
        
        # Mock documents query
        mock_documents = [
            Mock(file_size=1024000, file_type="pdf"),
            Mock(file_size=512000, file_type="docx"),
            Mock(file_size=256000, file_type="pdf"),
            Mock(file_size=128000, file_type="txt")
        ]
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_documents
        mock_db_session.execute.return_value = mock_result
        
        # Mock vector store stats
        mock_vector_store.get_collection_stats.return_value = {
            "document_count": 150,
            "storage_path": "/data/test/chromadb"
        }
        
        result = await rag_service.get_dataset_statistics(
            user_id="user@example.com",
            dataset_id="dataset-123"
        )
        
        # Verify result structure
        assert result["dataset_id"] == "dataset-123"
        assert result["dataset_name"] == "Research Papers"
        assert result["description"] == "Collection of AI research papers"
        assert result["user_id"] == "user@example.com"
        assert result["document_count"] == 5
        assert result["chunk_count"] == 150
        assert result["vector_count"] == 150
        assert result["total_size_bytes"] == 1920000  # Sum of all file sizes
        assert result["file_types"] == {"pdf": 2, "docx": 1, "txt": 1}
        assert result["chunking_strategy"] == "hybrid"
        assert result["status"] == "active"
        assert result["storage_path"] == "/data/test/chromadb"
    
    @pytest.mark.asyncio
    async def test_get_dataset_statistics_access_denied(self, rag_service, mock_db_session, sample_rag_dataset):
        """Test dataset statistics with wrong user access"""
        sample_rag_dataset.user_id = "other@example.com"
        mock_db_session.get.return_value = sample_rag_dataset
        
        with pytest.raises(ValueError, match="Dataset not found or access denied"):
            await rag_service.get_dataset_statistics(
                user_id="user@example.com",
                dataset_id="dataset-123"
            )


class TestRAGServiceIntegration:
    """Integration tests for RAG Service workflows"""
    
    @pytest.mark.asyncio
    async def test_complete_rag_workflow(self, rag_service, mock_db_session, mock_resource_client, mock_vector_store, sample_chunks, sample_embeddings):
        """Test complete RAG workflow from dataset creation to search"""
        # 1. Create dataset
        created_dataset = Mock(spec=RAGDataset)
        created_dataset.id = "workflow-dataset"
        created_dataset.dataset_name = "Workflow Test"
        created_dataset.user_id = "user@example.com"
        created_dataset.chunking_strategy = "hybrid"
        created_dataset.document_count = 0
        created_dataset.chunk_count = 0
        
        mock_vector_store.create_user_collection.return_value = "user@example.com_Workflow Test"
        
        with patch.object(rag_service.db, 'add') as mock_add:
            def mock_add_side_effect(obj):
                if hasattr(obj, 'dataset_name'):
                    obj.id = "workflow-dataset"
            mock_add.side_effect = mock_add_side_effect
            
            dataset_id = await rag_service.create_dataset(
                user_id="user@example.com",
                dataset_name="Workflow Test",
                description="Integration test dataset"
            )
        
        assert dataset_id == "workflow-dataset"
        
        # 2. Upload document
        mock_db_session.get.return_value = created_dataset
        mock_resource_client.process_document.return_value = sample_chunks
        mock_resource_client.generate_embeddings.return_value = sample_embeddings
        mock_vector_store.store_vectors.return_value = True
        
        file_content = b"Sample document for testing workflow"
        
        with patch.object(rag_service.db, 'add') as mock_add:
            def mock_add_side_effect(obj):
                if hasattr(obj, 'filename'):
                    obj.id = 1
            mock_add.side_effect = mock_add_side_effect
            
            document_id = await rag_service.upload_document(
                user_id="user@example.com",
                dataset_id="workflow-dataset",
                file_content=file_content,
                filename="test_document.pdf",
                file_type="application/pdf"
            )
        
        assert document_id == 1
        
        # 3. Search dataset
        query_embedding = [0.1, 0.2, 0.3] * 100
        mock_resource_client.generate_query_embeddings.return_value = [query_embedding]
        
        search_results = [
            VectorSearchResult(
                document_id="chunk-1",
                text="Sample chunk from the uploaded document",
                score=0.92,
                metadata={"document_id": 1, "filename": "test_document.pdf"}
            )
        ]
        mock_vector_store.search.return_value = search_results
        
        results = await rag_service.search_dataset(
            user_id="user@example.com",
            dataset_id="workflow-dataset",
            query="sample document",
            top_k=5
        )
        
        assert len(results) == 1
        assert results[0]["text"] == "Sample chunk from the uploaded document"
        assert results[0]["score"] == 0.92
        
        # 4. Get conversation context
        with patch.object(rag_service, 'search_dataset') as mock_search:
            mock_search.return_value = results
            
            context_string, citations = await rag_service.get_conversation_context(
                user_id="user@example.com",
                conversation_id="test-conv",
                query="sample document",
                dataset_ids=["workflow-dataset"]
            )
        
        assert "Sample chunk from the uploaded document" in context_string
        assert len(citations) == 1
        assert citations[0]["filename"] == "test_document.pdf"
        
        # 5. Get dataset statistics
        mock_documents = [Mock(file_size=len(file_content), file_type="pdf")]
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_documents
        mock_db_session.execute.return_value = mock_result
        
        mock_vector_store.get_collection_stats.return_value = {
            "document_count": 3,
            "storage_path": "/data/test/chromadb"
        }
        
        stats = await rag_service.get_dataset_statistics(
            user_id="user@example.com",
            dataset_id="workflow-dataset"
        )
        
        assert stats["dataset_name"] == "Workflow Test"
        assert stats["vector_count"] == 3
        assert stats["total_size_bytes"] == len(file_content)
    
    @pytest.mark.asyncio
    async def test_user_isolation_validation(self, rag_service, mock_db_session, mock_vector_store):
        """Test that user isolation is properly enforced"""
        # Create datasets for different users
        user1_dataset = Mock(spec=RAGDataset)
        user1_dataset.id = "user1-dataset"
        user1_dataset.user_id = "user1@example.com"
        user1_dataset.dataset_name = "User 1 Dataset"
        
        user2_dataset = Mock(spec=RAGDataset)
        user2_dataset.id = "user2-dataset"
        user2_dataset.user_id = "user2@example.com"
        user2_dataset.dataset_name = "User 2 Dataset"
        
        # Test that user1 cannot access user2's dataset
        mock_db_session.get.return_value = user2_dataset
        
        with pytest.raises(ValueError, match="Dataset not found or access denied"):
            await rag_service.search_dataset(
                user_id="user1@example.com",
                dataset_id="user2-dataset",
                query="unauthorized access attempt"
            )
        
        with pytest.raises(ValueError, match="Dataset not found or access denied"):
            await rag_service.upload_document(
                user_id="user1@example.com",
                dataset_id="user2-dataset",
                file_content=b"unauthorized",
                filename="hack.pdf",
                file_type="application/pdf"
            )
        
        with pytest.raises(ValueError, match="Dataset not found or access denied"):
            await rag_service.delete_dataset(
                user_id="user1@example.com",
                dataset_id="user2-dataset"
            )
    
    @pytest.mark.asyncio
    async def test_error_handling_and_cleanup(self, rag_service, mock_db_session, mock_resource_client, mock_vector_store, sample_rag_dataset):
        """Test error handling and proper cleanup on failures"""
        # Test document upload failure with cleanup
        mock_db_session.get.return_value = sample_rag_dataset
        mock_resource_client.process_document.return_value = []  # Empty chunks
        mock_resource_client.generate_embeddings.side_effect = Exception("Embedding generation failed")
        
        with pytest.raises(Exception, match="Embedding generation failed"):
            await rag_service.upload_document(
                user_id="user@example.com",
                dataset_id="dataset-123",
                file_content=b"test content",
                filename="test.pdf",
                file_type="application/pdf"
            )
        
        # Verify rollback was called
        mock_db_session.rollback.assert_called_once()
        
        # Test search failure handling
        mock_resource_client.generate_query_embeddings.side_effect = Exception("Query embedding failed")
        
        with pytest.raises(Exception, match="Query embedding failed"):
            await rag_service.search_dataset(
                user_id="user@example.com",
                dataset_id="dataset-123",
                query="test query"
            )
    
    @pytest.mark.asyncio
    async def test_conversation_context_error_resilience(self, rag_service, mock_db_session):
        """Test conversation context handles individual dataset search failures"""
        # Mock multiple datasets
        mock_result = Mock()
        mock_datasets = [
            Mock(id="dataset-1", user_id="user@example.com", status="active"),
            Mock(id="dataset-2", user_id="user@example.com", status="active"),
            Mock(id="dataset-3", user_id="user@example.com", status="active")
        ]
        mock_result.scalars.return_value.all.return_value = mock_datasets
        mock_db_session.execute.return_value = mock_result
        
        # Mock search results with one failure
        with patch.object(rag_service, 'search_dataset') as mock_search:
            mock_search.side_effect = [
                [{"text": "Result from dataset 1", "score": 0.9, "filename": "doc1.pdf", "chunk_index": 0}],
                Exception("Dataset 2 search failed"),  # This should be caught and logged
                [{"text": "Result from dataset 3", "score": 0.8, "filename": "doc3.pdf", "chunk_index": 0}]
            ]
            
            context_string, citations = await rag_service.get_conversation_context(
                user_id="user@example.com",
                conversation_id="conv-123",
                query="test query"
            )
        
        # Should continue with successful datasets despite one failure
        assert "Result from dataset 1" in context_string
        assert "Result from dataset 3" in context_string
        assert len(citations) == 2
        assert citations[0]["filename"] == "doc1.pdf"
        assert citations[1]["filename"] == "doc3.pdf"
    
    @pytest.mark.asyncio
    async def test_chunking_strategy_variations(self, rag_service, mock_db_session, mock_resource_client, mock_vector_store):
        """Test different chunking strategies"""
        strategies = ["fixed", "semantic", "hierarchical", "hybrid"]
        
        for strategy in strategies:
            # Create dataset with specific chunking strategy
            dataset = Mock(spec=RAGDataset)
            dataset.id = f"dataset-{strategy}"
            dataset.user_id = "user@example.com"
            dataset.dataset_name = f"Dataset {strategy}"
            dataset.chunking_strategy = strategy
            dataset.document_count = 0
            dataset.chunk_count = 0
            
            mock_db_session.get.return_value = dataset
            
            # Mock different chunk patterns for each strategy
            if strategy == "fixed":
                chunks = [{"text": f"Fixed chunk {i}", "metadata": {"size": 512}} for i in range(5)]
            elif strategy == "semantic":
                chunks = [{"text": f"Semantic section {i}", "metadata": {"topic": f"topic_{i}"}} for i in range(3)]
            elif strategy == "hierarchical":
                chunks = [{"text": f"Chapter {i} content", "metadata": {"level": i}} for i in range(4)]
            else:  # hybrid
                chunks = [{"text": f"Hybrid chunk {i}", "metadata": {"type": "mixed"}} for i in range(6)]
            
            mock_resource_client.process_document.return_value = chunks
            mock_resource_client.generate_embeddings.return_value = [[0.1] * 100] * len(chunks)
            mock_vector_store.store_vectors.return_value = True
            
            with patch.object(rag_service.db, 'add') as mock_add:
                def mock_add_side_effect(obj):
                    if hasattr(obj, 'filename'):
                        obj.id = 1
                mock_add.side_effect = mock_add_side_effect
                
                result = await rag_service.upload_document(
                    user_id="user@example.com",
                    dataset_id=f"dataset-{strategy}",
                    file_content=b"test content",
                    filename=f"test_{strategy}.pdf",
                    file_type="application/pdf"
                )
            
            # Verify processing was called with correct strategy
            mock_resource_client.process_document.assert_called_with(
                content=b"test content",
                document_type="application/pdf",
                chunking_strategy=strategy
            )
            
            assert result == 1
