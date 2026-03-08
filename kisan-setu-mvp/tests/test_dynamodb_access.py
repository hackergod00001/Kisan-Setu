"""
Unit tests for DynamoDB access patterns.

Note: These tests use mocked DynamoDB operations to avoid requiring
actual AWS infrastructure during testing.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

import pytest
from datetime import datetime, date
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from common.models import (
    Farmer, FPO, Transaction, ReliabilityScore, NDVIResult, Message,
    MessageType, SyncStatus
)
from common.dynamodb_access import DynamoDBAccess


@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table."""
    with patch('common.dynamodb_access.dynamodb') as mock_dynamodb:
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        yield mock_table


class TestFPOOperations:
    """Tests for FPO operations."""
    
    def test_create_fpo(self, mock_dynamodb_table):
        """Test creating an FPO."""
        db = DynamoDBAccess()
        
        fpo = FPO(
            fpo_id="fpo123",
            name="Test FPO",
            location="Delhi",
            manager_contact="+919876543210",
            created_date=date.today(),
            member_count=100
        )
        
        result = db.create_fpo(fpo, "admin123")
        
        assert result is True
        assert mock_dynamodb_table.put_item.call_count == 2  # FPO + audit trail
    
    def test_get_fpo(self, mock_dynamodb_table):
        """Test retrieving an FPO."""
        db = DynamoDBAccess()
        
        mock_dynamodb_table.get_item.return_value = {
            'Item': {
                'fpo_id': 'fpo123',
                'name': 'Test FPO',
                'location': 'Delhi',
                'manager_contact': '+919876543210',
                'created_date': '2024-01-01',
                'member_count': 100
            }
        }
        
        fpo = db.get_fpo("fpo123")
        
        assert fpo is not None
        assert fpo.fpo_id == "fpo123"
        assert fpo.name == "Test FPO"
        assert fpo.member_count == 100


class TestFarmerOperations:
    """Tests for Farmer operations."""
    
    def test_create_farmer(self, mock_dynamodb_table):
        """Test creating a farmer."""
        db = DynamoDBAccess()
        
        farmer = Farmer(
            farmer_id="farmer123",
            name="Ram Kumar",
            phone="+919876543210",
            fpo_id="fpo456",
            gps_coords=(28.6139, 77.2090),
            preferred_language="hi-IN",
            join_date=date.today()
        )
        
        result = db.create_farmer(farmer, "admin123")
        
        assert result is True
        assert mock_dynamodb_table.put_item.call_count == 3  # Farmer + GSI + audit
    
    def test_create_farmer_invalid_gps(self, mock_dynamodb_table):
        """Test creating farmer with invalid GPS coordinates."""
        db = DynamoDBAccess()
        
        farmer = Farmer(
            farmer_id="farmer123",
            name="Ram Kumar",
            phone="+919876543210",
            fpo_id="fpo456",
            gps_coords=(91.0, 77.2090),  # Invalid latitude
            preferred_language="hi-IN",
            join_date=date.today()
        )
        
        result = db.create_farmer(farmer, "admin123")
        
        assert result is False
        assert mock_dynamodb_table.put_item.call_count == 0
    
    def test_create_farmer_invalid_phone(self, mock_dynamodb_table):
        """Test creating farmer with invalid phone number."""
        db = DynamoDBAccess()
        
        farmer = Farmer(
            farmer_id="farmer123",
            name="Ram Kumar",
            phone="1234567890",  # Invalid phone
            fpo_id="fpo456",
            gps_coords=(28.6139, 77.2090),
            preferred_language="hi-IN",
            join_date=date.today()
        )
        
        result = db.create_farmer(farmer, "admin123")
        
        assert result is False
        assert mock_dynamodb_table.put_item.call_count == 0
    
    def test_get_farmer(self, mock_dynamodb_table):
        """Test retrieving a farmer."""
        db = DynamoDBAccess()
        
        mock_dynamodb_table.get_item.return_value = {
            'Item': {
                'farmer_id': 'farmer123',
                'name': 'Ram Kumar',
                'phone': '+919876543210',
                'fpo_id': 'fpo456',
                'gps_latitude': Decimal('28.6139'),
                'gps_longitude': Decimal('77.2090'),
                'preferred_language': 'hi-IN',
                'join_date': '2024-01-01'
            }
        }
        
        farmer = db.get_farmer("farmer123")
        
        assert farmer is not None
        assert farmer.farmer_id == "farmer123"
        assert farmer.name == "Ram Kumar"
        assert farmer.gps_coords == (28.6139, 77.2090)


class TestTransactionOperations:
    """Tests for Transaction operations."""
    
    def test_create_transaction(self, mock_dynamodb_table):
        """Test creating a transaction."""
        db = DynamoDBAccess()
        
        txn = Transaction(
            transaction_id="txn123",
            farmer_id="farmer456",
            fpo_id="fpo789",
            quantity=100.0,
            crop_type="wheat",
            quality_grade="A",
            moisture=12.0,
            price=5000.0,
            timestamp=datetime.now(),
            sync_status=SyncStatus.SYNCED
        )
        
        result = db.create_transaction(txn, "admin123")
        
        assert result is True
        assert mock_dynamodb_table.put_item.call_count == 3  # Transaction + GSI + audit
    
    def test_get_transactions(self, mock_dynamodb_table):
        """Test retrieving transactions."""
        db = DynamoDBAccess()
        
        mock_dynamodb_table.query.return_value = {
            'Items': [
                {
                    'transaction_id': 'txn123',
                    'farmer_id': 'farmer456',
                    'fpo_id': 'fpo789',
                    'quantity': Decimal('100.0'),
                    'crop_type': 'wheat',
                    'quality_grade': 'A',
                    'moisture': Decimal('12.0'),
                    'price': Decimal('5000.0'),
                    'timestamp': '2024-01-01T10:00:00',
                    'sync_status': 'synced'
                }
            ]
        }
        
        transactions = db.get_transactions("farmer456")
        
        assert len(transactions) == 1
        assert transactions[0].transaction_id == "txn123"
        assert transactions[0].quantity == 100.0


class TestCreditScoreOperations:
    """Tests for credit score operations."""
    
    def test_save_credit_score(self, mock_dynamodb_table):
        """Test saving a credit score."""
        db = DynamoDBAccess()
        
        score = ReliabilityScore(
            farmer_id="farmer123",
            total_score=75.0,
            supply_consistency=25.0,
            quality_metrics=20.0,
            transaction_history=15.0,
            financial_behavior=10.0,
            operational_transparency=5.0,
            calculation_date=datetime.now(),
            score_change=5.0
        )
        
        result = db.save_credit_score(score, "system")
        
        assert result is True
        assert mock_dynamodb_table.put_item.call_count == 2  # Score + audit
    
    def test_get_credit_score(self, mock_dynamodb_table):
        """Test retrieving credit score."""
        db = DynamoDBAccess()
        
        mock_dynamodb_table.query.return_value = {
            'Items': [
                {
                    'farmer_id': 'farmer123',
                    'total_score': Decimal('75.0'),
                    'supply_consistency': Decimal('25.0'),
                    'quality_metrics': Decimal('20.0'),
                    'transaction_history': Decimal('15.0'),
                    'financial_behavior': Decimal('10.0'),
                    'operational_transparency': Decimal('5.0'),
                    'calculation_date': '2024-01-01T10:00:00',
                    'score_change': Decimal('5.0')
                }
            ]
        }
        
        score = db.get_credit_score("farmer123")
        
        assert score is not None
        assert score.farmer_id == "farmer123"
        assert score.total_score == 75.0


class TestNDVIOperations:
    """Tests for NDVI operations."""
    
    def test_save_ndvi_result(self, mock_dynamodb_table):
        """Test saving NDVI result."""
        db = DynamoDBAccess()
        
        ndvi = NDVIResult(
            field_id="field123",
            gps_coords=(28.6139, 77.2090),
            ndvi_value=0.75,
            timestamp=datetime.now(),
            confidence=0.92,
            satellite_image_url="s3://bucket/image.tif"
        )
        
        result = db.save_ndvi_result(ndvi, "system")
        
        assert result is True
        assert mock_dynamodb_table.put_item.call_count == 2  # NDVI + audit
    
    def test_save_ndvi_invalid_gps(self, mock_dynamodb_table):
        """Test saving NDVI with invalid GPS."""
        db = DynamoDBAccess()
        
        ndvi = NDVIResult(
            field_id="field123",
            gps_coords=(91.0, 77.2090),  # Invalid
            ndvi_value=0.75,
            timestamp=datetime.now(),
            confidence=0.92,
            satellite_image_url="s3://bucket/image.tif"
        )
        
        result = db.save_ndvi_result(ndvi, "system")
        
        assert result is False
        assert mock_dynamodb_table.put_item.call_count == 0


class TestMessageOperations:
    """Tests for message operations."""
    
    def test_save_message(self, mock_dynamodb_table):
        """Test saving a message."""
        db = DynamoDBAccess()
        
        msg = Message(
            message_id="msg123",
            sender_id="user456",
            message_type=MessageType.TEXT,
            content="Hello",
            timestamp=datetime.now(),
            language="hi-IN"
        )
        
        result = db.save_message(msg)
        
        assert result is True
        assert mock_dynamodb_table.put_item.call_count == 1


class TestAuditTrailOperations:
    """Tests for audit trail operations."""
    
    def test_create_audit_trail(self, mock_dynamodb_table):
        """Test creating audit trail."""
        db = DynamoDBAccess()
        
        result = db._create_audit_trail(
            entity_type="Farmer",
            entity_id="farmer123",
            operation="create",
            user_id="admin123",
            changed_fields={"name": "Ram Kumar"}
        )
        
        assert result is True
        assert mock_dynamodb_table.put_item.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
