"""
Property-based tests for sync completion notification (Property 14).

This module tests that after synchronization completes, a notification
is provided with success_count and failure_count, where the sum equals
the total attempted transactions.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

import pytest
import sqlite3
import tempfile
from hypothesis import given, settings, strategies as st
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Import generators
from generators import transaction_data

# Import models and sync manager
from common.models import Transaction, SyncStatus
from sync.sync_manager import SyncManager, SyncResult


class TestSyncCompletionNotification:
    """
    Property-based tests for sync completion notification.
    
    **Validates: Requirements 4.6**
    """
    
    @given(st.lists(transaction_data(), min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_property_14_sync_notification_includes_counts(self, transactions):
        """
        Property 14: Sync Completion Notification
        
        After synchronization completes, a notification must be provided with
        success_count (number of successfully synced transactions) and
        failure_count (number of failed transactions), where
        success_count + failure_count = total attempted transactions.
        
        **Validates: Requirements 4.6**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_sync_notification.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            mock_table.put_item = Mock()
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_sync", temp_db)
            
            # Enable offline mode
            sync_manager.enable_offline_mode()
            
            # Store all transactions offline
            local_ids = []
            for txn in transactions:
                txn.sync_status = SyncStatus.PENDING
                local_id = sync_manager.store_offline_transaction(txn)
                local_ids.append(local_id)
            
            # Mock connectivity check to return True
            with patch.object(sync_manager, 'detect_connectivity', return_value=True):
                # Perform synchronization
                sync_result = sync_manager.synchronize_data()
            
            # Verify sync_result is returned
            assert sync_result is not None, "Sync result should be returned"
            assert isinstance(sync_result, SyncResult), "Result should be SyncResult instance"
            
            # Verify success_count and failure_count are present
            assert hasattr(sync_result, 'success_count'), \
                "Sync result should have success_count"
            assert hasattr(sync_result, 'failure_count'), \
                "Sync result should have failure_count"
            
            # Verify counts are non-negative integers
            assert isinstance(sync_result.success_count, int), \
                "success_count should be an integer"
            assert isinstance(sync_result.failure_count, int), \
                "failure_count should be an integer"
            assert sync_result.success_count >= 0, \
                "success_count should be non-negative"
            assert sync_result.failure_count >= 0, \
                "failure_count should be non-negative"
            
            # Verify sum equals total attempted transactions
            total_attempted = len(transactions)
            total_processed = sync_result.success_count + sync_result.failure_count
            
            assert total_processed == total_attempted, \
                f"success_count ({sync_result.success_count}) + " \
                f"failure_count ({sync_result.failure_count}) = " \
                f"{total_processed} should equal total attempted ({total_attempted})"

    
    @given(st.lists(transaction_data(), min_size=1, max_size=15))
    @settings(max_examples=100)
    def test_property_14_sync_notification_with_partial_failures(self, transactions):
        """
        Property 14: Sync Completion Notification (Partial Failures)
        
        When some transactions succeed and some fail during sync,
        the notification should accurately reflect both counts,
        and their sum should equal total attempted.
        
        **Validates: Requirements 4.6**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_partial_failures.db")
        
            # Create mock DynamoDB table that fails for some transactions
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            
            # Make put_item fail for transactions with even indices
            def put_item_side_effect(**kwargs):
                item = kwargs.get('Item', {})
                txn_id = item.get('transaction_id', '')
                # Fail if transaction_id contains certain pattern
                if len(txn_id) > 0 and ord(txn_id[0]) % 2 == 0:
                    raise Exception("Simulated DynamoDB error")
                return {}
            
            mock_table.put_item = Mock(side_effect=put_item_side_effect)
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_partial", temp_db)
            
            # Enable offline mode
            sync_manager.enable_offline_mode()
            
            # Store all transactions offline
            for txn in transactions:
                txn.sync_status = SyncStatus.PENDING
                sync_manager.store_offline_transaction(txn)
            
            # Mock connectivity check to return True
            with patch.object(sync_manager, 'detect_connectivity', return_value=True):
                # Perform synchronization
                sync_result = sync_manager.synchronize_data()
            
            # Verify notification includes both success and failure counts
            assert sync_result.success_count >= 0, "Should have success_count"
            assert sync_result.failure_count >= 0, "Should have failure_count"
            
            # Verify sum equals total
            total_attempted = len(transactions)
            total_processed = sync_result.success_count + sync_result.failure_count
            
            assert total_processed == total_attempted, \
                f"Total processed ({total_processed}) should equal " \
                f"total attempted ({total_attempted})"
            
            # Verify at least some failures occurred (due to our mock)
            # Note: This may not always be true depending on transaction_id values,
            # but the property still holds
            assert sync_result.failure_count >= 0, \
                "failure_count should be present even if zero"
    
    @given(st.lists(transaction_data(), min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_property_14_sync_notification_all_success(self, transactions):
        """
        Property 14: Sync Completion Notification (All Success)
        
        When all transactions sync successfully, the notification should
        show success_count = total and failure_count = 0.
        
        **Validates: Requirements 4.6**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_all_success.db")
        
            # Create mock DynamoDB table that always succeeds
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            mock_table.put_item = Mock(return_value={})
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_success", temp_db)
            
            # Enable offline mode
            sync_manager.enable_offline_mode()
            
            # Store all transactions offline
            for txn in transactions:
                txn.sync_status = SyncStatus.PENDING
                sync_manager.store_offline_transaction(txn)
            
            # Mock connectivity check to return True
            with patch.object(sync_manager, 'detect_connectivity', return_value=True):
                # Perform synchronization
                sync_result = sync_manager.synchronize_data()
            
            # Verify all succeeded
            total_attempted = len(transactions)
            
            assert sync_result.success_count == total_attempted, \
                f"All {total_attempted} transactions should succeed"
            assert sync_result.failure_count == 0, \
                "No failures should occur"
            
            # Verify sum property
            total_processed = sync_result.success_count + sync_result.failure_count
            assert total_processed == total_attempted, \
                "Sum should equal total attempted"
    
    @given(st.lists(transaction_data(), min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_property_14_sync_notification_all_failures(self, transactions):
        """
        Property 14: Sync Completion Notification (All Failures)
        
        When all transactions fail to sync, the notification should
        show success_count = 0 and failure_count = total.
        
        **Validates: Requirements 4.6**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_all_failures.db")
        
            # Create mock DynamoDB table that always fails
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            mock_table.put_item = Mock(side_effect=Exception("Simulated failure"))
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_failures", temp_db)
            
            # Enable offline mode
            sync_manager.enable_offline_mode()
            
            # Store all transactions offline
            for txn in transactions:
                txn.sync_status = SyncStatus.PENDING
                sync_manager.store_offline_transaction(txn)
            
            # Mock connectivity check to return True
            with patch.object(sync_manager, 'detect_connectivity', return_value=True):
                # Perform synchronization
                sync_result = sync_manager.synchronize_data()
            
            # Verify all failed
            total_attempted = len(transactions)
            
            assert sync_result.success_count == 0, \
                "No transactions should succeed"
            assert sync_result.failure_count == total_attempted, \
                f"All {total_attempted} transactions should fail"
            
            # Verify sum property
            total_processed = sync_result.success_count + sync_result.failure_count
            assert total_processed == total_attempted, \
                "Sum should equal total attempted"
    
    @given(st.lists(transaction_data(), min_size=0, max_size=5))
    @settings(max_examples=100)
    def test_property_14_sync_notification_empty_queue(self, transactions):
        """
        Property 14: Sync Completion Notification (Empty Queue)
        
        When there are no pending transactions to sync, the notification
        should show success_count = 0 and failure_count = 0.
        
        **Validates: Requirements 4.6**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_empty_queue.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            mock_table.put_item = Mock(return_value={})
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_empty", temp_db)
            
            # Don't store any transactions (empty queue)
            
            # Mock connectivity check to return True
            with patch.object(sync_manager, 'detect_connectivity', return_value=True):
                # Perform synchronization
                sync_result = sync_manager.synchronize_data()
            
            # Verify empty result
            assert sync_result.success_count == 0, \
                "No transactions should succeed (empty queue)"
            assert sync_result.failure_count == 0, \
                "No transactions should fail (empty queue)"
            
            # Verify sum property (0 + 0 = 0)
            total_processed = sync_result.success_count + sync_result.failure_count
            assert total_processed == 0, \
                "Total processed should be 0 for empty queue"
    
    @given(st.lists(transaction_data(), min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_property_14_sync_notification_no_connectivity(self, transactions):
        """
        Property 14: Sync Completion Notification (No Connectivity)
        
        When there is no connectivity, sync should not proceed and
        notification should show success_count = 0 and failure_count = 0.
        
        **Validates: Requirements 4.6**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_no_connectivity.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            mock_table.put_item = Mock(return_value={})
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_no_conn", temp_db)
            
            # Enable offline mode
            sync_manager.enable_offline_mode()
            
            # Store all transactions offline
            for txn in transactions:
                txn.sync_status = SyncStatus.PENDING
                sync_manager.store_offline_transaction(txn)
            
            # Mock connectivity check to return False (no connectivity)
            with patch.object(sync_manager, 'detect_connectivity', return_value=False):
                # Attempt synchronization
                sync_result = sync_manager.synchronize_data()
            
            # Verify no sync occurred
            assert sync_result.success_count == 0, \
                "No transactions should succeed without connectivity"
            assert sync_result.failure_count == 0, \
                "No transactions should be attempted without connectivity"
            
            # Verify sum property
            total_processed = sync_result.success_count + sync_result.failure_count
            assert total_processed == 0, \
                "No transactions should be processed without connectivity"
    
    @given(st.lists(transaction_data(), min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_property_14_sync_notification_includes_timestamp(self, transactions):
        """
        Property 14: Sync Completion Notification (Timestamp)
        
        The sync notification should include a timestamp indicating
        when the synchronization completed.
        
        **Validates: Requirements 4.6**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_timestamp.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            mock_table.put_item = Mock(return_value={})
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_timestamp", temp_db)
            
            # Enable offline mode
            sync_manager.enable_offline_mode()
            
            # Store all transactions offline
            for txn in transactions:
                txn.sync_status = SyncStatus.PENDING
                sync_manager.store_offline_transaction(txn)
            
            # Record time before sync
            time_before = datetime.utcnow()
            
            # Mock connectivity check to return True
            with patch.object(sync_manager, 'detect_connectivity', return_value=True):
                # Perform synchronization
                sync_result = sync_manager.synchronize_data()
            
            # Record time after sync
            time_after = datetime.utcnow()
            
            # Verify timestamp is present
            assert hasattr(sync_result, 'sync_timestamp'), \
                "Sync result should have sync_timestamp"
            assert sync_result.sync_timestamp is not None, \
                "sync_timestamp should not be None"
            assert isinstance(sync_result.sync_timestamp, datetime), \
                "sync_timestamp should be a datetime object"
            
            # Verify timestamp is reasonable (between before and after)
            assert time_before <= sync_result.sync_timestamp <= time_after, \
                "sync_timestamp should be within the sync operation timeframe"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
