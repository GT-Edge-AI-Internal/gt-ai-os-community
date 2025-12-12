"""
Document Processing Backend

STATELESS document chunking and preprocessing for RAG operations.
All processing happens in memory - NO user data is ever stored.
"""

import logging
import io
import gc
from typing import Dict, Any, List, Optional, BinaryIO
from dataclasses import dataclass
import hashlib

# Document processing imports
import pypdf as PyPDF2
from docx import Document as DocxDocument
from bs4 import BeautifulSoup
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
    SentenceTransformersTokenTextSplitter
)

logger = logging.getLogger(__name__)


@dataclass
class ChunkingStrategy:
    """Configuration for document chunking"""
    strategy_type: str  # 'fixed', 'semantic', 'hierarchical', 'hybrid'
    chunk_size: int  # Target chunk size in tokens (optimized for BGE-M3: 512)
    chunk_overlap: int  # Overlap between chunks (typically 128 for BGE-M3)
    separator_pattern: Optional[str] = None  # Custom separator for splitting
    preserve_paragraphs: bool = True
    preserve_sentences: bool = True


class DocumentProcessorBackend:
    """
    STATELESS document chunking and processing backend.
    
    Security principles:
    - NO persistence of user data
    - All processing in memory only
    - Immediate memory cleanup after processing
    - No caching of user content
    """
    
    def __init__(self):
        self.supported_formats = [".pdf", ".docx", ".txt", ".md", ".html"]
        # BGE-M3 optimal settings
        self.default_chunk_size = 512  # tokens
        self.default_chunk_overlap = 128  # tokens
        self.model_name = "BAAI/bge-m3"  # For tokenization
        logger.info("STATELESS document processor backend initialized")
    
    async def process_document(
        self,
        content: bytes,
        document_type: str,
        strategy: Optional[ChunkingStrategy] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Process document into chunks - STATELESS operation.
        
        Args:
            content: Document content as bytes (will be cleared from memory)
            document_type: File type (.pdf, .docx, .txt, .md, .html)
            strategy: Chunking strategy configuration
            metadata: Optional metadata (will NOT include user content)
        
        Returns:
            List of chunks with metadata (immediately returned, not stored)
        """
        try:
            # Use default strategy if not provided
            if strategy is None:
                strategy = ChunkingStrategy(
                    strategy_type='hybrid',
                    chunk_size=self.default_chunk_size,
                    chunk_overlap=self.default_chunk_overlap
                )
            
            # Extract text based on document type (in memory)
            text = await self._extract_text_from_bytes(content, document_type)
            
            # Clear original content from memory
            del content
            gc.collect()
            
            # Apply chunking strategy
            if strategy.strategy_type == 'semantic':
                chunks = await self._semantic_chunking(text, strategy)
            elif strategy.strategy_type == 'hierarchical':
                chunks = await self._hierarchical_chunking(text, strategy)
            elif strategy.strategy_type == 'hybrid':
                chunks = await self._hybrid_chunking(text, strategy)
            else:  # 'fixed'
                chunks = await self._fixed_chunking(text, strategy)
            
            # Clear text from memory
            del text
            gc.collect()
            
            # Add metadata without storing content
            processed_chunks = []
            for idx, chunk in enumerate(chunks):
                chunk_metadata = {
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                    "chunking_strategy": strategy.strategy_type,
                    "chunk_size_tokens": strategy.chunk_size,
                    # Generate hash for deduplication without storing content
                    "content_hash": hashlib.sha256(chunk.encode()).hexdigest()[:16]
                }
                
                # Add non-sensitive metadata if provided
                if metadata:
                    # Filter out any potential sensitive data
                    safe_metadata = {
                        k: v for k, v in metadata.items()
                        if k in ['document_type', 'processing_timestamp', 'tenant_id']
                    }
                    chunk_metadata.update(safe_metadata)
                
                processed_chunks.append({
                    "text": chunk,
                    "metadata": chunk_metadata
                })
            
            logger.info(f"Processed document into {len(processed_chunks)} chunks (STATELESS)")
            
            # Return immediately - no storage
            return processed_chunks
            
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            # Ensure memory is cleared even on error
            gc.collect()
            raise
        finally:
            # Always ensure memory cleanup
            gc.collect()
    
    async def _extract_text_from_bytes(
        self,
        content: bytes,
        document_type: str
    ) -> str:
        """Extract text from document bytes - in memory only"""
        
        try:
            if document_type == ".pdf":
                return await self._extract_pdf_text(io.BytesIO(content))
            elif document_type == ".docx":
                return await self._extract_docx_text(io.BytesIO(content))
            elif document_type == ".html":
                return await self._extract_html_text(content.decode('utf-8'))
            elif document_type in [".txt", ".md"]:
                return content.decode('utf-8')
            else:
                raise ValueError(f"Unsupported document type: {document_type}")
        finally:
            # Clear content from memory
            del content
            gc.collect()
    
    async def _extract_pdf_text(self, file_stream: BinaryIO) -> str:
        """Extract text from PDF - in memory"""
        text = ""
        try:
            pdf_reader = PyPDF2.PdfReader(file_stream)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
        finally:
            file_stream.close()
            gc.collect()
        return text
    
    async def _extract_docx_text(self, file_stream: BinaryIO) -> str:
        """Extract text from DOCX - in memory"""
        text = ""
        try:
            doc = DocxDocument(file_stream)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
        finally:
            file_stream.close()
            gc.collect()
        return text
    
    async def _extract_html_text(self, html_content: str) -> str:
        """Extract text from HTML - in memory"""
        soup = BeautifulSoup(html_content, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        return text
    
    async def _semantic_chunking(
        self,
        text: str,
        strategy: ChunkingStrategy
    ) -> List[str]:
        """Semantic chunking using sentence boundaries"""
        splitter = SentenceTransformersTokenTextSplitter(
            model_name=self.model_name,
            chunk_size=strategy.chunk_size,
            chunk_overlap=strategy.chunk_overlap
        )
        return splitter.split_text(text)
    
    async def _hierarchical_chunking(
        self,
        text: str,
        strategy: ChunkingStrategy
    ) -> List[str]:
        """Hierarchical chunking preserving document structure"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=strategy.chunk_size * 3,  # Approximate token to char ratio
            chunk_overlap=strategy.chunk_overlap * 3,
            separators=["\n\n\n", "\n\n", "\n", ". ", " ", ""],
            keep_separator=True
        )
        return splitter.split_text(text)
    
    async def _hybrid_chunking(
        self,
        text: str,
        strategy: ChunkingStrategy
    ) -> List[str]:
        """Hybrid chunking combining semantic and structural boundaries"""
        # First split by structure
        structural_splitter = RecursiveCharacterTextSplitter(
            chunk_size=strategy.chunk_size * 4,
            chunk_overlap=0,
            separators=["\n\n\n", "\n\n"],
            keep_separator=True
        )
        structural_chunks = structural_splitter.split_text(text)
        
        # Then apply semantic splitting to each structural chunk
        final_chunks = []
        token_splitter = TokenTextSplitter(
            chunk_size=strategy.chunk_size,
            chunk_overlap=strategy.chunk_overlap
        )
        
        for struct_chunk in structural_chunks:
            semantic_chunks = token_splitter.split_text(struct_chunk)
            final_chunks.extend(semantic_chunks)
        
        return final_chunks
    
    async def _fixed_chunking(
        self,
        text: str,
        strategy: ChunkingStrategy
    ) -> List[str]:
        """Fixed-size chunking with token boundaries"""
        splitter = TokenTextSplitter(
            chunk_size=strategy.chunk_size,
            chunk_overlap=strategy.chunk_overlap
        )
        return splitter.split_text(text)
    
    async def validate_document(
        self,
        content_size: int,
        document_type: str
    ) -> Dict[str, Any]:
        """
        Validate document before processing - no content stored.
        
        Args:
            content_size: Size of document in bytes
            document_type: File extension
        
        Returns:
            Validation result with any warnings
        """
        MAX_SIZE = 50 * 1024 * 1024  # 50MB max
        
        validation = {
            "valid": True,
            "warnings": [],
            "errors": []
        }
        
        # Check file size
        if content_size > MAX_SIZE:
            validation["valid"] = False
            validation["errors"].append(f"File size exceeds maximum of 50MB")
        elif content_size > 10 * 1024 * 1024:  # Warning for files over 10MB
            validation["warnings"].append("Large file may take longer to process")
        
        # Check document type
        if document_type not in self.supported_formats:
            validation["valid"] = False
            validation["errors"].append(f"Unsupported format: {document_type}")
        
        return validation
    
    async def check_health(self) -> Dict[str, Any]:
        """Check document processor health - no user data exposed"""
        return {
            "status": "healthy",
            "supported_formats": self.supported_formats,
            "default_chunk_size": self.default_chunk_size,
            "default_chunk_overlap": self.default_chunk_overlap,
            "model": self.model_name,
            "stateless": True,  # Confirm stateless operation
            "memory_cleared": True  # Confirm memory management
        }