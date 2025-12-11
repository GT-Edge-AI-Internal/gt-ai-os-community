"""
GT 2.0 Resource Cluster - Encryption Utilities
Secure data encryption for SSO tokens and sensitive data
"""

import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Union
import logging

logger = logging.getLogger(__name__)

class EncryptionManager:
    """Handles encryption and decryption of sensitive data"""
    
    def __init__(self):
        self._key = None
        self._fernet = None
        self._initialize_encryption()
    
    def _initialize_encryption(self):
        """Initialize encryption key from environment or generate new one"""
        # Get encryption key from environment or generate new one
        key_material = os.environ.get("GT_ENCRYPTION_KEY", "default-dev-key-change-in-production")
        
        # Derive a proper encryption key using PBKDF2
        salt = b"GT2.0-Resource-Cluster-Salt"  # Fixed salt for consistency
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(key_material.encode()))
        
        self._key = key
        self._fernet = Fernet(key)
        
        logger.info("Encryption manager initialized")
    
    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """Encrypt data and return base64 encoded result"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        encrypted = self._fernet.encrypt(data)
        return base64.urlsafe_b64encode(encrypted)
    
    def decrypt(self, encrypted_data: Union[str, bytes]) -> str:
        """Decrypt base64 encoded data and return string"""
        if isinstance(encrypted_data, str):
            encrypted_data = encrypted_data.encode('utf-8')
        
        # Decode from base64 first
        decoded = base64.urlsafe_b64decode(encrypted_data)
        
        # Decrypt
        decrypted = self._fernet.decrypt(decoded)
        return decrypted.decode('utf-8')

# Global encryption manager instance
_encryption_manager = EncryptionManager()

def encrypt_data(data: Union[str, bytes]) -> bytes:
    """Encrypt data using global encryption manager"""
    return _encryption_manager.encrypt(data)

def decrypt_data(encrypted_data: Union[str, bytes]) -> str:
    """Decrypt data using global encryption manager"""
    return _encryption_manager.decrypt(encrypted_data)