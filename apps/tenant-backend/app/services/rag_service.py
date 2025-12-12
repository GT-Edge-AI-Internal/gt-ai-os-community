"""
RAG Service for GT 2.0 Tenant Backend

Orchestrates document processing, embedding generation, and vector storage
with perfect tenant isolation and zero downtime compliance.
"""

import logging
import asyncio
import aiofiles
import os
import json
import gc
from typing import Dict, Any, List, Optional, BinaryIO
from datetime import datetime
from pathlib import Path
import hashlib

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.models.document import Document, RAGDataset, DatasetDocument, DocumentChunk
from app.core.database import get_db_session
from app.core.config import get_settings
from app.core.resource_client import ResourceClusterClient

logger = logging.getLogger(__name__)


class RAGService:
    """
    Comprehensive RAG service with perfect tenant isolation.
    
    GT 2.0 Security Principles:
    - Perfect tenant isolation (all operations user-scoped)
    - Stateless document processing (no data persistence in Resource Cluster)
    - Encrypted vector storage per tenant
    - Zero downtime compliance (async operations)
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.resource_client = ResourceClusterClient()
        
        # Tenant-specific directories
        self.upload_directory = Path(self.settings.upload_directory)
        self.temp_directory = Path(self.settings.temp_directory)
        
        # Ensure directories exist with secure permissions
        self._ensure_directories()
        
        logger.info("RAG service initialized with tenant isolation")
    
    def _ensure_directories(self):
        """Ensure required directories exist with secure permissions"""
        for directory in [self.upload_directory, self.temp_directory]:
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    
    async def create_rag_dataset(
        self,
        user_id: str,
        dataset_name: str,
        description: Optional[str] = None,
        chunking_strategy: str = "hybrid",
        chunk_size: int = 512,
        chunk_overlap: int = 128,
        embedding_model: str = "BAAI/bge-m3"
    ) -> RAGDataset:
        """Create a new RAG dataset with tenant isolation"""
        try:
            # Check if dataset already exists for this user
            existing = await self.db.execute(
                select(RAGDataset).where(
                    and_(
                        RAGDataset.user_id == user_id,
                        RAGDataset.dataset_name == dataset_name
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Dataset '{dataset_name}' already exists for user")
            
            # Create dataset
            dataset = RAGDataset(
                user_id=user_id,
                dataset_name=dataset_name,
                description=description,
                chunking_strategy=chunking_strategy,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                embedding_model=embedding_model
            )
            
            self.db.add(dataset)
            await self.db.commit()
            await self.db.refresh(dataset)
            
            logger.info(f"Created RAG dataset '{dataset_name}' for user {user_id}")
            return dataset
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create RAG dataset: {e}")
            raise
    
    async def upload_document(
        self,
        user_id: str,
        file_content: bytes,
        filename: str,
        file_type: str,
        dataset_id: Optional[str] = None
    ) -> Document:
        """Upload and store document with tenant isolation"""
        try:
            # Validate file
            file_extension = Path(filename).suffix.lower()
            if not file_extension:
                raise ValueError("File must have an extension")
            
            # Generate secure filename
            file_hash = hashlib.sha256(file_content).hexdigest()[:16]
            secure_filename = f"{user_id}_{file_hash}_{filename}"
            
            # Tenant-specific file path
            user_upload_dir = self.upload_directory / user_id
            user_upload_dir.mkdir(exist_ok=True, mode=0o700)
            
            file_path = user_upload_dir / secure_filename
            
            # Save file with secure permissions
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)
            
            # Set file permissions (owner read/write only)
            os.chmod(file_path, 0o600)
            
            # Create document record
            document = Document(
                filename=secure_filename,
                original_filename=filename,
                file_path=str(file_path),
                file_type=file_type,
                file_extension=file_extension,
                file_size_bytes=len(file_content),
                uploaded_by=user_id,
                processing_status="pending"
            )
            
            self.db.add(document)
            await self.db.commit()
            await self.db.refresh(document)
            
            # Add to dataset if specified
            if dataset_id:
                await self.add_document_to_dataset(user_id, document.id, dataset_id)
            
            # Clear file content from memory
            del file_content
            gc.collect()
            
            logger.info(f"Uploaded document '{filename}' for user {user_id}")
            return document
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to upload document: {e}")
            # Clear sensitive data even on error
            if 'file_content' in locals():
                del file_content
                gc.collect()
            raise
    
    async def process_document(
        self,
        user_id: str,
        document_id: int,
        tenant_id: str,
        chunking_strategy: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process document into chunks and generate embeddings"""
        try:
            # Get document with ownership check
            document = await self._get_user_document(user_id, document_id)
            if not document:
                raise PermissionError("Document not found or access denied")
            
            # Check if already processed
            if document.is_processing_complete():
                logger.info(f"Document {document_id} already processed")
                return {"status": "already_processed", "chunk_count": document.chunk_count}
            
            # Mark as processing
            document.mark_processing_started()
            await self.db.commit()
            
            # Read document file
            file_content = await self._read_document_file(document)
            
            # Process document using Resource Cluster (stateless)
            chunks = await self.resource_client.process_document(
                content=file_content,
                document_type=document.file_extension,
                strategy_type=chunking_strategy or "hybrid",
                tenant_id=tenant_id,
                user_id=user_id
            )
            
            # Clear file content from memory immediately
            del file_content
            gc.collect()
            
            if not chunks:
                raise ValueError("Document processing returned no chunks")
            
            # Generate embeddings for chunks (stateless)
            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings = await self.resource_client.generate_document_embeddings(
                documents=chunk_texts,
                tenant_id=tenant_id,
                user_id=user_id
            )
            
            if len(embeddings) != len(chunk_texts):
                raise ValueError("Embedding count mismatch with chunk count")
            
            # Store vectors in ChromaDB via Resource Cluster
            dataset_name = f"doc_{document.id}"
            collection_created = await self.resource_client.create_vector_collection(
                tenant_id=tenant_id,
                user_id=user_id,
                dataset_name=dataset_name
            )
            
            if not collection_created:
                raise RuntimeError("Failed to create vector collection")
            
            # Store vectors with metadata
            chunk_metadata = [chunk["metadata"] for chunk in chunks]
            vector_stored = await self.resource_client.store_vectors(
                tenant_id=tenant_id,
                user_id=user_id,
                dataset_name=dataset_name,
                documents=chunk_texts,
                embeddings=embeddings,
                metadata=chunk_metadata
            )
            
            if not vector_stored:
                raise RuntimeError("Failed to store vectors")
            
            # Clear embedding data from memory
            del chunk_texts, embeddings
            gc.collect()
            
            # Update document record
            vector_store_ids = [f"{tenant_id}:{user_id}:{dataset_name}"]
            document.mark_processing_complete(
                chunk_count=len(chunks),
                vector_store_ids=vector_store_ids
            )
            
            await self.db.commit()
            
            logger.info(f"Processed document {document_id} into {len(chunks)} chunks")
            
            return {
                "status": "completed",
                "document_id": document_id,
                "chunk_count": len(chunks),
                "vector_store_ids": vector_store_ids
            }
            
        except Exception as e:
            # Mark document processing as failed
            if 'document' in locals() and document:
                document.mark_processing_failed({"error": str(e)})
                await self.db.commit()
            
            logger.error(f"Failed to process document {document_id}: {e}")
            # Ensure memory cleanup
            gc.collect()
            raise
    
    async def add_document_to_dataset(
        self,
        user_id: str,
        document_id: int,
        dataset_id: str
    ) -> DatasetDocument:
        """Add processed document to RAG dataset"""
        try:
            # Verify dataset ownership
            dataset = await self._get_user_dataset(user_id, dataset_id)
            if not dataset:
                raise PermissionError("Dataset not found or access denied")
            
            # Verify document ownership
            document = await self._get_user_document(user_id, document_id)
            if not document:
                raise PermissionError("Document not found or access denied")
            
            # Check if already in dataset
            existing = await self.db.execute(
                select(DatasetDocument).where(
                    and_(
                        DatasetDocument.dataset_id == dataset_id,
                        DatasetDocument.document_id == document_id
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError("Document already in dataset")
            
            # Create dataset document relationship
            dataset_doc = DatasetDocument(
                dataset_id=dataset_id,
                document_id=document_id,
                user_id=user_id,
                chunk_count=document.chunk_count,
                vector_count=document.chunk_count  # Assuming 1 vector per chunk
            )
            
            self.db.add(dataset_doc)
            
            # Update dataset statistics
            dataset.document_count += 1
            dataset.chunk_count += document.chunk_count
            dataset.vector_count += document.chunk_count
            dataset.total_size_bytes += document.file_size_bytes
            
            await self.db.commit()
            await self.db.refresh(dataset_doc)
            
            logger.info(f"Added document {document_id} to dataset {dataset_id}")
            return dataset_doc
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to add document to dataset: {e}")
            raise
    
    async def search_documents(
        self,
        user_id: str,
        tenant_id: str,
        query: str,
        dataset_ids: Optional[List[str]] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search documents using RAG with tenant isolation"""
        try:
            # Generate query embedding
            query_embeddings = await self.resource_client.generate_query_embeddings(
                queries=[query],
                tenant_id=tenant_id,
                user_id=user_id
            )
            
            if not query_embeddings:
                raise ValueError("Failed to generate query embedding")
            
            query_embedding = query_embeddings[0]
            
            # Get user's datasets if not specified
            if not dataset_ids:
                datasets = await self.list_user_datasets(user_id)
                dataset_ids = [d.id for d in datasets]
            
            # Search across datasets
            all_results = []
            for dataset_id in dataset_ids:
                # Verify dataset ownership
                dataset = await self._get_user_dataset(user_id, dataset_id)
                if not dataset:
                    continue
                
                # Search in ChromaDB
                dataset_name = f"dataset_{dataset_id}"
                results = await self.resource_client.search_vectors(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    dataset_name=dataset_name,
                    query_embedding=query_embedding,
                    top_k=top_k
                )
                
                # Filter by similarity threshold and add dataset context
                for result in results:
                    if result.get("similarity", 0) >= similarity_threshold:
                        result["dataset_id"] = dataset_id
                        result["dataset_name"] = dataset.dataset_name
                        all_results.append(result)
            
            # Sort by similarity and limit
            all_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
            final_results = all_results[:top_k]
            
            # Clear query embedding from memory
            del query_embedding, query_embeddings
            gc.collect()
            
            logger.info(f"Search found {len(final_results)} results for user {user_id}")
            return final_results
            
        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            gc.collect()
            raise
    
    async def get_document_context(
        self,
        user_id: str,
        tenant_id: str,
        document_id: int,
        query: str,
        context_size: int = 3
    ) -> Dict[str, Any]:
        """Get relevant context from a specific document"""
        try:
            # Verify document ownership
            document = await self._get_user_document(user_id, document_id)
            if not document:
                raise PermissionError("Document not found or access denied")
            
            if not document.is_processing_complete():
                raise ValueError("Document not yet processed")
            
            # Generate query embedding
            query_embeddings = await self.resource_client.generate_query_embeddings(
                queries=[query],
                tenant_id=tenant_id,
                user_id=user_id
            )
            
            query_embedding = query_embeddings[0]
            
            # Search document's vectors
            dataset_name = f"doc_{document_id}"
            results = await self.resource_client.search_vectors(
                tenant_id=tenant_id,
                user_id=user_id,
                dataset_name=dataset_name,
                query_embedding=query_embedding,
                top_k=context_size
            )
            
            context = {
                "document_id": document_id,
                "document_name": document.original_filename,
                "query": query,
                "relevant_chunks": results,
                "context_text": "\n\n".join([r["document"] for r in results])
            }
            
            # Clear query embedding from memory
            del query_embedding, query_embeddings
            gc.collect()
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to get document context: {e}")
            gc.collect()
            raise
    
    async def list_user_documents(
        self,
        user_id: str,
        status_filter: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> List[Document]:
        """List user's documents with optional filtering"""
        try:
            query = select(Document).where(Document.uploaded_by == user_id)
            
            if status_filter:
                query = query.where(Document.processing_status == status_filter)
            
            query = query.order_by(Document.created_at.desc())
            query = query.offset(offset).limit(limit)
            
            result = await self.db.execute(query)
            documents = result.scalars().all()
            
            return list(documents)
            
        except Exception as e:
            logger.error(f"Failed to list user documents: {e}")
            raise
    
    async def list_user_datasets(
        self,
        user_id: str,
        include_stats: bool = True
    ) -> List[RAGDataset]:
        """List user's RAG datasets"""
        try:
            query = select(RAGDataset).where(RAGDataset.user_id == user_id)
            
            if include_stats:
                query = query.options(selectinload(RAGDataset.documents))
            
            query = query.order_by(RAGDataset.created_at.desc())
            
            result = await self.db.execute(query)
            datasets = result.scalars().all()
            
            return list(datasets)
            
        except Exception as e:
            logger.error(f"Failed to list user datasets: {e}")
            raise
    
    async def delete_document(
        self,
        user_id: str,
        tenant_id: str,
        document_id: int
    ) -> bool:
        """Delete document and associated vectors"""
        try:
            # Verify document ownership
            document = await self._get_user_document(user_id, document_id)
            if not document:
                raise PermissionError("Document not found or access denied")
            
            # Delete vectors from ChromaDB if processed
            if document.is_processing_complete():
                dataset_name = f"doc_{document_id}"
                await self.resource_client.delete_vector_collection(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    dataset_name=dataset_name
                )
            
            # Delete physical file
            if document.file_exists():
                os.remove(document.get_absolute_file_path())
            
            # Delete from database (cascade will handle related records)
            await self.db.delete(document)
            await self.db.commit()
            
            logger.info(f"Deleted document {document_id} for user {user_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete document: {e}")
            raise
    
    async def delete_dataset(
        self,
        user_id: str,
        tenant_id: str,
        dataset_id: str
    ) -> bool:
        """Delete RAG dataset and associated vectors"""
        try:
            # Verify dataset ownership
            dataset = await self._get_user_dataset(user_id, dataset_id)
            if not dataset:
                raise PermissionError("Dataset not found or access denied")
            
            # Delete vectors from ChromaDB
            dataset_name = f"dataset_{dataset_id}"
            await self.resource_client.delete_vector_collection(
                tenant_id=tenant_id,
                user_id=user_id,
                dataset_name=dataset_name
            )
            
            # Delete from database (cascade will handle related records)
            await self.db.delete(dataset)
            await self.db.commit()
            
            logger.info(f"Deleted dataset {dataset_id} for user {user_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete dataset: {e}")
            raise
    
    async def get_rag_statistics(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """Get RAG usage statistics for user"""
        try:
            # Document statistics
            doc_query = select(Document).where(Document.uploaded_by == user_id)
            doc_result = await self.db.execute(doc_query)
            documents = doc_result.scalars().all()
            
            # Dataset statistics
            dataset_query = select(RAGDataset).where(RAGDataset.user_id == user_id)
            dataset_result = await self.db.execute(dataset_query)
            datasets = dataset_result.scalars().all()
            
            total_size = sum(doc.file_size_bytes for doc in documents)
            total_chunks = sum(doc.chunk_count for doc in documents)
            
            stats = {
                "user_id": user_id,
                "document_count": len(documents),
                "dataset_count": len(datasets),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "total_chunks": total_chunks,
                "processed_documents": len([d for d in documents if d.is_processing_complete()]),
                "pending_documents": len([d for d in documents if d.is_pending_processing()]),
                "failed_documents": len([d for d in documents if d.is_processing_failed()])
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get RAG statistics: {e}")
            raise
    
    # Private helper methods
    
    async def _get_user_document(self, user_id: str, document_id: int) -> Optional[Document]:
        """Get document with ownership verification"""
        result = await self.db.execute(
            select(Document).where(
                and_(
                    Document.id == document_id,
                    Document.uploaded_by == user_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_user_dataset(self, user_id: str, dataset_id: str) -> Optional[RAGDataset]:
        """Get dataset with ownership verification"""
        result = await self.db.execute(
            select(RAGDataset).where(
                and_(
                    RAGDataset.id == dataset_id,
                    RAGDataset.user_id == user_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _read_document_file(self, document: Document) -> bytes:
        """Read document file content"""
        file_path = document.get_absolute_file_path()
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Document file not found: {file_path}")
        
        async with aiofiles.open(file_path, 'rb') as f:
            content = await f.read()
        
        return content


# Factory function for dependency injection
async def get_rag_service(db: AsyncSession = None) -> RAGService:
    """Get RAG service instance"""
    if db is None:
        async with get_db_session() as session:
            return RAGService(session)
    return RAGService(db)