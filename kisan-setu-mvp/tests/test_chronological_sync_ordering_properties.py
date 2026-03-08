"""
Property-based tests for chronological sync ordering (Property 12).

This module tests that offline transactions are synchronized in chronological
order based on their timestamps (oldest first).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

import pytest
import sqlite3
import json
import tempfile
from hypothesis import given, settings
from hypothesis import strategies as st
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from decimal import Decimal

# Import generators
from generators import transaction_data

# Import models and sync manager
from common.models import Transaction, SyncStatus
from sync.sync_manager import SyncManager


class TestChronologicalSyncOrdering:
    """
    Property-based tests for chronological sync ordering.
    
    **Validates: Requirements 4.4**
    """
    
    @given(st.lists(transaction_data(), min_size=2, max_size=10))
    @settings(max_examples=100)
    def test_property_12_chronological_sync_ordering(self, transactions):
        """
        Property 12: Chronological Sync Ordering
        
        For any set of offline transactions, when synchronized to the cloud,
        they should be uploaded in chronological order based on their timestamps
        (earliest first).
        
        **Validates: Requirements 4.4**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_chronological_sync.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            
            # Track the order of put_item calls
            upload_order = []
            
            def track_put_item(Item):
                """Track the order of uploads by timestamp"""
                upload_order.append({
                    'transaction_id': Item['transaction_id'],
                    'timestamp': Item['timestamp']
                })
            
            mock_table.put_item = Mock(side_effect=track_put_item)
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_chronological", temp_db)
            
            # Ensure transactions have different timestamps
            # Sort them randomly first, then assign sequential timestamps
            base_time = datetime(2023, 1, 1, 0, 0, 0)
            for i, txn in enumerate(transactions):
                txn.sync_status = SyncStatus.PENDING
                # Assign timestamps with at least 1 second apart
                txn.timestamp = base_time + timedelta(seconds=i * 10)
                txn.transaction_id = f"txn_{i}_{txn.transaction_id}"
            
            # Store transactions in random order (shuffle)
            import random
            shuffled_transactions = transactions.copy()
            random.shuffle(shuffled_transactions)
            
            # Store all transactions offline
            local_ids = []
            for txn in shuffled_transactions:
                local_id = sync_manager.store_offline_transaction(txn)
                local_ids.append(local_id)
            
            # Verify all transactions are stored
            assert len(local_ids) == len(transactions), \
                "All transactions should be stored"
            
            # Synchronize data
            sync_result = sync_manager.synchronize_data()
            
            # Verify sync was successful
            assert sync_result.success_count == len(transactions), \
                f"All {len(transactions)} transactions should sync successfully"
            assert sync_result.failure_count == 0, \
                "No transactions should fail"
            
            # Verify chronological ordering
            assert len(upload_order) == len(transactions), \
                "All transactions should be uploaded"
            
            # Extract timestamps from upload order
            uploaded_timestamps = [
                datetime.fromisoformat(item['timestamp'])
                for item in upload_order
            ]
            
            # Verify timestamps are in ascending order (oldest first)
            for i in range(len(uploaded_timestamps) - 1):
                assert uploaded_timestamps[i] <= uploaded_timestamps[i + 1], \
                    f"Transactions should be synced in chronological order: " \
                    f"{uploaded_timestamps[i]} should be <= {uploaded_timestamps[i + 1]}"
            
            # Verify the order matches the original sorted order
            expected_order = sorted(transactions, key=lambda x: x.timestamp)
            expected_timestamps = [txn.timestamp for txn in expected_order]
            
            assert uploaded_timestamps == expected_timestamps, \
                "Upload order should match chronological order of original transactions"
    
    @given(st.lists(transaction_data(), min_size=3, max_size=8))
    @settings(max_examples=100)
    def test_property_12_oldest_first_ordering(self, transactions):
        """
        Property 12: Chronological Sync Ordering (Oldest First)
        
        For any set of offline transactions, the oldest transaction (by timestamp)
        should be synced first, and the newest should be synced last.
        
        **Validates: Requirements 4.4**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_oldest_first.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            
            # Track upload order
            upload_order = []
            
            def track_put_item(Item):
                upload_order.append({
                    'transaction_id': Item['transaction_id'],
                    'timestamp': datetime.fromisoformat(Item['timestamp'])
                })
            
            mock_table.put_item = Mock(side_effect=track_put_item)
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_oldest", temp_db)
            
            # Assign distinct timestamps
            base_time = datetime(2023, 6, 1, 12, 0, 0)
            for i, txn in enumerate(transactions):
                txn.sync_status = SyncStatus.PENDING
                txn.timestamp = base_time + timedelta(hours=i)
                txn.transaction_id = f"txn_oldest_{i}_{txn.transaction_id}"
            
            # Find oldest and newest
            oldest_txn = min(transactions, key=lambda x: x.timestamp)
            newest_txn = max(transactions, key=lambda x: x.timestamp)
            
            # Store transactions in reverse order (newest first)
            sorted_desc = sorted(transactions, key=lambda x: x.timestamp, reverse=True)
            for txn in sorted_desc:
                sync_manager.store_offline_transaction(txn)
            
            # Synchronize
            sync_result = sync_manager.synchronize_data()
            
            # Verify sync success
            assert sync_result.success_count == len(transactions), \
                "All transactions should sync successfully"
            
            # Verify oldest is first
            first_uploaded = upload_order[0]
            assert first_uploaded['transaction_id'] == oldest_txn.transaction_id, \
                f"Oldest transaction should be synced first: " \
                f"expected {oldest_txn.transaction_id}, got {first_uploaded['transaction_id']}"
            assert first_uploaded['timestamp'] == oldest_txn.timestamp, \
                "First uploaded timestamp should match oldest transaction"
            
            # Verify newest is last
            last_uploaded = upload_order[-1]
            assert last_uploaded['transaction_id'] == newest_txn.transaction_id, \
                f"Newest transaction should be synced last: " \
                f"expected {newest_txn.transaction_id}, got {last_uploaded['transaction_id']}"
            assert last_uploaded['timestamp'] == newest_txn.timestamp, \
                "Last uploaded timestamp should match newest transaction"
    
    @given(st.lists(transaction_data(), min_size=2, max_size=6))
    @settings(max_examples=100)
    def test_property_12_timestamp_preservation_during_sync(self, transactions):
        """
        Property 12: Chronological Sync Ordering (Timestamp Preservation)
        
        For any set of offline transactions, their timestamps should be preserved
        during synchronization, maintaining the chronological relationship.
        
        **Validates: Requirements 4.4**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_timestamp_preservation.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            
            # Track uploaded items
            uploaded_items = []
            
            def track_put_item(Item):
                uploaded_items.append(Item.copy())
            
            mock_table.put_item = Mock(side_effect=track_put_item)
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_preservation", temp_db)
            
            # Assign timestamps
            base_time = datetime(2023, 3, 15, 8, 30, 0)
            for i, txn in enumerate(transactions):
                txn.sync_status = SyncStatus.PENDING
                txn.timestamp = base_time + timedelta(minutes=i * 5)
                txn.transaction_id = f"txn_preserve_{i}_{txn.transaction_id}"
            
            # Store transactions
            for txn in transactions:
                sync_manager.store_offline_transaction(txn)
            
            # Synchronize
            sync_result = sync_manager.synchronize_data()
            
            # Verify all synced
            assert sync_result.success_count == len(transactions), \
                "All transactions should sync"
            
            # Verify timestamps are preserved
            for i, item in enumerate(uploaded_items):
                uploaded_timestamp = datetime.fromisoformat(item['timestamp'])
                
                # Find matching original transaction
                matching_txn = next(
                    (txn for txn in transactions if txn.transaction_id == item['transaction_id']),
                    None
                )
                
                assert matching_txn is not None, \
                    f"Uploaded transaction {item['transaction_id']} should match an original"
                
                # Verify timestamp is preserved
                time_diff = abs((uploaded_timestamp - matching_txn.timestamp).total_seconds())
                assert time_diff < 1.0, \
                    f"Timestamp should be preserved (diff: {time_diff}s)"
            
            # Verify chronological order is maintained
            uploaded_timestamps = [
                datetime.fromisoformat(item['timestamp'])
                for item in uploaded_items
            ]
            
            for i in range(len(uploaded_timestamps) - 1):
                assert uploaded_timestamps[i] <= uploaded_timestamps[i + 1], \
                    "Chronological order should be maintained"
    
    @given(st.lists(transaction_data(), min_size=4, max_size=12))
    @settings(max_examples=100)
    def test_property_12_no_timestamp_reordering(self, transactions):
        """
        Property 12: Chronological Sync Ordering (No Reordering)
        
        For any set of offline transactions with distinct timestamps,
        the sync order should never violate chronological ordering
        (no transaction with later timestamp should be synced before
        a transaction with earlier timestamp).
        
        **Validates: Requirements 4.4**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_no_reordering.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            
            # Track sync order with timestamps
            sync_sequence = []
            
            def track_put_item(Item):
                sync_sequence.append({
                    'transaction_id': Item['transaction_id'],
                    'timestamp': datetime.fromisoformat(Item['timestamp']),
                    'sync_order': len(sync_sequence)
                })
            
            mock_table.put_item = Mock(side_effect=track_put_item)
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_no_reorder", temp_db)
            
            # Assign distinct timestamps with gaps
            base_time = datetime(2023, 9, 1, 0, 0, 0)
            for i, txn in enumerate(transactions):
                txn.sync_status = SyncStatus.PENDING
                # Use varying gaps to make timestamps more realistic
                gap = (i * 7) + (i % 3)  # Variable gaps
                txn.timestamp = base_time + timedelta(minutes=gap)
                txn.transaction_id = f"txn_reorder_{i}_{txn.transaction_id}"
            
            # Store in completely random order
            import random
            random_order = transactions.copy()
            random.shuffle(random_order)
            
            for txn in random_order:
                sync_manager.store_offline_transaction(txn)
            
            # Synchronize
            sync_result = sync_manager.synchronize_data()
            
            # Verify all synced
            assert sync_result.success_count == len(transactions), \
                "All transactions should sync"
            
            # Verify no chronological violations
            for i in range(len(sync_sequence)):
                for j in range(i + 1, len(sync_sequence)):
                    earlier_sync = sync_sequence[i]
                    later_sync = sync_sequence[j]
                    
                    # Transaction synced earlier should have earlier or equal timestamp
                    assert earlier_sync['timestamp'] <= later_sync['timestamp'], \
                        f"Chronological violation: transaction synced at position {i} " \
                        f"(timestamp {earlier_sync['timestamp']}) should not have " \
                        f"later timestamp than transaction at position {j} " \
                        f"(timestamp {later_sync['timestamp']})"
    
    @given(st.lists(transaction_data(), min_size=2, max_size=5))
    @settings(max_examples=100)
    def test_property_12_same_timestamp_handling(self, transactions):
        """
        Property 12: Chronological Sync Ordering (Same Timestamp)
        
        For any set of offline transactions where some have identical timestamps,
        all transactions should still be synced without loss, and transactions
        with earlier timestamps should be synced before those with later timestamps.
        
        **Validates: Requirements 4.4**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_same_timestamp.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            
            # Track uploads
            uploaded = []
            
            def track_put_item(Item):
                uploaded.append({
                    'transaction_id': Item['transaction_id'],
                    'timestamp': datetime.fromisoformat(Item['timestamp'])
                })
            
            mock_table.put_item = Mock(side_effect=track_put_item)
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_same_ts", temp_db)
            
            # Assign timestamps with some duplicates
            base_time = datetime(2023, 11, 20, 14, 0, 0)
            for i, txn in enumerate(transactions):
                txn.sync_status = SyncStatus.PENDING
                # Some transactions get same timestamp
                time_group = i // 2  # Groups of 2 get same timestamp
                txn.timestamp = base_time + timedelta(hours=time_group)
                txn.transaction_id = f"txn_same_{i}_{txn.transaction_id}"
            
            # Store transactions
            for txn in transactions:
                sync_manager.store_offline_transaction(txn)
            
            # Synchronize
            sync_result = sync_manager.synchronize_data()
            
            # Verify all transactions synced (no loss)
            assert sync_result.success_count == len(transactions), \
                f"All {len(transactions)} transactions should sync, " \
                f"got {sync_result.success_count}"
            
            assert len(uploaded) == len(transactions), \
                "All transactions should be uploaded"
            
            # Verify chronological ordering is maintained
            for i in range(len(uploaded) - 1):
                current_ts = uploaded[i]['timestamp']
                next_ts = uploaded[i + 1]['timestamp']
                
                assert current_ts <= next_ts, \
                    f"Chronological order should be maintained even with duplicate timestamps: " \
                    f"{current_ts} should be <= {next_ts}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
