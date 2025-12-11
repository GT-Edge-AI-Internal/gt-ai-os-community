"""
Enhanced Document Processing Pipeline with Dual-Engine Support

Implements the DocumentProcessingPipeline from CLAUDE.md with both native
and Unstructured.io engine support, capability-based selection, and 
stateless processing.
"""

import logging
import asyncio
import gc
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json

from app.core.backends.document_processor import (
    DocumentProcessorBackend,
    ChunkingStrategy
)

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of document processing"""
    chunks: List[Dict[str, str]]
    embeddings: Optional[List[List[float]]]  # Optional embeddings
    metadata: Dict[str, Any]
    engine_used: str
    processing_time_ms: float
    token_count: int


@dataclass
class ProcessingOptions:
    """Options for document processing"""
    engine_preference: str = "auto"  # "native", "unstructured", "auto"
    chunking_strategy: str = "hybrid"  # "fixed", "semantic", "hierarchical", "hybrid"
    chunk_size: int = 512  # tokens for BGE-M3
    chunk_overlap: int = 128  # overlap tokens
    generate_embeddings: bool = True
    extract_metadata: bool = True
    language_detection: bool = True
    ocr_enabled: bool = False  # For scanned PDFs


class UnstructuredAPIEngine:
    """
    Mock Unstructured.io API engine for advanced document parsing.
    In production, this would call the actual Unstructured API.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        self.api_key = api_key
        self.api_url = api_url or "https://api.unstructured.io"
        self.supported_features = [
            "table_extraction",
            "image_extraction",
            "ocr",
            "language_detection",
            "metadata_extraction",
            "hierarchical_parsing"
        ]
    
    async def process(
        self,
        content: bytes,
        file_type: str,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process document using Unstructured API.
        
        This is a mock implementation. In production:
        1. Send content to Unstructured API
        2. Handle rate limiting and retries
        3. Parse structured response
        """
        # Mock processing delay
        await asyncio.sleep(0.5)
        
        # Mock response structure
        return {
            "elements": [
                {
                    "type": "Title",
                    "text": "Document Title",
                    "metadata": {"page_number": 1}
                },
                {
                    "type": "NarrativeText",
                    "text": "This is the main content of the document...",
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


class NativeChunkingEngine:
    """
    Native chunking engine using the existing DocumentProcessorBackend.
    Fast, lightweight, and suitable for most text documents.
    """
    
    def __init__(self):
        self.processor = DocumentProcessorBackend()
    
    async def process(
        self,
        content: bytes,
        file_type: str,
        options: ProcessingOptions
    ) -> List[Dict[str, Any]]:
        """Process document using native chunking"""
        
        strategy = ChunkingStrategy(
            strategy_type=options.chunking_strategy,
            chunk_size=options.chunk_size,
            chunk_overlap=options.chunk_overlap,
            preserve_paragraphs=True,
            preserve_sentences=True
        )
        
        chunks = await self.processor.process_document(
            content=content,
            document_type=file_type,
            strategy=strategy,
            metadata={
                "processing_timestamp": datetime.utcnow().isoformat(),
                "engine": "native"
            }
        )
        
        return chunks


class DocumentProcessingPipeline:
    """
    Dual-engine document processing pipeline with capability-based selection.
    
    Features:
    - Native engine for fast, simple processing
    - Unstructured API for advanced features
    - Capability-based engine selection
    - Stateless processing with memory cleanup
    - Optional embedding generation
    """
    
    def __init__(self, resource_cluster_url: Optional[str] = None):
        self.resource_cluster_url = resource_cluster_url or "http://localhost:8004"
        self.native_engine = NativeChunkingEngine()
        self.unstructured_engine = None  # Lazy initialization
        self.embedding_cache = {}  # Cache for frequently used embeddings
        
        logger.info("Document Processing Pipeline initialized")
    
    def select_engine(
        self,
        filename: str,
        token_data: Dict[str, Any],
        options: ProcessingOptions
    ) -> str:
        """
        Select processing engine based on file type and capabilities.
        
        Args:
            filename: Name of the file being processed
            token_data: Capability token data
            options: Processing options
            
        Returns:
            Engine name: "native" or "unstructured"
        """
        # Check if user has premium parsing capability
        has_premium = any(
            cap.get("resource") == "premium_parsing"
            for cap in token_data.get("capabilities", [])
        )
        
        # Force native if no premium capability
        if not has_premium and options.engine_preference == "unstructured":
            logger.info("Premium parsing requested but not available, using native engine")
            return "native"
        
        # Auto selection logic
        if options.engine_preference == "auto":
            # Use Unstructured for complex formats if available
            complex_formats = [".pdf", ".docx", ".pptx", ".xlsx"]
            needs_ocr = options.ocr_enabled
            needs_tables = filename.lower().endswith((".xlsx", ".csv"))
            
            if has_premium and (
                any(filename.lower().endswith(fmt) for fmt in complex_formats) or
                needs_ocr or needs_tables
            ):
                return "unstructured"
            else:
                return "native"
        
        # Respect explicit preference if capability allows
        if options.engine_preference == "unstructured" and has_premium:
            return "unstructured"
        
        return "native"
    
    async def process_document(
        self,
        file: bytes,
        filename: str,
        token_data: Dict[str, Any],
        options: Optional[ProcessingOptions] = None
    ) -> ProcessingResult:
        """
        Process document with selected engine.
        
        Args:
            file: Document content as bytes
            filename: Name of the file
            token_data: Capability token data
            options: Processing options
            
        Returns:
            ProcessingResult with chunks, embeddings, and metadata
        """
        start_time = datetime.utcnow()
        
        try:
            # Use default options if not provided
            if options is None:
                options = ProcessingOptions()
            
            # Determine file type
            file_type = self._get_file_extension(filename)
            
            # Select engine based on capabilities
            engine = self.select_engine(filename, token_data, options)
            
            # Process with selected engine
            if engine == "unstructured" and token_data.get("has_capability", {}).get("premium_parsing"):
                result = await self._process_with_unstructured(file, filename, token_data, options)
            else:
                result = await self._process_with_native(file, filename, token_data, options)
            
            # Generate embeddings if requested
            embeddings = None
            if options.generate_embeddings:
                embeddings = await self._generate_embeddings(result.chunks, token_data)
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Calculate token count
            token_count = sum(len(chunk["text"].split()) for chunk in result.chunks)
            
            return ProcessingResult(
                chunks=result.chunks,
                embeddings=embeddings,
                metadata={
                    "filename": filename,
                    "file_type": file_type,
                    "processing_timestamp": start_time.isoformat(),
                    "chunk_count": len(result.chunks),
                    "engine_used": engine,
                    "options": {
                        "chunking_strategy": options.chunking_strategy,
                        "chunk_size": options.chunk_size,
                        "chunk_overlap": options.chunk_overlap
                    }
                },
                engine_used=engine,
                processing_time_ms=processing_time,
                token_count=token_count
            )
            
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            raise
        finally:
            # Ensure memory cleanup
            del file
            gc.collect()
    
    async def _process_with_native(
        self,
        file: bytes,
        filename: str,
        token_data: Dict[str, Any],
        options: ProcessingOptions
    ) -> ProcessingResult:
        """Process document with native engine"""
        
        file_type = self._get_file_extension(filename)
        chunks = await self.native_engine.process(file, file_type, options)
        
        return ProcessingResult(
            chunks=chunks,
            embeddings=None,
            metadata={"engine": "native"},
            engine_used="native",
            processing_time_ms=0,
            token_count=0
        )
    
    async def _process_with_unstructured(
        self,
        file: bytes,
        filename: str,
        token_data: Dict[str, Any],
        options: ProcessingOptions
    ) -> ProcessingResult:
        """Process document with Unstructured API"""
        
        # Initialize Unstructured engine if needed
        if self.unstructured_engine is None:
            # Get API key from token constraints or environment
            api_key = token_data.get("constraints", {}).get("unstructured_api_key")
            self.unstructured_engine = UnstructuredAPIEngine(api_key=api_key)
        
        file_type = self._get_file_extension(filename)
        
        # Process with Unstructured
        unstructured_result = await self.unstructured_engine.process(
            content=file,
            file_type=file_type,
            options={
                "ocr": options.ocr_enabled,
                "extract_tables": True,
                "extract_images": False,  # Don't extract images for security
                "languages": ["en", "es", "fr", "de", "zh"]
            }
        )
        
        # Convert Unstructured elements to chunks
        chunks = []
        for element in unstructured_result.get("elements", []):
            chunk_text = element.get("text", "")
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "element_type": element.get("type"),
                        "page_number": element.get("metadata", {}).get("page_number"),
                        "engine": "unstructured"
                    }
                })
        
        # Apply chunking strategy if chunks are too large
        final_chunks = await self._apply_chunking_to_elements(chunks, options)
        
        return ProcessingResult(
            chunks=final_chunks,
            embeddings=None,
            metadata={
                "engine": "unstructured",
                "detected_languages": unstructured_result.get("metadata", {}).get("languages", []),
                "page_count": unstructured_result.get("metadata", {}).get("page_count", 0),
                "has_tables": unstructured_result.get("metadata", {}).get("has_tables", False),
                "has_images": unstructured_result.get("metadata", {}).get("has_images", False)
            },
            engine_used="unstructured",
            processing_time_ms=0,
            token_count=0
        )
    
    async def _apply_chunking_to_elements(
        self,
        elements: List[Dict[str, Any]],
        options: ProcessingOptions
    ) -> List[Dict[str, Any]]:
        """Apply chunking strategy to Unstructured elements if needed"""
        
        final_chunks = []
        
        for element in elements:
            text = element["text"]
            
            # Estimate token count (rough approximation)
            estimated_tokens = len(text.split()) * 1.3
            
            # If element is small enough, keep as is
            if estimated_tokens <= options.chunk_size:
                final_chunks.append(element)
            else:
                # Split large elements using native chunking
                sub_chunks = await self._chunk_text(
                    text,
                    options.chunk_size,
                    options.chunk_overlap
                )
                
                for idx, sub_chunk in enumerate(sub_chunks):
                    chunk_metadata = element["metadata"].copy()
                    chunk_metadata["sub_chunk_index"] = idx
                    chunk_metadata["parent_element_type"] = element["metadata"].get("element_type")
                    
                    final_chunks.append({
                        "text": sub_chunk,
                        "metadata": chunk_metadata
                    })
        
        return final_chunks
    
    async def _chunk_text(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int
    ) -> List[str]:
        """Simple text chunking for large elements"""
        
        words = text.split()
        chunks = []
        
        # Simple word-based chunking
        for i in range(0, len(words), chunk_size - chunk_overlap):
            chunk_words = words[i:i + chunk_size]
            chunks.append(" ".join(chunk_words))
        
        return chunks
    
    async def _generate_embeddings(
        self,
        chunks: List[Dict[str, Any]],
        token_data: Dict[str, Any]
    ) -> List[List[float]]:
        """
        Generate embeddings for chunks.
        
        This is a mock implementation. In production, this would:
        1. Call the embedding service (BGE-M3 or similar)
        2. Handle batching for efficiency
        3. Apply caching for common chunks
        """
        embeddings = []
        
        for chunk in chunks:
            # Check cache first
            chunk_hash = hashlib.sha256(chunk["text"].encode()).hexdigest()
            
            if chunk_hash in self.embedding_cache:
                embeddings.append(self.embedding_cache[chunk_hash])
            else:
                # Mock embedding generation
                # In production: call embedding API
                embedding = [0.1] * 768  # Mock 768-dim embedding (BGE-M3 size)
                embeddings.append(embedding)
                
                # Cache for reuse (with size limit)
                if len(self.embedding_cache) < 1000:
                    self.embedding_cache[chunk_hash] = embedding
        
        return embeddings
    
    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename"""
        
        parts = filename.lower().split(".")
        if len(parts) > 1:
            return f".{parts[-1]}"
        return ".txt"  # Default to text
    
    async def validate_document(
        self,
        file_size: int,
        filename: str,
        token_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate document before processing.
        
        Args:
            file_size: Size of file in bytes
            filename: Name of the file
            token_data: Capability token data
            
        Returns:
            Validation result with warnings and errors
        """
        # Get size limits from token
        max_size = token_data.get("constraints", {}).get("max_file_size", 50 * 1024 * 1024)
        
        validation = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": []
        }
        
        # Check file size
        if file_size > max_size:
            validation["valid"] = False
            validation["errors"].append(f"File exceeds maximum size of {max_size / 1024 / 1024:.1f} MiB")
        elif file_size > 10 * 1024 * 1024:
            validation["warnings"].append("Large file may take longer to process")
            validation["recommendations"].append("Consider using streaming processing for better performance")
        
        # Check file type
        file_type = self._get_file_extension(filename)
        supported_types = [".pdf", ".docx", ".txt", ".md", ".html", ".csv", ".xlsx", ".pptx"]
        
        if file_type not in supported_types:
            validation["valid"] = False
            validation["errors"].append(f"Unsupported file type: {file_type}")
            validation["recommendations"].append(f"Supported types: {', '.join(supported_types)}")
        
        # Check for special processing needs
        if file_type in [".xlsx", ".csv"]:
            validation["recommendations"].append("Table extraction will be applied automatically")
        
        if file_type == ".pdf":
            validation["recommendations"].append("Enable OCR if document contains scanned images")
        
        return validation
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        
        return {
            "engines_available": ["native", "unstructured"],
            "native_engine_status": "ready",
            "unstructured_engine_status": "ready" if self.unstructured_engine else "not_initialized",
            "embedding_cache_size": len(self.embedding_cache),
            "supported_formats": [".pdf", ".docx", ".txt", ".md", ".html", ".csv", ".xlsx", ".pptx"],
            "default_chunk_size": 512,
            "default_chunk_overlap": 128,
            "stateless": True
        }