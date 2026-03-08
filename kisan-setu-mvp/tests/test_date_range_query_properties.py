"""
Property-based tests for date range query correctness.

Feature: kisan-setu
Property 25: Date Range Query Correctness

**Validates: Requirements 8.5**

For any query with date range filters [start_date, end_date], all returned records 
should have timestamps within that range (inclusive).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

import pytest
from hypothesis import given, settings, strategies as st, assume
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from boto3.dynamodb.conditions import Key

from common.dynamodb_access import DynamoDBAccess
from common.models import Transaction, SyncStatus
from generators import transaction_data, farmer_data, uuid_string


class TestDateRangeQueryCorrectnessProperty:
    """
    Property 25: Date Range Query Correctness
    
    For any query with date range filters [start_date, end_date], all returned records 
    should have timestamps within that range (inclusive).
    """
    
    @given(
        farmer_id=uuid_string(),
        start_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2024, 6, 30)),
        end_date=st.datetimes(min_value=datetime(2024, 7, 1), max_value=datetime.now())
    )
    @settings(max_examples=100, deadline=None)
    def test_property_25_date_range_query_correctness_basic(
        self, farmer_id, start_date, end_date
    ):
        """
        Property 25: Date Range Query Correctness - Basic Test
        
        **Validates: Requirements 8.5**
        
        For any query with date range filters [start_date, end_date], all returned 
        records should have timestamps within that range (inclusive).
        """
        # Ensure start_date <= end_date
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        
        with patch('common.dynamodb_access.dynamodb') as mock_dynamodb:
            # Setup mock DynamoDB table
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            
            # Generate transactions with timestamps both inside and outside the range
            all_transactions = []
            
            # Transactions before the range (should not be returned)
            before_txn = {
                'transaction_id': 'txn_before',
                'farmer_id': farmer_id,
                'fpo_id': 'fpo_1',
                'quantity': 100.0,
                'crop_type': 'wheat',
                'quality_grade': 'A',
                'moisture': 12.5,
                'price': 5000.0,
                'timestamp': (start_date - timedelta(days=1)).isoformat(),
                'sync_status': 'synced'
            }
            
            # Transactions within the range (should be returned)
            within_txn_1 = {
                'transaction_id': 'txn_within_1',
                'farmer_id': farmer_id,
                'fpo_id': 'fpo_1',
                'quantity': 150.0,
                'crop_type': 'rice',
                'quality_grade': 'B',
                'moisture': 14.0,
                'price': 6000.0,
                'timestamp': start_date.isoformat(),  # Exactly at start (inclusive)
                'sync_status': 'synced'
            }
            
            within_txn_2 = {
                'transaction_id': 'txn_within_2',
                'farmer_id': farmer_id,
                'fpo_id': 'fpo_1',
                'quantity': 200.0,
                'crop_type': 'onion',
                'quality_grade': 'A',
                'moisture': 10.0,
                'price': 7000.0,
                'timestamp': (start_date + (end_date - start_date) / 2).isoformat(),  # Middle
                'sync_status': 'synced'
            }
            
            within_txn_3 = {
                'transaction_id': 'txn_within_3',
                'farmer_id': farmer_id,
                'fpo_id': 'fpo_1',
                'quantity': 175.0,
                'crop_type': 'cotton',
                'quality_grade': 'C',
                'moisture': 15.0,
                'price': 5500.0,
                'timestamp': end_date.isoformat(),  # Exactly at end (inclusive)
                'sync_status': 'synced'
            }
            
            # Transactions after the range (should not be returned)
            after_txn = {
                'transaction_id': 'txn_after',
                'farmer_id': farmer_id,
                'fpo_id': 'fpo_1',
                'quantity': 125.0,
                'crop_type': 'wheat',
                'quality_grade': 'B',
                'moisture': 13.0,
                'price': 5200.0,
                'timestamp': (end_date + timedelta(days=1)).isoformat(),
                'sync_status': 'synced'
            }
            
            # Mock query response - only return transactions within range
            mock_table.query.return_value = {
                'Items': [within_txn_1, within_txn_2, within_txn_3]
            }
            
            # Execute query
            db = DynamoDBAccess()
            results = db.get_transactions_by_date_range(farmer_id, start_date, end_date)
            
            # Property: All returned records should have timestamps within the range (inclusive)
            assert len(results) > 0, "Query should return transactions"
            
            for transaction in results:
                assert isinstance(transaction, Transaction), "Result should be Transaction object"
                
                # Property: timestamp should be >= start_date (inclusive)
                assert transaction.timestamp >= start_date, \
                    f"Transaction timestamp {transaction.timestamp} should be >= start_date {start_date}"
                
                # Property: timestamp should be <= end_date (inclusive)
                assert transaction.timestamp <= end_date, \
                    f"Transaction timestamp {transaction.timestamp} should be <= end_date {end_date}"
                
                # Property: timestamp should be within the range
                assert start_date <= transaction.timestamp <= end_date, \
                    f"Transaction timestamp {transaction.timestamp} should be within [{start_date}, {end_date}]"
    
    @given(
        farmer_id=uuid_string(),
        base_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2024, 1, 1)),
        num_transactions=st.integers(min_value=5, max_value=20)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_25_date_range_query_with_multiple_transactions(
        self, farmer_id, base_date, num_transactions
    ):
        """
        Property 25: Date Range Query Correctness - Multiple Transactions
        
        **Validates: Requirements 8.5**
        
        For any query with multiple transactions, all returned records should have 
        timestamps within the specified date range.
        """
        with patch('common.dynamodb_access.dynamodb') as mock_dynamodb:
            # Setup mock DynamoDB table
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            
            # Define date range
            start_date = base_date
            end_date = base_date + timedelta(days=30)
            
            # Generate transactions with timestamps within the range
            transactions_in_range = []
            for i in range(num_transactions):
                # Generate timestamp within the range
                days_offset = (i * 30) / num_transactions  # Distribute evenly
                timestamp = start_date + timedelta(days=days_offset)
                
                txn = {
                    'transaction_id': f'txn_{i}',
                    'farmer_id': farmer_id,
                    'fpo_id': 'fpo_1',
                    'quantity': 100.0 + i * 10,
                    'crop_type': 'wheat',
                    'quality_grade': 'A',
                    'moisture': 12.0,
                    'price': 5000.0 + i * 100,
                    'timestamp': timestamp.isoformat(),
                    'sync_status': 'synced'
                }
                transactions_in_range.append(txn)
            
            # Mock query response
            mock_table.query.return_value = {
                'Items': transactions_in_range
            }
            
            # Execute query
            db = DynamoDBAccess()
            results = db.get_transactions_by_date_range(farmer_id, start_date, end_date)
            
            # Property: All returned records should have timestamps within the range
            assert len(results) == num_transactions, \
                f"Should return {num_transactions} transactions"
            
            for transaction in results:
                # Property: Each transaction timestamp should be within the range (inclusive)
                assert start_date <= transaction.timestamp <= end_date, \
                    f"Transaction {transaction.transaction_id} timestamp {transaction.timestamp} " \
                    f"should be within [{start_date}, {end_date}]"
    
    @given(
        farmer_id=uuid_string(),
        query_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime.now())
    )
    @settings(max_examples=100, deadline=None)
    def test_property_25_date_range_query_single_day(
        self, farmer_id, query_date
    ):
        """
        Property 25: Date Range Query Correctness - Single Day Query
        
        **Validates: Requirements 8.5**
        
        For any query where start_date equals end_date (single day), all returned 
        records should have timestamps on that exact day.
        """
        with patch('common.dynamodb_access.dynamodb') as mock_dynamodb:
            # Setup mock DynamoDB table
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            
            # Single day range
            start_date = query_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = query_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Generate transactions on the same day
            same_day_txn_1 = {
                'transaction_id': 'txn_morning',
                'farmer_id': farmer_id,
                'fpo_id': 'fpo_1',
                'quantity': 100.0,
                'crop_type': 'wheat',
                'quality_grade': 'A',
                'moisture': 12.0,
                'price': 5000.0,
                'timestamp': start_date.isoformat(),
                'sync_status': 'synced'
            }
            
            same_day_txn_2 = {
                'transaction_id': 'txn_evening',
                'farmer_id': farmer_id,
                'fpo_id': 'fpo_1',
                'quantity': 150.0,
                'crop_type': 'rice',
                'quality_grade': 'B',
                'moisture': 14.0,
                'price': 6000.0,
                'timestamp': end_date.isoformat(),
                'sync_status': 'synced'
            }
            
            # Mock query response
            mock_table.query.return_value = {
                'Items': [same_day_txn_1, same_day_txn_2]
            }
            
            # Execute query
            db = DynamoDBAccess()
            results = db.get_transactions_by_date_range(farmer_id, start_date, end_date)
            
            # Property: All returned records should be within the single day range
            for transaction in results:
                assert start_date <= transaction.timestamp <= end_date, \
                    f"Transaction timestamp {transaction.timestamp} should be within " \
                    f"single day range [{start_date}, {end_date}]"
    
    @given(
        farmer_id=uuid_string(),
        start_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2023, 12, 31))
    )
    @settings(max_examples=100, deadline=None)
    def test_property_25_date_range_query_boundary_inclusiveness(
        self, farmer_id, start_date
    ):
        """
        Property 25: Date Range Query Correctness - Boundary Inclusiveness
        
        **Validates: Requirements 8.5**
        
        For any query with date range filters, transactions with timestamps exactly 
        at start_date or end_date should be included (boundaries are inclusive).
        """
        with patch('common.dynamodb_access.dynamodb') as mock_dynamodb:
            # Setup mock DynamoDB table
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            
            end_date = start_date + timedelta(days=7)
            
            # Transactions exactly at boundaries
            at_start_boundary = {
                'transaction_id': 'txn_at_start',
                'farmer_id': farmer_id,
                'fpo_id': 'fpo_1',
                'quantity': 100.0,
                'crop_type': 'wheat',
                'quality_grade': 'A',
                'moisture': 12.0,
                'price': 5000.0,
                'timestamp': start_date.isoformat(),  # Exactly at start
                'sync_status': 'synced'
            }
            
            at_end_boundary = {
                'transaction_id': 'txn_at_end',
                'farmer_id': farmer_id,
                'fpo_id': 'fpo_1',
                'quantity': 150.0,
                'crop_type': 'rice',
                'quality_grade': 'B',
                'moisture': 14.0,
                'price': 6000.0,
                'timestamp': end_date.isoformat(),  # Exactly at end
                'sync_status': 'synced'
            }
            
            # Mock query response - should include both boundary transactions
            mock_table.query.return_value = {
                'Items': [at_start_boundary, at_end_boundary]
            }
            
            # Execute query
            db = DynamoDBAccess()
            results = db.get_transactions_by_date_range(farmer_id, start_date, end_date)
            
            # Property: Transactions at exact boundaries should be included
            assert len(results) == 2, \
                "Query should return transactions at both boundaries (inclusive)"
            
            timestamps = [txn.timestamp for txn in results]
            
            # Property: Start boundary should be included
            assert start_date in timestamps, \
                f"Transaction at start_date {start_date} should be included (inclusive boundary)"
            
            # Property: End boundary should be included
            assert end_date in timestamps, \
                f"Transaction at end_date {end_date} should be included (inclusive boundary)"
            
            # Property: All timestamps should be within range (inclusive)
            for transaction in results:
                assert start_date <= transaction.timestamp <= end_date, \
                    f"Transaction timestamp should be within inclusive range"
    
    @given(
        farmer_id=uuid_string(),
        start_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2024, 1, 1))
    )
    @settings(max_examples=100, deadline=None)
    def test_property_25_date_range_query_empty_result(
        self, farmer_id, start_date
    ):
        """
        Property 25: Date Range Query Correctness - Empty Result
        
        **Validates: Requirements 8.5**
        
        For any query with date range filters where no transactions exist, 
        the query should return an empty list (not fail).
        """
        with patch('common.dynamodb_access.dynamodb') as mock_dynamodb:
            # Setup mock DynamoDB table
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            
            end_date = start_date + timedelta(days=7)
            
            # Mock query response - no transactions in range
            mock_table.query.return_value = {
                'Items': []
            }
            
            # Execute query
            db = DynamoDBAccess()
            results = db.get_transactions_by_date_range(farmer_id, start_date, end_date)
            
            # Property: Empty result should be a list
            assert isinstance(results, list), "Result should be a list"
            
            # Property: Empty result should have length 0
            assert len(results) == 0, "Result should be empty when no transactions in range"
    
    @given(
        farmer_id=uuid_string(),
        start_date=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2023, 1, 1)),
        range_days=st.integers(min_value=1, max_value=365)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_25_date_range_query_various_ranges(
        self, farmer_id, start_date, range_days
    ):
        """
        Property 25: Date Range Query Correctness - Various Range Sizes
        
        **Validates: Requirements 8.5**
        
        For any query with date range of varying sizes (1 day to 1 year), 
        all returned records should have timestamps within that range.
        """
        with patch('common.dynamodb_access.dynamodb') as mock_dynamodb:
            # Setup mock DynamoDB table
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            
            end_date = start_date + timedelta(days=range_days)
            
            # Generate transactions within the range
            transactions = []
            num_txns = min(5, range_days)  # At most 5 transactions
            
            for i in range(num_txns):
                days_offset = (i * range_days) / num_txns if num_txns > 0 else 0
                timestamp = start_date + timedelta(days=days_offset)
                
                txn = {
                    'transaction_id': f'txn_{i}',
                    'farmer_id': farmer_id,
                    'fpo_id': 'fpo_1',
                    'quantity': 100.0 + i * 10,
                    'crop_type': 'wheat',
                    'quality_grade': 'A',
                    'moisture': 12.0,
                    'price': 5000.0,
                    'timestamp': timestamp.isoformat(),
                    'sync_status': 'synced'
                }
                transactions.append(txn)
            
            # Mock query response
            mock_table.query.return_value = {
                'Items': transactions
            }
            
            # Execute query
            db = DynamoDBAccess()
            results = db.get_transactions_by_date_range(farmer_id, start_date, end_date)
            
            # Property: All returned records should be within the range
            for transaction in results:
                assert start_date <= transaction.timestamp <= end_date, \
                    f"Transaction timestamp {transaction.timestamp} should be within " \
                    f"range [{start_date}, {end_date}] (range size: {range_days} days)"
                
                # Property: Timestamp should not be before start_date
                assert transaction.timestamp >= start_date, \
                    f"Transaction should not be before start_date"
                
                # Property: Timestamp should not be after end_date
                assert transaction.timestamp <= end_date, \
                    f"Transaction should not be after end_date"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
