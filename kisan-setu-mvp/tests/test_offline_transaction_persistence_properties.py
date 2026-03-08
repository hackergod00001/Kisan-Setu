"""
Property-based tests for offline transaction persistence (Property 11).

This module tests that transactions created while offline are persisted
correctly in local storage with sync_status='PENDING' and are not lost
until successfully synced to the server.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

import pytest
import sqlite3
import json
import tempfile
from hypothesis import given, settings
from datetime import datetime, timedelta
from unittest.mock import Mock

# Import generators
from generators import transaction_data

# Import models and sync manager
from common.models import Transaction, SyncStatus
from sync.sync_manager import SyncManager


class TestOfflineTransactionPersistence:
    """
    Property-based tests for offline transaction persistence.
    
    **Validates: Requirements 4.2**
    """
    
    @given(transaction_data())
    @settings(max_examples=100)
    def test_property_11_offline_transaction_persistence(self, transaction):
        """
        Property 11: Offline Transaction Persistence
        
        For any transaction entered in offline mode, the transaction should be
        stored locally with a timestamp and retrievable until synchronization occurs.
        
        **Validates: Requirements 4.2**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, f"test_offline_{transaction.transaction_id}.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            mock_table.put_item = Mock()
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_001", temp_db)
            
            # Enable offline mode
            sync_manager.enable_offline_mode()
            
            # Set transaction sync_status to PENDING (offline mode)
            transaction.sync_status = SyncStatus.PENDING
            
            # Store transaction offline
            local_id = sync_manager.store_offline_transaction(transaction)
            
            # Verify local_id was generated
            assert local_id is not None, "Local ID should be generated"
            assert isinstance(local_id, str), "Local ID should be a string"
            assert len(local_id) > 0, "Local ID should not be empty"
            
            # Verify transaction is stored in local database
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT local_id, transaction_data, timestamp, sync_status FROM offline_transactions WHERE local_id = ?',
                (local_id,)
            )
            result = cursor.fetchone()
            conn.close()
            
            # Verify transaction exists in database
            assert result is not None, "Transaction should be stored in local database"
            
            stored_local_id, stored_data_json, stored_timestamp, stored_sync_status = result
            
            # Verify local_id matches
            assert stored_local_id == local_id, "Stored local_id should match returned local_id"
            
            # Verify sync_status is PENDING
            assert stored_sync_status == 'pending', \
                f"Sync status should be 'pending', got '{stored_sync_status}'"
            
            # Verify timestamp is stored
            assert stored_timestamp is not None, "Timestamp should be stored"
            stored_dt = datetime.fromisoformat(stored_timestamp)
            assert isinstance(stored_dt, datetime), "Timestamp should be a valid datetime"
            
            # Verify transaction data is preserved
            stored_data = json.loads(stored_data_json)
            assert stored_data['transaction_id'] == transaction.transaction_id, \
                "Transaction ID should be preserved"
            assert stored_data['farmer_id'] == transaction.farmer_id, \
                "Farmer ID should be preserved"
            assert stored_data['fpo_id'] == transaction.fpo_id, \
                "FPO ID should be preserved"
            assert abs(stored_data['quantity'] - transaction.quantity) < 0.01, \
                "Quantity should be preserved"
            assert stored_data['crop_type'] == transaction.crop_type, \
                "Crop type should be preserved"
            assert stored_data['quality_grade'] == transaction.quality_grade, \
                "Quality grade should be preserved"
            assert abs(stored_data['moisture'] - transaction.moisture) < 0.01, \
                "Moisture should be preserved"
            assert abs(stored_data['price'] - transaction.price) < 0.01, \
                "Price should be preserved"
            assert stored_data['sync_status'] in ['PENDING', 'pending'], \
                "Sync status should be PENDING or pending in stored data"
    
    @given(transaction_data())
    @settings(max_examples=100)
    def test_property_11_transaction_retrievable_until_sync(self, transaction):
        """
        Property 11: Offline Transaction Persistence (Retrievability)
        
        For any transaction stored offline, it should remain retrievable
        from local storage until it is successfully synchronized.
        
        **Validates: Requirements 4.2**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, f"test_retrieve_{transaction.transaction_id}.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            mock_table.put_item = Mock()
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_002", temp_db)
            
            # Set transaction sync_status to PENDING
            transaction.sync_status = SyncStatus.PENDING
            
            # Store transaction offline
            local_id = sync_manager.store_offline_transaction(transaction)
            
            # Retrieve pending transactions (before sync)
            pending_txns = sync_manager._get_pending_transactions()
            
            # Verify transaction is retrievable
            assert len(pending_txns) >= 1, "At least one pending transaction should exist"
            
            # Find our transaction
            our_txn = None
            for txn in pending_txns:
                if txn.local_id == local_id:
                    our_txn = txn
                    break
            
            assert our_txn is not None, "Our transaction should be retrievable"
            assert our_txn.sync_status == 'pending', "Sync status should be pending"
            assert our_txn.transaction_data['transaction_id'] == transaction.transaction_id, \
                "Transaction ID should match"
            
            # Simulate successful sync by updating status
            sync_manager._update_local_sync_status(local_id, 'synced')
            
            # Retrieve pending transactions (after sync)
            pending_txns_after = sync_manager._get_pending_transactions()
            
            # Verify transaction is no longer in pending list
            our_txn_after = None
            for txn in pending_txns_after:
                if txn.local_id == local_id:
                    our_txn_after = txn
                    break
            
            assert our_txn_after is None, \
                "Transaction should not be in pending list after sync"
    
    @given(transaction_data())
    @settings(max_examples=100)
    def test_property_11_transaction_not_lost_before_sync(self, transaction):
        """
        Property 11: Offline Transaction Persistence (Data Loss Prevention)
        
        For any transaction stored offline, it must not be lost or deleted
        until it is successfully synced to the server.
        
        **Validates: Requirements 4.2**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, f"test_loss_{transaction.transaction_id}.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            mock_table.put_item = Mock()
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_003", temp_db)
            
            # Set transaction sync_status to PENDING
            transaction.sync_status = SyncStatus.PENDING
            
            # Store transaction offline
            local_id = sync_manager.store_offline_transaction(transaction)
            
            # Verify transaction exists in database
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) FROM offline_transactions WHERE local_id = ?',
                (local_id,)
            )
            count_before = cursor.fetchone()[0]
            conn.close()
            
            assert count_before == 1, "Transaction should exist in database"
            
            # Simulate multiple retrieval operations (transaction should persist)
            for _ in range(5):
                pending_txns = sync_manager._get_pending_transactions()
                assert any(txn.local_id == local_id for txn in pending_txns), \
                    "Transaction should persist across multiple retrievals"
            
            # Verify transaction still exists after multiple retrievals
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) FROM offline_transactions WHERE local_id = ? AND sync_status = ?',
                (local_id, 'pending')
            )
            count_after = cursor.fetchone()[0]
            conn.close()
            
            assert count_after == 1, \
                "Transaction should not be lost after multiple retrievals"
    
    @given(transaction_data())
    @settings(max_examples=100)
    def test_property_11_timestamp_preserved_during_storage(self, transaction):
        """
        Property 11: Offline Transaction Persistence (Timestamp Preservation)
        
        For any transaction stored offline, its timestamp should be preserved
        accurately for chronological synchronization.
        
        **Validates: Requirements 4.2**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, f"test_timestamp_{transaction.transaction_id}.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            mock_table.put_item = Mock()
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_004", temp_db)
            
            # Set transaction sync_status to PENDING
            transaction.sync_status = SyncStatus.PENDING
            
            # Record original timestamp
            original_timestamp = transaction.timestamp
            
            # Store transaction offline
            local_id = sync_manager.store_offline_transaction(transaction)
            
            # Retrieve transaction from database
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT transaction_data, timestamp FROM offline_transactions WHERE local_id = ?',
                (local_id,)
            )
            result = cursor.fetchone()
            conn.close()
            
            assert result is not None, "Transaction should be stored"
            
            stored_data_json, stored_timestamp_str = result
            stored_data = json.loads(stored_data_json)
            
            # Verify timestamp in transaction data
            stored_txn_timestamp = datetime.fromisoformat(stored_data['timestamp'])
            
            # Allow small time difference due to serialization (< 1 second)
            time_diff = abs((stored_txn_timestamp - original_timestamp).total_seconds())
            assert time_diff < 1.0, \
                f"Timestamp should be preserved (diff: {time_diff}s)"
            
            # Verify storage timestamp
            stored_timestamp = datetime.fromisoformat(stored_timestamp_str)
            time_diff_storage = abs((stored_timestamp - original_timestamp).total_seconds())
            assert time_diff_storage < 2.0, \
                f"Storage timestamp should be close to original (diff: {time_diff_storage}s)"
    
    @given(transaction_data())
    @settings(max_examples=100)
    def test_property_11_multiple_transactions_all_persisted(self, transaction):
        """
        Property 11: Offline Transaction Persistence (Multiple Transactions)
        
        For any set of transactions stored offline, all transactions should
        be persisted and none should be lost.
        
        **Validates: Requirements 4.2**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, f"test_multiple_{transaction.transaction_id}.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            mock_table.put_item = Mock()
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_005", temp_db)
            
            # Create multiple transactions (3-5)
            num_transactions = 3
            local_ids = []
            
            for i in range(num_transactions):
                # Create a variant of the transaction
                txn = Transaction(
                    transaction_id=f"{transaction.transaction_id}_{i}",
                    farmer_id=transaction.farmer_id,
                    fpo_id=transaction.fpo_id,
                    quantity=transaction.quantity + i,
                    crop_type=transaction.crop_type,
                    quality_grade=transaction.quality_grade,
                    moisture=transaction.moisture,
                    price=transaction.price + (i * 100),
                    timestamp=transaction.timestamp + timedelta(minutes=i),
                    ledger_image_url=transaction.ledger_image_url,
                    sync_status=SyncStatus.PENDING
                )
                
                # Store transaction
                local_id = sync_manager.store_offline_transaction(txn)
                local_ids.append(local_id)
            
            # Verify all transactions are stored
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) FROM offline_transactions WHERE sync_status = ?',
                ('pending',)
            )
            count = cursor.fetchone()[0]
            conn.close()
            
            assert count >= num_transactions, \
                f"All {num_transactions} transactions should be persisted, found {count}"
            
            # Verify all local_ids are retrievable
            pending_txns = sync_manager._get_pending_transactions()
            retrieved_ids = [txn.local_id for txn in pending_txns]
            
            for local_id in local_ids:
                assert local_id in retrieved_ids, \
                    f"Transaction {local_id} should be retrievable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
