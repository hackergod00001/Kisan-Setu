"""
Property-based tests for DynamoDB key structure compliance.

This module validates that all data entities stored in DynamoDB follow
the defined partition key (PK) and sort key (SK) patterns as specified
in the design document.

Feature: kisan-setu
Property 22: DynamoDB Key Structure Compliance
**Validates: Requirements 8.1**
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

import pytest
import re
from hypothesis import given, settings, assume
from datetime import datetime

# Import generators
from generators import (
    farmer_data, fpo_data, transaction_data, ndvi_result,
    reliability_score, message_data, gps_coordinates, uuid_string
)

# Import models
from common.models import (
    Farmer, FPO, Transaction, ReliabilityScore, NDVIResult, Message
)


# ============================================================================
# Key Pattern Validators
# ============================================================================

class DynamoDBKeyPatterns:
    """
    Validators for DynamoDB key patterns as defined in the design document.
    
    Key Patterns:
    1. FPO: PK="FPO#{fpo_id}", SK="METADATA"
    2. Farmer: PK="FARMER#{farmer_id}", SK="METADATA"
    3. Transaction: PK="FARMER#{farmer_id}", SK="TXN#{timestamp}"
    4. Reliability Score: PK="FARMER#{farmer_id}", SK="SCORE#{date}"
    5. Satellite Analysis: PK="FIELD#{gps_coords_hash}", SK="NDVI#{timestamp}"
    6. Conversation History: PK="CONVERSATION#{farmer_id}", SK="MSG#{timestamp}"
    7. Offline Sync Queue: PK="SYNC#{device_id}", SK="PENDING#{timestamp}"
    """
    
    # Regex patterns for validation
    FPO_PK_PATTERN = re.compile(r'^FPO#[a-f0-9]+$')
    FPO_SK_PATTERN = re.compile(r'^METADATA$')
    
    FARMER_PK_PATTERN = re.compile(r'^FARMER#[a-f0-9]+$')
    FARMER_SK_PATTERN = re.compile(r'^METADATA$')
    
    TRANSACTION_PK_PATTERN = re.compile(r'^FARMER#[a-f0-9]+$')
    TRANSACTION_SK_PATTERN = re.compile(r'^TXN#\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
    
    SCORE_PK_PATTERN = re.compile(r'^FARMER#[a-f0-9]+$')
    SCORE_SK_PATTERN = re.compile(r'^SCORE#\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
    
    FIELD_PK_PATTERN = re.compile(r'^FIELD#-?\d+\.\d+_-?\d+\.\d+$')
    NDVI_SK_PATTERN = re.compile(r'^NDVI#\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
    
    CONVERSATION_PK_PATTERN = re.compile(r'^CONVERSATION#[a-f0-9]+$')
    MESSAGE_SK_PATTERN = re.compile(r'^MSG#\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
    
    SYNC_PK_PATTERN = re.compile(r'^SYNC#[a-f0-9]+$')
    PENDING_SK_PATTERN = re.compile(r'^PENDING#\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
    
    @staticmethod
    def validate_fpo_keys(pk: str, sk: str) -> bool:
        """Validate FPO entity keys."""
        return (DynamoDBKeyPatterns.FPO_PK_PATTERN.match(pk) is not None and
                DynamoDBKeyPatterns.FPO_SK_PATTERN.match(sk) is not None)
    
    @staticmethod
    def validate_farmer_keys(pk: str, sk: str) -> bool:
        """Validate Farmer entity keys."""
        return (DynamoDBKeyPatterns.FARMER_PK_PATTERN.match(pk) is not None and
                DynamoDBKeyPatterns.FARMER_SK_PATTERN.match(sk) is not None)
    
    @staticmethod
    def validate_transaction_keys(pk: str, sk: str) -> bool:
        """Validate Transaction entity keys."""
        return (DynamoDBKeyPatterns.TRANSACTION_PK_PATTERN.match(pk) is not None and
                DynamoDBKeyPatterns.TRANSACTION_SK_PATTERN.match(sk) is not None)
    
    @staticmethod
    def validate_score_keys(pk: str, sk: str) -> bool:
        """Validate Reliability Score entity keys."""
        return (DynamoDBKeyPatterns.SCORE_PK_PATTERN.match(pk) is not None and
                DynamoDBKeyPatterns.SCORE_SK_PATTERN.match(sk) is not None)
    
    @staticmethod
    def validate_ndvi_keys(pk: str, sk: str) -> bool:
        """Validate NDVI/Satellite Analysis entity keys."""
        return (DynamoDBKeyPatterns.FIELD_PK_PATTERN.match(pk) is not None and
                DynamoDBKeyPatterns.NDVI_SK_PATTERN.match(sk) is not None)
    
    @staticmethod
    def validate_message_keys(pk: str, sk: str) -> bool:
        """Validate Conversation Message entity keys."""
        return (DynamoDBKeyPatterns.CONVERSATION_PK_PATTERN.match(pk) is not None and
                DynamoDBKeyPatterns.MESSAGE_SK_PATTERN.match(sk) is not None)
    
    @staticmethod
    def validate_sync_keys(pk: str, sk: str) -> bool:
        """Validate Offline Sync Queue entity keys."""
        return (DynamoDBKeyPatterns.SYNC_PK_PATTERN.match(pk) is not None and
                DynamoDBKeyPatterns.PENDING_SK_PATTERN.match(sk) is not None)


# ============================================================================
# Key Generation Functions
# ============================================================================

def generate_fpo_keys(fpo: FPO) -> tuple:
    """Generate DynamoDB keys for FPO entity."""
    pk = f'FPO#{fpo.fpo_id}'
    sk = 'METADATA'
    return (pk, sk)


def generate_farmer_keys(farmer: Farmer) -> tuple:
    """Generate DynamoDB keys for Farmer entity."""
    pk = f'FARMER#{farmer.farmer_id}'
    sk = 'METADATA'
    return (pk, sk)


def generate_transaction_keys(transaction: Transaction) -> tuple:
    """Generate DynamoDB keys for Transaction entity."""
    pk = f'FARMER#{transaction.farmer_id}'
    sk = f'TXN#{transaction.timestamp.isoformat()}'
    return (pk, sk)


def generate_score_keys(score: ReliabilityScore) -> tuple:
    """Generate DynamoDB keys for Reliability Score entity."""
    pk = f'FARMER#{score.farmer_id}'
    sk = f'SCORE#{score.calculation_date.isoformat()}'
    return (pk, sk)


def generate_ndvi_keys(ndvi: NDVIResult) -> tuple:
    """Generate DynamoDB keys for NDVI/Satellite Analysis entity."""
    coords_hash = f"{ndvi.gps_coords[0]:.6f}_{ndvi.gps_coords[1]:.6f}"
    pk = f'FIELD#{coords_hash}'
    sk = f'NDVI#{ndvi.timestamp.isoformat()}'
    return (pk, sk)


def generate_message_keys(message: Message) -> tuple:
    """Generate DynamoDB keys for Conversation Message entity."""
    pk = f'CONVERSATION#{message.sender_id}'
    sk = f'MSG#{message.timestamp.isoformat()}'
    return (pk, sk)


def generate_sync_keys(device_id: str, timestamp: datetime) -> tuple:
    """Generate DynamoDB keys for Offline Sync Queue entity."""
    pk = f'SYNC#{device_id}'
    sk = f'PENDING#{timestamp.isoformat()}'
    return (pk, sk)


# ============================================================================
# Property Tests
# ============================================================================

class TestDynamoDBKeyStructure:
    """
    Property-based tests for DynamoDB key structure compliance.
    
    Feature: kisan-setu
    Property 22: DynamoDB Key Structure Compliance
    **Validates: Requirements 8.1**
    
    For any data entity stored in DynamoDB, the partition key (PK) and
    sort key (SK) should follow the defined format for that entity type.
    """
    
    @given(fpo_data())
    @settings(max_examples=100)
    def test_property_22_fpo_key_structure(self, fpo):
        """
        Property 22.1: FPO Key Structure
        
        For any FPO entity, the keys should follow:
        - PK: "FPO#{fpo_id}"
        - SK: "METADATA"
        
        **Validates: Requirements 8.1**
        """
        pk, sk = generate_fpo_keys(fpo)
        
        # Validate key structure
        assert DynamoDBKeyPatterns.validate_fpo_keys(pk, sk), \
            f"FPO keys do not match pattern. PK: {pk}, SK: {sk}"
        
        # Validate PK contains the FPO ID
        assert fpo.fpo_id in pk, \
            f"FPO ID {fpo.fpo_id} not found in PK {pk}"
        
        # Validate SK is exactly "METADATA"
        assert sk == "METADATA", \
            f"FPO SK should be 'METADATA', got {sk}"
    
    @given(farmer_data())
    @settings(max_examples=100)
    def test_property_22_farmer_key_structure(self, farmer):
        """
        Property 22.2: Farmer Key Structure
        
        For any Farmer entity, the keys should follow:
        - PK: "FARMER#{farmer_id}"
        - SK: "METADATA"
        
        **Validates: Requirements 8.1**
        """
        pk, sk = generate_farmer_keys(farmer)
        
        # Validate key structure
        assert DynamoDBKeyPatterns.validate_farmer_keys(pk, sk), \
            f"Farmer keys do not match pattern. PK: {pk}, SK: {sk}"
        
        # Validate PK contains the Farmer ID
        assert farmer.farmer_id in pk, \
            f"Farmer ID {farmer.farmer_id} not found in PK {pk}"
        
        # Validate SK is exactly "METADATA"
        assert sk == "METADATA", \
            f"Farmer SK should be 'METADATA', got {sk}"
    
    @given(transaction_data())
    @settings(max_examples=100)
    def test_property_22_transaction_key_structure(self, transaction):
        """
        Property 22.3: Transaction Key Structure
        
        For any Transaction entity, the keys should follow:
        - PK: "FARMER#{farmer_id}"
        - SK: "TXN#{timestamp}"
        
        **Validates: Requirements 8.1**
        """
        pk, sk = generate_transaction_keys(transaction)
        
        # Validate key structure
        assert DynamoDBKeyPatterns.validate_transaction_keys(pk, sk), \
            f"Transaction keys do not match pattern. PK: {pk}, SK: {sk}"
        
        # Validate PK contains the Farmer ID
        assert transaction.farmer_id in pk, \
            f"Farmer ID {transaction.farmer_id} not found in PK {pk}"
        
        # Validate SK starts with "TXN#"
        assert sk.startswith("TXN#"), \
            f"Transaction SK should start with 'TXN#', got {sk}"
        
        # Validate SK contains timestamp
        timestamp_str = transaction.timestamp.isoformat()
        assert timestamp_str in sk, \
            f"Timestamp {timestamp_str} not found in SK {sk}"
    
    @given(reliability_score())
    @settings(max_examples=100)
    def test_property_22_score_key_structure(self, score):
        """
        Property 22.4: Reliability Score Key Structure
        
        For any Reliability Score entity, the keys should follow:
        - PK: "FARMER#{farmer_id}"
        - SK: "SCORE#{date}"
        
        **Validates: Requirements 8.1**
        """
        pk, sk = generate_score_keys(score)
        
        # Validate key structure
        assert DynamoDBKeyPatterns.validate_score_keys(pk, sk), \
            f"Score keys do not match pattern. PK: {pk}, SK: {sk}"
        
        # Validate PK contains the Farmer ID
        assert score.farmer_id in pk, \
            f"Farmer ID {score.farmer_id} not found in PK {pk}"
        
        # Validate SK starts with "SCORE#"
        assert sk.startswith("SCORE#"), \
            f"Score SK should start with 'SCORE#', got {sk}"
        
        # Validate SK contains date
        date_str = score.calculation_date.isoformat()
        assert date_str in sk, \
            f"Date {date_str} not found in SK {sk}"
    
    @given(ndvi_result())
    @settings(max_examples=100)
    def test_property_22_ndvi_key_structure(self, ndvi):
        """
        Property 22.5: NDVI/Satellite Analysis Key Structure
        
        For any NDVI entity, the keys should follow:
        - PK: "FIELD#{gps_coords_hash}"
        - SK: "NDVI#{timestamp}"
        
        **Validates: Requirements 8.1**
        """
        pk, sk = generate_ndvi_keys(ndvi)
        
        # Validate key structure
        assert DynamoDBKeyPatterns.validate_ndvi_keys(pk, sk), \
            f"NDVI keys do not match pattern. PK: {pk}, SK: {sk}"
        
        # Validate PK starts with "FIELD#"
        assert pk.startswith("FIELD#"), \
            f"NDVI PK should start with 'FIELD#', got {pk}"
        
        # Validate PK contains GPS coordinates
        coords_hash = f"{ndvi.gps_coords[0]:.6f}_{ndvi.gps_coords[1]:.6f}"
        assert coords_hash in pk, \
            f"GPS coords hash {coords_hash} not found in PK {pk}"
        
        # Validate SK starts with "NDVI#"
        assert sk.startswith("NDVI#"), \
            f"NDVI SK should start with 'NDVI#', got {sk}"
        
        # Validate SK contains timestamp
        timestamp_str = ndvi.timestamp.isoformat()
        assert timestamp_str in sk, \
            f"Timestamp {timestamp_str} not found in SK {sk}"
    
    @given(message_data())
    @settings(max_examples=100)
    def test_property_22_message_key_structure(self, message):
        """
        Property 22.6: Conversation Message Key Structure
        
        For any Message entity, the keys should follow:
        - PK: "CONVERSATION#{farmer_id}"
        - SK: "MSG#{timestamp}"
        
        **Validates: Requirements 8.1**
        """
        pk, sk = generate_message_keys(message)
        
        # Validate key structure
        assert DynamoDBKeyPatterns.validate_message_keys(pk, sk), \
            f"Message keys do not match pattern. PK: {pk}, SK: {sk}"
        
        # Validate PK starts with "CONVERSATION#"
        assert pk.startswith("CONVERSATION#"), \
            f"Message PK should start with 'CONVERSATION#', got {pk}"
        
        # Validate PK contains sender ID
        assert message.sender_id in pk, \
            f"Sender ID {message.sender_id} not found in PK {pk}"
        
        # Validate SK starts with "MSG#"
        assert sk.startswith("MSG#"), \
            f"Message SK should start with 'MSG#', got {sk}"
        
        # Validate SK contains timestamp
        timestamp_str = message.timestamp.isoformat()
        assert timestamp_str in sk, \
            f"Timestamp {timestamp_str} not found in SK {sk}"
    
    @given(uuid_string())
    @settings(max_examples=100)
    def test_property_22_sync_key_structure(self, device_id):
        """
        Property 22.7: Offline Sync Queue Key Structure
        
        For any Sync Queue entity, the keys should follow:
        - PK: "SYNC#{device_id}"
        - SK: "PENDING#{timestamp}"
        
        **Validates: Requirements 8.1**
        """
        timestamp = datetime.now()
        pk, sk = generate_sync_keys(device_id, timestamp)
        
        # Validate key structure
        assert DynamoDBKeyPatterns.validate_sync_keys(pk, sk), \
            f"Sync keys do not match pattern. PK: {pk}, SK: {sk}"
        
        # Validate PK starts with "SYNC#"
        assert pk.startswith("SYNC#"), \
            f"Sync PK should start with 'SYNC#', got {pk}"
        
        # Validate PK contains device ID
        assert device_id in pk, \
            f"Device ID {device_id} not found in PK {pk}"
        
        # Validate SK starts with "PENDING#"
        assert sk.startswith("PENDING#"), \
            f"Sync SK should start with 'PENDING#', got {sk}"
        
        # Validate SK contains timestamp
        timestamp_str = timestamp.isoformat()
        assert timestamp_str in sk, \
            f"Timestamp {timestamp_str} not found in SK {sk}"


# ============================================================================
# Integration Tests with DynamoDB Access
# ============================================================================

class TestDynamoDBKeyStructureIntegration:
    """
    Integration tests validating that DynamoDB access layer generates
    correct key structures.
    """
    
    @given(fpo_data())
    @settings(max_examples=100)
    def test_fpo_keys_match_access_layer(self, fpo):
        """
        Verify that FPO keys generated match the access layer implementation.
        """
        # Expected keys from our generator
        expected_pk, expected_sk = generate_fpo_keys(fpo)
        
        # Keys that would be generated by DynamoDB access layer
        actual_pk = f'FPO#{fpo.fpo_id}'
        actual_sk = 'METADATA'
        
        assert expected_pk == actual_pk, \
            f"FPO PK mismatch: expected {expected_pk}, got {actual_pk}"
        assert expected_sk == actual_sk, \
            f"FPO SK mismatch: expected {expected_sk}, got {actual_sk}"
    
    @given(farmer_data())
    @settings(max_examples=100)
    def test_farmer_keys_match_access_layer(self, farmer):
        """
        Verify that Farmer keys generated match the access layer implementation.
        """
        # Expected keys from our generator
        expected_pk, expected_sk = generate_farmer_keys(farmer)
        
        # Keys that would be generated by DynamoDB access layer
        actual_pk = f'FARMER#{farmer.farmer_id}'
        actual_sk = 'METADATA'
        
        assert expected_pk == actual_pk, \
            f"Farmer PK mismatch: expected {expected_pk}, got {actual_pk}"
        assert expected_sk == actual_sk, \
            f"Farmer SK mismatch: expected {expected_sk}, got {actual_sk}"
    
    @given(transaction_data())
    @settings(max_examples=100)
    def test_transaction_keys_match_access_layer(self, transaction):
        """
        Verify that Transaction keys generated match the access layer implementation.
        """
        # Expected keys from our generator
        expected_pk, expected_sk = generate_transaction_keys(transaction)
        
        # Keys that would be generated by DynamoDB access layer
        actual_pk = f'FARMER#{transaction.farmer_id}'
        actual_sk = f'TXN#{transaction.timestamp.isoformat()}'
        
        assert expected_pk == actual_pk, \
            f"Transaction PK mismatch: expected {expected_pk}, got {actual_pk}"
        assert expected_sk == actual_sk, \
            f"Transaction SK mismatch: expected {expected_sk}, got {actual_sk}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
