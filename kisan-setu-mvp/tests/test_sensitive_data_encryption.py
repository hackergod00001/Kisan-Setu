"""
Property-based tests for sensitive data encryption (Property 26).

**Validates: Requirements 8.6**

Tests that sensitive fields (price, financial_behavior, phone numbers) are
encrypted at rest in DynamoDB.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import Mock, patch, MagicMock
import base64

from common.models import Transaction, Farmer, FPO, ReliabilityScore, LedgerData
from common.encryption import (
    EncryptionService, 
    encrypt_sensitive_fields, 
    decrypt_sensitive_fields,
    SENSITIVE_FIELDS
)
from tests.generators import (
    transaction_data,
    farmer_data,
    fpo_data,
    reliability_score,
    ledger_data
)


# ============================================================================
# Mock KMS Client for Testing
# ============================================================================

class MockKMSClient:
    """Mock KMS client for testing without actual AWS calls."""
    
    def __init__(self):
        # Use a fixed key for testing
        self.data_key = b'0' * 32  # 32 bytes for AES-256
        self.encrypted_key = b'encrypted_key_blob'
    
    def generate_data_key(self, KeyId, KeySpec):
        """Mock generate_data_key."""
        return {
            'Plaintext': self.data_key,
            'CiphertextBlob': self.encrypted_key
        }
    
    def decrypt(self, CiphertextBlob):
        """Mock decrypt."""
        return {
            'Plaintext': self.data_key
        }


@pytest.fixture
def mock_kms():
    """Fixture to mock KMS client."""
    with patch('boto3.client') as mock_boto_client:
        mock_client = MockKMSClient()
        mock_boto_client.return_value = mock_client
        yield mock_client


@pytest.fixture
def encryption_service(mock_kms):
    """Fixture to create encryption service with mocked KMS."""
    with patch.dict(os.environ, {'KMS_KEY_ID': 'test-key-id'}):
        service = EncryptionService(kms_key_id='test-key-id')
        service.kms_client = mock_kms
        return service


# ============================================================================
# Property 26: Sensitive Data Encryption
# ============================================================================

@given(transaction_data())
@settings(max_examples=100)
def test_property_26_transaction_price_encryption(transaction):
    """
    Feature: kisan-setu, Property 26: Sensitive Data Encryption
    
    For any Transaction entity containing price field, the price should be
    encrypted before storage in DynamoDB.
    
    **Validates: Requirements 8.6**
    """
    # Create encryption service with mocked KMS
    with patch('boto3.client') as mock_boto_client:
        mock_client = MockKMSClient()
        mock_boto_client.return_value = mock_client
        
        with patch.dict(os.environ, {'KMS_KEY_ID': 'test-key-id'}):
            encryption_service = EncryptionService(kms_key_id='test-key-id')
            encryption_service.kms_client = mock_client
            
            # Convert transaction to dict
            transaction_dict = {
                'transaction_id': transaction.transaction_id,
                'farmer_id': transaction.farmer_id,
                'fpo_id': transaction.fpo_id,
                'quantity': transaction.quantity,
                'crop_type': transaction.crop_type,
                'quality_grade': transaction.quality_grade,
                'moisture': transaction.moisture,
                'price': transaction.price,
                'timestamp': transaction.timestamp.isoformat(),
                'sync_status': transaction.sync_status.value
            }
            
            # Encrypt sensitive fields
            encrypted_dict = encrypt_sensitive_fields(
                transaction_dict, 
                SENSITIVE_FIELDS['Transaction']
            )
            
            # Property: price field should be encrypted
            assert 'price' in encrypted_dict
            assert encrypted_dict['price'] != transaction.price
            assert encryption_service.is_encrypted(str(encrypted_dict['price']))
            
            # Property: encrypted value should be in format "encrypted_key:ciphertext"
            assert ':' in encrypted_dict['price']
            parts = encrypted_dict['price'].split(':', 1)
            assert len(parts) == 2
            
            # Property: both parts should be valid base64
            try:
                base64.b64decode(parts[0])
                base64.b64decode(parts[1])
            except Exception:
                pytest.fail("Encrypted value parts are not valid base64")
            
            # Property: decryption should recover original value
            decrypted_dict = decrypt_sensitive_fields(
                encrypted_dict,
                SENSITIVE_FIELDS['Transaction']
            )
            assert float(decrypted_dict['price']) == pytest.approx(transaction.price, rel=1e-6)
            
            # Property: non-sensitive fields should remain unchanged
            assert encrypted_dict['quantity'] == transaction.quantity
            assert encrypted_dict['crop_type'] == transaction.crop_type
            assert encrypted_dict['farmer_id'] == transaction.farmer_id


@given(farmer_data())
@settings(max_examples=100)
def test_property_26_farmer_phone_encryption(farmer):
    """
    Feature: kisan-setu, Property 26: Sensitive Data Encryption
    
    For any Farmer entity containing phone field, the phone number should be
    encrypted before storage in DynamoDB.
    
    **Validates: Requirements 8.6**
    """
    with patch('boto3.client') as mock_boto_client:
        mock_client = MockKMSClient()
        mock_boto_client.return_value = mock_client
        
        with patch.dict(os.environ, {'KMS_KEY_ID': 'test-key-id'}):
            encryption_service = EncryptionService(kms_key_id='test-key-id')
            encryption_service.kms_client = mock_client
            
            # Convert farmer to dict
            farmer_dict = {
                'farmer_id': farmer.farmer_id,
                'name': farmer.name,
                'phone': farmer.phone,
                'fpo_id': farmer.fpo_id,
                'gps_coords': farmer.gps_coords,
                'preferred_language': farmer.preferred_language,
                'join_date': farmer.join_date.isoformat()
            }
            
            # Encrypt sensitive fields
            encrypted_dict = encrypt_sensitive_fields(
                farmer_dict,
                SENSITIVE_FIELDS['Farmer']
            )
            
            # Property: phone field should be encrypted
            assert 'phone' in encrypted_dict
            assert encrypted_dict['phone'] != farmer.phone
            assert encryption_service.is_encrypted(encrypted_dict['phone'])
            
            # Property: encrypted value should be in correct format
            assert ':' in encrypted_dict['phone']
            parts = encrypted_dict['phone'].split(':', 1)
            assert len(parts) == 2
            
            # Property: decryption should recover original value
            decrypted_dict = decrypt_sensitive_fields(
                encrypted_dict,
                SENSITIVE_FIELDS['Farmer']
            )
            assert decrypted_dict['phone'] == farmer.phone
            
            # Property: non-sensitive fields should remain unchanged
            assert encrypted_dict['name'] == farmer.name
            assert encrypted_dict['farmer_id'] == farmer.farmer_id
            assert encrypted_dict['fpo_id'] == farmer.fpo_id


@given(reliability_score())
@settings(max_examples=100)
def test_property_26_financial_behavior_encryption(score):
    """
    Feature: kisan-setu, Property 26: Sensitive Data Encryption
    
    For any ReliabilityScore entity containing financial_behavior field,
    the financial_behavior score should be encrypted before storage in DynamoDB.
    
    **Validates: Requirements 8.6**
    """
    with patch('boto3.client') as mock_boto_client:
        mock_client = MockKMSClient()
        mock_boto_client.return_value = mock_client
        
        with patch.dict(os.environ, {'KMS_KEY_ID': 'test-key-id'}):
            encryption_service = EncryptionService(kms_key_id='test-key-id')
            encryption_service.kms_client = mock_client
            
            # Convert score to dict
            score_dict = {
                'farmer_id': score.farmer_id,
                'total_score': score.total_score,
                'supply_consistency': score.supply_consistency,
                'quality_metrics': score.quality_metrics,
                'transaction_history': score.transaction_history,
                'financial_behavior': score.financial_behavior,
                'operational_transparency': score.operational_transparency,
                'calculation_date': score.calculation_date.isoformat(),
                'score_change': score.score_change
            }
            
            # Encrypt sensitive fields
            encrypted_dict = encrypt_sensitive_fields(
                score_dict,
                SENSITIVE_FIELDS['ReliabilityScore']
            )
            
            # Property: financial_behavior field should be encrypted
            assert 'financial_behavior' in encrypted_dict
            assert encrypted_dict['financial_behavior'] != score.financial_behavior
            assert encryption_service.is_encrypted(str(encrypted_dict['financial_behavior']))
            
            # Property: encrypted value should be in correct format
            assert ':' in encrypted_dict['financial_behavior']
            
            # Property: decryption should recover original value
            decrypted_dict = decrypt_sensitive_fields(
                encrypted_dict,
                SENSITIVE_FIELDS['ReliabilityScore']
            )
            assert float(decrypted_dict['financial_behavior']) == pytest.approx(
                score.financial_behavior, rel=1e-6
            )
            
            # Property: non-sensitive fields should remain unchanged
            assert encrypted_dict['total_score'] == score.total_score
            assert encrypted_dict['supply_consistency'] == score.supply_consistency
            assert encrypted_dict['quality_metrics'] == score.quality_metrics


@given(ledger_data())
@settings(max_examples=100)
def test_property_26_ledger_price_encryption(ledger):
    """
    Feature: kisan-setu, Property 26: Sensitive Data Encryption
    
    For any LedgerData entity containing price field, the price should be
    encrypted before storage in DynamoDB.
    
    **Validates: Requirements 8.6**
    """
    with patch('boto3.client') as mock_boto_client:
        mock_client = MockKMSClient()
        mock_boto_client.return_value = mock_client
        
        with patch.dict(os.environ, {'KMS_KEY_ID': 'test-key-id'}):
            encryption_service = EncryptionService(kms_key_id='test-key-id')
            encryption_service.kms_client = mock_client
            
            # Convert ledger to dict
            ledger_dict = {
                'ledger_id': ledger.ledger_id,
                'farmer_id': ledger.farmer_id,
                'quantity': ledger.quantity,
                'moisture': ledger.moisture,
                'price': ledger.price,
                'date': ledger.date if isinstance(ledger.date, str) else ledger.date.isoformat(),
                'crop_type': ledger.crop_type,
                'image_url': ledger.image_url
            }
            
            # Encrypt sensitive fields
            encrypted_dict = encrypt_sensitive_fields(
                ledger_dict,
                SENSITIVE_FIELDS['LedgerData']
            )
            
            # Property: price field should be encrypted
            assert 'price' in encrypted_dict
            assert encrypted_dict['price'] != ledger.price
            assert encryption_service.is_encrypted(str(encrypted_dict['price']))
            
            # Property: decryption should recover original value
            decrypted_dict = decrypt_sensitive_fields(
                encrypted_dict,
                SENSITIVE_FIELDS['LedgerData']
            )
            assert float(decrypted_dict['price']) == pytest.approx(ledger.price, rel=1e-6)
            
            # Property: non-sensitive fields should remain unchanged
            assert encrypted_dict['quantity'] == ledger.quantity
            assert encrypted_dict['moisture'] == ledger.moisture
            assert encrypted_dict['crop_type'] == ledger.crop_type


@given(fpo_data())
@settings(max_examples=100)
def test_property_26_fpo_manager_contact_encryption(fpo):
    """
    Feature: kisan-setu, Property 26: Sensitive Data Encryption
    
    For any FPO entity containing manager_contact field, the phone number
    should be encrypted before storage in DynamoDB.
    
    **Validates: Requirements 8.6**
    """
    with patch('boto3.client') as mock_boto_client:
        mock_client = MockKMSClient()
        mock_boto_client.return_value = mock_client
        
        with patch.dict(os.environ, {'KMS_KEY_ID': 'test-key-id'}):
            encryption_service = EncryptionService(kms_key_id='test-key-id')
            encryption_service.kms_client = mock_client
            
            # Convert FPO to dict
            fpo_dict = {
                'fpo_id': fpo.fpo_id,
                'name': fpo.name,
                'location': fpo.location,
                'manager_contact': fpo.manager_contact,
                'created_date': fpo.created_date.isoformat(),
                'member_count': fpo.member_count
            }
            
            # Encrypt sensitive fields
            encrypted_dict = encrypt_sensitive_fields(
                fpo_dict,
                SENSITIVE_FIELDS['FPO']
            )
            
            # Property: manager_contact field should be encrypted
            assert 'manager_contact' in encrypted_dict
            assert encrypted_dict['manager_contact'] != fpo.manager_contact
            assert encryption_service.is_encrypted(encrypted_dict['manager_contact'])
            
            # Property: decryption should recover original value
            decrypted_dict = decrypt_sensitive_fields(
                encrypted_dict,
                SENSITIVE_FIELDS['FPO']
            )
            assert decrypted_dict['manager_contact'] == fpo.manager_contact
            
            # Property: non-sensitive fields should remain unchanged
            assert encrypted_dict['name'] == fpo.name
            assert encrypted_dict['location'] == fpo.location
            assert encrypted_dict['member_count'] == fpo.member_count


# ============================================================================
# Additional Encryption Properties
# ============================================================================

@given(st.text(min_size=1, max_size=100))
@settings(max_examples=100)
def test_encryption_roundtrip_property(plaintext):
    """
    Property: For any plaintext value, encrypting and then decrypting
    should recover the original value.
    """
    with patch('boto3.client') as mock_boto_client:
        mock_client = MockKMSClient()
        mock_boto_client.return_value = mock_client
        
        with patch.dict(os.environ, {'KMS_KEY_ID': 'test-key-id'}):
            encryption_service = EncryptionService(kms_key_id='test-key-id')
            encryption_service.kms_client = mock_client
            
            encrypted = encryption_service.encrypt_field(plaintext)
            decrypted = encryption_service.decrypt_field(encrypted)
            assert decrypted == plaintext


@given(st.floats(min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_encryption_numeric_roundtrip_property(number):
    """
    Property: For any numeric value, encrypting and then decrypting
    should recover the original value (as string representation).
    """
    with patch('boto3.client') as mock_boto_client:
        mock_client = MockKMSClient()
        mock_boto_client.return_value = mock_client
        
        with patch.dict(os.environ, {'KMS_KEY_ID': 'test-key-id'}):
            encryption_service = EncryptionService(kms_key_id='test-key-id')
            encryption_service.kms_client = mock_client
            
            encrypted = encryption_service.encrypt_field(number)
            decrypted = encryption_service.decrypt_field(encrypted)
            assert float(decrypted) == pytest.approx(number, rel=1e-6)


@given(st.text(min_size=1, max_size=100))
@settings(max_examples=100)
def test_encrypted_values_are_different_property(plaintext):
    """
    Property: For any plaintext value, the encrypted value should be
    different from the plaintext (no identity encryption).
    """
    with patch('boto3.client') as mock_boto_client:
        mock_client = MockKMSClient()
        mock_boto_client.return_value = mock_client
        
        with patch.dict(os.environ, {'KMS_KEY_ID': 'test-key-id'}):
            encryption_service = EncryptionService(kms_key_id='test-key-id')
            encryption_service.kms_client = mock_client
            
            encrypted = encryption_service.encrypt_field(plaintext)
            assert encrypted != plaintext


@given(st.text(min_size=1, max_size=100))
@settings(max_examples=100)
def test_is_encrypted_detection_property(plaintext):
    """
    Property: For any plaintext value, after encryption, is_encrypted
    should return True, and before encryption it should return False.
    """
    with patch('boto3.client') as mock_boto_client:
        mock_client = MockKMSClient()
        mock_boto_client.return_value = mock_client
        
        with patch.dict(os.environ, {'KMS_KEY_ID': 'test-key-id'}):
            encryption_service = EncryptionService(kms_key_id='test-key-id')
            encryption_service.kms_client = mock_client
            
            # Before encryption
            assert not encryption_service.is_encrypted(plaintext)
            
            # After encryption
            encrypted = encryption_service.encrypt_field(plaintext)
            assert encryption_service.is_encrypted(encrypted)
