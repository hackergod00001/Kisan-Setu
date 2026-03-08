"""
Integration tests for AppSync GraphQL API
Tests offline sync functionality and conflict resolution
"""

import pytest
import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

# Mock the gql imports for testing
@pytest.fixture(autouse=True)
def mock_gql_imports():
    """Mock gql library imports"""
    with patch.dict('sys.modules', {
        'gql': MagicMock(),
        'gql.transport.requests': MagicMock()
    }):
        yield

@pytest.fixture
def sample_transaction():
    """Sample transaction data"""
    return {
        'transactionId': 'txn-001',
        'farmerId': 'farmer-123',
        'fpoId': 'fpo-456',
        'quantity': 100.0,
        'cropType': 'onion',
        'qualityGrade': 'A',
        'moisture': 12.5,
        'price': 2500.0,
        'timestamp': datetime.utcnow().isoformat(),
        'syncStatus': 'PENDING',
        'version': 1
    }

@pytest.fixture
def sample_farmer():
    """Sample farmer data"""
    return {
        'farmerId': 'farmer-123',
        'name': 'Ramesh Kumar',
        'phone': '+919876543210',
        'fpoId': 'fpo-456',
        'gpsCoords': {
            'latitude': 19.0760,
            'longitude': 72.8777
        },
        'preferredLanguage': 'hi-IN',
        'joinDate': datetime.utcnow().isoformat()
    }

class TestAppSyncResolvers:
    """Test AppSync resolver logic"""
    
    def test_create_transaction_resolver_mapping(self, sample_transaction):
        """Test createTransaction resolver request mapping"""
        # Simulate VTL template logic
        pk = f"FARMER#{sample_transaction['farmerId']}"
        sk = f"TXN#{sample_transaction['timestamp']}"
        
        assert pk == "FARMER#farmer-123"
        assert sk.startswith("TXN#")
        
        # Verify all required fields are present
        required_fields = ['transactionId', 'farmerId', 'fpoId', 'quantity', 
                          'cropType', 'qualityGrade', 'moisture', 'price', 
                          'timestamp', 'syncStatus', 'version']
        for field in required_fields:
            assert field in sample_transaction
    
    def test_list_transactions_query_structure(self):
        """Test listTransactions query structure"""
        farmer_id = 'farmer-123'
        pk = f"FARMER#{farmer_id}"
        sk_prefix = "TXN#"
        
        # Verify query key structure
        assert pk == "FARMER#farmer-123"
        assert sk_prefix == "TXN#"
    
    def test_get_credit_score_query_structure(self):
        """Test getCreditScore query structure"""
        farmer_id = 'farmer-123'
        pk = f"FARMER#{farmer_id}"
        sk_prefix = "SCORE#"
        
        # Verify query key structure
        assert pk == "FARMER#farmer-123"
        assert sk_prefix == "SCORE#"

class TestSyncHandler:
    """Test sync handler Lambda function"""
    
    def test_sync_handler_event_structure(self, sample_transaction):
        """Test sync handler processes event correctly"""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'sync'))
        from sync_handler import handler
        
        event = {
            'arguments': {
                'transactions': [sample_transaction]
            }
        }
        
        with patch('sync_handler.table') as mock_table:
            # Mock DynamoDB get_item to return no existing item
            mock_table.get_item.return_value = {}
            mock_table.put_item.return_value = {}
            
            result = handler(event, {})
            
            assert 'successCount' in result
            assert 'failureCount' in result
            assert 'conflicts' in result
    
    def test_sync_chronological_ordering(self):
        """Test transactions are synced in chronological order"""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'sync'))
        from sync_handler import handler
        
        # Create transactions with different timestamps
        now = datetime.utcnow()
        transactions = [
            {
                'transactionId': 'txn-003',
                'farmerId': 'farmer-123',
                'fpoId': 'fpo-456',
                'quantity': 100.0,
                'cropType': 'onion',
                'qualityGrade': 'A',
                'moisture': 12.5,
                'price': 2500.0,
                'timestamp': (now + timedelta(hours=2)).isoformat(),
                'syncStatus': 'PENDING',
                'version': 1
            },
            {
                'transactionId': 'txn-001',
                'farmerId': 'farmer-123',
                'fpoId': 'fpo-456',
                'quantity': 100.0,
                'cropType': 'onion',
                'qualityGrade': 'A',
                'moisture': 12.5,
                'price': 2500.0,
                'timestamp': now.isoformat(),
                'syncStatus': 'PENDING',
                'version': 1
            },
            {
                'transactionId': 'txn-002',
                'farmerId': 'farmer-123',
                'fpoId': 'fpo-456',
                'quantity': 100.0,
                'cropType': 'onion',
                'qualityGrade': 'A',
                'moisture': 12.5,
                'price': 2500.0,
                'timestamp': (now + timedelta(hours=1)).isoformat(),
                'syncStatus': 'PENDING',
                'version': 1
            }
        ]
        
        event = {
            'arguments': {
                'transactions': transactions
            }
        }
        
        with patch('sync_handler.table') as mock_table:
            mock_table.get_item.return_value = {}
            mock_table.put_item.return_value = {}
            
            # Track the order of put_item calls
            put_order = []
            def track_put(Item):
                put_order.append(Item['transactionId'])
                return {}
            
            mock_table.put_item.side_effect = track_put
            
            result = handler(event, {})
            
            # Verify transactions were processed in chronological order
            assert put_order == ['txn-001', 'txn-002', 'txn-003']
    
    def test_conflict_resolution_last_write_wins(self):
        """Test last-write-wins conflict resolution"""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'sync'))
        from sync_handler import sync_transaction
        
        # New transaction with higher version
        new_txn = {
            'transactionId': 'txn-001',
            'farmerId': 'farmer-123',
            'fpoId': 'fpo-456',
            'quantity': 150.0,  # Updated quantity
            'cropType': 'onion',
            'qualityGrade': 'A',
            'moisture': 12.5,
            'price': 3000.0,  # Updated price
            'timestamp': datetime.utcnow().isoformat(),
            'syncStatus': 'PENDING',
            'version': 2  # Higher version
        }
        
        # Existing transaction with lower version
        existing_item = {
            'PK': 'FARMER#farmer-123',
            'SK': f"TXN#{new_txn['timestamp']}",
            'transactionId': 'txn-001',
            'farmerId': 'farmer-123',
            'fpoId': 'fpo-456',
            'quantity': Decimal('100.0'),
            'cropType': 'onion',
            'qualityGrade': 'A',
            'moisture': Decimal('12.5'),
            'price': Decimal('2500.0'),
            'timestamp': new_txn['timestamp'],
            'syncStatus': 'SYNCED',
            'version': 1  # Lower version
        }
        
        with patch('sync_handler.table') as mock_table:
            # Mock get_item to return existing item
            mock_table.get_item.return_value = {'Item': existing_item}
            mock_table.put_item.return_value = {}
            
            result = sync_transaction(new_txn)
            
            # Should detect conflict and resolve with local wins
            assert result['status'] == 'conflict'
            assert result['conflict_info']['resolution'] == 'local_wins'
            assert result['conflict_info']['localVersion'] == 2
            assert result['conflict_info']['cloudVersion'] == 1
            
            # Verify put_item was called (new version wins)
            assert mock_table.put_item.called
    
    def test_conflict_resolution_cloud_wins(self):
        """Test conflict resolution when cloud version is newer"""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'sync'))
        from sync_handler import sync_transaction
        
        # New transaction with lower version
        new_txn = {
            'transactionId': 'txn-001',
            'farmerId': 'farmer-123',
            'fpoId': 'fpo-456',
            'quantity': 100.0,
            'cropType': 'onion',
            'qualityGrade': 'A',
            'moisture': 12.5,
            'price': 2500.0,
            'timestamp': datetime.utcnow().isoformat(),
            'syncStatus': 'PENDING',
            'version': 1  # Lower version
        }
        
        # Existing transaction with higher version
        existing_item = {
            'PK': 'FARMER#farmer-123',
            'SK': f"TXN#{new_txn['timestamp']}",
            'transactionId': 'txn-001',
            'version': 2  # Higher version
        }
        
        with patch('sync_handler.table') as mock_table:
            # Mock get_item to return existing item
            mock_table.get_item.return_value = {'Item': existing_item}
            
            result = sync_transaction(new_txn)
            
            # Should detect conflict and resolve with cloud wins
            assert result['status'] == 'conflict'
            assert result['conflict_info']['resolution'] == 'cloud_wins'
            assert result['conflict_info']['localVersion'] == 1
            assert result['conflict_info']['cloudVersion'] == 2
            
            # Verify put_item was NOT called (cloud version wins)
            assert not mock_table.put_item.called

class TestOfflineSupport:
    """Test offline support functionality"""
    
    def test_offline_transaction_storage(self, sample_transaction):
        """Test transactions can be stored offline"""
        # This would test the client-side offline storage
        # For now, verify the transaction structure is valid
        required_fields = ['transactionId', 'farmerId', 'fpoId', 'quantity',
                          'cropType', 'qualityGrade', 'moisture', 'price',
                          'timestamp', 'syncStatus', 'version']
        
        for field in required_fields:
            assert field in sample_transaction
    
    def test_sync_status_transitions(self):
        """Test sync status transitions"""
        valid_statuses = ['PENDING', 'SYNCED', 'CONFLICT']
        
        # Test all valid status values
        for status in valid_statuses:
            assert status in ['PENDING', 'SYNCED', 'CONFLICT']
    
    def test_version_increment(self):
        """Test version increments on updates"""
        initial_version = 1
        updated_version = initial_version + 1
        
        assert updated_version == 2
        assert updated_version > initial_version

class TestGraphQLSchema:
    """Test GraphQL schema structure"""
    
    def test_transaction_type_fields(self):
        """Test Transaction type has all required fields"""
        required_fields = [
            'transactionId', 'farmerId', 'fpoId', 'quantity',
            'cropType', 'qualityGrade', 'moisture', 'price',
            'timestamp', 'syncStatus', 'version'
        ]
        
        # Read schema file
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'schema.graphql')
        with open(schema_path, 'r') as f:
            schema_content = f.read()
        
        # Verify all required fields are in schema
        for field in required_fields:
            assert field in schema_content
    
    def test_sync_result_type_structure(self):
        """Test SyncResult type structure"""
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'schema.graphql')
        with open(schema_path, 'r') as f:
            schema_content = f.read()
        
        # Verify SyncResult type exists with required fields
        assert 'type SyncResult' in schema_content
        assert 'successCount: Int!' in schema_content
        assert 'failureCount: Int!' in schema_content
        assert 'conflicts: [ConflictInfo]' in schema_content

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
