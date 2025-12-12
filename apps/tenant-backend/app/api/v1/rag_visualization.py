"""
RAG Network Visualization API for GT 2.0
Provides force-directed graph data and semantic relationships
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db_session
from app.core.security import get_current_user
from app.services.rag_service import RAGService
import random
import math
import json
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rag/visualization", tags=["rag-visualization"])

class NetworkNode:
    """Represents a node in the knowledge network"""
    def __init__(self, id: str, label: str, type: str, metadata: Dict[str, Any]):
        self.id = id
        self.label = label
        self.type = type  # document, chunk, concept, query
        self.metadata = metadata
        self.x = random.uniform(-100, 100)
        self.y = random.uniform(-100, 100)
        self.size = self._calculate_size(type, metadata)
        self.color = self._get_color_by_type(type)
        self.importance = metadata.get('importance', 0.5)
        
    def _calculate_size(self, type: str, metadata: Dict[str, Any]) -> int:
        """Calculate node size based on type and metadata"""
        base_sizes = {
            "document": 20,
            "chunk": 10,
            "concept": 15,
            "query": 25
        }
        
        base_size = base_sizes.get(type, 10)
        
        # Adjust based on importance/usage
        if 'usage_count' in metadata:
            usage_multiplier = min(2.0, 1.0 + metadata['usage_count'] / 10.0)
            base_size = int(base_size * usage_multiplier)
            
        if 'relevance_score' in metadata:
            relevance_multiplier = 0.5 + metadata['relevance_score'] * 0.5
            base_size = int(base_size * relevance_multiplier)
            
        return max(5, min(50, base_size))
    
    def _get_color_by_type(self, type: str) -> str:
        """Get color based on node type"""
        colors = {
            "document": "#00d084",      # GT Green
            "chunk": "#677489",         # GT Gray
            "concept": "#4a5568",       # Darker gray
            "query": "#ff6b6b",         # Red for queries
            "dataset": "#4ade80",       # Light green
            "user": "#3b82f6"           # Blue
        }
        return colors.get(type, "#9aa5b1")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "label": self.label,
            "type": self.type,
            "x": float(self.x),
            "y": float(self.y),
            "size": self.size,
            "color": self.color,
            "importance": self.importance,
            "metadata": self.metadata
        }

class NetworkEdge:
    """Represents an edge in the knowledge network"""
    def __init__(self, source: str, target: str, weight: float, edge_type: str = "semantic"):
        self.source = source
        self.target = target
        self.weight = max(0.0, min(1.0, weight))  # Clamp to 0-1
        self.type = edge_type
        self.color = self._get_edge_color(weight)
        self.width = self._get_edge_width(weight)
        self.animated = weight > 0.7
    
    def _get_edge_color(self, weight: float) -> str:
        """Get edge color based on weight"""
        if weight > 0.8:
            return "#00d084"      # Strong connection - GT green
        elif weight > 0.6:
            return "#4ade80"      # Medium-strong - light green
        elif weight > 0.4:
            return "#9aa5b1"      # Medium - gray
        else:
            return "#d1d9e0"      # Weak - light gray
    
    def _get_edge_width(self, weight: float) -> float:
        """Get edge width based on weight"""
        return 1.0 + (weight * 4.0)  # 1-5px width
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "source": self.source,
            "target": self.target,
            "weight": self.weight,
            "type": self.type,
            "color": self.color,
            "width": self.width,
            "animated": self.animated
        }

@router.get("/network/{dataset_id}")
async def get_knowledge_network(
    dataset_id: str,
    max_nodes: int = Query(default=100, le=500),
    min_similarity: float = Query(default=0.3, ge=0, le=1),
    include_concepts: bool = Query(default=True),
    layout_algorithm: str = Query(default="force", description="force, circular, hierarchical"),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get force-directed graph data for a RAG dataset
    Returns nodes (documents/chunks/concepts) and edges (semantic relationships)
    """
    try:
        # rag_service = RAGService(db)
        user_id = current_user["sub"]
        tenant_id = current_user.get("tenant_id", "default")
        
        # TODO: Verify dataset ownership and access permissions
        # dataset = await rag_service._get_user_dataset(user_id, dataset_id)
        # if not dataset:
        #     raise HTTPException(status_code=404, detail="Dataset not found")
        
        # For now, generate mock data that represents the expected structure
        nodes = []
        edges = []
        
        # Generate mock document nodes
        doc_count = min(max_nodes // 3, 20)
        for i in range(doc_count):
            doc_node = NetworkNode(
                id=f"doc_{i}",
                label=f"Document {i+1}",
                type="document",
                metadata={
                    "filename": f"document_{i+1}.pdf",
                    "size_bytes": random.randint(1000, 100000),
                    "chunk_count": random.randint(5, 50),
                    "upload_date": datetime.utcnow().isoformat(),
                    "usage_count": random.randint(0, 100),
                    "relevance_score": random.uniform(0.3, 1.0)
                }
            )
            nodes.append(doc_node.to_dict())
            
            # Generate chunks for this document
            chunk_count = min(5, (max_nodes - len(nodes)) // (doc_count - i))
            for j in range(chunk_count):
                chunk_node = NetworkNode(
                    id=f"chunk_{i}_{j}",
                    label=f"Chunk {j+1}",
                    type="chunk", 
                    metadata={
                        "document_id": f"doc_{i}",
                        "chunk_index": j,
                        "token_count": random.randint(50, 500),
                        "semantic_density": random.uniform(0.2, 0.9)
                    }
                )
                nodes.append(chunk_node.to_dict())
                
                # Connect chunk to document
                edge = NetworkEdge(
                    source=f"doc_{i}",
                    target=f"chunk_{i}_{j}",
                    weight=1.0,
                    edge_type="contains"
                )
                edges.append(edge.to_dict())
        
        # Generate concept nodes if requested
        if include_concepts:
            concept_count = min(10, max_nodes - len(nodes))
            concepts = ["AI", "Machine Learning", "Neural Networks", "Data Science", 
                       "Python", "JavaScript", "API", "Database", "Security", "Cloud"]
            
            for i in range(concept_count):
                if i < len(concepts):
                    concept_node = NetworkNode(
                        id=f"concept_{i}",
                        label=concepts[i],
                        type="concept",
                        metadata={
                            "frequency": random.randint(1, 50),
                            "co_occurrence_score": random.uniform(0.1, 0.8),
                            "domain": "technology"
                        }
                    )
                    nodes.append(concept_node.to_dict())
        
        # Generate semantic relationships between chunks
        chunk_nodes = [n for n in nodes if n["type"] == "chunk"]
        relationship_count = 0
        max_relationships = min(len(chunk_nodes) * 2, 100)
        
        for i, node1 in enumerate(chunk_nodes):
            if relationship_count >= max_relationships:
                break
                
            # Connect to a few other chunks based on semantic similarity
            connection_count = random.randint(1, 4)
            
            for _ in range(connection_count):
                if relationship_count >= max_relationships:
                    break
                    
                # Select random target (avoid self-connection)
                target_idx = random.randint(0, len(chunk_nodes) - 1)
                if target_idx == i:
                    continue
                    
                node2 = chunk_nodes[target_idx]
                
                # Generate similarity score (higher for nodes with related content)
                similarity = random.uniform(0.2, 0.9)
                
                # Apply minimum similarity filter
                if similarity >= min_similarity:
                    edge = NetworkEdge(
                        source=node1["id"],
                        target=node2["id"],
                        weight=similarity,
                        edge_type="semantic_similarity"
                    )
                    edges.append(edge.to_dict())
                    relationship_count += 1
        
        # Connect concepts to relevant chunks
        concept_nodes = [n for n in nodes if n["type"] == "concept"]
        for concept in concept_nodes:
            # Connect to 2-5 relevant chunks
            connection_count = random.randint(2, 6)
            connected_chunks = random.sample(
                range(len(chunk_nodes)),
                k=min(connection_count, len(chunk_nodes))
            )
            
            for chunk_idx in connected_chunks:
                chunk = chunk_nodes[chunk_idx]
                relevance = random.uniform(0.4, 0.9)
                
                edge = NetworkEdge(
                    source=concept["id"],
                    target=chunk["id"],
                    weight=relevance,
                    edge_type="concept_relevance"
                )
                edges.append(edge.to_dict())
        
        # Apply layout algorithm positioning
        if layout_algorithm == "circular":
            _apply_circular_layout(nodes)
        elif layout_algorithm == "hierarchical":
            _apply_hierarchical_layout(nodes)
        # force layout uses random positioning (already applied)
        
        return {
            "dataset_id": dataset_id,
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "dataset_name": f"Dataset {dataset_id}",
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "node_types": {
                    node_type: len([n for n in nodes if n["type"] == node_type])
                    for node_type in set(n["type"] for n in nodes)
                },
                "edge_types": {
                    edge_type: len([e for e in edges if e["type"] == edge_type])
                    for edge_type in set(e["type"] for e in edges)
                },
                "min_similarity": min_similarity,
                "layout_algorithm": layout_algorithm,
                "generated_at": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating knowledge network: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search/visual")
async def visual_search(
    query: str,
    dataset_ids: Optional[List[str]] = Query(default=None),
    top_k: int = Query(default=10, le=50),
    include_network: bool = Query(default=True),
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Perform semantic search with visualization metadata
    Returns search results with connection paths and confidence scores
    """
    try:
        # rag_service = RAGService(db)
        user_id = current_user["sub"]
        tenant_id = current_user.get("tenant_id", "default")
        
        # TODO: Perform actual search using RAG service
        # results = await rag_service.search_documents(
        #     user_id=user_id,
        #     tenant_id=tenant_id,
        #     query=query,
        #     dataset_ids=dataset_ids,
        #     top_k=top_k
        # )
        
        # Generate mock search results for now
        results = []
        for i in range(top_k):
            similarity = random.uniform(0.5, 0.95)  # Mock similarity scores
            results.append({
                "id": f"result_{i}",
                "document_id": f"doc_{random.randint(0, 9)}",
                "chunk_id": f"chunk_{i}",
                "content": f"Mock search result {i+1} for query: {query}",
                "metadata": {
                    "filename": f"document_{i}.pdf",
                    "page_number": random.randint(1, 100),
                    "chunk_index": i
                },
                "similarity": similarity,
                "dataset_id": dataset_ids[0] if dataset_ids else "default"
            })
        
        # Enhance results with visualization data
        visual_results = []
        for i, result in enumerate(results):
            visual_result = {
                **result,
                "visual_metadata": {
                    "position": i + 1,
                    "relevance_score": result["similarity"],
                    "confidence_level": _calculate_confidence(result["similarity"]),
                    "connection_strength": result["similarity"],
                    "highlight_color": _get_relevance_color(result["similarity"]),
                    "path_to_query": _generate_path(query, result),
                    "semantic_distance": 1.0 - result["similarity"],
                    "cluster_id": f"cluster_{random.randint(0, 2)}"
                }
            }
            visual_results.append(visual_result)
        
        response = {
            "query": query,
            "results": visual_results,
            "total_results": len(visual_results),
            "search_metadata": {
                "execution_time_ms": random.randint(50, 200),
                "datasets_searched": dataset_ids or ["all"],
                "semantic_method": "embedding_similarity",
                "reranking_applied": True
            }
        }
        
        # Add network visualization if requested
        if include_network:
            network_data = _generate_search_network(query, visual_results)
            response["network_visualization"] = network_data
            
        return response
        
    except Exception as e:
        logger.error(f"Error in visual search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/datasets/{dataset_id}/stats")
async def get_dataset_stats(
    dataset_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get statistical information about a dataset for visualization"""
    try:
        # TODO: Implement actual dataset statistics
        return {
            "dataset_id": dataset_id,
            "document_count": random.randint(10, 100),
            "chunk_count": random.randint(100, 1000),
            "total_tokens": random.randint(10000, 100000),
            "concept_count": random.randint(20, 200),
            "average_document_similarity": random.uniform(0.3, 0.8),
            "semantic_clusters": random.randint(3, 10),
            "most_connected_documents": [
                {"id": f"doc_{i}", "connections": random.randint(5, 50)}
                for i in range(5)
            ],
            "topic_distribution": {
                f"topic_{i}": random.uniform(0.05, 0.3)
                for i in range(5)
            },
            "last_updated": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting dataset stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
def _calculate_confidence(similarity: float) -> str:
    """Calculate confidence level from similarity score"""
    if similarity > 0.9:
        return "very_high"
    elif similarity > 0.75:
        return "high"
    elif similarity > 0.6:
        return "medium"
    elif similarity > 0.4:
        return "low"
    else:
        return "very_low"

def _get_relevance_color(similarity: float) -> str:
    """Get color based on relevance score"""
    if similarity > 0.8:
        return "#00d084"  # GT Green
    elif similarity > 0.6:
        return "#4ade80"  # Light green
    elif similarity > 0.4:
        return "#fbbf24"  # Yellow
    else:
        return "#ef4444"  # Red

def _generate_path(query: str, result: Dict[str, Any]) -> List[str]:
    """Generate conceptual path from query to result"""
    return [
        "query",
        f"dataset_{result.get('dataset_id', 'unknown')}",
        f"document_{result.get('document_id', 'unknown')}",
        f"chunk_{result.get('chunk_id', 'unknown')}"
    ]

def _generate_search_network(query: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate network visualization for search results"""
    nodes = []
    edges = []
    
    # Add query node
    query_node = NetworkNode(
        id="query",
        label=query[:50] + "..." if len(query) > 50 else query,
        type="query",
        metadata={"original_query": query}
    )
    nodes.append(query_node.to_dict())
    
    # Add result nodes and connections
    for i, result in enumerate(results):
        result_node = NetworkNode(
            id=f"result_{i}",
            label=result.get("content", "")[:30] + "...",
            type="chunk",
            metadata={
                "similarity": result["similarity"],
                "position": i + 1,
                "document_id": result.get("document_id")
            }
        )
        nodes.append(result_node.to_dict())
        
        # Connect query to result
        edge = NetworkEdge(
            source="query",
            target=f"result_{i}",
            weight=result["similarity"],
            edge_type="search_result"
        )
        edges.append(edge.to_dict())
    
    return {
        "nodes": nodes,
        "edges": edges,
        "center_node_id": "query",
        "layout": "radial"
    }

def _apply_circular_layout(nodes: List[Dict[str, Any]]) -> None:
    """Apply circular layout to nodes"""
    if not nodes:
        return
        
    radius = 150
    angle_step = 2 * math.pi / len(nodes)

    for i, node in enumerate(nodes):
        angle = i * angle_step
        node["x"] = radius * math.cos(angle)
        node["y"] = radius * math.sin(angle)

def _apply_hierarchical_layout(nodes: List[Dict[str, Any]]) -> None:
    """Apply hierarchical layout to nodes"""
    if not nodes:
        return
    
    # Group by type
    node_types = {}
    for node in nodes:
        node_type = node["type"]
        if node_type not in node_types:
            node_types[node_type] = []
        node_types[node_type].append(node)
    
    # Position by type levels
    y_positions = {"document": -100, "concept": 0, "chunk": 100, "query": -150}
    
    for node_type, type_nodes in node_types.items():
        y_pos = y_positions.get(node_type, 0)
        x_step = 300 / max(1, len(type_nodes) - 1) if len(type_nodes) > 1 else 0
        
        for i, node in enumerate(type_nodes):
            node["y"] = y_pos
            node["x"] = -150 + (i * x_step) if len(type_nodes) > 1 else 0