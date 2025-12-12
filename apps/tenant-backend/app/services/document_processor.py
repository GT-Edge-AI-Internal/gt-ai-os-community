"""
Document Processing Service for GT 2.0

Handles file upload, text extraction, chunking, and embedding generation
for RAG pipeline. Supports multiple file formats with intelligent chunking.
"""

import asyncio
import logging
import hashlib
import mimetypes
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import uuid

# Document processing libraries
import pypdf as PyPDF2  # pypdf is the maintained successor to PyPDF2
import docx
import pandas as pd
import json
import csv
from io import StringIO

# Database and core services
from app.core.postgresql_client import get_postgresql_client

# Resource cluster client for embeddings
import httpx
from app.services.embedding_client import get_embedding_client

# Document summarization
from app.services.summarization_service import SummarizationService

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Comprehensive document processing service for RAG pipeline.

    Features:
    - Multi-format support (PDF, DOCX, TXT, MD, CSV, JSON)
    - Intelligent chunking with overlap
    - Async embedding generation with batch processing
    - Progress tracking
    - Error handling and recovery
    """

    def __init__(self, db=None, tenant_domain=None):
        self.db = db
        self.tenant_domain = tenant_domain or "test"  # Default fallback
        # Use configurable embedding client instead of hardcoded URL
        self.embedding_client = get_embedding_client()
        self.chunk_size = 512  # Default chunk size in tokens
        self.chunk_overlap = 128  # Default overlap
        self.max_file_size = 100 * 1024 * 1024  # 100MB limit

        # Embedding batch processing configuration
        self.EMBEDDING_BATCH_SIZE = 15  # Process embeddings in batches of 15 (ARM64 optimized)
        self.MAX_CONCURRENT_BATCHES = 3  # Process up to 3 batches concurrently
        self.MAX_RETRIES = 3  # Maximum retries per batch
        self.INITIAL_RETRY_DELAY = 1.0  # Initial delay in seconds
        
        # Supported file types
        self.supported_types = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.csv': 'text/csv',
            '.json': 'application/json'
        }
    
    async def process_file(
        self,
        file_path: Path,
        dataset_id: str,
        user_id: str,
        original_filename: str,
        document_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a uploaded file through the complete RAG pipeline.

        Args:
            file_path: Path to uploaded file
            dataset_id: Dataset UUID to attach to
            user_id: User who uploaded the file
            original_filename: Original filename
            document_id: Optional existing document ID to update instead of creating new

        Returns:
            Dict: Document record with processing status
        """
        logger.info(f"Processing file {original_filename} for dataset {dataset_id}")

        # Process file directly (no session management needed with PostgreSQL client)
        return await self._process_file_internal(file_path, dataset_id, user_id, original_filename, document_id)

    async def _process_file_internal(
        self,
        file_path: Path,
        dataset_id: str,
        user_id: str,
        original_filename: str,
        document_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Internal file processing method"""
        try:
            # 1. Validate file
            await self._validate_file(file_path)

            # 2. Create or use existing document record
            if document_id:
                # Use existing document
                document = {"id": document_id}
                logger.info(f"Using existing document {document_id} for processing")
            else:
                # Create new document record
                document = await self._create_document_record(
                    file_path, dataset_id, user_id, original_filename
                )
            
            # 3. Get or extract text content
            await self._update_processing_status(document["id"], "processing", processing_stage="Getting text content")

            # Check if content already exists (e.g., from upload-time extraction)
            existing_content, storage_type = await self._get_existing_document_content(document["id"])

            if existing_content and storage_type in ["pdf_extracted", "text"]:
                # Use existing extracted content
                text_content = existing_content
                logger.info(f"Using existing extracted content ({len(text_content)} chars, type: {storage_type})")
            else:
                # Extract text from file
                await self._update_processing_status(document["id"], "processing", processing_stage="Extracting text")

                # Determine file type for extraction
                if document_id:
                    # For existing documents, determine file type from file extension
                    file_ext = file_path.suffix.lower()
                    file_type = self.supported_types.get(file_ext, 'text/plain')
                else:
                    file_type = document["file_type"]

                text_content = await self._extract_text(file_path, file_type)

                # 4. Update document with extracted text
                await self._update_document_content(document["id"], text_content)

            # 5. Generate document summary
            await self._update_processing_status(document["id"], "processing", processing_stage="Generating summary")
            await self._generate_document_summary(document["id"], text_content, original_filename, user_id)

            # 6. Chunk the document
            await self._update_processing_status(document["id"], "processing", processing_stage="Creating chunks")
            chunks = await self._chunk_text(text_content, document["id"])

            # Set expected chunk count for progress tracking
            await self._update_processing_status(
                document["id"], "processing",
                processing_stage="Preparing for embedding generation",
                total_chunks_expected=len(chunks)
            )

            # 7. Generate embeddings
            await self._update_processing_status(document["id"], "processing", processing_stage="Starting embedding generation")
            await self._generate_embeddings_for_chunks(chunks, dataset_id, user_id)

            # 8. Update final status
            await self._update_processing_status(
                document["id"], "completed",
                processing_stage="Completed",
                chunks_processed=len(chunks),
                total_chunks_expected=len(chunks)
            )
            await self._update_chunk_count(document["id"], len(chunks))

            # 9. Update dataset summary (after document is fully processed)
            await self._update_dataset_summary_after_document_change(dataset_id, user_id)

            logger.info(f"Successfully processed {original_filename} with {len(chunks)} chunks")
            return document
            
        except Exception as e:
            logger.error(f"Error processing file {original_filename}: {e}")
            if 'document' in locals():
                await self._update_processing_status(
                    document["id"], "failed",
                    error_message=str(e),
                    processing_stage="Failed"
                )
            raise
    
    async def _validate_file(self, file_path: Path):
        """Validate file size and type"""
        if not file_path.exists():
            raise ValueError("File does not exist")
        
        file_size = file_path.stat().st_size
        if file_size > self.max_file_size:
            raise ValueError(f"File too large: {file_size} bytes (max: {self.max_file_size})")
        
        file_ext = file_path.suffix.lower()
        if file_ext not in self.supported_types:
            raise ValueError(f"Unsupported file type: {file_ext}")
    
    async def _create_document_record(
        self,
        file_path: Path,
        dataset_id: str,
        user_id: str,
        original_filename: str
    ) -> Dict[str, Any]:
        """Create document record in database"""
        
        # Calculate file hash
        with open(file_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        file_ext = file_path.suffix.lower()
        file_size = file_path.stat().st_size
        document_id = str(uuid.uuid4())

        # Insert document record using raw SQL
        # Note: tenant_id is nullable UUID, so we set it to NULL for individual documents
        pg_client = await get_postgresql_client()
        await pg_client.execute_command(
            """INSERT INTO documents (
                id, user_id, dataset_id, filename, original_filename,
                file_type, file_size_bytes, file_hash, processing_status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
            document_id, str(user_id), dataset_id, str(file_path.name),
            original_filename, self.supported_types[file_ext], file_size, file_hash, "pending"
        )

        return {
            "id": document_id,
            "user_id": user_id,
            "dataset_id": dataset_id,
            "filename": str(file_path.name),
            "original_filename": original_filename,
            "file_type": self.supported_types[file_ext],
            "file_size_bytes": file_size,
            "file_hash": file_hash,
            "processing_status": "pending",
            "chunk_count": 0
        }
    
    async def _extract_text(self, file_path: Path, file_type: str) -> str:
        """Extract text content from various file formats"""
        
        try:
            if file_type == 'application/pdf':
                return await self._extract_pdf_text(file_path)
            elif 'wordprocessingml' in file_type:
                return await self._extract_docx_text(file_path)
            elif file_type == 'text/csv':
                return await self._extract_csv_text(file_path)
            elif file_type == 'application/json':
                return await self._extract_json_text(file_path)
            else:  # text/plain, text/markdown
                return await self._extract_plain_text(file_path)
                
        except Exception as e:
            logger.error(f"Text extraction failed for {file_path}: {e}")
            raise ValueError(f"Could not extract text from file: {e}")
    
    async def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF file"""
        text_parts = []
        
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text.strip():
                        text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
                except Exception as e:
                    logger.warning(f"Could not extract text from page {page_num + 1}: {e}")
        
        if not text_parts:
            raise ValueError("No text could be extracted from PDF")
        
        return "\n\n".join(text_parts)
    
    async def _extract_docx_text(self, file_path: Path) -> str:
        """Extract text from DOCX file"""
        doc = docx.Document(file_path)
        text_parts = []
        
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        
        if not text_parts:
            raise ValueError("No text could be extracted from DOCX")
        
        return "\n\n".join(text_parts)
    
    async def _extract_csv_text(self, file_path: Path) -> str:
        """Extract and format text from CSV file"""
        try:
            df = pd.read_csv(file_path)
            
            # Create readable format
            text_parts = [f"CSV Data with {len(df)} rows and {len(df.columns)} columns"]
            text_parts.append(f"Columns: {', '.join(df.columns.tolist())}")
            text_parts.append("")
            
            # Sample first few rows in readable format
            for idx, row in df.head(20).iterrows():
                row_text = []
                for col in df.columns:
                    if pd.notna(row[col]):
                        row_text.append(f"{col}: {row[col]}")
                text_parts.append(f"Row {idx + 1}: " + " | ".join(row_text))
            
            return "\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"CSV parsing error: {e}")
            # Fallback to reading as plain text
            return await self._extract_plain_text(file_path)
    
    async def _extract_json_text(self, file_path: Path) -> str:
        """Extract and format text from JSON file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert JSON to readable text format
        def json_to_text(obj, prefix=""):
            text_parts = []
            
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, (dict, list)):
                        text_parts.append(f"{prefix}{key}:")
                        text_parts.extend(json_to_text(value, prefix + "  "))
                    else:
                        text_parts.append(f"{prefix}{key}: {value}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    if isinstance(item, (dict, list)):
                        text_parts.append(f"{prefix}Item {i + 1}:")
                        text_parts.extend(json_to_text(item, prefix + "  "))
                    else:
                        text_parts.append(f"{prefix}Item {i + 1}: {item}")
            else:
                text_parts.append(f"{prefix}{obj}")
            
            return text_parts
        
        return "\n".join(json_to_text(data))
    
    async def _extract_plain_text(self, file_path: Path) -> str:
        """Extract text from plain text files"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with latin-1 encoding
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()

    async def extract_text_from_path(self, file_path: Path, content_type: str) -> str:
        """Public wrapper for text extraction from file path"""
        return await self._extract_text(file_path, content_type)

    async def chunk_text_simple(self, text: str) -> List[str]:
        """Public wrapper for simple text chunking without document_id"""
        chunks = []
        chunk_size = self.chunk_size * 4  # ~2048 chars
        overlap = self.chunk_overlap * 4   # ~512 chars

        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size]
            if chunk.strip():
                chunks.append(chunk)

        return chunks

    async def _chunk_text(self, text: str, document_id: str) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks optimized for embeddings.
        
        Returns:
            List of chunk dictionaries with content and metadata
        """
        # Simple sentence-aware chunking
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        chunks = []
        current_chunk = ""
        current_tokens = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence_tokens = len(sentence.split())
            
            # If adding this sentence would exceed chunk size, save current chunk
            if current_tokens + sentence_tokens > self.chunk_size and current_chunk:
                # Create chunk with overlap from previous chunk
                chunk_content = current_chunk.strip()
                if chunk_content:
                    chunks.append({
                        "document_id": document_id,
                        "chunk_index": chunk_index,
                        "content": chunk_content,
                        "token_count": current_tokens,
                        "content_hash": hashlib.md5(chunk_content.encode()).hexdigest()
                    })
                    chunk_index += 1
                
                # Start new chunk with overlap
                if self.chunk_overlap > 0 and chunks:
                    # Take last few sentences for overlap
                    overlap_sentences = current_chunk.split('.')[-2:]  # Rough overlap
                    current_chunk = '. '.join(s.strip() for s in overlap_sentences if s.strip())
                    current_tokens = len(current_chunk.split())
                else:
                    current_chunk = ""
                    current_tokens = 0
            
            # Add sentence to current chunk
            if current_chunk:
                current_chunk += ". " + sentence
            else:
                current_chunk = sentence
            current_tokens += sentence_tokens
        
        # Add final chunk
        if current_chunk.strip():
            chunk_content = current_chunk.strip()
            chunks.append({
                "document_id": document_id,
                "chunk_index": chunk_index,
                "content": chunk_content,
                "token_count": current_tokens,
                "content_hash": hashlib.md5(chunk_content.encode()).hexdigest()
            })
        
        logger.info(f"Created {len(chunks)} chunks from document {document_id}")
        return chunks
    
    async def _generate_embeddings_for_chunks(
        self,
        chunks: List[Dict[str, Any]],
        dataset_id: str,
        user_id: str
    ):
        """
        Generate embeddings for all chunks using concurrent batch processing.

        Processes chunks in batches with controlled concurrency to optimize performance
        while preventing system overload. Includes retry logic and progressive storage.
        """

        if not chunks:
            return

        total_chunks = len(chunks)
        document_id = chunks[0]["document_id"]
        total_batches = (total_chunks + self.EMBEDDING_BATCH_SIZE - 1) // self.EMBEDDING_BATCH_SIZE

        logger.info(f"Starting concurrent embedding generation for {total_chunks} chunks")
        logger.info(f"Batch size: {self.EMBEDDING_BATCH_SIZE}, Total batches: {total_batches}, Max concurrent: {self.MAX_CONCURRENT_BATCHES}")

        # Create semaphore to limit concurrent batches
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_BATCHES)

        # Create batch data with metadata
        batch_tasks = []
        for batch_start in range(0, total_chunks, self.EMBEDDING_BATCH_SIZE):
            batch_end = min(batch_start + self.EMBEDDING_BATCH_SIZE, total_chunks)
            batch_chunks = chunks[batch_start:batch_end]
            batch_num = (batch_start // self.EMBEDDING_BATCH_SIZE) + 1

            batch_metadata = {
                "chunks": batch_chunks,
                "batch_num": batch_num,
                "start_index": batch_start,
                "end_index": batch_end,
                "dataset_id": dataset_id,
                "user_id": user_id,
                "document_id": document_id
            }

            # Create task for this batch
            task = self._process_batch_with_semaphore(semaphore, batch_metadata, total_batches, total_chunks)
            batch_tasks.append(task)

        # Process all batches concurrently
        logger.info(f"Starting concurrent processing of {len(batch_tasks)} batches")
        start_time = asyncio.get_event_loop().time()

        results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        end_time = asyncio.get_event_loop().time()
        processing_time = end_time - start_time

        # Analyze results
        successful_batches = []
        failed_batches = []

        for i, result in enumerate(results):
            batch_num = i + 1
            if isinstance(result, Exception):
                failed_batches.append({
                    "batch_num": batch_num,
                    "error": str(result)
                })
                logger.error(f"Batch {batch_num} failed: {result}")
            else:
                successful_batches.append(result)

        successful_chunks = sum(len(batch["chunks"]) for batch in successful_batches)

        logger.info(f"Concurrent processing completed in {processing_time:.2f} seconds")
        logger.info(f"Successfully processed {successful_chunks}/{total_chunks} chunks in {len(successful_batches)}/{total_batches} batches")

        # Report final results
        if failed_batches:
            failed_chunk_count = total_chunks - successful_chunks
            error_details = "; ".join([f"Batch {b['batch_num']}: {b['error']}" for b in failed_batches[:3]])
            if len(failed_batches) > 3:
                error_details += f" (and {len(failed_batches) - 3} more failures)"

            raise ValueError(f"Failed to generate embeddings for {failed_chunk_count}/{total_chunks} chunks. Errors: {error_details}")

        logger.info(f"Successfully stored all {total_chunks} chunks with embeddings")

    async def _process_batch_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        batch_metadata: Dict[str, Any],
        total_batches: int,
        total_chunks: int
    ) -> Dict[str, Any]:
        """
        Process a single batch with semaphore-controlled concurrency.

        Args:
            semaphore: Concurrency control semaphore
            batch_metadata: Batch information including chunks and metadata
            total_batches: Total number of batches
            total_chunks: Total number of chunks

        Returns:
            Dict with batch processing results
        """
        async with semaphore:
            batch_chunks = batch_metadata["chunks"]
            batch_num = batch_metadata["batch_num"]
            dataset_id = batch_metadata["dataset_id"]
            user_id = batch_metadata["user_id"]
            document_id = batch_metadata["document_id"]

            logger.info(f"Starting batch {batch_num}/{total_batches} ({len(batch_chunks)} chunks)")

            try:
                # Generate embeddings for this batch (pass user_id for billing)
                embeddings = await self._generate_embedding_batch(batch_chunks, user_id=user_id)

                # Store embeddings for this batch immediately
                await self._store_chunk_embeddings(batch_chunks, embeddings, dataset_id, user_id)

                # Update progress in database
                progress_stage = f"Completed batch {batch_num}/{total_batches}"

                # Calculate current progress (approximate since batches complete out of order)
                await self._update_processing_status(
                    document_id, "processing",
                    processing_stage=progress_stage,
                    chunks_processed=batch_num * self.EMBEDDING_BATCH_SIZE,  # Approximate
                    total_chunks_expected=total_chunks
                )

                logger.info(f"Successfully completed batch {batch_num}/{total_batches}")

                return {
                    "batch_num": batch_num,
                    "chunks": batch_chunks,
                    "success": True
                }

            except Exception as e:
                logger.error(f"Failed to process batch {batch_num}/{total_batches}: {e}")
                raise ValueError(f"Batch {batch_num} failed: {str(e)}")

    async def _generate_embedding_batch(
        self,
        batch_chunks: List[Dict[str, Any]],
        user_id: str = None
    ) -> List[List[float]]:
        """
        Generate embeddings for a single batch of chunks with retry logic.

        Args:
            batch_chunks: List of chunk dictionaries
            user_id: User ID for usage tracking

        Returns:
            List of embedding vectors

        Raises:
            ValueError: If embedding generation fails after all retries
        """
        texts = [chunk["content"] for chunk in batch_chunks]

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                # Use the configurable embedding client with tenant/user context for billing
                embeddings = await self.embedding_client.generate_embeddings(
                    texts,
                    tenant_id=self.tenant_domain,
                    user_id=str(user_id) if user_id else None
                )

                if len(embeddings) != len(texts):
                    raise ValueError(f"Embedding count mismatch: expected {len(texts)}, got {len(embeddings)}")

                return embeddings

            except Exception as e:
                if attempt < self.MAX_RETRIES:
                    delay = self.INITIAL_RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Embedding generation attempt {attempt + 1}/{self.MAX_RETRIES + 1} failed: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {self.MAX_RETRIES + 1} embedding generation attempts failed. Final error: {e}")
                    logger.error(f"Failed request details: URL=http://gentwo-vllm-embeddings:8000/v1/embeddings, texts_count={len(texts)}")
                    raise ValueError(f"Embedding generation failed after {self.MAX_RETRIES + 1} attempts: {str(e)}")

    async def _store_chunk_embeddings(
        self,
        batch_chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        dataset_id: str,
        user_id: str
    ):
        """Store chunk embeddings in database with proper error handling."""

        pg_client = await get_postgresql_client()
        for chunk_data, embedding in zip(batch_chunks, embeddings):
            chunk_id = str(uuid.uuid4())

            # Convert embedding list to PostgreSQL array format
            embedding_array = f"[{','.join(map(str, embedding))}]" if embedding else None

            await pg_client.execute_command(
                """INSERT INTO document_chunks (
                    id, document_id, user_id, dataset_id, chunk_index,
                    content, content_hash, token_count, embedding
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::vector)""",
                chunk_id, chunk_data["document_id"], str(user_id),
                dataset_id, chunk_data["chunk_index"], chunk_data["content"],
                chunk_data["content_hash"], chunk_data["token_count"], embedding_array
            )
    
    async def _update_processing_status(
        self,
        document_id: str,
        status: str,
        error_message: Optional[str] = None,
        processing_stage: Optional[str] = None,
        chunks_processed: Optional[int] = None,
        total_chunks_expected: Optional[int] = None
    ):
        """Update document processing status with progress tracking via metadata JSONB"""

        # Calculate progress percentage if we have the data
        processing_progress = None
        if chunks_processed is not None and total_chunks_expected is not None and total_chunks_expected > 0:
            processing_progress = min(100, int((chunks_processed / total_chunks_expected) * 100))

        # Build progress metadata object
        import json
        progress_data = {}
        if processing_stage is not None:
            progress_data['processing_stage'] = processing_stage
        if chunks_processed is not None:
            progress_data['chunks_processed'] = chunks_processed
        if total_chunks_expected is not None:
            progress_data['total_chunks_expected'] = total_chunks_expected
        if processing_progress is not None:
            progress_data['processing_progress'] = processing_progress

        pg_client = await get_postgresql_client()
        if error_message:
            await pg_client.execute_command(
                """UPDATE documents SET
                   processing_status = $1,
                   error_message = $2,
                   metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb,
                   updated_at = NOW()
                   WHERE id = $4""",
                status, error_message, json.dumps(progress_data), document_id
            )
        else:
            await pg_client.execute_command(
                """UPDATE documents SET
                   processing_status = $1,
                   metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb,
                   updated_at = NOW()
                   WHERE id = $3""",
                status, json.dumps(progress_data), document_id
            )
    
    async def _get_existing_document_content(self, document_id: str) -> tuple[str, str]:
        """Get existing document content and storage type"""
        pg_client = await get_postgresql_client()
        result = await pg_client.fetch_one(
            "SELECT content_text, metadata FROM documents WHERE id = $1",
            document_id
        )
        if result and result["content_text"]:
            # Handle metadata - might be JSON string or dict
            metadata_raw = result["metadata"] or "{}"
            if isinstance(metadata_raw, str):
                import json
                try:
                    metadata = json.loads(metadata_raw)
                except json.JSONDecodeError:
                    metadata = {}
            else:
                metadata = metadata_raw or {}
            storage_type = metadata.get("storage_type", "unknown")
            return result["content_text"], storage_type
        return None, None

    async def _update_document_content(self, document_id: str, content: str):
        """Update document with extracted text content"""
        pg_client = await get_postgresql_client()
        await pg_client.execute_command(
            "UPDATE documents SET content_text = $1, updated_at = NOW() WHERE id = $2",
            content, document_id
        )

    async def _update_chunk_count(self, document_id: str, chunk_count: int):
        """Update document with final chunk count"""
        pg_client = await get_postgresql_client()
        await pg_client.execute_command(
            "UPDATE documents SET chunk_count = $1, updated_at = NOW() WHERE id = $2",
            chunk_count, document_id
        )

    async def _generate_document_summary(
        self,
        document_id: str,
        content: str,
        filename: str,
        user_id: str
    ):
        """Generate and store AI summary for the document"""
        try:
            # Use tenant_domain from instance context
            tenant_domain = self.tenant_domain

            # Create summarization service instance
            summarization_service = SummarizationService(tenant_domain, user_id)

            # Generate summary using our new service
            summary = await summarization_service.generate_document_summary(
                document_id=document_id,
                document_content=content,
                document_name=filename
            )

            if summary:
                logger.info(f"Generated summary for document {document_id}: {summary[:100]}...")
            else:
                logger.warning(f"Failed to generate summary for document {document_id}")

        except Exception as e:
            logger.error(f"Error generating document summary for {document_id}: {e}")
            # Don't fail the entire document processing if summarization fails

    async def _update_dataset_summary_after_document_change(
        self,
        dataset_id: str,
        user_id: str
    ):
        """Update dataset summary after a document is added or removed"""
        try:
            # Create summarization service instance
            summarization_service = SummarizationService(self.tenant_domain, user_id)

            # Update dataset summary asynchronously (don't block document processing)
            asyncio.create_task(
                summarization_service.update_dataset_summary_on_change(dataset_id)
            )

            logger.info(f"Triggered dataset summary update for dataset {dataset_id}")

        except Exception as e:
            logger.error(f"Error triggering dataset summary update for {dataset_id}: {e}")
            # Don't fail document processing if dataset summary update fails

    async def get_processing_status(self, document_id: str) -> Dict[str, Any]:
        """Get current processing status of a document with progress information from metadata"""
        pg_client = await get_postgresql_client()
        result = await pg_client.fetch_one(
            """SELECT processing_status, error_message, chunk_count, metadata
               FROM documents WHERE id = $1""",
            document_id
        )

        if not result:
            raise ValueError("Document not found")

        # Extract progress data from metadata JSONB
        metadata = result["metadata"] or {}

        return {
            "status": result["processing_status"],
            "error_message": result["error_message"],
            "chunk_count": result["chunk_count"],
            "chunks_processed": metadata.get("chunks_processed"),
            "total_chunks_expected": metadata.get("total_chunks_expected"),
            "processing_progress": metadata.get("processing_progress"),
            "processing_stage": metadata.get("processing_stage")
        }


# Factory function for document processor
async def get_document_processor(tenant_domain=None):
    """Get document processor instance (will create its own DB session when needed)"""
    return DocumentProcessor(tenant_domain=tenant_domain)