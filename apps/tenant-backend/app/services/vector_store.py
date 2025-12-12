"""
Vector Store Service for Tenant Backend

Manages tenant-specific ChromaDB instances with encryption.
All vectors are stored locally in the tenant's encrypted database.
"""

import logging
import os
import hashlib
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import chromadb
from chromadb.config import Settings
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class VectorSearchResult:
    """Result from vector search"""
    document_id: str
    text: str
    score: float
    metadata: Dict[str, Any]


class TenantEncryption:
    """Encryption handler for tenant data"""
    
    def __init__(self, tenant_id: str):
        """Initialize encryption for tenant"""
        # Derive encryption key from tenant-specific secret
        tenant_key = f"{settings.SECRET_KEY}:{tenant_id}"
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=tenant_id.encode(),
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(tenant_key.encode()))
        self.cipher = Fernet(key)
    
    def encrypt(self, data: str) -> bytes:
        """Encrypt string data"""
        return self.cipher.encrypt(data.encode())
    
    def decrypt(self, encrypted_data: bytes) -> str:
        """Decrypt data to string"""
        return self.cipher.decrypt(encrypted_data).decode()
    
    def encrypt_vector(self, vector: List[float]) -> bytes:
        """Encrypt vector data"""
        vector_str = json.dumps(vector)
        return self.encrypt(vector_str)
    
    def decrypt_vector(self, encrypted_vector: bytes) -> List[float]:
        """Decrypt vector data"""
        vector_str = self.decrypt(encrypted_vector)
        return json.loads(vector_str)


class VectorStoreService:
    """
    Manages tenant-specific vector storage with ChromaDB.
    
    Security principles:
    - All vectors stored in tenant-specific directory
    - Encryption at rest for all data
    - User-scoped collections
    - No cross-tenant access
    """
    
    def __init__(self, tenant_id: str, tenant_domain: str):
        self.tenant_id = tenant_id
        self.tenant_domain = tenant_domain
        
        # Initialize encryption
        self.encryption = TenantEncryption(tenant_id)
        
        # Initialize ChromaDB client based on configuration mode
        if settings.chromadb_mode == "http":
            # Use HTTP client for per-tenant ChromaDB server
            self.client = chromadb.HttpClient(
                host=settings.chromadb_host,
                port=settings.chromadb_port,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=False
                )
            )
            logger.info(f"Vector store initialized for tenant {tenant_domain} using HTTP mode at {settings.chromadb_host}:{settings.chromadb_port}")
        else:
            # Use file-based client (fallback)
            self.storage_path = settings.chromadb_path
            os.makedirs(self.storage_path, exist_ok=True, mode=0o700)
            
            self.client = chromadb.PersistentClient(
                path=self.storage_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=False,
                    is_persistent=True
                )
            )
            logger.info(f"Vector store initialized for tenant {tenant_domain} using file mode at {self.storage_path}")
    
    async def create_user_collection(
        self,
        user_id: str,
        collection_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a user-scoped collection.
        
        Args:
            user_id: User identifier
            collection_name: Name of the collection
            metadata: Optional collection metadata
        
        Returns:
            Collection ID
        """
        # Generate unique collection name for user
        collection_id = f"{user_id}_{collection_name}"
        collection_hash = hashlib.sha256(collection_id.encode()).hexdigest()[:8]
        internal_name = f"col_{collection_hash}"
        
        try:
            # Create or get collection
            collection = self.client.get_or_create_collection(
                name=internal_name,
                metadata={
                    "user_id": user_id,
                    "collection_name": collection_name,
                    "tenant_id": self.tenant_id,
                    **(metadata or {})
                }
            )
            
            logger.info(f"Created collection {collection_name} for user {user_id}")
            return collection_id
            
        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            raise
    
    async def store_vectors(
        self,
        user_id: str,
        collection_name: str,
        documents: List[str],
        embeddings: List[List[float]],
        ids: Optional[List[str]] = None,
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Store vectors in user collection with encryption.
        
        Args:
            user_id: User identifier
            collection_name: Collection name
            documents: List of document texts
            embeddings: List of embedding vectors
            ids: Optional document IDs
            metadata: Optional document metadata
        
        Returns:
            Success status
        """
        try:
            # Get collection
            collection_id = f"{user_id}_{collection_name}"
            collection_hash = hashlib.sha256(collection_id.encode()).hexdigest()[:8]
            internal_name = f"col_{collection_hash}"
            
            collection = self.client.get_collection(name=internal_name)
            
            # Generate IDs if not provided
            if ids is None:
                ids = [
                    hashlib.sha256(f"{doc}:{i}".encode()).hexdigest()[:16]
                    for i, doc in enumerate(documents)
                ]
            
            # Encrypt documents before storage
            encrypted_docs = [
                self.encryption.encrypt(doc).decode('latin-1')
                for doc in documents
            ]
            
            # Prepare metadata with encryption status
            final_metadata = []
            for i, doc_meta in enumerate(metadata or [{}] * len(documents)):
                meta = {
                    **doc_meta,
                    "encrypted": True,
                    "user_id": user_id,
                    "doc_hash": hashlib.sha256(documents[i].encode()).hexdigest()[:16]
                }
                final_metadata.append(meta)
            
            # Add to collection
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=encrypted_docs,
                metadatas=final_metadata
            )
            
            logger.info(
                f"Stored {len(documents)} vectors in collection {collection_name} "
                f"for user {user_id}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error storing vectors: {e}")
            raise
    
    async def search(
        self,
        user_id: str,
        collection_name: str,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """
        Search for similar vectors in user collection.
        
        Args:
            user_id: User identifier
            collection_name: Collection name
            query_embedding: Query vector
            top_k: Number of results to return
            filter_metadata: Optional metadata filters
        
        Returns:
            List of search results with decrypted content
        """
        try:
            # Get collection
            collection_id = f"{user_id}_{collection_name}"
            collection_hash = hashlib.sha256(collection_id.encode()).hexdigest()[:8]
            internal_name = f"col_{collection_hash}"
            
            collection = self.client.get_collection(name=internal_name)
            
            # Prepare filter
            where_filter = {"user_id": user_id}
            if filter_metadata:
                where_filter.update(filter_metadata)
            
            # Query collection
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter
            )
            
            # Process results
            search_results = []
            if results and results['ids'] and len(results['ids'][0]) > 0:
                for i in range(len(results['ids'][0])):
                    # Decrypt document text
                    encrypted_doc = results['documents'][0][i].encode('latin-1')
                    decrypted_doc = self.encryption.decrypt(encrypted_doc)
                    
                    search_results.append(VectorSearchResult(
                        document_id=results['ids'][0][i],
                        text=decrypted_doc,
                        score=1.0 - results['distances'][0][i],  # Convert distance to similarity
                        metadata=results['metadatas'][0][i] if results['metadatas'] else {}
                    ))
            
            logger.info(
                f"Found {len(search_results)} results in collection {collection_name} "
                f"for user {user_id}"
            )
            return search_results
            
        except Exception as e:
            logger.error(f"Error searching vectors: {e}")
            raise
    
    async def delete_collection(
        self,
        user_id: str,
        collection_name: str
    ) -> bool:
        """
        Delete a user collection.
        
        Args:
            user_id: User identifier
            collection_name: Collection name
        
        Returns:
            Success status
        """
        try:
            collection_id = f"{user_id}_{collection_name}"
            collection_hash = hashlib.sha256(collection_id.encode()).hexdigest()[:8]
            internal_name = f"col_{collection_hash}"
            
            self.client.delete_collection(name=internal_name)
            
            logger.info(f"Deleted collection {collection_name} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            raise
    
    async def list_user_collections(
        self,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        List all collections for a user.
        
        Args:
            user_id: User identifier
        
        Returns:
            List of collection information
        """
        try:
            all_collections = self.client.list_collections()
            user_collections = []
            
            for collection in all_collections:
                metadata = collection.metadata
                if metadata and metadata.get("user_id") == user_id:
                    user_collections.append({
                        "name": metadata.get("collection_name"),
                        "created_at": metadata.get("created_at"),
                        "document_count": collection.count(),
                        "metadata": metadata
                    })
            
            return user_collections
            
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            raise
    
    async def get_collection_stats(
        self,
        user_id: str,
        collection_name: str
    ) -> Dict[str, Any]:
        """
        Get statistics for a user collection.
        
        Args:
            user_id: User identifier
            collection_name: Collection name
        
        Returns:
            Collection statistics
        """
        try:
            collection_id = f"{user_id}_{collection_name}"
            collection_hash = hashlib.sha256(collection_id.encode()).hexdigest()[:8]
            internal_name = f"col_{collection_hash}"
            
            collection = self.client.get_collection(name=internal_name)
            
            stats = {
                "document_count": collection.count(),
                "collection_name": collection_name,
                "user_id": user_id,
                "metadata": collection.metadata,
                "storage_mode": settings.chromadb_mode,
                "storage_path": getattr(self, 'storage_path', f"{settings.chromadb_host}:{settings.chromadb_port}")
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            raise
    
    async def update_document(
        self,
        user_id: str,
        collection_name: str,
        document_id: str,
        new_text: Optional[str] = None,
        new_embedding: Optional[List[float]] = None,
        new_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update a document in the collection.
        
        Args:
            user_id: User identifier
            collection_name: Collection name
            document_id: Document ID to update
            new_text: Optional new text
            new_embedding: Optional new embedding
            new_metadata: Optional new metadata
        
        Returns:
            Success status
        """
        try:
            collection_id = f"{user_id}_{collection_name}"
            collection_hash = hashlib.sha256(collection_id.encode()).hexdigest()[:8]
            internal_name = f"col_{collection_hash}"
            
            collection = self.client.get_collection(name=internal_name)
            
            update_params = {"ids": [document_id]}
            
            if new_text:
                encrypted_text = self.encryption.encrypt(new_text).decode('latin-1')
                update_params["documents"] = [encrypted_text]
            
            if new_embedding:
                update_params["embeddings"] = [new_embedding]
            
            if new_metadata:
                update_params["metadatas"] = [{
                    **new_metadata,
                    "encrypted": True,
                    "user_id": user_id
                }]
            
            collection.update(**update_params)
            
            logger.info(f"Updated document {document_id} in collection {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating document: {e}")
            raise