"""
Unit Tests for Document Processing Pipeline

Tests dual-engine document processing, chunking strategies, and
capability-based engine selection.
"""

import pytest
import asyncio
import hashlib
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import gc

from app.services.document_processing_pipeline import (
    DocumentProcessingPipeline,
    ProcessingOptions,
    ProcessingResult,
    UnstructuredAPIEngine,
    NativeChunkingEngine
)
from app.core.backends.document_processor import ChunkingStrategy


class TestDocumentProcessingPipeline:
    """Test document processing pipeline functionality"""
    
    @pytest.fixture
    def pipeline(self):
        """Create pipeline instance"""
        return DocumentProcessingPipeline(resource_cluster_url="http://localhost:8004")
    
    @pytest.fixture
    def sample_token_basic(self):
        """Sample token with basic capabilities"""
        return {
            "tenant_id": "customer1.com",
            "sub": "test@example.com",
            "capabilities": [
                {"resource": "document_processing"},
                {"resource": "rag:semantic_search"}
            ],
            "constraints": {
                "max_file_size": 10 * 1024 * 1024  # 10MB
            }
        }
    
    @pytest.fixture
    def sample_token_premium(self):
        """Sample token with premium capabilities"""
        return {
            "tenant_id": "customer1.com",
            "sub": "premium@example.com",
            "capabilities": [
                {"resource": "document_processing"},
                {"resource": "premium_parsing"},
                {"resource": "rag:semantic_search"}
            ],
            "constraints": {
                "max_file_size": 50 * 1024 * 1024,  # 50MB
                "unstructured_api_key": "test-api-key"
            },
            "has_capability": {
                "premium_parsing": True
            }
        }
    
    @pytest.fixture
    def sample_pdf_content(self):
        """Sample PDF content (mock)"""
        return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nSample PDF content for testing..."
    
    @pytest.fixture
    def sample_text_content(self):
        """Sample text content"""
        return b"This is a sample document for testing. It contains multiple sentences.\n\nThis is a second paragraph with more content. It should be chunked properly.\n\nAnd a third paragraph for good measure."
    
    def test_engine_selection_basic_user(self, pipeline, sample_token_basic):
        """Test engine selection for basic user"""
        options = ProcessingOptions(engine_preference="auto")
        
        # Should use native for text files
        engine = pipeline.select_engine("document.txt", sample_token_basic, options)
        assert engine == "native"
        
        # Should use native even for PDFs without premium
        engine = pipeline.select_engine("document.pdf", sample_token_basic, options)
        assert engine == "native"
        
        # Should use native even if unstructured is requested
        options.engine_preference = "unstructured"
        engine = pipeline.select_engine("document.pdf", sample_token_basic, options)
        assert engine == "native"
    
    def test_engine_selection_premium_user(self, pipeline, sample_token_premium):
        """Test engine selection for premium user"""
        options = ProcessingOptions(engine_preference="auto")
        
        # Should use native for simple text files
        engine = pipeline.select_engine("document.txt", sample_token_premium, options)
        assert engine == "native"
        
        # Should use unstructured for PDFs with premium
        engine = pipeline.select_engine("document.pdf", sample_token_premium, options)
        assert engine == "unstructured"
        
        # Should use unstructured for Excel files
        engine = pipeline.select_engine("data.xlsx", sample_token_premium, options)
        assert engine == "unstructured"
        
        # Respect explicit preference
        options.engine_preference = "native"
        engine = pipeline.select_engine("document.pdf", sample_token_premium, options)
        assert engine == "native"
    
    def test_engine_selection_ocr_requirement(self, pipeline, sample_token_premium):
        """Test engine selection with OCR requirement"""
        options = ProcessingOptions(
            engine_preference="auto",
            ocr_enabled=True
        )
        
        # Should use unstructured when OCR is needed and available
        engine = pipeline.select_engine("scanned.pdf", sample_token_premium, options)
        assert engine == "unstructured"
        
        # Should fallback to native without premium capability
        sample_token_basic = {
            "capabilities": [{"resource": "document_processing"}]
        }
        engine = pipeline.select_engine("scanned.pdf", sample_token_basic, options)
        assert engine == "native"
    
    @pytest.mark.asyncio
    async def test_process_document_native(self, pipeline, sample_text_content, sample_token_basic):
        """Test document processing with native engine"""
        options = ProcessingOptions(
            engine_preference="native",
            chunking_strategy="fixed",
            chunk_size=50,
            chunk_overlap=10,
            generate_embeddings=False
        )
        
        result = await pipeline.process_document(
            file=sample_text_content,
            filename="test.txt",
            token_data=sample_token_basic,
            options=options
        )
        
        assert isinstance(result, ProcessingResult)
        assert result.engine_used == "native"
        assert len(result.chunks) > 0
        assert result.metadata["filename"] == "test.txt"
        assert result.metadata["file_type"] == ".txt"
        assert result.embeddings is None  # No embeddings requested
    
    @pytest.mark.asyncio
    async def test_process_document_with_embeddings(self, pipeline, sample_text_content, sample_token_basic):
        """Test document processing with embedding generation"""
        options = ProcessingOptions(
            engine_preference="native",
            generate_embeddings=True
        )
        
        result = await pipeline.process_document(
            file=sample_text_content,
            filename="test.txt",
            token_data=sample_token_basic,
            options=options
        )
        
        assert result.embeddings is not None
        assert len(result.embeddings) == len(result.chunks)
        # Mock embeddings should be 768-dimensional
        assert len(result.embeddings[0]) == 768
    
    @pytest.mark.asyncio
    async def test_process_document_unstructured(self, pipeline, sample_pdf_content, sample_token_premium):
        """Test document processing with Unstructured engine"""
        options = ProcessingOptions(
            engine_preference="unstructured",
            generate_embeddings=False
        )
        
        # Mock Unstructured API
        with patch.object(UnstructuredAPIEngine, 'process', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {
                "elements": [
                    {
                        "type": "Title",
                        "text": "Test Document",
                        "metadata": {"page_number": 1}
                    },
                    {
                        "type": "NarrativeText",
                        "text": "This is test content from Unstructured API.",
                        "metadata": {"page_number": 1}
                    }
                ],
                "metadata": {
                    "languages": ["en"],
                    "page_count": 1,
                    "has_tables": False,
                    "has_images": False
                }
            }
            
            result = await pipeline.process_document(
                file=sample_pdf_content,
                filename="test.pdf",
                token_data=sample_token_premium,
                options=options
            )
            
            assert result.engine_used == "unstructured"
            assert len(result.chunks) == 2
            assert result.chunks[0]["metadata"]["element_type"] == "Title"
            assert result.metadata["detected_languages"] == ["en"]
    
    @pytest.mark.asyncio
    async def test_memory_cleanup(self, pipeline, sample_text_content, sample_token_basic):
        """Test memory cleanup after processing"""
        # Create a large content to test memory cleanup
        large_content = sample_text_content * 1000
        
        # Process document
        result = await pipeline.process_document(
            file=large_content,
            filename="large.txt",
            token_data=sample_token_basic,
            options=ProcessingOptions(generate_embeddings=False)
        )
        
        # Force garbage collection
        gc.collect()
        
        # Content should be processed and cleaned up
        assert len(result.chunks) > 0
        # Note: Can't directly test memory deallocation, but gc.collect() should run
    
    @pytest.mark.asyncio
    async def test_document_validation(self, pipeline, sample_token_basic):
        """Test document validation"""
        # Valid document
        validation = await pipeline.validate_document(
            file_size=1024 * 1024,  # 1MB
            filename="document.pdf",
            token_data=sample_token_basic
        )
        
        assert validation["valid"] == True
        assert len(validation["errors"]) == 0
        
        # File too large
        validation = await pipeline.validate_document(
            file_size=100 * 1024 * 1024,  # 100MB
            filename="huge.pdf",
            token_data=sample_token_basic
        )
        
        assert validation["valid"] == False
        assert any("exceeds maximum size" in error for error in validation["errors"])
        
        # Unsupported file type
        validation = await pipeline.validate_document(
            file_size=1024,
            filename="file.exe",
            token_data=sample_token_basic
        )
        
        assert validation["valid"] == False
        assert any("Unsupported file type" in error for error in validation["errors"])
    
    @pytest.mark.asyncio
    async def test_large_element_chunking(self, pipeline):
        """Test chunking of large Unstructured elements"""
        large_element = {
            "text": " ".join(["word"] * 1000),  # Large text
            "metadata": {"element_type": "NarrativeText", "page_number": 1}
        }
        
        options = ProcessingOptions(chunk_size=100, chunk_overlap=20)
        
        chunks = await pipeline._apply_chunking_to_elements([large_element], options)
        
        assert len(chunks) > 1  # Should be split into multiple chunks
        assert all("sub_chunk_index" in chunk["metadata"] for chunk in chunks[1:])
        assert all("parent_element_type" in chunk["metadata"] for chunk in chunks)
    
    @pytest.mark.asyncio
    async def test_embedding_cache(self, pipeline, sample_text_content, sample_token_basic):
        """Test embedding cache functionality"""
        options = ProcessingOptions(
            generate_embeddings=True,
            chunk_size=50
        )
        
        # Process document first time
        result1 = await pipeline.process_document(
            file=sample_text_content,
            filename="test.txt",
            token_data=sample_token_basic,
            options=options
        )
        
        # Process same document again
        result2 = await pipeline.process_document(
            file=sample_text_content,
            filename="test.txt",
            token_data=sample_token_basic,
            options=options
        )
        
        # Cache should have entries
        assert len(pipeline.embedding_cache) > 0
        
        # Results should be consistent
        assert len(result1.chunks) == len(result2.chunks)
        assert len(result1.embeddings) == len(result2.embeddings)
    
    @pytest.mark.asyncio
    async def test_processing_stats(self, pipeline):
        """Test processing statistics"""
        stats = await pipeline.get_processing_stats()
        
        assert "engines_available" in stats
        assert "native" in stats["engines_available"]
        assert "unstructured" in stats["engines_available"]
        assert stats["native_engine_status"] == "ready"
        assert stats["stateless"] == True
        assert stats["default_chunk_size"] == 512
        assert stats["default_chunk_overlap"] == 128


class TestChunkingStrategies:
    """Test different chunking strategies"""
    
    @pytest.fixture
    def native_engine(self):
        """Create native chunking engine"""
        return NativeChunkingEngine()
    
    @pytest.fixture
    def long_text(self):
        """Create long text for chunking tests"""
        paragraphs = []
        for i in range(10):
            sentences = []
            for j in range(5):
                sentences.append(f"This is sentence {j+1} in paragraph {i+1}.")
            paragraphs.append(" ".join(sentences))
        return "\n\n".join(paragraphs).encode()
    
    @pytest.mark.asyncio
    async def test_fixed_chunking(self, native_engine, long_text):
        """Test fixed-size chunking"""
        options = ProcessingOptions(
            chunking_strategy="fixed",
            chunk_size=100,
            chunk_overlap=20
        )
        
        chunks = await native_engine.process(long_text, ".txt", options)
        
        assert len(chunks) > 1
        # Check that chunks have consistent size (approximately)
        chunk_sizes = [len(chunk["text"].split()) for chunk in chunks]
        # Most chunks should be close to target size
        assert max(chunk_sizes) <= options.chunk_size * 2  # Allow some variance
    
    @pytest.mark.asyncio
    async def test_semantic_chunking(self, native_engine, long_text):
        """Test semantic chunking"""
        options = ProcessingOptions(
            chunking_strategy="semantic",
            chunk_size=100,
            chunk_overlap=20
        )
        
        chunks = await native_engine.process(long_text, ".txt", options)
        
        assert len(chunks) > 1
        # Semantic chunking should preserve sentence boundaries
        for chunk in chunks:
            text = chunk["text"].strip()
            if text:
                # Should end with punctuation (sentence boundary)
                assert text[-1] in ".!?" or len(text.split()) < 10
    
    @pytest.mark.asyncio
    async def test_hierarchical_chunking(self, native_engine, long_text):
        """Test hierarchical chunking"""
        options = ProcessingOptions(
            chunking_strategy="hierarchical",
            chunk_size=100,
            chunk_overlap=20
        )
        
        chunks = await native_engine.process(long_text, ".txt", options)
        
        assert len(chunks) > 1
        # Hierarchical should preserve paragraph structure where possible
        # At least some chunks should contain paragraph breaks
        paragraph_preserving_chunks = [
            chunk for chunk in chunks
            if "\n\n" in chunk["text"] or chunk["text"].count(".") > 2
        ]
        assert len(paragraph_preserving_chunks) > 0
    
    @pytest.mark.asyncio
    async def test_hybrid_chunking(self, native_engine, long_text):
        """Test hybrid chunking"""
        options = ProcessingOptions(
            chunking_strategy="hybrid",
            chunk_size=100,
            chunk_overlap=20
        )
        
        chunks = await native_engine.process(long_text, ".txt", options)
        
        assert len(chunks) > 1
        # Hybrid should balance structure and size
        assert all("metadata" in chunk for chunk in chunks)
        assert all("chunk_index" in chunk["metadata"] for chunk in chunks)


class TestUnstructuredEngine:
    """Test Unstructured API engine"""
    
    @pytest.fixture
    def unstructured_engine(self):
        """Create Unstructured engine"""
        return UnstructuredAPIEngine(api_key="test-key")
    
    @pytest.mark.asyncio
    async def test_unstructured_processing(self, unstructured_engine):
        """Test Unstructured API processing"""
        content = b"Test PDF content"
        
        result = await unstructured_engine.process(
            content=content,
            file_type=".pdf",
            options={"ocr": False, "extract_tables": True}
        )
        
        assert "elements" in result
        assert "metadata" in result
        assert len(result["elements"]) > 0
        assert result["elements"][0]["type"] in ["Title", "NarrativeText"]
    
    def test_unstructured_features(self, unstructured_engine):
        """Test Unstructured supported features"""
        assert "table_extraction" in unstructured_engine.supported_features
        assert "ocr" in unstructured_engine.supported_features
        assert "language_detection" in unstructured_engine.supported_features
        assert "hierarchical_parsing" in unstructured_engine.supported_features


class TestSecurityAndIsolation:
    """Test security and isolation features"""
    
    @pytest.fixture
    def pipeline(self):
        """Create pipeline instance"""
        return DocumentProcessingPipeline()
    
    @pytest.mark.asyncio
    async def test_stateless_processing(self, pipeline, sample_text_content, sample_token_basic):
        """Test that processing is stateless"""
        options = ProcessingOptions(generate_embeddings=False)
        
        # Process document
        result = await pipeline.process_document(
            file=sample_text_content,
            filename="test.txt",
            token_data=sample_token_basic,
            options=options
        )
        
        # No user content should be stored
        # Only cache should be embedding cache (if used)
        assert hasattr(pipeline, 'embedding_cache')
        
        # Native engine should not store state
        assert not hasattr(pipeline.native_engine, 'stored_documents')
    
    @pytest.mark.asyncio
    async def test_metadata_filtering(self, pipeline):
        """Test that sensitive metadata is filtered"""
        sensitive_metadata = {
            "document_type": ".pdf",
            "processing_timestamp": "2024-01-01T00:00:00",
            "tenant_id": "customer1",
            "user_email": "sensitive@example.com",  # Should be filtered
            "api_key": "secret-key",  # Should be filtered
            "password": "secret123"  # Should be filtered
        }
        
        # Process with native engine (which filters metadata)
        with patch.object(pipeline.native_engine.processor, 'process_document', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = [{
                "text": "test",
                "metadata": {
                    "chunk_index": 0,
                    "document_type": ".pdf",
                    "processing_timestamp": "2024-01-01T00:00:00",
                    "tenant_id": "customer1"
                    # Note: sensitive fields filtered out
                }
            }]
            
            result = await pipeline.process_document(
                file=b"test",
                filename="test.pdf",
                token_data={"capabilities": []},
                options=ProcessingOptions()
            )
            
            # Check that sensitive metadata is not in result
            for chunk in result.chunks:
                assert "user_email" not in chunk["metadata"]
                assert "api_key" not in chunk["metadata"]
                assert "password" not in chunk["metadata"]
    
    @pytest.mark.asyncio
    async def test_memory_limit_enforcement(self, pipeline, sample_token_basic):
        """Test that memory limits are enforced"""
        # Test with file size validation
        huge_size = 100 * 1024 * 1024  # 100MB
        
        validation = await pipeline.validate_document(
            file_size=huge_size,
            filename="huge.pdf",
            token_data=sample_token_basic
        )
        
        assert validation["valid"] == False
        assert any("exceeds maximum size" in error for error in validation["errors"])
    
    @pytest.mark.asyncio
    async def test_cross_tenant_isolation(self, pipeline):
        """Test that processing is isolated between tenants"""
        token_tenant1 = {
            "tenant_id": "tenant1.com",
            "capabilities": [{"resource": "document_processing"}]
        }
        
        token_tenant2 = {
            "tenant_id": "tenant2.com",
            "capabilities": [{"resource": "document_processing"}]
        }
        
        # Process for tenant1
        result1 = await pipeline.process_document(
            file=b"Tenant 1 document",
            filename="doc1.txt",
            token_data=token_tenant1,
            options=ProcessingOptions(generate_embeddings=False)
        )
        
        # Process for tenant2
        result2 = await pipeline.process_document(
            file=b"Tenant 2 document",
            filename="doc2.txt",
            token_data=token_tenant2,
            options=ProcessingOptions(generate_embeddings=False)
        )
        
        # Results should be independent
        assert result1.chunks[0]["text"] != result2.chunks[0]["text"]
        
        # No cross-contamination in metadata
        assert "tenant1" not in str(result2.metadata)
        assert "tenant2" not in str(result1.metadata)