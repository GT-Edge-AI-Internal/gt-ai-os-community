"""
Client modules for service-to-service communication
"""
from app.clients.resource_cluster_client import ResourceClusterClient, get_resource_cluster_client

__all__ = ["ResourceClusterClient", "get_resource_cluster_client"]
