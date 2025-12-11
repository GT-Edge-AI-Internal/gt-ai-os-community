"""
Conversation File Service for GT 2.0

Handles conversation-scoped file attachments as a simpler alternative to dataset-based uploads.
Preserves all existing dataset infrastructure while providing direct conversation file storage.
"""

import os
import uuid
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import UploadFile, HTTPException
from app.core.config import get_settings
from app.core.postgresql_client import get_postgresql_client
from app.services.embedding_client import BGE_M3_EmbeddingClient
from app.services.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)


class ConversationFileService:
    """Service for managing conversation-scoped file attachments"""

    def __init__(self, tenant_domain: str, user_id: str):
        self.tenant_domain = tenant_domain
        self.user_id = user_id
        self.settings = get_settings()
        self.schema_name = f"tenant_{tenant_domain.replace('.', '_').replace('-', '_')}"

        # File storage configuration
        self.storage_root = Path(self.settings.file_storage_path) / tenant_domain / "conversations"
        self.storage_root.mkdir(parents=True, exist_ok=True)

        logger.info(f"ConversationFileService initialized for {tenant_domain}/{user_id}")

    def _get_conversation_storage_path(self, conversation_id: str) -> Path:
        """Get storage directory for conversation files"""
        conv_path = self.storage_root / conversation_id
        conv_path.mkdir(parents=True, exist_ok=True)
        return conv_path

    def _generate_safe_filename(self, original_filename: str, file_id: str) -> str:
        """Generate safe filename for storage"""
        # Sanitize filename and prepend file ID
        safe_name = "".join(c for c in original_filename if c.isalnum() or c in ".-_")
        return f"{file_id}-{safe_name}"

    async def upload_files(
        self,
        conversation_id: str,
        files: List[UploadFile],
        user_id: str
    ) -> List[Dict[str, Any]]:
        """Upload files directly to conversation"""
        try:
            # Validate conversation access
            await self._validate_conversation_access(conversation_id, user_id)

            uploaded_files = []

            for file in files:
                if not file.filename:
                    raise HTTPException(status_code=400, detail="File must have a filename")

                # Generate file metadata
                file_id = str(uuid.uuid4())
                safe_filename = self._generate_safe_filename(file.filename, file_id)
                conversation_path = self._get_conversation_storage_path(conversation_id)
                file_path = conversation_path / safe_filename

                # Store file to disk
                content = await file.read()
                with open(file_path, "wb") as f:
                    f.write(content)

                # Create database record
                file_record = await self._create_file_record(
                    file_id=file_id,
                    conversation_id=conversation_id,
                    original_filename=file.filename,
                    safe_filename=safe_filename,
                    content_type=file.content_type or "application/octet-stream",
                    file_size=len(content),
                    file_path=str(file_path.relative_to(Path(self.settings.file_storage_path))),
                    uploaded_by=user_id
                )

                uploaded_files.append(file_record)

                # Queue for background processing
                asyncio.create_task(self._process_file_embeddings(file_id))

                logger.info(f"Uploaded conversation file: {file.filename} -> {file_id}")

            return uploaded_files

        except Exception as e:
            logger.error(f"Failed to upload conversation files: {e}")
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    async def _get_user_uuid(self, user_email: str) -> str:
        """Resolve user email to UUID"""
        client = await get_postgresql_client()
        query = f"SELECT id FROM {self.schema_name}.users WHERE email = $1 LIMIT 1"
        result = await client.fetch_one(query, user_email)
        if not result:
            raise ValueError(f"User not found: {user_email}")
        return str(result['id'])

    async def _create_file_record(
        self,
        file_id: str,
        conversation_id: str,
        original_filename: str,
        safe_filename: str,
        content_type: str,
        file_size: int,
        file_path: str,
        uploaded_by: str
    ) -> Dict[str, Any]:
        """Create conversation_files database record"""

        client = await get_postgresql_client()

        # Resolve user email to UUID if needed
        user_uuid = uploaded_by
        if '@' in uploaded_by:  # Check if it's an email
            user_uuid = await self._get_user_uuid(uploaded_by)

        query = f"""
            INSERT INTO {self.schema_name}.conversation_files (
                id, conversation_id, filename, original_filename, content_type,
                file_size_bytes, file_path, uploaded_by, processing_status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
            RETURNING id, filename, original_filename, content_type, file_size_bytes,
                     processing_status, uploaded_at
        """

        result = await client.fetch_one(
            query,
            file_id, conversation_id, safe_filename, original_filename,
            content_type, file_size, file_path, user_uuid
        )

        # Convert UUID fields to strings for JSON serialization
        result_dict = dict(result)
        if 'id' in result_dict and result_dict['id']:
            result_dict['id'] = str(result_dict['id'])

        return result_dict

    async def _process_file_embeddings(self, file_id: str):
        """Background task to process file content and generate embeddings"""
        try:
            # Update status to processing
            await self._update_processing_status(file_id, "processing")

            # Get file record
            file_record = await self._get_file_record(file_id)
            if not file_record:
                logger.error(f"File record not found: {file_id}")
                return

            # Read file content
            file_path = Path(self.settings.file_storage_path) / file_record['file_path']
            if not file_path.exists():
                logger.error(f"File not found on disk: {file_path}")
                await self._update_processing_status(file_id, "failed")
                return

            # Extract text content using DocumentProcessor public methods
            processor = DocumentProcessor()

            text_content = await processor.extract_text_from_path(
                file_path,
                file_record['content_type']
            )

            if not text_content:
                logger.warning(f"No text content extracted from {file_record['original_filename']}")
                await self._update_processing_status(file_id, "completed")
                return

            # Chunk content for RAG
            chunks = await processor.chunk_text_simple(text_content)

            # Generate embeddings for full document (single embedding for semantic search)
            embedding_client = BGE_M3_EmbeddingClient()
            embeddings = await embedding_client.generate_embeddings([text_content])

            if not embeddings:
                logger.error(f"Failed to generate embeddings for {file_id}")
                await self._update_processing_status(file_id, "failed")
                return

            # Update record with processed content (chunks as JSONB, embedding as vector)
            await self._update_file_processing_results(
                file_id, chunks, embeddings[0], "completed"
            )

            logger.info(f"Successfully processed file: {file_record['original_filename']}")

        except Exception as e:
            logger.error(f"Failed to process file {file_id}: {e}")
            await self._update_processing_status(file_id, "failed")

    async def _update_processing_status(self, file_id: str, status: str):
        """Update file processing status"""
        client = await get_postgresql_client()

        query = f"""
            UPDATE {self.schema_name}.conversation_files
            SET processing_status = $1,
                processed_at = CASE WHEN $1 IN ('completed', 'failed') THEN NOW() ELSE processed_at END
            WHERE id = $2
        """

        await client.execute_query(query, status, file_id)

    async def _update_file_processing_results(
        self,
        file_id: str,
        chunks: List[str],
        embedding: List[float],
        status: str
    ):
        """Update file with processing results"""
        import json
        client = await get_postgresql_client()

        # Sanitize chunks: remove null bytes and other control characters
        # that PostgreSQL can't handle in JSONB
        sanitized_chunks = [
            chunk.replace('\u0000', '').replace('\x00', '')
            for chunk in chunks
        ]

        # Convert chunks list to JSONB-compatible format
        chunks_json = json.dumps(sanitized_chunks)

        # Convert embedding to PostgreSQL vector format
        embedding_str = f"[{','.join(map(str, embedding))}]"

        query = f"""
            UPDATE {self.schema_name}.conversation_files
            SET processed_chunks = $1::jsonb,
                embeddings = $2::vector,
                processing_status = $3,
                processed_at = NOW()
            WHERE id = $4
        """

        await client.execute_query(query, chunks_json, embedding_str, status, file_id)

    async def _get_file_record(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file record by ID"""
        client = await get_postgresql_client()

        query = f"""
            SELECT id, conversation_id, filename, original_filename, content_type,
                   file_size_bytes, file_path, processing_status, uploaded_at
            FROM {self.schema_name}.conversation_files
            WHERE id = $1
        """

        result = await client.fetch_one(query, file_id)
        return dict(result) if result else None

    async def list_files(self, conversation_id: str) -> List[Dict[str, Any]]:
        """List files attached to conversation"""
        try:
            client = await get_postgresql_client()

            query = f"""
                SELECT id, filename, original_filename, content_type, file_size_bytes,
                       processing_status, uploaded_at, processed_at
                FROM {self.schema_name}.conversation_files
                WHERE conversation_id = $1
                ORDER BY uploaded_at DESC
            """

            rows = await client.execute_query(query, conversation_id)
            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to list conversation files: {e}")
            return []

    async def delete_file(self, conversation_id: str, file_id: str, user_id: str, allow_post_message_deletion: bool = False) -> bool:
        """Delete specific file from conversation

        Args:
            conversation_id: The conversation ID
            file_id: The file ID to delete
            user_id: The user requesting deletion
            allow_post_message_deletion: If False, prevents deletion after messages exist (default: False)
        """
        try:
            logger.info(f"DELETE FILE CALLED: file_id={file_id}, conversation_id={conversation_id}, user_id={user_id}")

            # Validate access
            await self._validate_conversation_access(conversation_id, user_id)
            logger.info(f"DELETE FILE: Access validated")

            # Check if conversation has messages (unless explicitly allowed to delete post-message)
            if not allow_post_message_deletion:
                client = await get_postgresql_client()
                message_check_query = f"""
                    SELECT COUNT(*) as count
                    FROM {self.schema_name}.messages
                    WHERE conversation_id = $1
                """
                message_count_result = await client.fetch_one(message_check_query, conversation_id)
                message_count = message_count_result['count'] if message_count_result else 0

                if message_count > 0:
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot delete files after conversation has started. Files are part of the conversation context."
                    )

            # Get file record for cleanup
            file_record = await self._get_file_record(file_id)
            logger.info(f"DELETE FILE: file_record={file_record}")
            if not file_record or str(file_record['conversation_id']) != conversation_id:
                logger.warning(f"DELETE FILE FAILED: file not found or conversation mismatch. file_record={file_record}, expected_conv_id={conversation_id}")
                return False

            # Delete from database
            client = await get_postgresql_client()
            query = f"""
                DELETE FROM {self.schema_name}.conversation_files
                WHERE id = $1 AND conversation_id = $2
            """

            rows_deleted = await client.execute_command(query, file_id, conversation_id)

            if rows_deleted > 0:
                # Delete file from disk
                file_path = Path(self.settings.file_storage_path) / file_record['file_path']
                if file_path.exists():
                    file_path.unlink()

                logger.info(f"Deleted conversation file: {file_id}")
                return True

            return False

        except HTTPException:
            raise  # Re-raise HTTPException to preserve status code and message
        except Exception as e:
            logger.error(f"Failed to delete conversation file: {e}")
            return False

    async def search_conversation_files(
        self,
        conversation_id: str,
        query: str,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Search files within a conversation using vector similarity"""
        try:
            # Generate query embedding
            embedding_client = BGE_M3_EmbeddingClient()
            embeddings = await embedding_client.generate_embeddings([query])

            if not embeddings:
                return []

            query_embedding = embeddings[0]

            # Convert embedding to PostgreSQL vector format
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'

            # Vector search against conversation files
            client = await get_postgresql_client()

            search_query = f"""
                SELECT id, filename, original_filename, processed_chunks,
                       1 - (embeddings <=> $1::vector) as similarity_score
                FROM {self.schema_name}.conversation_files
                WHERE conversation_id = $2
                  AND processing_status = 'completed'
                  AND embeddings IS NOT NULL
                  AND 1 - (embeddings <=> $1::vector) > 0.1
                ORDER BY embeddings <=> $1::vector
                LIMIT $3
            """

            rows = await client.execute_query(
                search_query, embedding_str, conversation_id, max_results
            )

            results = []

            for row in rows:
                processed_chunks = row.get('processed_chunks', [])

                if not processed_chunks:
                    continue

                # Handle case where processed_chunks might be returned as JSON string
                if isinstance(processed_chunks, str):
                    import json
                    processed_chunks = json.loads(processed_chunks)

                for idx, chunk_text in enumerate(processed_chunks):
                    results.append({
                        'id': f"{row['id']}_chunk_{idx}",
                        'document_id': row['id'],
                        'document_name': row['original_filename'],
                        'original_filename': row['original_filename'],
                        'chunk_index': idx,
                        'content': chunk_text,
                        'similarity_score': row['similarity_score'],
                        'source': 'conversation_file',
                        'source_type': 'conversation_file'
                    })

                if len(results) >= max_results:
                    results = results[:max_results]
                    break

            logger.info(f"Found {len(results)} chunks from {len(rows)} matching conversation files")
            return results

        except Exception as e:
            logger.error(f"Failed to search conversation files: {e}")
            return []

    async def get_all_chunks_for_conversation(
        self,
        conversation_id: str,
        max_chunks_per_file: int = 50,
        max_total_chunks: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve ALL chunks from files attached to conversation.
        Non-query-dependent - returns everything up to limits.

        Args:
            conversation_id: UUID of conversation
            max_chunks_per_file: Limit per file (enforces diversity)
            max_total_chunks: Total chunk limit across all files

        Returns:
            List of chunks with metadata, grouped by file
        """
        try:
            client = await get_postgresql_client()

            query = f"""
                SELECT id, filename, original_filename, processed_chunks,
                       file_size_bytes, uploaded_at
                FROM {self.schema_name}.conversation_files
                WHERE conversation_id = $1
                  AND processing_status = 'completed'
                  AND processed_chunks IS NOT NULL
                ORDER BY uploaded_at ASC
            """

            rows = await client.execute_query(query, conversation_id)

            results = []
            total_chunks = 0

            for row in rows:
                if total_chunks >= max_total_chunks:
                    break

                processed_chunks = row.get('processed_chunks', [])

                # Handle JSON string if needed
                if isinstance(processed_chunks, str):
                    import json
                    processed_chunks = json.loads(processed_chunks)

                # Limit chunks per file (diversity enforcement)
                chunks_from_this_file = 0

                for idx, chunk_text in enumerate(processed_chunks):
                    if chunks_from_this_file >= max_chunks_per_file:
                        break
                    if total_chunks >= max_total_chunks:
                        break

                    results.append({
                        'id': f"{row['id']}_chunk_{idx}",
                        'document_id': row['id'],
                        'document_name': row['original_filename'],
                        'original_filename': row['original_filename'],
                        'chunk_index': idx,
                        'total_chunks': len(processed_chunks),
                        'content': chunk_text,
                        'file_size_bytes': row['file_size_bytes'],
                        'source': 'conversation_file',
                        'source_type': 'conversation_file'
                    })

                    chunks_from_this_file += 1
                    total_chunks += 1

            logger.info(f"Retrieved {len(results)} total chunks from {len(rows)} conversation files")
            return results

        except Exception as e:
            logger.error(f"Failed to get all chunks for conversation: {e}")
            return []

    async def _validate_conversation_access(self, conversation_id: str, user_id: str):
        """Validate user has access to conversation"""
        client = await get_postgresql_client()

        query = f"""
            SELECT id FROM {self.schema_name}.conversations
            WHERE id = $1 AND user_id = (
                SELECT id FROM {self.schema_name}.users WHERE email = $2 LIMIT 1
            )
        """

        result = await client.fetch_one(query, conversation_id, user_id)
        if not result:
            raise HTTPException(
                status_code=403,
                detail="Access denied: conversation not found or access denied"
            )

    async def get_file_content(self, file_id: str, user_id: str) -> Optional[bytes]:
        """Get file content for download"""
        try:
            file_record = await self._get_file_record(file_id)
            if not file_record:
                return None

            # Validate access to conversation
            await self._validate_conversation_access(file_record['conversation_id'], user_id)

            # Read file content
            file_path = Path(self.settings.file_storage_path) / file_record['file_path']
            if file_path.exists():
                with open(file_path, "rb") as f:
                    return f.read()

            return None

        except Exception as e:
            logger.error(f"Failed to get file content: {e}")
            return None


# Factory function for service instances
def get_conversation_file_service(tenant_domain: str, user_id: str) -> ConversationFileService:
    """Get conversation file service instance"""
    return ConversationFileService(tenant_domain, user_id)