"""
Document and RAG Models for GT 2.0 Tenant Backend - Service-Based Architecture

Pydantic models for document entities using the PostgreSQL + PGVector backend.
Stores document metadata, RAG datasets, and processing status.
Perfect tenant isolation - each tenant has separate document data.
All vectors stored encrypted in tenant-specific ChromaDB.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid

from pydantic import Field, ConfigDict
from app.models.base import BaseServiceModel, BaseCreateModel, BaseUpdateModel, BaseResponseModel

# SQLAlchemy imports for database models
from sqlalchemy import Column, String, Integer, BigInteger, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

# PGVector import for embeddings
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    # Fallback if pgvector not available
    from sqlalchemy import Text as Vector


class DocumentStatus(str, Enum):
    """Document processing status enumeration"""
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class DocumentType(str, Enum):
    """Document type enumeration"""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"
    HTML = "html"
    JSON = "json"
    CSV = "csv"
    OTHER = "other"


class Document(BaseServiceModel):
    """
    Document model for GT 2.0 service-based architecture.
    
    Represents a document with metadata, processing status,
    and RAG integration for knowledge retrieval.
    """
    
    # Core document properties
    filename: str = Field(..., min_length=1, max_length=255, description="Original filename")
    original_name: str = Field(..., min_length=1, max_length=255, description="User-provided name")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    mime_type: str = Field(..., max_length=100, description="MIME type of the file")
    doc_type: DocumentType = Field(..., description="Document type classification")
    
    # Storage and processing
    file_path: str = Field(..., description="Storage path for the file")
    content_hash: Optional[str] = Field(None, max_length=64, description="SHA-256 hash of content")
    status: DocumentStatus = Field(default=DocumentStatus.UPLOADING, description="Processing status")
    
    # Owner and access
    owner_id: str = Field(..., description="User ID of the document owner")
    dataset_id: Optional[str] = Field(None, description="Associated dataset ID")
    
    # RAG and processing metadata
    content_preview: Optional[str] = Field(None, max_length=500, description="Content preview")
    extracted_text: Optional[str] = Field(None, description="Extracted text content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    
    # Processing statistics
    chunk_count: int = Field(default=0, description="Number of chunks created")
    vector_count: int = Field(default=0, description="Number of vectors stored")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")
    
    # Errors and logs
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    processing_log: List[str] = Field(default_factory=list, description="Processing log entries")
    
    # Timestamps
    processed_at: Optional[datetime] = Field(None, description="When processing completed")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "documents"
    
    def mark_processing(self) -> None:
        """Mark document as processing"""
        self.status = DocumentStatus.PROCESSING
        self.update_timestamp()
    
    def mark_completed(self, chunk_count: int, vector_count: int, processing_time_ms: float) -> None:
        """Mark document processing as completed"""
        self.status = DocumentStatus.COMPLETED
        self.chunk_count = chunk_count
        self.vector_count = vector_count
        self.processing_time_ms = processing_time_ms
        self.processed_at = datetime.utcnow()
        self.update_timestamp()
    
    def mark_failed(self, error_message: str) -> None:
        """Mark document processing as failed"""
        self.status = DocumentStatus.FAILED
        self.error_message = error_message
        self.update_timestamp()
    
    def add_log_entry(self, message: str) -> None:
        """Add a processing log entry"""
        timestamp = datetime.utcnow().isoformat()
        self.processing_log.append(f"[{timestamp}] {message}")


class RAGDataset(BaseServiceModel):
    """
    RAG Dataset model for organizing documents into collections.
    
    Groups related documents together for focused retrieval and
    provides dataset-level configuration and statistics.
    """
    
    # Core dataset properties
    name: str = Field(..., min_length=1, max_length=255, description="Dataset name")
    description: Optional[str] = Field(None, max_length=1000, description="Dataset description")
    
    # Owner and access
    owner_id: str = Field(..., description="User ID of the dataset owner")
    
    # Configuration
    chunk_size: int = Field(default=1000, ge=100, le=5000, description="Default chunk size")
    chunk_overlap: int = Field(default=200, ge=0, le=1000, description="Default chunk overlap")
    embedding_model: str = Field(default="all-MiniLM-L6-v2", description="Embedding model to use")
    
    # Statistics
    document_count: int = Field(default=0, description="Number of documents")
    total_chunks: int = Field(default=0, description="Total chunks across all documents")
    total_vectors: int = Field(default=0, description="Total vectors stored")
    total_size_bytes: int = Field(default=0, description="Total size of all documents")
    
    # Status
    is_public: bool = Field(default=False, description="Whether dataset is publicly accessible")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "rag_datasets"
    
    def update_statistics(self, doc_count: int, chunk_count: int, vector_count: int, size_bytes: int) -> None:
        """Update dataset statistics"""
        self.document_count = doc_count
        self.total_chunks = chunk_count
        self.total_vectors = vector_count
        self.total_size_bytes = size_bytes
        self.update_timestamp()


class DatasetDocument(BaseServiceModel):
    """
    Dataset-Document relationship model for GT 2.0 service-based architecture.
    
    Junction table model that links documents to RAG datasets,
    tracking the relationship and statistics.
    """
    
    # Core relationship properties
    dataset_id: str = Field(..., description="RAG dataset ID")
    document_id: str = Field(..., description="Document ID")
    user_id: str = Field(..., description="User who added document to dataset")
    
    # Statistics
    chunk_count: int = Field(default=0, description="Number of chunks for this document")
    vector_count: int = Field(default=0, description="Number of vectors stored for this document")
    
    # Status
    processing_status: str = Field(default="pending", max_length=50, description="Processing status")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "dataset_documents"


class DocumentChunk(BaseServiceModel):
    """
    Document chunk model for processed document pieces.
    
    Represents individual chunks of processed documents with 
    embeddings and metadata for RAG retrieval.
    """
    
    # Core chunk properties
    document_id: str = Field(..., description="Parent document ID")
    chunk_index: int = Field(..., ge=0, description="Chunk index within document")
    chunk_text: str = Field(..., min_length=1, description="Chunk text content")
    
    # Chunk metadata
    chunk_size: int = Field(..., ge=1, description="Character count of chunk")
    token_count: Optional[int] = Field(None, description="Token count for chunk")
    chunk_metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk-specific metadata")
    
    # Embedding information
    embedding_id: Optional[str] = Field(None, description="Vector store embedding ID")
    embedding_model: Optional[str] = Field(None, max_length=100, description="Model used for embedding")
    
    # Position and context
    start_char: Optional[int] = Field(None, description="Starting character position in document")
    end_char: Optional[int] = Field(None, description="Ending character position in document")
    
    # Model configuration
    model_config = ConfigDict(
        protected_namespaces=(),
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get the database table name"""
        return "document_chunks"


class DocumentCreate(BaseCreateModel):
    """Model for creating new documents"""
    filename: str = Field(..., min_length=1, max_length=255)
    original_name: str = Field(..., min_length=1, max_length=255)
    file_size: int = Field(..., ge=0)
    mime_type: str = Field(..., max_length=100)
    doc_type: DocumentType
    file_path: str
    content_hash: Optional[str] = Field(None, max_length=64)
    owner_id: str
    dataset_id: Optional[str] = None
    content_preview: Optional[str] = Field(None, max_length=500)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentUpdate(BaseUpdateModel):
    """Model for updating documents"""
    original_name: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[DocumentStatus] = None
    dataset_id: Optional[str] = None
    content_preview: Optional[str] = Field(None, max_length=500)
    extracted_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    chunk_count: Optional[int] = Field(None, ge=0)
    vector_count: Optional[int] = Field(None, ge=0)
    processing_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None


class DocumentResponse(BaseResponseModel):
    """Model for document API responses"""
    id: str
    filename: str
    original_name: str
    file_size: int
    mime_type: str
    doc_type: DocumentType
    file_path: str
    content_hash: Optional[str]
    status: DocumentStatus
    owner_id: str
    dataset_id: Optional[str]
    content_preview: Optional[str]
    metadata: Dict[str, Any]
    chunk_count: int
    vector_count: int
    processing_time_ms: Optional[float]
    error_message: Optional[str]
    processing_log: List[str]
    processed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class RAGDatasetCreate(BaseCreateModel):
    """Model for creating new RAG datasets"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    owner_id: str
    chunk_size: int = Field(default=1000, ge=100, le=5000)
    chunk_overlap: int = Field(default=200, ge=0, le=1000)
    embedding_model: str = Field(default="all-MiniLM-L6-v2")
    is_public: bool = Field(default=False)


class RAGDatasetUpdate(BaseUpdateModel):
    """Model for updating RAG datasets"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    chunk_size: Optional[int] = Field(None, ge=100, le=5000)
    chunk_overlap: Optional[int] = Field(None, ge=0, le=1000)
    embedding_model: Optional[str] = None
    is_public: Optional[bool] = None


class RAGDatasetResponse(BaseResponseModel):
    """Model for RAG dataset API responses"""
    id: str
    name: str
    description: Optional[str]
    owner_id: str
    chunk_size: int
    chunk_overlap: int
    embedding_model: str
    document_count: int
    total_chunks: int
    total_vectors: int
    total_size_bytes: int
    is_public: bool
    created_at: datetime
    updated_at: datetime


# SQLAlchemy Database Models for PostgreSQL + PGVector

class Document(Base):
    """SQLAlchemy model for documents table"""
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    dataset_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    file_hash = Column(String(64), nullable=True)

    content_text = Column(Text, nullable=True)
    chunk_count = Column(Integer, default=0)
    processing_status = Column(String(50), default="pending")
    error_message = Column(Text, nullable=True)

    doc_metadata = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """SQLAlchemy model for document_chunks table"""
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    dataset_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(32), nullable=True)
    token_count = Column(Integer, nullable=True)

    # PGVector embedding column (1024 dimensions for BGE-M3)
    embedding = Column(Vector(1024), nullable=True)

    chunk_metadata = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    document = relationship("Document", back_populates="chunks")


class Dataset(Base):
    """SQLAlchemy model for datasets table"""
    __tablename__ = "datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # created_by in schema

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    chunk_size = Column(Integer, default=512)
    chunk_overlap = Column(Integer, default=128)
    embedding_model = Column(String(100), default='BAAI/bge-m3')
    search_method = Column(String(20), default='hybrid')
    specialized_language = Column(Boolean, default=False)

    is_active = Column(Boolean, default=True)
    visibility = Column(String(20), default='individual')
    access_group = Column(String(50), default='individual')

    dataset_metadata = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())