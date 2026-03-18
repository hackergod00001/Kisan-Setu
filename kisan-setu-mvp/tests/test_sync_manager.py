"""
Unit tests for Sync Manager Component
"""

import pytest
import json
import sqlite3
import os
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lambda'))
sys.path.insert(0, os.path.dirname(__file__))

from lib.sync_manager import SyncManager, SyncResult, OfflineTransaction
from common.models import Transaction, SyncStatus


@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table."""
    table = Mock()
    table.table_status = 'ACTIVE'
    table.put_item = Mock()
    table.query = Mock(return_value={'Items': []})
    return table


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    return str(tmp_path / "test_sync.db")


@pytest.fixture
def sync_manager(mock_dynamodb_table, temp_db_path):
    """Create a SyncManager instance for testing."""
    return SyncManager(mock_dynamodb_table, "test_device_001", temp_db_path)


@pytest.fixture
def sample_transaction():
    """Create a sample transaction."""
    return Transaction(
        transaction_id="TXN001",
        farmer_id="FARMER#001",
        fpo_id="FPO#001",
        quantity=100.0,
        crop_type="onion",
        quality_grade="A",
        moisture=12.5,
        price=5000.0,
        timestamp=datetime.utcnow(),
        ledger_image_url="s3://bucket/ledger.jpg",
        sync_status=SyncStatus.PENDING
    )


class TestSyncManagerInitialization:
    """Test Sync Manager initialization."""
    
    def test_init_creates_local_database(self, mock_dynamodb_table, temp_db_path):
        """Test that initialization creates local SQLite database."""
        manager = SyncManager(mock_dynamodb_table, "device_001", temp_db_path)
        
        # Check database file exists
        assert os.path.exists(temp_db_path)
        
        # Check tables exist
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        assert 'offline_transactions' in tables
        assert 'sync_metadata' in tables
    
    def test_init_sets_device_id(self, sync_manager):
        """Test that device ID is set correctly."""
        assert sync_manager.device_id == "test_device_001"
    
    def test_init_offline_mode_false(self, sync_manager):
        """Test that offline mode is initially false."""
        assert sync_manager.offline_mode is False


class TestEnableOfflineMode:
    """Test enable_offline_mode method."""
    
    def test_enable_offline_mode_success(self, sync_manager):
        """Test enabling offline mode."""
        result = sync_manager.enable_offline_mode()
        
        assert result is True
        assert sync_manager.offline_mode is True
    
    def test_enable_offline_mode_stores_in_db(self, sync_manager, temp_db_path):
        """Test that offline mode status is stored in database."""
        sync_manager.enable_offline_mode()
        
        # Check database
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM sync_metadata WHERE key = 'offline_mode'")
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None
        assert result[0] == 'true'


class TestStoreOfflineTransaction:
    """Test store_offline_transaction method."""
    
    def test_store_transaction_returns_local_id(self, sync_manager, sample_transaction):
        """Test that storing transaction returns a local ID."""
        local_id = sync_manager.store_offline_transaction(sample_transaction)
        
        assert local_id is not None
        assert local_id.startswith("test_device_001#")
        assert "TXN001" in local_id
    
    def test_store_transaction_saves_to_db(self, sync_manager, sample_transaction, temp_db_path):
        """Test that transaction is saved to local database."""
        local_id = sync_manager.store_offline_transaction(sample_transaction)
        
        # Check database
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM offline_transactions WHERE local_id = ?", (local_id,))
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None
        assert result[0] == local_id
        assert result[3] == 'pending'  # sync_status
        assert result[4] == 0  # retry_count
    
    def test_store_transaction_preserves_data(self, sync_manager, sample_transaction, temp_db_path):
        """Test that transaction data is preserved correctly."""
        local_id = sync_manager.store_offline_transaction(sample_transaction)
        
        # Retrieve from database
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT transaction_data FROM offline_transactions WHERE local_id = ?", (local_id,))
        result = cursor.fetchone()
        conn.close()
        
        data = json.loads(result[0])
        assert data['transaction_id'] == "TXN001"
        assert data['farmer_id'] == "FARMER#001"
        assert data['quantity'] == 100.0
        assert data['crop_type'] == "onion"
        assert data['moisture'] == 12.5


class TestDetectConnectivity:
    """Test detect_connectivity method."""
    
    def test_detect_connectivity_when_connected(self, sync_manager, mock_dynamodb_table):
        """Test connectivity detection when online."""
        mock_dynamodb_table.table_status = 'ACTIVE'
        
        result = sync_manager.detect_connectivity()
        
        assert result is True
    
    def test_detect_connectivity_when_disconnected(self, sync_manager, mock_dynamodb_table):
        """Test connectivity detection when offline."""
        # Simulate connection error
        type(mock_dynamodb_table).table_status = property(
            lambda self: (_ for _ in ()).throw(Exception("No connection"))
        )
        
        result = sync_manager.detect_connectivity()
        
        assert result is False


class TestSynchronizeData:
    """Test synchronize_data method."""
    
    def test_synchronize_with_no_pending_transactions(self, sync_manager):
        """Test synchronization when no pending transactions exist."""
        result = sync_manager.synchronize_data()
        
        assert isinstance(result, SyncResult)
        assert result.success_count == 0
        assert result.failure_count == 0
        assert len(result.conflicts) == 0
    
    def test_synchronize_with_pending_transactions(self, sync_manager, sample_transaction, mock_dynamodb_table):
        """Test synchronization with pending transactions."""
        # Store a transaction
        sync_manager.store_offline_transaction(sample_transaction)
        
        # Synchronize
        result = sync_manager.synchronize_data()
        
        assert result.success_count == 1
        assert result.failure_count == 0
        assert mock_dynamodb_table.put_item.called
    
    def test_synchronize_chronological_order(self, sync_manager, mock_dynamodb_table):
        """Test that transactions are synced in chronological order."""
        # Create transactions with different timestamps
        now = datetime.utcnow()
        
        txn1 = Transaction(
            transaction_id="TXN001",
            farmer_id="FARMER#001",
            fpo_id="FPO#001",
            quantity=100.0,
            crop_type="onion",
            quality_grade="A",
            moisture=12.5,
            price=5000.0,
            timestamp=now - timedelta(hours=2),
            sync_status=SyncStatus.PENDING
        )
        
        txn2 = Transaction(
            transaction_id="TXN002",
            farmer_id="FARMER#001",
            fpo_id="FPO#001",
            quantity=150.0,
            crop_type="wheat",
            quality_grade="B",
            moisture=14.0,
            price=6000.0,
            timestamp=now - timedelta(hours=1),
            sync_status=SyncStatus.PENDING
        )
        
        txn3 = Transaction(
            transaction_id="TXN003",
            farmer_id="FARMER#001",
            fpo_id="FPO#001",
            quantity=200.0,
            crop_type="rice",
            quality_grade="A",
            moisture=13.0,
            price=7000.0,
            timestamp=now,
            sync_status=SyncStatus.PENDING
        )
        
        # Store in random order
        sync_manager.store_offline_transaction(txn2)
        sync_manager.store_offline_transaction(txn1)
        sync_manager.store_offline_transaction(txn3)
        
        # Synchronize
        result = sync_manager.synchronize_data()
        
        # Check that all were synced
        assert result.success_count == 3
        
        # Verify order by checking put_item calls
        calls = mock_dynamodb_table.put_item.call_args_list
        assert len(calls) == 3
        
        # Extract timestamps from calls
        timestamps = []
        for call in calls:
            item = call[1]['Item']
            timestamps.append(item['timestamp'])
        
        # Verify chronological order
        assert timestamps[0] < timestamps[1] < timestamps[2]
    
    def test_synchronize_updates_local_status(self, sync_manager, sample_transaction, temp_db_path):
        """Test that local sync status is updated after successful sync."""
        local_id = sync_manager.store_offline_transaction(sample_transaction)
        
        # Synchronize
        sync_manager.synchronize_data()
        
        # Check database
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT sync_status FROM offline_transactions WHERE local_id = ?", (local_id,))
        result = cursor.fetchone()
        conn.close()
        
        assert result[0] == 'synced'
    
    def test_synchronize_without_connectivity(self, sync_manager, sample_transaction, mock_dynamodb_table):
        """Test synchronization fails gracefully without connectivity."""
        # Store a transaction
        sync_manager.store_offline_transaction(sample_transaction)
        
        # Simulate no connectivity
        type(mock_dynamodb_table).table_status = property(
            lambda self: (_ for _ in ()).throw(Exception("No connection"))
        )
        
        # Synchronize
        result = sync_manager.synchronize_data()
        
        assert result.success_count == 0
        assert result.failure_count == 0


class TestResolveConflict:
    """Test resolve_conflict method."""
    
    def test_resolve_conflict_local_wins(self, sync_manager):
        """Test conflict resolution when local data is newer."""
        now = datetime.utcnow()
        
        local_data = {
            'transaction_id': 'TXN001',
            'farmer_id': 'FARMER#001',
            'quantity': 100.0,
            'timestamp': now.isoformat()
        }
        
        cloud_data = {
            'transaction_id': 'TXN001',
            'farmer_id': 'FARMER#001',
            'quantity': 90.0,
            'timestamp': (now - timedelta(hours=1)).isoformat()
        }
        
        result = sync_manager.resolve_conflict(local_data, cloud_data)
        
        assert result == local_data
        assert result['quantity'] == 100.0
    
    def test_resolve_conflict_cloud_wins(self, sync_manager):
        """Test conflict resolution when cloud data is newer."""
        now = datetime.utcnow()
        
        local_data = {
            'transaction_id': 'TXN001',
            'farmer_id': 'FARMER#001',
            'quantity': 100.0,
            'timestamp': (now - timedelta(hours=1)).isoformat()
        }
        
        cloud_data = {
            'transaction_id': 'TXN001',
            'farmer_id': 'FARMER#001',
            'quantity': 90.0,
            'timestamp': now.isoformat()
        }
        
        result = sync_manager.resolve_conflict(local_data, cloud_data)
        
        assert result == cloud_data
        assert result['quantity'] == 90.0
    
    def test_resolve_conflict_equal_timestamps(self, sync_manager):
        """Test conflict resolution when timestamps are equal (local wins)."""
        now = datetime.utcnow()
        
        local_data = {
            'transaction_id': 'TXN001',
            'farmer_id': 'FARMER#001',
            'quantity': 100.0,
            'timestamp': now.isoformat()
        }
        
        cloud_data = {
            'transaction_id': 'TXN001',
            'farmer_id': 'FARMER#001',
            'quantity': 90.0,
            'timestamp': now.isoformat()
        }
        
        result = sync_manager.resolve_conflict(local_data, cloud_data)
        
        # With equal timestamps, local wins (>=)
        assert result == local_data
    
    def test_resolve_conflict_logs_to_dynamodb(self, sync_manager, mock_dynamodb_table):
        """Test that conflicts are logged to DynamoDB."""
        now = datetime.utcnow()
        
        local_data = {
            'transaction_id': 'TXN001',
            'farmer_id': 'FARMER#001',
            'quantity': 100.0,
            'timestamp': now.isoformat()
        }
        
        cloud_data = {
            'transaction_id': 'TXN001',
            'farmer_id': 'FARMER#001',
            'quantity': 90.0,
            'timestamp': (now - timedelta(hours=1)).isoformat()
        }
        
        sync_manager.resolve_conflict(local_data, cloud_data)
        
        # Check that conflict was logged
        assert mock_dynamodb_table.put_item.called
        call_args = mock_dynamodb_table.put_item.call_args
        item = call_args[1]['Item']
        
        assert item['PK'].startswith('CONFLICT#')
        assert item['SK'].startswith('LOG#')
        assert item['transaction_id'] == 'TXN001'
        assert item['winner'] == 'local'


class TestSyncResultNotification:
    """Test sync result notification."""
    
    def test_sync_result_includes_all_fields(self, sync_manager, sample_transaction):
        """Test that SyncResult includes all required fields."""
        sync_manager.store_offline_transaction(sample_transaction)
        
        result = sync_manager.synchronize_data()
        
        assert hasattr(result, 'success_count')
        assert hasattr(result, 'failure_count')
        assert hasattr(result, 'conflicts')
        assert hasattr(result, 'sync_timestamp')
        assert isinstance(result.sync_timestamp, datetime)


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_store_transaction_with_missing_optional_fields(self, sync_manager):
        """Test storing transaction without optional fields."""
        txn = Transaction(
            transaction_id="TXN001",
            farmer_id="FARMER#001",
            fpo_id="FPO#001",
            quantity=100.0,
            crop_type="onion",
            quality_grade="A",
            moisture=12.5,
            price=5000.0,
            timestamp=datetime.utcnow(),
            ledger_image_url=None,  # Optional field
            sync_status=SyncStatus.PENDING
        )
        
        local_id = sync_manager.store_offline_transaction(txn)
        
        assert local_id is not None
    
    def test_synchronize_with_partial_failures(self, sync_manager, mock_dynamodb_table):
        """Test synchronization with some failures."""
        # Store multiple transactions
        now = datetime.utcnow()
        
        for i in range(3):
            txn = Transaction(
                transaction_id=f"TXN{i:03d}",
                farmer_id="FARMER#001",
                fpo_id="FPO#001",
                quantity=100.0 + i,
                crop_type="onion",
                quality_grade="A",
                moisture=12.5,
                price=5000.0,
                timestamp=now + timedelta(minutes=i),
                sync_status=SyncStatus.PENDING
            )
            sync_manager.store_offline_transaction(txn)
        
        # Make second upload fail
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Upload failed")
        
        mock_dynamodb_table.put_item.side_effect = side_effect
        
        # Synchronize
        result = sync_manager.synchronize_data()
        
        # Should have 2 successes and 1 failure
        assert result.success_count == 2
        assert result.failure_count == 1
    
    def test_empty_database_synchronization(self, sync_manager):
        """Test synchronization with empty local database."""
        result = sync_manager.synchronize_data()
        
        assert result.success_count == 0
        assert result.failure_count == 0
        assert len(result.conflicts) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
