"""
GT 2.0 PostgreSQL File Storage Service

Replaces MinIO with PostgreSQL-based file storage using:
- BYTEA for small files (<10MB)
- PostgreSQL Large Objects (LOBs) for large files (10MB-1GB)
- Filesystem with metadata for massive files (>1GB)

Provides perfect tenant isolation through PostgreSQL schemas.
"""

import asyncio
import json
import logging
import os
import hashlib
import mimetypes
from typing import Dict, Any, List, Optional, BinaryIO, AsyncIterator, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import aiofiles
from fastapi import UploadFile

from app.core.postgresql_client import get_postgresql_client
from app.core.config import get_settings
from app.core.permissions import ADMIN_ROLES
from app.core.path_security import sanitize_tenant_domain, sanitize_filename, safe_join_path

logger = logging.getLogger(__name__)

class PostgreSQLFileService:
    """PostgreSQL-based file storage service with tenant isolation"""

    # Storage type thresholds
    SMALL_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB - use BYTEA
    LARGE_FILE_THRESHOLD = 1024 * 1024 * 1024  # 1GB - use LOBs

    def __init__(self, tenant_domain: str, user_id: str, user_role: str = "user"):
        self.tenant_domain = tenant_domain
        self.user_id = user_id
        self.user_role = user_role
        self.settings = get_settings()

        # Filesystem path for massive files (>1GB)
        # Sanitize tenant_domain to prevent path traversal
        safe_tenant = sanitize_tenant_domain(tenant_domain)
        self.filesystem_base = Path("/data") / safe_tenant / "files"  # codeql[py/path-injection] sanitize_tenant_domain() validates input
        self.filesystem_base.mkdir(parents=True, exist_ok=True, mode=0o700)

        logger.info(f"PostgreSQL file service initialized for {tenant_domain}/{user_id} (role: {user_role})")
    
    async def store_file(
        self,
        file: UploadFile,
        dataset_id: Optional[str] = None,
        category: str = "documents"
    ) -> Dict[str, Any]:
        """Store file using appropriate PostgreSQL strategy"""

        try:
            logger.info(f"PostgreSQL file service: storing file {file.filename} for tenant {self.tenant_domain}, user {self.user_id}")
            logger.info(f"Dataset ID: {dataset_id}, Category: {category}")
            # Read file content
            content = await file.read()
            file_size = len(content)
            
            # Generate file metadata
            file_hash = hashlib.sha256(content).hexdigest()[:16]
            content_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
            
            # Handle different file types with appropriate processing
            if file_size <= self.SMALL_FILE_THRESHOLD and content_type.startswith('text/'):
                # Small text files stored directly
                storage_type = "text"
                storage_ref = "content_text"
                try:
                    text_content = content.decode('utf-8')
                except UnicodeDecodeError:
                    text_content = content.decode('latin-1')  # Fallback encoding
            elif content_type == 'application/pdf':
                # PDF files: extract text content, store binary separately
                storage_type = "pdf_extracted"
                storage_ref = "content_text"
                text_content = await self._extract_pdf_text(content)
            else:
                # Other binary files: store as base64 for now
                import base64
                storage_type = "base64"
                storage_ref = "content_text"
                text_content = base64.b64encode(content).decode('utf-8')
            
            # Get PostgreSQL client
            logger.info("Getting PostgreSQL client")
            pg_client = await get_postgresql_client()

            # Always expect user_id to be a UUID string - no email lookups
            logger.info(f"Using user UUID: {self.user_id}")

            # Validate user_id is a valid UUID format
            try:
                import uuid
                user_uuid = str(uuid.UUID(self.user_id))
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid user UUID format: {self.user_id}, error: {e}")
                raise ValueError(f"Invalid user ID format. Expected UUID, got: {self.user_id}")

            logger.info(f"Validated user UUID: {user_uuid}")

            # 1. Validate user_uuid is present
            if not user_uuid:
                raise ValueError("User UUID is required but not found")

            # 2. Validate and clean dataset_id
            dataset_uuid_param = None
            if dataset_id and dataset_id.strip() and dataset_id != "":
                try:
                    import uuid
                    dataset_uuid_param = str(uuid.UUID(dataset_id.strip()))
                    logger.info(f"Dataset UUID validated: {dataset_uuid_param}")
                except ValueError as e:
                    logger.error(f"Invalid dataset UUID: {dataset_id}, error: {e}")
                    raise ValueError(f"Invalid dataset ID format: {dataset_id}")
            else:
                logger.info("No dataset_id provided, using NULL")

            # 3. Validate file content and metadata
            if not file.filename or not file.filename.strip():
                raise ValueError("Filename cannot be empty")

            if not content:
                raise ValueError("File content cannot be empty")

            # 4. Generate and validate all string parameters
            safe_filename = f"{file_hash}_{file.filename}"
            safe_original_filename = file.filename.strip()
            safe_content_type = content_type or "application/octet-stream"
            safe_file_hash = file_hash
            safe_metadata = json.dumps({
                "storage_type": storage_type,
                "storage_ref": storage_ref,
                "category": category
            })

            logger.info(f"All parameters validated:")
            logger.info(f"  user_uuid: {user_uuid}")
            logger.info(f"  dataset_uuid: {dataset_uuid_param}")
            logger.info(f"  filename: {safe_filename}")
            logger.info(f"  original_filename: {safe_original_filename}")
            logger.info(f"  file_type: {safe_content_type}")
            logger.info(f"  file_size: {file_size}")
            logger.info(f"  file_hash: {safe_file_hash}")

            # Store metadata in documents table (using existing schema)
            try:
                # Application user now has BYPASSRLS privilege - no RLS context needed
                logger.info("Storing document with BYPASSRLS privilege")

                # Require dataset_id for all document uploads
                if not dataset_uuid_param:
                    raise ValueError("dataset_id is required for document uploads")

                logger.info(f"Storing document with dataset_id: {dataset_uuid_param}")
                logger.info(f"Document details: {safe_filename} ({file_size} bytes)")

                # Insert with dataset_id
                # Determine if content is searchable (under PostgreSQL tsvector size limit)
                is_searchable = text_content is None or len(text_content) < 1048575

                async with pg_client.get_connection() as conn:
                    # Get tenant_id for the document
                    tenant_id = await conn.fetchval("""
                        SELECT id FROM tenants WHERE domain = $1 LIMIT 1
                    """, self.tenant_domain)

                    if not tenant_id:
                        raise ValueError(f"Tenant not found for domain: {self.tenant_domain}")

                    document_id = await conn.fetchval("""
                        INSERT INTO documents (
                            tenant_id, user_id, dataset_id, filename, original_filename,
                            file_type, file_size_bytes, file_hash, content_text, processing_status,
                            metadata, is_searchable, created_at, updated_at
                        ) VALUES (
                            $1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9, 'pending', $10, $11, NOW(), NOW()
                        )
                        RETURNING id
                    """,
                        tenant_id, user_uuid, dataset_uuid_param, safe_filename, safe_original_filename,
                        safe_content_type, file_size, safe_file_hash, text_content,
                        safe_metadata, is_searchable
                    )
                logger.info(f"Document inserted successfully with ID: {document_id}")

            except Exception as db_error:
                logger.error(f"Database insertion failed: {db_error}")
                logger.error(f"Tenant domain: {self.tenant_domain}")
                logger.error(f"User ID: {self.user_id}")
                logger.error(f"Dataset ID: {dataset_id}")
                raise
            
            result = {
                "id": document_id,
                "filename": file.filename,
                "content_type": content_type,
                "file_size": file_size,
                "file_hash": file_hash,
                "storage_type": storage_type,
                "storage_ref": storage_ref,
                "upload_timestamp": datetime.utcnow().isoformat(),
                "download_url": f"/api/v1/files/{document_id}"
            }
            
            logger.info(f"Stored file {file.filename} ({file_size} bytes) as {storage_type} for user {self.user_id}")

            # Trigger document processing pipeline for RAG functionality
            try:
                await self._trigger_document_processing(document_id, dataset_id, user_uuid, file.filename)
                logger.info(f"Successfully triggered document processing for {document_id}")
            except Exception as process_error:
                logger.error(f"Failed to trigger document processing for {document_id}: {process_error}")
                # Update document status to show processing failed
                try:
                    pg_client = await get_postgresql_client()
                    await pg_client.execute_command(
                        "UPDATE documents SET processing_status = 'failed', error_message = $1 WHERE id = $2",
                        f"Processing failed: {str(process_error)}", document_id
                    )
                except Exception as update_error:
                    logger.error(f"Failed to update document status after processing error: {update_error}")
                # Don't fail the upload if processing trigger fails - user can retry manually

            return result
            
        except Exception as e:
            logger.error(f"Failed to store file {file.filename}: {e}")
            raise
        finally:
            # Ensure content is cleared from memory
            if 'content' in locals():
                del content
    
    async def _store_as_bytea(
        self, 
        content: bytes, 
        filename: str, 
        content_type: str,
        file_hash: str,
        dataset_id: Optional[str],
        category: str
    ) -> str:
        """Store small file as BYTEA in documents table"""
        
        pg_client = await get_postgresql_client()
        
        # Store file content directly in BYTEA column
        # This will be handled by the main insert in store_file
        return "bytea_column"
    
    async def _store_as_lob(
        self, 
        content: bytes, 
        filename: str, 
        content_type: str,
        file_hash: str,
        dataset_id: Optional[str],
        category: str
    ) -> str:
        """Store large file as PostgreSQL Large Object"""
        
        pg_client = await get_postgresql_client()
        
        # Create Large Object and get OID
        async with pg_client.get_connection() as conn:
            # Start transaction for LOB operations
            async with conn.transaction():
                # Create LOB and get OID
                lob_oid = await conn.fetchval("SELECT lo_create(0)")
                
                # Open LOB for writing
                lob_fd = await conn.fetchval("SELECT lo_open($1, 131072)", lob_oid)  # INV_WRITE mode
                
                # Write content in chunks for memory efficiency
                chunk_size = 8192
                offset = 0
                for i in range(0, len(content), chunk_size):
                    chunk = content[i:i + chunk_size]
                    await conn.execute("SELECT lo_write($1, $2)", lob_fd, chunk)
                    offset += len(chunk)
                
                # Close LOB
                await conn.execute("SELECT lo_close($1)", lob_fd)
                
                logger.info(f"Created PostgreSQL LOB with OID {lob_oid} for {filename}")
                return str(lob_oid)
    
    async def _store_as_filesystem(
        self, 
        content: bytes, 
        filename: str, 
        content_type: str,
        file_hash: str,
        dataset_id: Optional[str],
        category: str
    ) -> str:
        """Store massive file on filesystem with PostgreSQL metadata"""
        
        # Create secure file path with user isolation
        user_dir = self.filesystem_base / self.user_id / category
        if dataset_id:
            user_dir = user_dir / dataset_id
        
        user_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        
        # Generate secure filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        secure_filename = f"{timestamp}_{file_hash}_{filename}"
        file_path = user_dir / secure_filename
        
        # Write file with secure permissions
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        # Set secure file permissions
        os.chmod(file_path, 0o600)
        
        logger.info(f"Stored large file on filesystem: {file_path}")
        return str(file_path)
    
    async def get_file(self, document_id: str) -> AsyncIterator[bytes]:
        """Stream file content by document ID"""
        
        try:
            pg_client = await get_postgresql_client()
            
            # Validate user_id is a valid UUID format
            try:
                import uuid
                user_uuid = str(uuid.UUID(self.user_id))
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid user UUID format: {self.user_id}, error: {e}")
                raise ValueError(f"Invalid user ID format. Expected UUID, got: {self.user_id}")

            # Get document metadata using UUID directly
            # Admins can access any document in their tenant, regular users only their own
            if self.user_role in ADMIN_ROLES:
                doc_info = await pg_client.fetch_one("""
                    SELECT metadata, file_size_bytes, filename, content_text
                    FROM documents d
                    WHERE d.id = $1
                      AND d.tenant_id = (SELECT id FROM tenants WHERE domain = $2)
                """, document_id, self.tenant_domain)
            else:
                doc_info = await pg_client.fetch_one("""
                    SELECT metadata, file_size_bytes, filename, content_text
                    FROM documents
                    WHERE id = $1 AND user_id = $2::uuid
                """, document_id, user_uuid)

            if not doc_info:
                raise FileNotFoundError(f"Document {document_id} not found")
            
            # Get storage info from metadata - handle JSON string or dict
            metadata_raw = doc_info["metadata"] or "{}"
            if isinstance(metadata_raw, str):
                import json
                metadata = json.loads(metadata_raw)
            else:
                metadata = metadata_raw or {}
            storage_type = metadata.get("storage_type", "text")
            
            if storage_type == "text":
                # Text content stored directly
                if doc_info["content_text"]:
                    content_bytes = doc_info["content_text"].encode('utf-8')
                    async for chunk in self._stream_from_bytea(content_bytes):
                        yield chunk
                else:
                    raise FileNotFoundError(f"Document content not found")
                    
            elif storage_type == "base64":
                # Base64 encoded binary content
                if doc_info["content_text"]:
                    import base64
                    content_bytes = base64.b64decode(doc_info["content_text"])
                    async for chunk in self._stream_from_bytea(content_bytes):
                        yield chunk
                else:
                    raise FileNotFoundError(f"Document content not found")
                    
            elif storage_type == "lob":
                # Stream from PostgreSQL LOB
                storage_ref = metadata.get("storage_ref", "")
                async for chunk in self._stream_from_lob(int(storage_ref)):
                    yield chunk
                    
            elif storage_type == "filesystem":
                # Stream from filesystem
                storage_ref = metadata.get("storage_ref", "")
                async for chunk in self._stream_from_filesystem(storage_ref):
                    yield chunk
            else:
                # Default: treat as text content
                if doc_info["content_text"]:
                    content_bytes = doc_info["content_text"].encode('utf-8')
                    async for chunk in self._stream_from_bytea(content_bytes):
                        yield chunk
                else:
                    raise FileNotFoundError(f"Document content not found")
                
        except Exception as e:
            logger.error(f"Failed to get file {document_id}: {e}")
            raise
    
    async def _stream_from_bytea(self, content: bytes) -> AsyncIterator[bytes]:
        """Stream content from BYTEA in chunks"""
        chunk_size = 8192
        for i in range(0, len(content), chunk_size):
            yield content[i:i + chunk_size]
    
    async def _stream_from_lob(self, lob_oid: int) -> AsyncIterator[bytes]:
        """Stream content from PostgreSQL Large Object"""
        
        pg_client = await get_postgresql_client()
        
        async with pg_client.get_connection() as conn:
            async with conn.transaction():
                # Open LOB for reading
                lob_fd = await conn.fetchval("SELECT lo_open($1, 262144)", lob_oid)  # INV_READ mode
                
                # Stream in chunks
                chunk_size = 8192
                while True:
                    chunk = await conn.fetchval("SELECT lo_read($1, $2)", lob_fd, chunk_size)
                    if not chunk:
                        break
                    yield chunk
                
                # Close LOB
                await conn.execute("SELECT lo_close($1)", lob_fd)
    
    async def _stream_from_filesystem(self, file_path: str) -> AsyncIterator[bytes]:
        """Stream content from filesystem"""
        
        # Verify file belongs to tenant (security check)
        path_obj = Path(file_path)
        if not str(path_obj).startswith(str(self.filesystem_base)):
            raise PermissionError("Access denied to file")
        
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        async with aiofiles.open(file_path, 'rb') as f:
            chunk_size = 8192
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    
    async def delete_file(self, document_id: str) -> bool:
        """Delete file and metadata"""
        
        try:
            pg_client = await get_postgresql_client()

            # Validate user_id is a valid UUID format
            try:
                import uuid
                user_uuid = str(uuid.UUID(self.user_id))
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid user UUID format: {self.user_id}, error: {e}")
                raise ValueError(f"Invalid user ID format. Expected UUID, got: {self.user_id}")

            # Get document info before deletion
            # Admins can delete any document in their tenant, regular users only their own
            if self.user_role in ADMIN_ROLES:
                doc_info = await pg_client.fetch_one("""
                    SELECT storage_type, storage_ref FROM documents d
                    WHERE d.id = $1
                      AND d.tenant_id = (SELECT id FROM tenants WHERE domain = $2)
                """, document_id, self.tenant_domain)
            else:
                doc_info = await pg_client.fetch_one("""
                    SELECT storage_type, storage_ref FROM documents
                    WHERE id = $1 AND user_id = $2::uuid
                """, document_id, user_uuid)

            if not doc_info:
                logger.warning(f"Document {document_id} not found for deletion")
                return False

            storage_type = doc_info["storage_type"]
            storage_ref = doc_info["storage_ref"]

            # Delete file content based on storage type
            if storage_type == "lob":
                # Delete LOB
                async with pg_client.get_connection() as conn:
                    await conn.execute("SELECT lo_unlink($1)", int(storage_ref))
            elif storage_type == "filesystem":
                # Delete filesystem file
                try:
                    path_obj = Path(storage_ref)
                    if path_obj.exists():
                        path_obj.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete filesystem file {storage_ref}: {e}")
            # BYTEA files are deleted with the row

            # Delete metadata record
            if self.user_role in ADMIN_ROLES:
                deleted = await pg_client.execute_command("""
                    DELETE FROM documents d
                    WHERE d.id = $1
                      AND d.tenant_id = (SELECT id FROM tenants WHERE domain = $2)
                """, document_id, self.tenant_domain)
            else:
                deleted = await pg_client.execute_command("""
                    DELETE FROM documents WHERE id = $1 AND user_id = $2::uuid
                """, document_id, user_uuid)
            
            if deleted > 0:
                logger.info(f"Deleted file {document_id} ({storage_type})")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete file {document_id}: {e}")
            return False
    
    async def get_file_info(self, document_id: str) -> Dict[str, Any]:
        """Get file metadata"""
        
        try:
            pg_client = await get_postgresql_client()

            # Validate user_id is a valid UUID format
            try:
                import uuid
                user_uuid = str(uuid.UUID(self.user_id))
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid user UUID format: {self.user_id}, error: {e}")
                raise ValueError(f"Invalid user ID format. Expected UUID, got: {self.user_id}")

            # Admins can access any document metadata in their tenant, regular users only their own
            if self.user_role in ADMIN_ROLES:
                doc_info = await pg_client.fetch_one("""
                    SELECT id, filename, original_filename, file_type as content_type, file_size_bytes as file_size,
                           file_hash, dataset_id, metadata->'storage_type' as storage_type, metadata->'category' as category, created_at
                    FROM documents d
                    WHERE d.id = $1
                      AND d.tenant_id = (SELECT id FROM tenants WHERE domain = $2)
                """, document_id, self.tenant_domain)
            else:
                doc_info = await pg_client.fetch_one("""
                    SELECT id, filename, original_filename, file_type as content_type, file_size_bytes as file_size,
                           file_hash, dataset_id, metadata->'storage_type' as storage_type, metadata->'category' as category, created_at
                    FROM documents
                    WHERE id = $1 AND user_id = $2::uuid
                """, document_id, user_uuid)

            if not doc_info:
                raise FileNotFoundError(f"Document {document_id} not found")
            
            return {
                "id": doc_info["id"],
                "filename": doc_info["filename"],
                "original_filename": doc_info["original_filename"],
                "content_type": doc_info["content_type"],
                "file_size": doc_info["file_size"],
                "file_hash": doc_info["file_hash"],
                "dataset_id": str(doc_info["dataset_id"]) if doc_info["dataset_id"] else None,
                "storage_type": doc_info["storage_type"],
                "category": doc_info["category"],
                "created_at": doc_info["created_at"].isoformat(),
                "download_url": f"/api/v1/files/{document_id}"
            }
            
        except Exception as e:
            logger.error(f"Failed to get file info for {document_id}: {e}")
            raise
    
    async def list_files(
        self, 
        dataset_id: Optional[str] = None,
        category: str = "documents",
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List user files with optional filtering"""
        
        try:
            pg_client = await get_postgresql_client()

            # Validate user_id is a valid UUID format
            try:
                import uuid
                user_uuid = str(uuid.UUID(self.user_id))
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid user UUID format: {self.user_id}, error: {e}")
                raise ValueError(f"Invalid user ID format. Expected UUID, got: {self.user_id}")

            # Build permission-aware query
            # Admins can list any documents in their tenant
            # Regular users can list documents they own OR documents in datasets they can access
            if self.user_role in ADMIN_ROLES:
                where_clauses = ["d.tenant_id = (SELECT id FROM tenants WHERE domain = $1)"]
                params = [self.tenant_domain]
                param_idx = 2
            else:
                # Non-admin users can see:
                # 1. Documents they own
                # 2. Documents in datasets with access_group = 'organization'
                # 3. Documents in datasets they're a member of (team access)
                where_clauses = ["""(
                    d.user_id = $1::uuid
                    OR EXISTS (
                        SELECT 1 FROM datasets ds
                        WHERE ds.id = d.dataset_id
                        AND ds.tenant_id = (SELECT id FROM tenants WHERE domain = $2)
                        AND (
                            ds.access_group = 'organization'
                            OR (ds.access_group = 'team' AND $1::uuid = ANY(ds.team_members))
                        )
                    )
                )"""]
                params = [user_uuid, self.tenant_domain]
                param_idx = 3

            if dataset_id:
                where_clauses.append(f"d.dataset_id = ${param_idx}::uuid")
                params.append(dataset_id)
                param_idx += 1

            if category:
                where_clauses.append(f"(d.metadata->>'category' = ${param_idx} OR d.metadata->>'category' IS NULL)")
                params.append(category)
                param_idx += 1

            query = f"""
                SELECT d.id, d.filename, d.original_filename, d.file_type as content_type, d.file_size_bytes as file_size,
                       d.metadata->>'storage_type' as storage_type, d.metadata->>'category' as category, d.created_at, d.updated_at, d.dataset_id,
                       d.processing_status, d.metadata, d.user_id, COUNT(dc.id) as chunk_count,
                       ds.created_by as dataset_owner_id
                FROM documents d
                LEFT JOIN document_chunks dc ON d.id = dc.document_id
                LEFT JOIN datasets ds ON d.dataset_id = ds.id
                WHERE {' AND '.join(where_clauses)}
                GROUP BY d.id, d.filename, d.original_filename, d.file_type, d.file_size_bytes, d.metadata, d.created_at, d.updated_at, d.dataset_id, d.processing_status, d.user_id, ds.created_by
                ORDER BY d.created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
            params.extend([limit, offset])

            files = await pg_client.execute_query(query, *params)

            # Helper function to parse metadata
            def parse_metadata(metadata_value):
                if metadata_value is None:
                    return {}
                if isinstance(metadata_value, str):
                    import json
                    try:
                        return json.loads(metadata_value)
                    except (json.JSONDecodeError, ValueError):
                        return {}
                return metadata_value if isinstance(metadata_value, dict) else {}

            return [
                {
                    "id": file["id"],
                    "filename": file["filename"],
                    "original_filename": file["original_filename"],
                    "content_type": file["content_type"],
                    "file_type": file["content_type"],
                    "file_size": file["file_size"],
                    "file_size_bytes": file["file_size"],
                    "dataset_id": file["dataset_id"],
                    "storage_type": file["storage_type"],
                    "category": file["category"],
                    "created_at": file["created_at"].isoformat(),
                    "updated_at": file["updated_at"].isoformat() if file.get("updated_at") else None,
                    "processing_status": file.get("processing_status", "pending"),
                    "chunk_count": file.get("chunk_count", 0),
                    "chunks_processed": parse_metadata(file.get("metadata")).get("chunks_processed", 0),
                    "total_chunks_expected": parse_metadata(file.get("metadata")).get("total_chunks_expected", 0),
                    "processing_progress": parse_metadata(file.get("metadata")).get("processing_progress", 0),
                    "processing_stage": parse_metadata(file.get("metadata")).get("processing_stage"),
                    "download_url": f"/api/v1/files/{file['id']}",
                    # Permission flags - user can delete if:
                    # 1. They are admin, OR
                    # 2. They uploaded the document, OR
                    # 3. They own the parent dataset
                    "can_delete": (
                        self.user_role in ADMIN_ROLES or
                        file["user_id"] == user_uuid or
                        (file.get("dataset_owner_id") and str(file["dataset_owner_id"]) == user_uuid)
                    )
                }
                for file in files
            ]
            
        except Exception as e:
            logger.error(f"Failed to list files for user {self.user_id}: {e}")
            return []
    
    async def cleanup_orphaned_files(self) -> int:
        """Clean up orphaned files and LOBs"""
        
        try:
            pg_client = await get_postgresql_client()
            cleanup_count = 0
            
            # Find orphaned LOBs (LOBs without corresponding document records)
            async with pg_client.get_connection() as conn:
                async with conn.transaction():
                    orphaned_lobs = await conn.fetch("""
                        SELECT lo.oid FROM pg_largeobject_metadata lo
                        LEFT JOIN documents d ON lo.oid::text = d.storage_ref
                        WHERE d.storage_ref IS NULL AND d.storage_type = 'lob'
                    """)
                    
                    for lob in orphaned_lobs:
                        await conn.execute("SELECT lo_unlink($1)", lob["oid"])
                        cleanup_count += 1
            
            # Find orphaned filesystem files
            # Note: This would require more complex logic to safely identify orphans
            
            logger.info(f"Cleaned up {cleanup_count} orphaned files")
            return cleanup_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned files: {e}")
            return 0

    async def _trigger_document_processing(
        self,
        document_id: str,
        dataset_id: Optional[str],
        user_uuid: str,
        filename: str
    ):
        """Trigger document processing pipeline for RAG functionality"""
        try:
            # Import here to avoid circular imports
            from app.services.document_processor import get_document_processor

            logger.info(f"Triggering document processing for {document_id}")

            # Get document processor instance
            processor = await get_document_processor(tenant_domain=self.tenant_domain)

            # For documents uploaded via PostgreSQL file service, the content is already stored
            # We need to process it from the database content rather than a file path
            await self._process_document_from_database(
                processor, document_id, dataset_id, user_uuid, filename
            )

        except Exception as e:
            logger.error(f"Document processing trigger failed for {document_id}: {e}")
            # Update document status to failed
            try:
                pg_client = await get_postgresql_client()
                await pg_client.execute_command(
                    "UPDATE documents SET processing_status = 'failed', error_message = $1 WHERE id = $2",
                    f"Processing trigger failed: {str(e)}", document_id
                )
            except Exception as update_error:
                logger.error(f"Failed to update document status to failed: {update_error}")
            raise

    async def _process_document_from_database(
        self,
        processor,
        document_id: str,
        dataset_id: Optional[str],
        user_uuid: str,
        filename: str
    ):
        """Process document using content already stored in database"""
        try:
            import tempfile
            import os
            from pathlib import Path

            # Get document content from database
            pg_client = await get_postgresql_client()
            doc_info = await pg_client.fetch_one("""
                SELECT content_text, file_type, metadata
                FROM documents
                WHERE id = $1 AND user_id = $2::uuid
            """, document_id, user_uuid)

            if not doc_info or not doc_info["content_text"]:
                raise ValueError("Document content not found in database")

            # Create temporary file with the content
            # Sanitize the file extension to prevent path injection
            safe_suffix = sanitize_filename(filename)
            safe_suffix = Path(safe_suffix).suffix if safe_suffix else ".tmp"
            # codeql[py/path-injection] safe_suffix is sanitized via sanitize_filename()
            with tempfile.NamedTemporaryFile(mode='w', suffix=safe_suffix, delete=False) as temp_file:
                # Handle different storage types - metadata might be JSON string or dict
                metadata_raw = doc_info["metadata"] or "{}"
                if isinstance(metadata_raw, str):
                    import json
                    metadata = json.loads(metadata_raw)
                else:
                    metadata = metadata_raw or {}
                storage_type = metadata.get("storage_type", "text")

                if storage_type == "text":
                    temp_file.write(doc_info["content_text"])
                elif storage_type == "base64":
                    import base64
                    content_bytes = base64.b64decode(doc_info["content_text"])
                    temp_file.close()
                    with open(temp_file.name, 'wb') as binary_file:
                        binary_file.write(content_bytes)
                elif storage_type == "pdf_extracted":
                    # For PDFs with extracted text, create a placeholder text file
                    # since the actual text content is already extracted
                    temp_file.write(doc_info["content_text"])
                else:
                    temp_file.write(doc_info["content_text"])

                temp_file_path = Path(temp_file.name)

            try:
                # Process the document using the existing document processor
                await processor.process_file(
                    file_path=temp_file_path,
                    dataset_id=dataset_id,  # Keep None as None - don't convert to empty string
                    user_id=user_uuid,
                    original_filename=filename,
                    document_id=document_id  # Use existing document instead of creating new one
                )

                logger.info(f"Successfully processed document {document_id} from database content")

            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temporary file {temp_file_path}: {cleanup_error}")

        except Exception as e:
            logger.error(f"Failed to process document from database content: {e}")
            raise

    async def _extract_pdf_text(self, content: bytes) -> str:
        """Extract text content from PDF bytes using pypdf"""
        import io
        import pypdf as PyPDF2  # pypdf is the maintained successor to PyPDF2

        try:
            # Create BytesIO object from content
            pdf_stream = io.BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_stream)

            text_parts = []
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text.strip():
                        text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
                except Exception as e:
                    logger.warning(f"Could not extract text from page {page_num + 1}: {e}")

            if not text_parts:
                # If no text could be extracted, return a placeholder
                return f"PDF document with {len(pdf_reader.pages)} pages (text extraction failed)"

            extracted_text = "\n\n".join(text_parts)
            logger.info(f"Successfully extracted {len(extracted_text)} characters from PDF with {len(pdf_reader.pages)} pages")
            return extracted_text

        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            # Return a fallback description instead of failing completely
            return f"PDF document (text extraction failed: {str(e)})"