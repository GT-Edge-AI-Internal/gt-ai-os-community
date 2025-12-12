"""
Document API endpoints for GT 2.0 Tenant Backend

Handles document upload and management using PostgreSQL file service with perfect tenant isolation.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form, Query
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Dict, Any, List, Optional

from app.core.security import get_current_user
from app.core.path_security import sanitize_filename
from app.services.postgresql_file_service import PostgreSQLFileService
from app.services.document_processor import DocumentProcessor, get_document_processor
from app.api.auth import get_tenant_user_uuid_by_email

logger = logging.getLogger(__name__)
router = APIRouter(tags=["documents"])


@router.get("/documents")
async def list_documents(
    status: Optional[str] = Query(None, description="Filter by processing status"),
    dataset_id: Optional[str] = Query(None, description="Filter by dataset ID"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List user's documents with optional filtering using PostgreSQL file service"""
    try:
        # Get tenant user UUID from Control Panel user
        user_email = current_user.get('email')
        if not user_email:
            raise HTTPException(status_code=401, detail="User email not found in token")

        tenant_user_uuid = await get_tenant_user_uuid_by_email(user_email)
        if not tenant_user_uuid:
            raise HTTPException(status_code=404, detail=f"User {user_email} not found in tenant system")

        # Get PostgreSQL file service
        file_service = PostgreSQLFileService(
            tenant_domain=current_user.get('tenant_domain', 'test'),
            user_id=tenant_user_uuid
        )
        
        # List files (documents) with optional dataset filter
        files = await file_service.list_files(
            category="documents",
            dataset_id=dataset_id,
            limit=limit,
            offset=offset
        )
        
        # Get chunk counts and document status for these documents
        document_ids = [file_info["id"] for file_info in files]
        chunk_counts = {}
        document_status = {}
        if document_ids:
            from app.core.database import get_postgresql_client
            pg_client = await get_postgresql_client()

            # Get chunk counts
            chunk_query = """
                SELECT document_id, COUNT(*) as chunk_count
                FROM document_chunks
                WHERE document_id = ANY($1)
                GROUP BY document_id
            """
            chunk_results = await pg_client.execute_query(chunk_query, document_ids)
            chunk_counts = {str(row["document_id"]): row["chunk_count"] for row in chunk_results}

            # Get document processing status and progress
            status_query = """
                SELECT id, processing_status, chunk_count, chunks_processed,
                       total_chunks_expected, processing_progress, processing_stage,
                       error_message, created_at, updated_at
                FROM documents
                WHERE id = ANY($1)
            """
            status_results = await pg_client.execute_query(status_query, document_ids)
            document_status = {str(row["id"]): row for row in status_results}

        # Convert to expected document format
        documents = []
        for file_info in files:
            doc_id = str(file_info["id"])
            chunk_count = chunk_counts.get(doc_id, 0)
            status_info = document_status.get(doc_id, {})

            documents.append({
                "id": file_info["id"],
                "filename": file_info["filename"],
                "original_filename": file_info["original_filename"],
                "file_type": file_info["content_type"],
                "file_size_bytes": file_info["file_size"],
                "dataset_id": file_info.get("dataset_id"),
                "processing_status": status_info.get("processing_status", "completed"),
                "chunk_count": chunk_count,
                "chunks_processed": status_info.get("chunks_processed", chunk_count),
                "total_chunks_expected": status_info.get("total_chunks_expected", chunk_count),
                "processing_progress": status_info.get("processing_progress", 100 if chunk_count > 0 else 0),
                "processing_stage": status_info.get("processing_stage", "Completed" if chunk_count > 0 else "Pending"),
                "error_message": status_info.get("error_message"),
                "vector_count": chunk_count,  # Each chunk gets one vector
                "created_at": file_info["created_at"],
                "processed_at": status_info.get("updated_at", file_info["created_at"])
            })
        
        # Apply status filter if provided
        if status:
            documents = [doc for doc in documents if doc["processing_status"] == status]
        
        return documents
        
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    dataset_id: Optional[str] = Form(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Upload new document using PostgreSQL file service"""
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Get file extension
        import pathlib
        file_extension = pathlib.Path(file.filename).suffix.lower()
        
        # Validate file type
        allowed_extensions = ['.pdf', '.docx', '.txt', '.md', '.html', '.csv', '.json']
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Get tenant user UUID from Control Panel user
        user_email = current_user.get('email')
        if not user_email:
            raise HTTPException(status_code=401, detail="User email not found in token")

        tenant_user_uuid = await get_tenant_user_uuid_by_email(user_email)
        if not tenant_user_uuid:
            raise HTTPException(status_code=404, detail=f"User {user_email} not found in tenant system")

        # Get PostgreSQL file service
        file_service = PostgreSQLFileService(
            tenant_domain=current_user.get('tenant_domain', 'test'),
            user_id=tenant_user_uuid
        )
        
        # Store file
        result = await file_service.store_file(
            file=file,
            dataset_id=dataset_id,
            category="documents"
        )

        # Start document processing if dataset_id is provided
        if dataset_id:
            try:
                # Get document processor with tenant domain
                tenant_domain = current_user.get('tenant_domain', 'test')
                processor = await get_document_processor(tenant_domain=tenant_domain)

                # Process document for RAG (async)
                from pathlib import Path
                import tempfile
                import os

                # Create temporary file for processing
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                    # Write file content to temp file
                    file.file.seek(0)  # Reset file pointer
                    temp_file.write(await file.read())
                    temp_file.flush()

                    # Process document using existing document ID
                    try:
                        processed_doc = await processor.process_file(
                            file_path=Path(temp_file.name),
                            dataset_id=dataset_id,
                            user_id=tenant_user_uuid,
                            original_filename=file.filename,
                            document_id=result["id"]  # Use existing document ID
                        )

                        processing_status = "completed"
                        chunk_count = getattr(processed_doc, 'chunk_count', 0)

                    except Exception as proc_error:
                        logger.error(f"Document processing failed: {proc_error}")
                        processing_status = "failed"
                        chunk_count = 0
                    finally:
                        # Clean up temp file
                        os.unlink(temp_file.name)

            except Exception as proc_error:
                logger.error(f"Failed to initiate document processing: {proc_error}")
                processing_status = "pending"
                chunk_count = 0
        else:
            processing_status = "completed"
            chunk_count = 0

        # Return in expected format
        return {
            "id": result["id"],
            "filename": result["filename"],
            "original_filename": file.filename,
            "file_type": result["content_type"],
            "file_size_bytes": result["file_size"],
            "processing_status": processing_status,
            "chunk_count": chunk_count,
            "vector_count": chunk_count,  # Each chunk gets one vector
            "created_at": result["upload_timestamp"],
            "processed_at": result["upload_timestamp"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{document_id}/process")
async def process_document(
    document_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Process a document for RAG pipeline (text extraction, chunking, embedding generation)"""
    try:
        # Get tenant user UUID from Control Panel user
        user_email = current_user.get('email')
        if not user_email:
            raise HTTPException(status_code=401, detail="User email not found in token")

        tenant_user_uuid = await get_tenant_user_uuid_by_email(user_email)
        if not tenant_user_uuid:
            raise HTTPException(status_code=404, detail=f"User {user_email} not found in tenant system")

        tenant_domain = current_user.get('tenant_domain', 'test')

        # Get PostgreSQL file service to verify document exists
        file_service = PostgreSQLFileService(
            tenant_domain=tenant_domain,
            user_id=tenant_user_uuid
        )

        # Get file info to verify ownership and get file metadata
        file_info = await file_service.get_file_info(document_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="Document not found")

        # Get document processor with tenant domain
        processor = await get_document_processor(tenant_domain=tenant_domain)

        # Get file extension for temp file
        import pathlib
        original_filename = file_info.get("original_filename", file_info.get("filename", "unknown"))
        # Sanitize the filename to prevent path injection
        safe_filename = sanitize_filename(original_filename)
        file_extension = pathlib.Path(safe_filename).suffix.lower() if safe_filename else ".tmp"

        # Create temporary file from database content for processing
        from pathlib import Path
        import tempfile
        import os

        # codeql[py/path-injection] file_extension derived from sanitize_filename() at line 273
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            # Stream file content from database to temp file
            async for chunk in file_service.get_file(document_id):
                temp_file.write(chunk)
            temp_file.flush()

            # Process document
            try:
                processed_doc = await processor.process_file(
                    file_path=Path(temp_file.name),
                    dataset_id=file_info.get("dataset_id"),
                    user_id=tenant_user_uuid,
                    original_filename=original_filename
                )

                processing_status = "completed"
                chunk_count = getattr(processed_doc, 'chunk_count', 0)

            except Exception as proc_error:
                logger.error(f"Document processing failed for {document_id}: {proc_error}")
                processing_status = "failed"
                chunk_count = 0
            finally:
                # Clean up temp file
                os.unlink(temp_file.name)

        return {
            "document_id": document_id,
            "processing_status": processing_status,
            "message": "Document processed successfully" if processing_status == "completed" else f"Processing failed: {processing_status}",
            "chunk_count": chunk_count,
            "processed_at": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get("/documents/{document_id}/status")
async def get_document_processing_status(
    document_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get processing status of a document"""
    try:
        # Get document processor to check status
        tenant_domain = current_user.get('tenant_domain', 'test')
        processor = await get_document_processor(tenant_domain=tenant_domain)
        status = await processor.get_processing_status(document_id)

        return {
            "document_id": document_id,
            "processing_status": status.get("status", "unknown"),
            "error_message": status.get("error_message"),
            "chunk_count": status.get("chunk_count", 0),
            "chunks_processed": status.get("chunks_processed", 0),
            "total_chunks_expected": status.get("total_chunks_expected", 0),
            "processing_progress": status.get("processing_progress", 0),
            "processing_stage": status.get("processing_stage", "")
        }

    except Exception as e:
        logger.error(f"Failed to get processing status for {document_id}: {e}", exc_info=True)
        return {
            "document_id": document_id,
            "processing_status": "unknown",
            "error_message": "Unable to retrieve processing status",
            "chunk_count": 0,
            "chunks_processed": 0,
            "total_chunks_expected": 0,
            "processing_progress": 0,
            "processing_stage": "Error"
        }


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a document and its associated data"""
    try:
        # Get tenant user UUID from Control Panel user
        user_email = current_user.get('email')
        if not user_email:
            raise HTTPException(status_code=401, detail="User email not found in token")

        tenant_user_uuid = await get_tenant_user_uuid_by_email(user_email)
        if not tenant_user_uuid:
            raise HTTPException(status_code=404, detail=f"User {user_email} not found in tenant system")

        # Get PostgreSQL file service
        file_service = PostgreSQLFileService(
            tenant_domain=current_user.get('tenant_domain', 'test'),
            user_id=tenant_user_uuid
        )

        # Verify document exists and user has permission to delete it
        file_info = await file_service.get_file_info(document_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="Document not found")

        # Delete the document
        success = await file_service.delete_file(document_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete document")

        return {
            "message": "Document deleted successfully",
            "document_id": document_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Additional endpoints can be added here as needed for RAG processing