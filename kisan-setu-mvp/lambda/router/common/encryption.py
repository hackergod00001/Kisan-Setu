"""
Encryption utilities for sensitive data at rest.

This module provides encryption/decryption for sensitive fields in DynamoDB
using AWS KMS (Key Management Service) for key management and the cryptography
library for actual encryption operations.

Sensitive fields include:
- price (financial data)
- phone numbers (personal information)
- financial_behavior scores (credit data)
"""

import boto3
import base64
import os
from typing import Optional, Union
from cryptography.fernet import Fernet


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data using AWS KMS.
    
    Uses KMS to generate data keys and Fernet for symmetric encryption.
    """
    
    def __init__(self, kms_key_id: Optional[str] = None):
        """
        Initialize encryption service.
        
        Args:
            kms_key_id: KMS key ID or ARN. If None, uses environment variable.
        """
        self.kms_client = boto3.client('kms')
        self.kms_key_id = kms_key_id or os.environ.get('KMS_KEY_ID')
        
        if not self.kms_key_id:
            raise ValueError("KMS_KEY_ID must be provided or set in environment")
    
    def _get_data_key(self) -> tuple[bytes, bytes]:
        """
        Generate a data encryption key using KMS.
        
        Returns:
            Tuple of (plaintext_key, encrypted_key)
        """
        response = self.kms_client.generate_data_key(
            KeyId=self.kms_key_id,
            KeySpec='AES_256'
        )
        return response['Plaintext'], response['CiphertextBlob']
    
    def _decrypt_data_key(self, encrypted_key: bytes) -> bytes:
        """
        Decrypt a data encryption key using KMS.
        
        Args:
            encrypted_key: Encrypted data key
            
        Returns:
            Plaintext data key
        """
        response = self.kms_client.decrypt(
            CiphertextBlob=encrypted_key
        )
        return response['Plaintext']
    
    def encrypt_field(self, plaintext: Union[str, float, int]) -> str:
        """
        Encrypt a sensitive field value.
        
        Args:
            plaintext: Value to encrypt (string, float, or int)
            
        Returns:
            Base64-encoded encrypted value with format: "encrypted_key:ciphertext"
        """
        # Convert to string if needed
        plaintext_str = str(plaintext)
        
        # Get data key from KMS
        plaintext_key, encrypted_key = self._get_data_key()
        
        # Create Fernet cipher with the data key
        fernet = Fernet(base64.urlsafe_b64encode(plaintext_key[:32]))
        
        # Encrypt the data
        ciphertext = fernet.encrypt(plaintext_str.encode('utf-8'))
        
        # Encode both encrypted key and ciphertext
        encrypted_key_b64 = base64.b64encode(encrypted_key).decode('utf-8')
        ciphertext_b64 = base64.b64encode(ciphertext).decode('utf-8')
        
        # Return format: "encrypted_key:ciphertext"
        return f"{encrypted_key_b64}:{ciphertext_b64}"
    
    def decrypt_field(self, encrypted_value: str) -> str:
        """
        Decrypt a sensitive field value.
        
        Args:
            encrypted_value: Encrypted value in format "encrypted_key:ciphertext"
            
        Returns:
            Decrypted plaintext value
        """
        # Split encrypted key and ciphertext
        parts = encrypted_value.split(':', 1)
        if len(parts) != 2:
            raise ValueError("Invalid encrypted value format")
        
        encrypted_key_b64, ciphertext_b64 = parts
        
        # Decode from base64
        encrypted_key = base64.b64decode(encrypted_key_b64)
        ciphertext = base64.b64decode(ciphertext_b64)
        
        # Decrypt the data key using KMS
        plaintext_key = self._decrypt_data_key(encrypted_key)
        
        # Create Fernet cipher with the decrypted key
        fernet = Fernet(base64.urlsafe_b64encode(plaintext_key[:32]))
        
        # Decrypt the data
        plaintext = fernet.decrypt(ciphertext)
        
        return plaintext.decode('utf-8')
    
    def is_encrypted(self, value: str) -> bool:
        """
        Check if a value appears to be encrypted.
        
        Args:
            value: Value to check
            
        Returns:
            True if value appears to be encrypted, False otherwise
        """
        if not isinstance(value, str):
            return False
        
        # Check for our encryption format: "base64:base64"
        parts = value.split(':', 1)
        if len(parts) != 2:
            return False
        
        try:
            # Try to decode both parts as base64
            base64.b64decode(parts[0])
            base64.b64decode(parts[1])
            return True
        except Exception:
            return False


# Singleton instance for easy access
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    Get or create the singleton encryption service instance.
    
    Returns:
        EncryptionService instance
    """
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def encrypt_sensitive_fields(data: dict, sensitive_fields: list[str]) -> dict:
    """
    Encrypt specified sensitive fields in a dictionary.
    
    Args:
        data: Dictionary containing data
        sensitive_fields: List of field names to encrypt
        
    Returns:
        Dictionary with sensitive fields encrypted
    """
    service = get_encryption_service()
    encrypted_data = data.copy()
    
    for field in sensitive_fields:
        if field in encrypted_data and encrypted_data[field] is not None:
            encrypted_data[field] = service.encrypt_field(encrypted_data[field])
    
    return encrypted_data


def decrypt_sensitive_fields(data: dict, sensitive_fields: list[str]) -> dict:
    """
    Decrypt specified sensitive fields in a dictionary.
    
    Args:
        data: Dictionary containing encrypted data
        sensitive_fields: List of field names to decrypt
        
    Returns:
        Dictionary with sensitive fields decrypted
    """
    service = get_encryption_service()
    decrypted_data = data.copy()
    
    for field in sensitive_fields:
        if field in decrypted_data and decrypted_data[field] is not None:
            if service.is_encrypted(str(decrypted_data[field])):
                decrypted_data[field] = service.decrypt_field(str(decrypted_data[field]))
    
    return decrypted_data


# Define which fields are sensitive for each entity type
SENSITIVE_FIELDS = {
    'Transaction': ['price'],
    'Farmer': ['phone'],
    'FPO': ['manager_contact'],
    'ReliabilityScore': ['financial_behavior'],
    'LedgerData': ['price']
}
