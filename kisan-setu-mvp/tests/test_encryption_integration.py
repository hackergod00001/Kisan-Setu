"""
Unit tests for encryption integration in DynamoDBAccess.

Verifies that:
- encrypt_sensitive_fields() is called before DynamoDB writes
- decrypt_sensitive_fields() is called after DynamoDB reads
- Backward compatibility: plaintext data is handled gracefully when encryption is unavailable
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

import pytest
from datetime import datetime, date
from unittest.mock import Mock, patch, MagicMock, call
from decimal import Decimal

from common.models import (
    Farmer, Transaction, ReliabilityScore, SyncStatus
)
from common.dynamodb_access import DynamoDBAccess


@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table."""
    with patch('common.dynamodb_access.dynamodb') as mock_dynamodb:
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        yield mock_table


class TestEncryptionOnWrite:
    """Tests that sensitive fields are encrypted before DynamoDB writes."""

    @patch('common.dynamodb_access.encrypt_sensitive_fields')
    def test_create_farmer_calls_encrypt(self, mock_encrypt, mock_dynamodb_table):
        """Verify create_farmer encrypts the phone field before writing."""
        mock_encrypt.side_effect = lambda data, fields: {
            **data, 'phone': 'ENCRYPTED_PHONE'
        } if 'phone' in fields else data
        mock_dynamodb_table.put_item.return_value = {}

        db = DynamoDBAccess()
        farmer = Farmer(
            farmer_id='F001', name='Test', phone='+919876543210',
            fpo_id='FPO001', gps_coords=(20.0, 78.0),
            preferred_language='hi', join_date=date(2024, 1, 1)
        )
        result = db.create_farmer(farmer, 'admin')

        assert result is True
        mock_encrypt.assert_called_once()
        # Verify the item written to DynamoDB has encrypted phone
        written_item = mock_dynamodb_table.put_item.call_args_list[0][1]['Item']
        assert written_item['phone'] == 'ENCRYPTED_PHONE'

    @patch('common.dynamodb_access.encrypt_sensitive_fields')
    def test_create_transaction_calls_encrypt(self, mock_encrypt, mock_dynamodb_table):
        """Verify create_transaction encrypts the price field before writing."""
        mock_encrypt.side_effect = lambda data, fields: {
            **data, 'price': 'ENCRYPTED_PRICE'
        } if 'price' in fields else data
        mock_dynamodb_table.put_item.return_value = {}

        db = DynamoDBAccess()
        txn = Transaction(
            transaction_id='T001', farmer_id='F001', fpo_id='FPO001',
            quantity=100.0, crop_type='wheat', quality_grade='A',
            moisture=12.0, price=Decimal('1500.00'),
            timestamp=datetime(2024, 6, 15, 10, 0, 0),
            sync_status=SyncStatus.SYNCED
        )
        result = db.create_transaction(txn, 'admin')

        assert result is True
        mock_encrypt.assert_called_once()
        written_item = mock_dynamodb_table.put_item.call_args_list[0][1]['Item']
        assert written_item['price'] == 'ENCRYPTED_PRICE'

    @patch('common.dynamodb_access.encrypt_sensitive_fields')
    def test_save_credit_score_calls_encrypt(self, mock_encrypt, mock_dynamodb_table):
        """Verify save_credit_score encrypts financial_behavior before writing."""
        mock_encrypt.side_effect = lambda data, fields: {
            **data, 'financial_behavior': 'ENCRYPTED_FB'
        } if 'financial_behavior' in fields else data
        mock_dynamodb_table.put_item.return_value = {}

        db = DynamoDBAccess()
        score = ReliabilityScore(
            farmer_id='F001', total_score=75.0,
            supply_consistency=20.0, quality_metrics=18.0,
            transaction_history=15.0, financial_behavior=12.0,
            operational_transparency=10.0,
            calculation_date=datetime(2024, 6, 15), score_change=2.0
        )
        result = db.save_credit_score(score, 'admin')

        assert result is True
        mock_encrypt.assert_called_once()
        written_item = mock_dynamodb_table.put_item.call_args_list[0][1]['Item']
        assert written_item['financial_behavior'] == 'ENCRYPTED_FB'


class TestDecryptionOnRead:
    """Tests that sensitive fields are decrypted after DynamoDB reads."""

    @patch('common.dynamodb_access.decrypt_sensitive_fields')
    def test_get_farmer_calls_decrypt(self, mock_decrypt, mock_dynamodb_table):
        """Verify get_farmer decrypts the phone field after reading."""
        mock_dynamodb_table.get_item.return_value = {
            'Item': {
                'farmer_id': 'F001', 'name': 'Test',
                'phone': 'ENCRYPTED_PHONE', 'fpo_id': 'FPO001',
                'gps_latitude': Decimal('20.0'), 'gps_longitude': Decimal('78.0'),
                'preferred_language': 'hi', 'join_date': '2024-01-01'
            }
        }
        mock_decrypt.side_effect = lambda data, fields: {
            **data, 'phone': '+919876543210'
        } if 'phone' in fields else data

        db = DynamoDBAccess()
        farmer = db.get_farmer('F001')

        assert farmer is not None
        assert farmer.phone == '+919876543210'
        mock_decrypt.assert_called_once()

    @patch('common.dynamodb_access.decrypt_sensitive_fields')
    def test_get_transactions_calls_decrypt(self, mock_decrypt, mock_dynamodb_table):
        """Verify get_transactions decrypts the price field after reading."""
        mock_dynamodb_table.query.return_value = {
            'Items': [{
                'transaction_id': 'T001', 'farmer_id': 'F001',
                'fpo_id': 'FPO001', 'quantity': Decimal('100'),
                'crop_type': 'wheat', 'quality_grade': 'A',
                'moisture': Decimal('12.0'), 'price': 'ENCRYPTED_PRICE',
                'timestamp': '2024-06-15T10:00:00',
                'sync_status': 'synced'
            }]
        }
        mock_decrypt.side_effect = lambda data, fields: {
            **data, 'price': Decimal('1500.00')
        } if 'price' in fields else data

        db = DynamoDBAccess()
        txns = db.get_transactions('F001')

        assert len(txns) == 1
        assert txns[0].price == 1500.00
        mock_decrypt.assert_called_once()

    @patch('common.dynamodb_access.decrypt_sensitive_fields')
    def test_get_credit_score_calls_decrypt(self, mock_decrypt, mock_dynamodb_table):
        """Verify get_credit_score decrypts financial_behavior after reading."""
        mock_dynamodb_table.query.return_value = {
            'Items': [{
                'farmer_id': 'F001', 'total_score': Decimal('75.0'),
                'supply_consistency': Decimal('20.0'),
                'quality_metrics': Decimal('18.0'),
                'transaction_history': Decimal('15.0'),
                'financial_behavior': 'ENCRYPTED_FB',
                'operational_transparency': Decimal('10.0'),
                'calculation_date': '2024-06-15T00:00:00',
                'score_change': Decimal('2.0')
            }]
        }
        mock_decrypt.side_effect = lambda data, fields: {
            **data, 'financial_behavior': Decimal('12.0')
        } if 'financial_behavior' in fields else data

        db = DynamoDBAccess()
        score = db.get_credit_score('F001')

        assert score is not None
        assert score.financial_behavior == 12.0
        mock_decrypt.assert_called_once()


class TestBackwardCompatibility:
    """Tests that plaintext (legacy) data is handled gracefully."""

    @patch('common.dynamodb_access.encrypt_sensitive_fields', side_effect=ValueError("KMS_KEY_ID not set"))
    def test_create_farmer_works_without_kms(self, mock_encrypt, mock_dynamodb_table):
        """When KMS is unavailable, farmer is still created with plaintext data."""
        mock_dynamodb_table.put_item.return_value = {}

        db = DynamoDBAccess()
        farmer = Farmer(
            farmer_id='F001', name='Test', phone='+919876543210',
            fpo_id='FPO001', gps_coords=(20.0, 78.0),
            preferred_language='hi', join_date=date(2024, 1, 1)
        )
        result = db.create_farmer(farmer, 'admin')

        assert result is True
        # Data should still be written (plaintext fallback)
        assert mock_dynamodb_table.put_item.called

    @patch('common.dynamodb_access.decrypt_sensitive_fields', side_effect=Exception("Decryption error"))
    def test_get_farmer_works_with_plaintext(self, mock_decrypt, mock_dynamodb_table):
        """When decryption fails, farmer is still returned with raw data."""
        mock_dynamodb_table.get_item.return_value = {
            'Item': {
                'farmer_id': 'F001', 'name': 'Test',
                'phone': '+919876543210', 'fpo_id': 'FPO001',
                'gps_latitude': Decimal('20.0'), 'gps_longitude': Decimal('78.0'),
                'preferred_language': 'hi', 'join_date': '2024-01-01'
            }
        }

        db = DynamoDBAccess()
        farmer = db.get_farmer('F001')

        assert farmer is not None
        assert farmer.phone == '+919876543210'
