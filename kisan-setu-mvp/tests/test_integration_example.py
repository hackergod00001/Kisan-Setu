"""
Example integration tests for Kisan-Setu.

These tests demonstrate how to write integration tests that use LocalStack
or real AWS services for testing the complete system.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

import pytest
import boto3
from datetime import datetime, date
from decimal import Decimal

from integration_config import (
    TestEnvironment,
    setup_dynamodb_table,
    cleanup_dynamodb_table,
    skip_if_no_aws
)
from test_data.loader import (
    get_all_farmers,
    get_all_transactions,
    load_test_fixture
)


# ============================================================================
# Helper Functions
# ============================================================================

def convert_floats_to_decimal(obj):
    """
    Recursively convert all float values to Decimal for DynamoDB compatibility.
    
    Args:
        obj: Object to convert (dict, list, or primitive)
    
    Returns: Object with floats converted to Decimal
    """
    if isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_floats_to_decimal(value) for key, value in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj


# ============================================================================
# Integration Test Fixtures
# ============================================================================

@pytest.fixture(scope='module')
def test_env():
    """Get test environment configuration."""
    return TestEnvironment.from_env()


@pytest.fixture(scope='module')
def dynamodb_client(test_env):
    """Create DynamoDB client for integration tests."""
    config = test_env.get_dynamodb_config()
    client = boto3.client('dynamodb', **config)
    
    # Setup table
    setup_dynamodb_table(client, test_env.dynamodb_config.table_name)
    
    yield client
    
    # Cleanup table
    cleanup_dynamodb_table(client, test_env.dynamodb_config.table_name)


@pytest.fixture(scope='module')
def dynamodb_resource(test_env):
    """Create DynamoDB resource for integration tests."""
    config = test_env.get_dynamodb_config()
    return boto3.resource('dynamodb', **config)


@pytest.fixture
def test_table(dynamodb_resource, test_env):
    """Get DynamoDB table for testing."""
    return dynamodb_resource.Table(test_env.dynamodb_config.table_name)


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
@skip_if_no_aws()
class TestDynamoDBIntegration:
    """Integration tests for DynamoDB operations."""
    
    def test_create_farmer(self, test_table):
        """Test creating a farmer in DynamoDB."""
        farmer_data = get_all_farmers()[0]
        
        # Store farmer in DynamoDB (convert floats to Decimal)
        item = convert_floats_to_decimal({
            'PK': f"FARMER#{farmer_data['farmer_id']}",
            'SK': 'METADATA',
            'name': farmer_data['name'],
            'phone': farmer_data['phone'],
            'fpo_id': farmer_data['fpo_id'],
            'gps_coords': farmer_data['gps_coords'],
            'preferred_language': farmer_data['preferred_language'],
            'join_date': farmer_data['join_date']
        })
        test_table.put_item(Item=item)
        
        # Retrieve farmer
        response = test_table.get_item(
            Key={
                'PK': f"FARMER#{farmer_data['farmer_id']}",
                'SK': 'METADATA'
            }
        )
        
        assert 'Item' in response
        assert response['Item']['name'] == farmer_data['name']
        assert response['Item']['phone'] == farmer_data['phone']
    
    def test_create_transaction(self, test_table):
        """Test creating a transaction in DynamoDB."""
        transaction_data = get_all_transactions()[0]
        
        # Store transaction
        test_table.put_item(
            Item={
                'PK': f"FARMER#{transaction_data['farmer_id']}",
                'SK': f"TXN#{transaction_data['timestamp']}",
                'transaction_id': transaction_data['transaction_id'],
                'fpo_id': transaction_data['fpo_id'],
                'quantity': str(transaction_data['quantity']),
                'crop_type': transaction_data['crop_type'],
                'quality_grade': transaction_data['quality_grade'],
                'moisture': str(transaction_data['moisture']),
                'price': str(transaction_data['price']),
                'timestamp': transaction_data['timestamp'],
                'sync_status': transaction_data['sync_status']
            }
        )
        
        # Retrieve transaction
        response = test_table.get_item(
            Key={
                'PK': f"FARMER#{transaction_data['farmer_id']}",
                'SK': f"TXN#{transaction_data['timestamp']}"
            }
        )
        
        assert 'Item' in response
        assert response['Item']['transaction_id'] == transaction_data['transaction_id']
        assert response['Item']['crop_type'] == transaction_data['crop_type']
    
    def test_query_farmer_transactions(self, test_table):
        """Test querying all transactions for a farmer."""
        # Load test data
        transactions = get_all_transactions()
        farmer_id = transactions[0]['farmer_id']
        
        # Store multiple transactions
        for txn in transactions[:3]:
            if txn['farmer_id'] == farmer_id:
                test_table.put_item(
                    Item={
                        'PK': f"FARMER#{txn['farmer_id']}",
                        'SK': f"TXN#{txn['timestamp']}",
                        'transaction_id': txn['transaction_id'],
                        'quantity': str(txn['quantity']),
                        'crop_type': txn['crop_type'],
                        'timestamp': txn['timestamp']
                    }
                )
        
        # Query transactions
        response = test_table.query(
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
            ExpressionAttributeValues={
                ':pk': f"FARMER#{farmer_id}",
                ':sk': 'TXN#'
            }
        )
        
        assert 'Items' in response
        assert len(response['Items']) >= 1
    
    def test_gsi_query_by_fpo(self, test_table):
        """Test querying transactions by FPO using GSI."""
        # Load test data
        transactions = get_all_transactions()
        fpo_id = transactions[0]['fpo_id']
        
        # Store transactions
        for txn in transactions[:2]:
            test_table.put_item(
                Item={
                    'PK': f"FARMER#{txn['farmer_id']}",
                    'SK': f"TXN#{txn['timestamp']}",
                    'transaction_id': txn['transaction_id'],
                    'fpo_id': txn['fpo_id'],
                    'timestamp': txn['timestamp']
                }
            )
        
        # Query using GSI2 (fpo_id + timestamp)
        response = test_table.query(
            IndexName='GSI2',
            KeyConditionExpression='fpo_id = :fpo_id',
            ExpressionAttributeValues={
                ':fpo_id': fpo_id
            }
        )
        
        assert 'Items' in response
        assert len(response['Items']) >= 1


@pytest.mark.integration
@skip_if_no_aws()
class TestDataAccessIntegration:
    """Integration tests for data access patterns."""
    
    def test_farmer_lifecycle(self, test_table):
        """Test complete farmer lifecycle: create, read, update, delete."""
        farmer_id = "integration_test_farmer_001"
        
        # Create farmer
        test_table.put_item(
            Item={
                'PK': f"FARMER#{farmer_id}",
                'SK': 'METADATA',
                'name': 'Integration Test Farmer',
                'phone': '+919999999999',
                'fpo_id': 'test_fpo_001',
                'gps_coords': [Decimal('28.6139'), Decimal('77.2090')],
                'preferred_language': 'hi-IN',
                'join_date': '2024-01-01'
            }
        )
        
        # Read farmer
        response = test_table.get_item(
            Key={'PK': f"FARMER#{farmer_id}", 'SK': 'METADATA'}
        )
        assert 'Item' in response
        assert response['Item']['name'] == 'Integration Test Farmer'
        
        # Update farmer
        test_table.update_item(
            Key={'PK': f"FARMER#{farmer_id}", 'SK': 'METADATA'},
            UpdateExpression='SET #name = :name',
            ExpressionAttributeNames={'#name': 'name'},
            ExpressionAttributeValues={':name': 'Updated Farmer Name'}
        )
        
        # Verify update
        response = test_table.get_item(
            Key={'PK': f"FARMER#{farmer_id}", 'SK': 'METADATA'}
        )
        assert response['Item']['name'] == 'Updated Farmer Name'
        
        # Delete farmer
        test_table.delete_item(
            Key={'PK': f"FARMER#{farmer_id}", 'SK': 'METADATA'}
        )
        
        # Verify deletion
        response = test_table.get_item(
            Key={'PK': f"FARMER#{farmer_id}", 'SK': 'METADATA'}
        )
        assert 'Item' not in response
    
    def test_transaction_history(self, test_table):
        """Test storing and retrieving transaction history."""
        farmer_id = "integration_test_farmer_002"
        
        # Create multiple transactions
        timestamps = [
            '2024-01-15T10:00:00Z',
            '2024-01-20T14:00:00Z',
            '2024-01-25T16:00:00Z'
        ]
        
        for i, timestamp in enumerate(timestamps):
            test_table.put_item(
                Item={
                    'PK': f"FARMER#{farmer_id}",
                    'SK': f"TXN#{timestamp}",
                    'transaction_id': f"txn_{i}",
                    'quantity': str(100 + i * 10),
                    'crop_type': 'onion',
                    'timestamp': timestamp
                }
            )
        
        # Query all transactions
        response = test_table.query(
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
            ExpressionAttributeValues={
                ':pk': f"FARMER#{farmer_id}",
                ':sk': 'TXN#'
            }
        )
        
        assert len(response['Items']) == 3
        
        # Verify chronological order
        items = sorted(response['Items'], key=lambda x: x['SK'])
        assert items[0]['quantity'] == '100'
        assert items[1]['quantity'] == '110'
        assert items[2]['quantity'] == '120'


@pytest.mark.integration
@pytest.mark.slow
@skip_if_no_aws()
class TestEndToEndIntegration:
    """End-to-end integration tests."""
    
    def test_complete_farmer_workflow(self, test_table):
        """Test complete workflow: farmer creation, transactions, credit score."""
        farmer_id = "e2e_test_farmer_001"
        
        # Step 1: Create farmer
        test_table.put_item(
            Item={
                'PK': f"FARMER#{farmer_id}",
                'SK': 'METADATA',
                'name': 'E2E Test Farmer',
                'phone': '+919888888888',
                'fpo_id': 'test_fpo_001',
                'gps_coords': [Decimal('28.6139'), Decimal('77.2090')],
                'preferred_language': 'hi-IN',
                'join_date': '2024-01-01'
            }
        )
        
        # Step 2: Add transactions
        for i in range(5):
            test_table.put_item(
                Item={
                    'PK': f"FARMER#{farmer_id}",
                    'SK': f"TXN#2024-01-{15+i:02d}T10:00:00Z",
                    'transaction_id': f"e2e_txn_{i}",
                    'quantity': str(100 + i * 20),
                    'crop_type': 'onion',
                    'quality_grade': 'A',
                    'moisture': str(12.0 + i * 0.5),
                    'price': str(5000 + i * 1000),
                    'timestamp': f"2024-01-{15+i:02d}T10:00:00Z"
                }
            )
        
        # Step 3: Add credit score
        test_table.put_item(
            Item={
                'PK': f"FARMER#{farmer_id}",
                'SK': 'SCORE#2024-01-30',
                'total_score': '85.0',
                'supply_consistency': '28.0',
                'quality_metrics': '23.0',
                'transaction_history': '18.0',
                'financial_behavior': '12.0',
                'operational_transparency': '4.0',
                'calculation_date': '2024-01-30T12:00:00Z'
            }
        )
        
        # Verify complete data
        # Check farmer exists
        farmer_response = test_table.get_item(
            Key={'PK': f"FARMER#{farmer_id}", 'SK': 'METADATA'}
        )
        assert 'Item' in farmer_response
        
        # Check transactions exist
        txn_response = test_table.query(
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
            ExpressionAttributeValues={
                ':pk': f"FARMER#{farmer_id}",
                ':sk': 'TXN#'
            }
        )
        assert len(txn_response['Items']) == 5
        
        # Check credit score exists
        score_response = test_table.get_item(
            Key={'PK': f"FARMER#{farmer_id}", 'SK': 'SCORE#2024-01-30'}
        )
        assert 'Item' in score_response
        assert score_response['Item']['total_score'] == '85.0'


# ============================================================================
# Test Execution
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'integration'])
