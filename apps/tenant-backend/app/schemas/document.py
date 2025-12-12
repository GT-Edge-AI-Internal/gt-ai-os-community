"""
Document Pydantic schemas for GT 2.0 Tenant Backend

Defines request/response schemas for document and RAG operations.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class DocumentResponse(BaseModel):
    """Document response schema"""
    id: int
    uuid: str
    filename: str
    original_filename: str
    file_type: str
    file_extension: str
    file_size_bytes: int
    processing_status: str
    chunk_count: int
    content_summary: Optional[str] = None
    detected_language: Optional[str] = None
    content_type: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    uploaded_by: str
    tags: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    access_count: int = 0
    is_active: bool = True
    is_searchable: bool = True
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RAGDatasetCreate(BaseModel):
    """Schema for creating a RAG dataset"""
    dataset_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    chunking_strategy: str = Field(default="hybrid", pattern="^(fixed|semantic|hierarchical|hybrid)$")
    chunk_size: int = Field(default=512, ge=128, le=2048)
    chunk_overlap: int = Field(default=128, ge=0, le=512)
    embedding_model: str = Field(default="BAAI/bge-m3")

    @validator('chunk_overlap')
    def validate_chunk_overlap(cls, v, values):
        if 'chunk_size' in values and v >= values['chunk_size']:
            raise ValueError('chunk_overlap must be less than chunk_size')
        return v


class RAGDatasetResponse(BaseModel):
    """RAG dataset response schema"""
    id: str
    user_id: str
    dataset_name: str
    description: Optional[str] = None
    chunking_strategy: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    document_count: int = 0
    chunk_count: int = 0
    vector_count: int = 0
    total_size_bytes: int = 0
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentChunkResponse(BaseModel):
    """Document chunk response schema"""
    id: str
    chunk_index: int
    chunk_metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    """Document search request schema"""
    query: str = Field(..., min_length=1, max_length=1000)
    dataset_ids: Optional[List[str]] = None
    top_k: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class SearchResult(BaseModel):
    """Document search result schema"""
    document_id: Optional[int] = None
    dataset_id: Optional[str] = None
    dataset_name: Optional[str] = None
    text: str
    similarity: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    filename: Optional[str] = None
    chunk_index: Optional[int] = None


class SearchResponse(BaseModel):
    """Document search response schema"""
    query: str
    results: List[SearchResult]
    total_results: int
    search_time_ms: Optional[float] = None


class DocumentContextResponse(BaseModel):
    """Document context response schema"""
    document_id: int
    document_name: str
    query: str
    relevant_chunks: List[SearchResult]
    context_text: str


class RAGStatistics(BaseModel):
    """RAG usage statistics schema"""
    user_id: str
    document_count: int
    dataset_count: int
    total_size_bytes: int
    total_size_mb: float
    total_chunks: int
    processed_documents: int
    pending_documents: int
    failed_documents: int


class ProcessDocumentRequest(BaseModel):
    """Document processing request schema"""
    chunking_strategy: Optional[str] = Field(default="hybrid", pattern="^(fixed|semantic|hierarchical|hybrid)$")


class ProcessDocumentResponse(BaseModel):
    """Document processing response schema"""
    status: str
    document_id: int
    chunk_count: int
    vector_store_ids: List[str]
    processing_time_ms: Optional[float] = None


class UploadDocumentResponse(BaseModel):
    """Document upload response schema"""
    document: DocumentResponse
    processing_initiated: bool = False
    message: str = "Document uploaded successfully"