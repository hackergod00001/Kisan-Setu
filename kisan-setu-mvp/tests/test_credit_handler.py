"""
Integration tests for Credit Lambda handler.

Tests the Lambda handler function that wraps the CreditEngine.
"""

import pytest
import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
import sys
import os

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from credit.credit import handler, CreditEngine


@pytest.fixture
def lambda_event():
    """Create a sample Lambda event."""
    return {
        'body': json.dumps({
            'farmer_id': 'FARMER#123'
        })
    }


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context."""
    context = Mock()
    context.function_name = 'credit-calculator'
    context.memory_limit_in_mb = 128
    context.invoked_function_arn = 'arn:aws:lambda:ap-south-1:123456789012:function:credit-calculator'
    return context


@pytest.fixture
def sample_transactions():
    """Create sample transaction data."""
    base_date = datetime.utcnow()
    return [
        {
            'PK': 'FARMER#123',
            'SK': f'TXN#{(base_date - timedelta(days=90)).isoformat()}',
            'quantity': 500.0,
            'moisture': 12.0,
            'quality_grade': 'A',
            'price': 25000.0,
            'crop_type': 'onion',
            'timestamp': (base_date - timedelta(days=90)).isoformat(),
            'ledger_image_url': 's3://bucket/image1.jpg',
            'status': 'success',
            'payment_status': 'timely'
        },
        {
            'PK': 'FARMER#123',
            'SK': f'TXN#{(base_date - timedelta(days=60)).isoformat()}',
            'quantity': 600.0,
            'moisture': 14.0,
            'quality_grade': 'A',
            'price': 30000.0,
            'crop_type': 'onion',
            'timestamp': (base_date - timedelta(days=60)).isoformat(),
            'ledger_image_url': 's3://bucket/image2.jpg',
            'status': 'success',
            'payment_status': 'timely'
        }
    ]


class TestCreditHandler:
    """Test suite for Lambda handler function."""
    
    @patch('credit.credit.table')
    def test_handler_success(self, mock_table, lambda_event, lambda_context, sample_transactions):
        """Test successful credit score calculation."""
        mock_table.query.return_value = {'Items': sample_transactions}
        mock_table.put_item.return_value = {}
        
        response = handler(lambda_event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'farmer_id' in body
        assert 'total_score' in body
        assert 'rating' in body
        assert 'breakdown' in body
        assert body['farmer_id'] == 'FARMER#123'
        assert 0 <= body['total_score'] <= 100
    
    @patch('credit.credit.table')
    def test_handler_missing_farmer_id(self, mock_table, lambda_context):
        """Test handler with missing farmer_id."""
        event = {'body': json.dumps({})}
        
        response = handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
    
    @patch('credit.credit.table')
    def test_handler_breakdown_structure(self, mock_table, lambda_event, lambda_context, sample_transactions):
        """Test that breakdown contains all required components."""
        mock_table.query.return_value = {'Items': sample_transactions}
        mock_table.put_item.return_value = {}
        
        response = handler(lambda_event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        breakdown = body['breakdown']
        
        assert 'supply_consistency' in breakdown
        assert 'quality_metrics' in breakdown
        assert 'transaction_history' in breakdown
        assert 'financial_behavior' in breakdown
        assert 'operational_transparency' in breakdown
        
        # Verify component ranges
        assert 0 <= breakdown['supply_consistency'] <= 30
        assert 0 <= breakdown['quality_metrics'] <= 25
        assert 0 <= breakdown['transaction_history'] <= 20
        assert 0 <= breakdown['financial_behavior'] <= 15
        assert 0 <= breakdown['operational_transparency'] <= 10
    
    @patch('credit.credit.table')
    def test_handler_components_sum_to_total(self, mock_table, lambda_event, lambda_context, sample_transactions):
        """Test that component scores sum to total score."""
        mock_table.query.return_value = {'Items': sample_transactions}
        mock_table.put_item.return_value = {}
        
        response = handler(lambda_event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        component_sum = (
            body['breakdown']['supply_consistency'] +
            body['breakdown']['quality_metrics'] +
            body['breakdown']['transaction_history'] +
            body['breakdown']['financial_behavior'] +
            body['breakdown']['operational_transparency']
        )
        
        assert abs(body['total_score'] - component_sum) < 0.01
    
    @patch('credit.credit.table')
    def test_handler_rating_mapping(self, mock_table, lambda_event, lambda_context, sample_transactions):
        """Test that rating is correctly mapped from score."""
        mock_table.query.return_value = {'Items': sample_transactions}
        mock_table.put_item.return_value = {}
        
        response = handler(lambda_event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        score = body['total_score']
        rating = body['rating']
        
        # Verify rating matches score
        if score >= 90:
            assert rating == 'Excellent'
        elif score >= 75:
            assert rating == 'Good'
        elif score >= 60:
            assert rating == 'Fair'
        elif score >= 40:
            assert rating == 'Poor'
        else:
            assert rating == 'Very Poor'
    
    @patch('credit.credit.table')
    def test_handler_error_handling(self, mock_table, lambda_event, lambda_context):
        """Test handler gracefully handles DynamoDB errors."""
        # CreditEngine catches DynamoDB errors and returns empty transaction list
        # This results in a score of 0, which is valid behavior
        mock_table.query.side_effect = Exception('DynamoDB error')
        mock_table.put_item.return_value = {}
        
        response = handler(lambda_event, lambda_context)
        
        # Should return 200 with score of 0 (no transactions)
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['total_score'] == 0.0
    
    @patch('credit.credit.table')
    def test_handler_cors_headers(self, mock_table, lambda_event, lambda_context, sample_transactions):
        """Test that CORS headers are included in response."""
        mock_table.query.return_value = {'Items': sample_transactions}
        mock_table.put_item.return_value = {}
        
        response = handler(lambda_event, lambda_context)
        
        assert 'headers' in response
        assert 'Access-Control-Allow-Origin' in response['headers']
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
        assert response['headers']['Content-Type'] == 'application/json'
