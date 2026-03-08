"""
Property-based tests for audit trail creation.

Feature: kisan-setu
Property 24: Audit Trail Creation

**Validates: Requirements 8.4**

For any data update operation (create, modify, delete), an audit record should be 
created containing the operation type, timestamp, user identifier, and changed fields.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

import pytest
from hypothesis import given, settings, strategies as st
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from common.dynamodb_access import DynamoDBAccess
from common.models import Farmer, Transaction, FPO, ReliabilityScore, NDVIResult
from generators import (
    farmer_data, transaction_data, fpo_data, 
    reliability_score, ndvi_result, uuid_string
)


class TestAuditTrailCreationProperty:
    """
    Property 24: Audit Trail Creation
    
    For any data update operation (create, modify, delete), an audit record should be 
    created containing the operation type, timestamp, user identifier, and changed fields.
    """
    
    @given(
        farmer=farmer_data(),
        user_id=uuid_string()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_24_audit_trail_on_farmer_create(self, farmer, user_id):
        """
        Property 24: Audit Trail Creation - Farmer Create Operation
        
        **Validates: Requirements 8.4**
        
        For any farmer creation operation, an audit record should be created with:
        - operation type = 'create'
        - timestamp (present and valid)
        - user_id (matches the user performing the operation)
        - changed_fields (contains the farmer data)
        """
        with patch('common.dynamodb_access.dynamodb') as mock_dynamodb:
            # Setup mock DynamoDB table
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            
            # Track all put_item calls
            put_item_calls = []
            def track_put_item(Item):
                put_item_calls.append(Item)
                return {'ResponseMetadata': {'HTTPStatusCode': 200}}
            
            mock_table.put_item.side_effect = track_put_item
            
            # Create farmer
            db = DynamoDBAccess()
            result = db.create_farmer(farmer, user_id)
            
            # Verify operation succeeded
            assert result is True
            
            # Find the audit trail record among all put_item calls
            audit_records = [
                item for item in put_item_calls 
                if item.get('entity_type') == 'AuditTrail'
            ]
            
            # Property: Audit record should be created
            assert len(audit_records) >= 1, "Audit trail record should be created for farmer creation"
            
            audit_record = audit_records[0]
            
            # Property: Audit record should contain operation type
            assert 'operation' in audit_record, "Audit record must contain operation type"
            assert audit_record['operation'] == 'create', "Operation type should be 'create'"
            
            # Property: Audit record should contain timestamp
            assert 'timestamp' in audit_record, "Audit record must contain timestamp"
            assert audit_record['timestamp'] is not None, "Timestamp should not be None"
            # Verify timestamp is a valid ISO format string
            try:
                datetime.fromisoformat(audit_record['timestamp'])
            except (ValueError, TypeError):
                pytest.fail("Timestamp should be a valid ISO format datetime string")
            
            # Property: Audit record should contain user_id
            assert 'user_id' in audit_record, "Audit record must contain user_id"
            assert audit_record['user_id'] == user_id, "User ID should match the user performing the operation"
            
            # Property: Audit record should contain changed_fields
            assert 'changed_fields' in audit_record, "Audit record must contain changed_fields"
            assert isinstance(audit_record['changed_fields'], dict), "Changed fields should be a dictionary"
            
            # Property: Audit record should contain entity information
            assert 'audited_entity_type' in audit_record, "Audit record must contain entity type"
            assert audit_record['audited_entity_type'] == 'Farmer', "Entity type should be 'Farmer'"
            assert 'audited_entity_id' in audit_record, "Audit record must contain entity ID"
            assert audit_record['audited_entity_id'] == farmer.farmer_id, "Entity ID should match farmer ID"
    
    @given(
        transaction=transaction_data(),
        user_id=uuid_string()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_24_audit_trail_on_transaction_create(self, transaction, user_id):
        """
        Property 24: Audit Trail Creation - Transaction Create Operation
        
        **Validates: Requirements 8.4**
        
        For any transaction creation operation, an audit record should be created with:
        - operation type = 'create'
        - timestamp (present and valid)
        - user_id (matches the user performing the operation)
        - changed_fields (contains the transaction data)
        """
        with patch('common.dynamodb_access.dynamodb') as mock_dynamodb:
            # Setup mock DynamoDB table
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            
            # Track all put_item calls
            put_item_calls = []
            def track_put_item(Item):
                put_item_calls.append(Item)
                return {'ResponseMetadata': {'HTTPStatusCode': 200}}
            
            mock_table.put_item.side_effect = track_put_item
            
            # Create transaction
            db = DynamoDBAccess()
            result = db.create_transaction(transaction, user_id)
            
            # Verify operation succeeded
            assert result is True
            
            # Find the audit trail record
            audit_records = [
                item for item in put_item_calls 
                if item.get('entity_type') == 'AuditTrail'
            ]
            
            # Property: Audit record should be created
            assert len(audit_records) >= 1, "Audit trail record should be created for transaction creation"
            
            audit_record = audit_records[0]
            
            # Property: Audit record should contain all required fields
            assert audit_record['operation'] == 'create', "Operation type should be 'create'"
            assert 'timestamp' in audit_record, "Audit record must contain timestamp"
            assert audit_record['user_id'] == user_id, "User ID should match"
            assert 'changed_fields' in audit_record, "Audit record must contain changed_fields"
            assert audit_record['audited_entity_type'] == 'Transaction', "Entity type should be 'Transaction'"
            assert audit_record['audited_entity_id'] == transaction.transaction_id, "Entity ID should match"
    
    @given(
        fpo=fpo_data(),
        user_id=uuid_string()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_24_audit_trail_on_fpo_create(self, fpo, user_id):
        """
        Property 24: Audit Trail Creation - FPO Create Operation
        
        **Validates: Requirements 8.4**
        
        For any FPO creation operation, an audit record should be created with:
        - operation type = 'create'
        - timestamp (present and valid)
        - user_id (matches the user performing the operation)
        - changed_fields (contains the FPO data)
        """
        with patch('common.dynamodb_access.dynamodb') as mock_dynamodb:
            # Setup mock DynamoDB table
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            
            # Track all put_item calls
            put_item_calls = []
            def track_put_item(Item):
                put_item_calls.append(Item)
                return {'ResponseMetadata': {'HTTPStatusCode': 200}}
            
            mock_table.put_item.side_effect = track_put_item
            
            # Create FPO
            db = DynamoDBAccess()
            result = db.create_fpo(fpo, user_id)
            
            # Verify operation succeeded
            assert result is True
            
            # Find the audit trail record
            audit_records = [
                item for item in put_item_calls 
                if item.get('entity_type') == 'AuditTrail'
            ]
            
            # Property: Audit record should be created
            assert len(audit_records) >= 1, "Audit trail record should be created for FPO creation"
            
            audit_record = audit_records[0]
            
            # Property: Audit record should contain all required fields
            assert audit_record['operation'] == 'create', "Operation type should be 'create'"
            assert 'timestamp' in audit_record, "Audit record must contain timestamp"
            assert audit_record['user_id'] == user_id, "User ID should match"
            assert 'changed_fields' in audit_record, "Audit record must contain changed_fields"
            assert audit_record['audited_entity_type'] == 'FPO', "Entity type should be 'FPO'"
            assert audit_record['audited_entity_id'] == fpo.fpo_id, "Entity ID should match"
    
    @given(
        score=reliability_score(),
        user_id=uuid_string()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_24_audit_trail_on_score_create(self, score, user_id):
        """
        Property 24: Audit Trail Creation - ReliabilityScore Create Operation
        
        **Validates: Requirements 8.4**
        
        For any reliability score creation operation, an audit record should be created.
        """
        with patch('common.dynamodb_access.dynamodb') as mock_dynamodb:
            # Setup mock DynamoDB table
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            
            # Track all put_item calls
            put_item_calls = []
            def track_put_item(Item):
                put_item_calls.append(Item)
                return {'ResponseMetadata': {'HTTPStatusCode': 200}}
            
            mock_table.put_item.side_effect = track_put_item
            
            # Create reliability score
            db = DynamoDBAccess()
            result = db.save_credit_score(score, user_id)
            
            # Verify operation succeeded
            assert result is True
            
            # Find the audit trail record
            audit_records = [
                item for item in put_item_calls 
                if item.get('entity_type') == 'AuditTrail'
            ]
            
            # Property: Audit record should be created
            assert len(audit_records) >= 1, "Audit trail record should be created for score creation"
            
            audit_record = audit_records[0]
            
            # Property: Audit record should contain all required fields
            assert audit_record['operation'] == 'create', "Operation type should be 'create'"
            assert 'timestamp' in audit_record, "Audit record must contain timestamp"
            assert audit_record['user_id'] == user_id, "User ID should match"
            assert 'changed_fields' in audit_record, "Audit record must contain changed_fields"
            assert audit_record['audited_entity_type'] == 'ReliabilityScore', "Entity type should be 'ReliabilityScore'"
    
    @given(
        ndvi=ndvi_result(),
        user_id=uuid_string()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_24_audit_trail_on_ndvi_create(self, ndvi, user_id):
        """
        Property 24: Audit Trail Creation - NDVIResult Create Operation
        
        **Validates: Requirements 8.4**
        
        For any NDVI result creation operation, an audit record should be created.
        """
        with patch('common.dynamodb_access.dynamodb') as mock_dynamodb:
            # Setup mock DynamoDB table
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            
            # Track all put_item calls
            put_item_calls = []
            def track_put_item(Item):
                put_item_calls.append(Item)
                return {'ResponseMetadata': {'HTTPStatusCode': 200}}
            
            mock_table.put_item.side_effect = track_put_item
            
            # Create NDVI result
            db = DynamoDBAccess()
            result = db.save_ndvi_result(ndvi, user_id)
            
            # Verify operation succeeded
            assert result is True
            
            # Find the audit trail record
            audit_records = [
                item for item in put_item_calls 
                if item.get('entity_type') == 'AuditTrail'
            ]
            
            # Property: Audit record should be created
            assert len(audit_records) >= 1, "Audit trail record should be created for NDVI creation"
            
            audit_record = audit_records[0]
            
            # Property: Audit record should contain all required fields
            assert audit_record['operation'] == 'create', "Operation type should be 'create'"
            assert 'timestamp' in audit_record, "Audit record must contain timestamp"
            assert audit_record['user_id'] == user_id, "User ID should match"
            assert 'changed_fields' in audit_record, "Audit record must contain changed_fields"
            assert audit_record['audited_entity_type'] == 'NDVIResult', "Entity type should be 'NDVIResult'"
    
    @given(
        operation=st.sampled_from(['create', 'update', 'delete']),
        entity_type=st.sampled_from(['Farmer', 'Transaction', 'FPO', 'ReliabilityScore', 'NDVIResult']),
        entity_id=uuid_string(),
        user_id=uuid_string(),
        changed_fields=st.dictionaries(
            keys=st.text(alphabet='abcdefghijklmnopqrstuvwxyz_', min_size=1, max_size=20),
            values=st.one_of(
                st.text(min_size=0, max_size=50),
                st.integers(min_value=0, max_value=1000)
            ),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_24_audit_trail_direct_creation(
        self, operation, entity_type, entity_id, user_id, changed_fields
    ):
        """
        Property 24: Audit Trail Creation - Direct Audit Trail Creation
        
        **Validates: Requirements 8.4**
        
        For any data update operation (create, modify, delete), calling _create_audit_trail
        should create an audit record with all required fields.
        """
        with patch('common.dynamodb_access.dynamodb') as mock_dynamodb:
            # Setup mock DynamoDB table
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            
            # Track put_item calls
            put_item_calls = []
            def track_put_item(Item):
                put_item_calls.append(Item)
                return {'ResponseMetadata': {'HTTPStatusCode': 200}}
            
            mock_table.put_item.side_effect = track_put_item
            
            # Create audit trail directly
            db = DynamoDBAccess()
            result = db._create_audit_trail(
                entity_type=entity_type,
                entity_id=entity_id,
                operation=operation,
                user_id=user_id,
                changed_fields=changed_fields
            )
            
            # Property: Operation should succeed
            assert result is True, "Audit trail creation should succeed"
            
            # Property: Exactly one audit record should be created
            assert len(put_item_calls) == 1, "Exactly one audit record should be created"
            
            audit_record = put_item_calls[0]
            
            # Property: Audit record should contain operation type
            assert 'operation' in audit_record, "Audit record must contain operation type"
            assert audit_record['operation'] == operation, f"Operation should be '{operation}'"
            assert audit_record['operation'] in ['create', 'update', 'delete'], "Operation must be create, update, or delete"
            
            # Property: Audit record should contain timestamp
            assert 'timestamp' in audit_record, "Audit record must contain timestamp"
            assert audit_record['timestamp'] is not None, "Timestamp should not be None"
            # Verify timestamp is valid and recent
            try:
                timestamp = datetime.fromisoformat(audit_record['timestamp'])
                # Timestamp should be within the last minute (test execution time)
                time_diff = (datetime.utcnow() - timestamp).total_seconds()
                assert time_diff < 60, "Timestamp should be recent (within last minute)"
            except (ValueError, TypeError):
                pytest.fail("Timestamp should be a valid ISO format datetime string")
            
            # Property: Audit record should contain user_id
            assert 'user_id' in audit_record, "Audit record must contain user_id"
            assert audit_record['user_id'] == user_id, "User ID should match the provided user_id"
            
            # Property: Audit record should contain changed_fields
            assert 'changed_fields' in audit_record, "Audit record must contain changed_fields"
            assert isinstance(audit_record['changed_fields'], dict), "Changed fields should be a dictionary"
            assert audit_record['changed_fields'] == changed_fields, "Changed fields should match provided data"
            
            # Property: Audit record should contain entity information
            assert 'audited_entity_type' in audit_record, "Audit record must contain entity type"
            assert audit_record['audited_entity_type'] == entity_type, "Entity type should match"
            assert 'audited_entity_id' in audit_record, "Audit record must contain entity ID"
            assert audit_record['audited_entity_id'] == entity_id, "Entity ID should match"
            
            # Property: Audit record should have proper DynamoDB keys
            assert 'PK' in audit_record, "Audit record must have partition key"
            assert audit_record['PK'].startswith('AUDIT#'), "Partition key should start with 'AUDIT#'"
            assert 'SK' in audit_record, "Audit record must have sort key"
            assert audit_record['SK'].startswith('AUDIT#'), "Sort key should start with 'AUDIT#'"
            
            # Property: Audit record should have entity_type field
            assert 'entity_type' in audit_record, "Audit record must have entity_type field"
            assert audit_record['entity_type'] == 'AuditTrail', "entity_type should be 'AuditTrail'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
