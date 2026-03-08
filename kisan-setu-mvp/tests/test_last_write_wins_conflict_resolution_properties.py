"""
Property-based tests for last-write-wins conflict resolution (Property 13).

This module tests that conflicts are resolved using last-write-wins strategy
based on timestamps, and that conflicts are logged for audit purposes.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

import pytest
import sqlite3
import json
import tempfile
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, call
from decimal import Decimal

# Import generators
from generators import transaction_data, conflicting_transactions

# Import models and sync manager
from common.models import Transaction, SyncStatus
from sync.sync_manager import SyncManager


class TestLastWriteWinsConflictResolution:
    """
    Property-based tests for last-write-wins conflict resolution.
    
    **Validates: Requirements 4.5**
    """
    
    @given(conflicting_transactions())
    @settings(max_examples=100)
    def test_property_13_last_write_wins_resolution(self, conflict_pair):
        """
        Property 13: Last-Write-Wins Conflict Resolution
        
        For any pair of conflicting transactions (same transaction_id, different data),
        the conflict resolution should select the transaction with the most recent
        timestamp and log the conflict.
        
        **Validates: Requirements 4.5**
        """
        txn1, txn2 = conflict_pair
        
        # Ensure txn2 has later timestamp (generator should do this, but verify)
        assume(txn2.timestamp > txn1.timestamp)
        
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_conflict_resolution.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            
            # Track put_item calls to verify conflict logging
            put_item_calls = []
            
            def track_put_item(Item):
                put_item_calls.append(Item.copy())
            
            mock_table.put_item = Mock(side_effect=track_put_item)
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_conflict", temp_db)
            
            # Prepare transaction data as dicts
            local_data = {
                'transaction_id': txn1.transaction_id,
                'farmer_id': txn1.farmer_id,
                'fpo_id': txn1.fpo_id,
                'quantity': float(txn1.quantity),
                'crop_type': txn1.crop_type,
                'quality_grade': txn1.quality_grade,
                'moisture': float(txn1.moisture),
                'price': float(txn1.price),
                'timestamp': txn1.timestamp.isoformat(),
                'sync_status': txn1.sync_status.value
            }
            
            cloud_data = {
                'transaction_id': txn2.transaction_id,
                'farmer_id': txn2.farmer_id,
                'fpo_id': txn2.fpo_id,
                'quantity': float(txn2.quantity),
                'crop_type': txn2.crop_type,
                'quality_grade': txn2.quality_grade,
                'moisture': float(txn2.moisture),
                'price': float(txn2.price),
                'timestamp': txn2.timestamp.isoformat(),
                'sync_status': txn2.sync_status.value
            }
            
            # Resolve conflict
            resolved = sync_manager.resolve_conflict(local_data, cloud_data)
            
            # Verify last-write-wins: txn2 (cloud) should win since it has later timestamp
            assert resolved['transaction_id'] == txn2.transaction_id, \
                "Resolved transaction should have the same transaction_id"
            
            resolved_timestamp = datetime.fromisoformat(resolved['timestamp'])
            assert resolved_timestamp == txn2.timestamp, \
                f"Resolved transaction should have the latest timestamp: " \
                f"expected {txn2.timestamp}, got {resolved_timestamp}"
            
            # Verify the winner is the one with the latest timestamp
            assert resolved['timestamp'] == cloud_data['timestamp'], \
                "Cloud data with later timestamp should win"
            
            # Verify conflict was logged
            conflict_logs = [
                item for item in put_item_calls
                if item.get('PK', '').startswith('CONFLICT#')
            ]
            
            assert len(conflict_logs) >= 1, \
                "Conflict should be logged to DynamoDB"
            
            # Verify conflict log contains required information
            conflict_log = conflict_logs[0]
            assert conflict_log['transaction_id'] == txn1.transaction_id, \
                "Conflict log should contain transaction_id"
            assert conflict_log['local_timestamp'] == local_data['timestamp'], \
                "Conflict log should contain local timestamp"
            assert conflict_log['cloud_timestamp'] == cloud_data['timestamp'], \
                "Conflict log should contain cloud timestamp"
            assert conflict_log['winner'] in ['local', 'cloud'], \
                "Conflict log should specify winner"
            assert conflict_log['resolution_strategy'] == 'last_write_wins', \
                "Conflict log should specify resolution strategy"
    
    @given(conflicting_transactions())
    @settings(max_examples=100)
    def test_property_13_local_wins_when_newer(self, conflict_pair):
        """
        Property 13: Last-Write-Wins Conflict Resolution (Local Wins)
        
        For any pair of conflicting transactions where local data has a more
        recent timestamp than cloud data, the local data should win.
        
        **Validates: Requirements 4.5**
        """
        txn1, txn2 = conflict_pair
        
        # Swap so txn1 (local) has later timestamp
        if txn1.timestamp < txn2.timestamp:
            txn1, txn2 = txn2, txn1
        
        assume(txn1.timestamp > txn2.timestamp)
        
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_local_wins.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            
            # Track conflict logs
            conflict_logs = []
            
            def track_put_item(Item):
                if Item.get('PK', '').startswith('CONFLICT#'):
                    conflict_logs.append(Item.copy())
            
            mock_table.put_item = Mock(side_effect=track_put_item)
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_local_wins", temp_db)
            
            # Prepare data (txn1 is local, txn2 is cloud)
            local_data = {
                'transaction_id': txn1.transaction_id,
                'farmer_id': txn1.farmer_id,
                'fpo_id': txn1.fpo_id,
                'quantity': float(txn1.quantity),
                'timestamp': txn1.timestamp.isoformat(),
                'price': float(txn1.price)
            }
            
            cloud_data = {
                'transaction_id': txn2.transaction_id,
                'farmer_id': txn2.farmer_id,
                'fpo_id': txn2.fpo_id,
                'quantity': float(txn2.quantity),
                'timestamp': txn2.timestamp.isoformat(),
                'price': float(txn2.price)
            }
            
            # Resolve conflict
            resolved = sync_manager.resolve_conflict(local_data, cloud_data)
            
            # Verify local wins
            assert resolved['timestamp'] == local_data['timestamp'], \
                "Local data with later timestamp should win"
            
            # Verify conflict logged with correct winner
            assert len(conflict_logs) >= 1, \
                "Conflict should be logged"
            
            assert conflict_logs[0]['winner'] == 'local', \
                "Conflict log should indicate local data won"
    
    @given(conflicting_transactions())
    @settings(max_examples=100)
    def test_property_13_cloud_wins_when_newer(self, conflict_pair):
        """
        Property 13: Last-Write-Wins Conflict Resolution (Cloud Wins)
        
        For any pair of conflicting transactions where cloud data has a more
        recent timestamp than local data, the cloud data should win.
        
        **Validates: Requirements 4.5**
        """
        txn1, txn2 = conflict_pair
        
        # Ensure txn2 (cloud) has later timestamp
        assume(txn2.timestamp > txn1.timestamp)
        
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_cloud_wins.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            
            # Track conflict logs
            conflict_logs = []
            
            def track_put_item(Item):
                if Item.get('PK', '').startswith('CONFLICT#'):
                    conflict_logs.append(Item.copy())
            
            mock_table.put_item = Mock(side_effect=track_put_item)
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_cloud_wins", temp_db)
            
            # Prepare data (txn1 is local, txn2 is cloud)
            local_data = {
                'transaction_id': txn1.transaction_id,
                'farmer_id': txn1.farmer_id,
                'timestamp': txn1.timestamp.isoformat(),
                'quantity': float(txn1.quantity)
            }
            
            cloud_data = {
                'transaction_id': txn2.transaction_id,
                'farmer_id': txn2.farmer_id,
                'timestamp': txn2.timestamp.isoformat(),
                'quantity': float(txn2.quantity)
            }
            
            # Resolve conflict
            resolved = sync_manager.resolve_conflict(local_data, cloud_data)
            
            # Verify cloud wins
            assert resolved['timestamp'] == cloud_data['timestamp'], \
                "Cloud data with later timestamp should win"
            
            # Verify conflict logged with correct winner
            assert len(conflict_logs) >= 1, \
                "Conflict should be logged"
            
            assert conflict_logs[0]['winner'] == 'cloud', \
                "Conflict log should indicate cloud data won"
    
    @given(st.lists(conflicting_transactions(), min_size=2, max_size=5))
    @settings(max_examples=100)
    def test_property_13_multiple_conflicts_all_logged(self, conflict_pairs):
        """
        Property 13: Last-Write-Wins Conflict Resolution (Multiple Conflicts)
        
        For any set of conflicting transaction pairs, each conflict should be
        resolved independently and all conflicts should be logged.
        
        **Validates: Requirements 4.5**
        """
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_multiple_conflicts.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            
            # Track all conflict logs
            all_conflict_logs = []
            
            def track_put_item(Item):
                if Item.get('PK', '').startswith('CONFLICT#'):
                    all_conflict_logs.append(Item.copy())
            
            mock_table.put_item = Mock(side_effect=track_put_item)
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_multiple", temp_db)
            
            # Resolve each conflict
            resolutions = []
            for txn1, txn2 in conflict_pairs:
                # Ensure different timestamps
                assume(txn1.timestamp != txn2.timestamp)
                
                local_data = {
                    'transaction_id': txn1.transaction_id,
                    'timestamp': txn1.timestamp.isoformat(),
                    'farmer_id': txn1.farmer_id
                }
                
                cloud_data = {
                    'transaction_id': txn2.transaction_id,
                    'timestamp': txn2.timestamp.isoformat(),
                    'farmer_id': txn2.farmer_id
                }
                
                resolved = sync_manager.resolve_conflict(local_data, cloud_data)
                resolutions.append(resolved)
            
            # Verify all conflicts were logged
            assert len(all_conflict_logs) == len(conflict_pairs), \
                f"All {len(conflict_pairs)} conflicts should be logged, " \
                f"got {len(all_conflict_logs)} logs"
            
            # Verify each resolution chose the latest timestamp
            for i, (txn1, txn2) in enumerate(conflict_pairs):
                resolved = resolutions[i]
                resolved_ts = datetime.fromisoformat(resolved['timestamp'])
                
                latest_ts = max(txn1.timestamp, txn2.timestamp)
                assert resolved_ts == latest_ts, \
                    f"Conflict {i} should resolve to latest timestamp"
    
    @given(transaction_data(), transaction_data())
    @settings(max_examples=100)
    def test_property_13_equal_timestamps_handled(self, txn1, txn2):
        """
        Property 13: Last-Write-Wins Conflict Resolution (Equal Timestamps)
        
        For any pair of conflicting transactions with equal timestamps,
        the conflict should be resolved (one should be chosen) and logged.
        
        **Validates: Requirements 4.5**
        """
        # Make them conflicting (same ID)
        txn2.transaction_id = txn1.transaction_id
        txn2.farmer_id = txn1.farmer_id
        txn2.fpo_id = txn1.fpo_id
        
        # Set equal timestamps
        txn2.timestamp = txn1.timestamp
        
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_equal_timestamps.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            
            # Track conflict logs
            conflict_logs = []
            
            def track_put_item(Item):
                if Item.get('PK', '').startswith('CONFLICT#'):
                    conflict_logs.append(Item.copy())
            
            mock_table.put_item = Mock(side_effect=track_put_item)
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_equal_ts", temp_db)
            
            # Prepare data
            local_data = {
                'transaction_id': txn1.transaction_id,
                'timestamp': txn1.timestamp.isoformat(),
                'quantity': float(txn1.quantity)
            }
            
            cloud_data = {
                'transaction_id': txn2.transaction_id,
                'timestamp': txn2.timestamp.isoformat(),
                'quantity': float(txn2.quantity)
            }
            
            # Resolve conflict
            resolved = sync_manager.resolve_conflict(local_data, cloud_data)
            
            # Verify a resolution was made (one of the two should be chosen)
            assert resolved is not None, \
                "Conflict should be resolved even with equal timestamps"
            
            assert resolved['transaction_id'] == txn1.transaction_id, \
                "Resolved transaction should have the correct ID"
            
            # Verify conflict was logged
            assert len(conflict_logs) >= 1, \
                "Conflict should be logged even with equal timestamps"
    
    @given(conflicting_transactions())
    @settings(max_examples=100)
    def test_property_13_conflict_log_contains_audit_info(self, conflict_pair):
        """
        Property 13: Last-Write-Wins Conflict Resolution (Audit Information)
        
        For any conflict resolution, the conflict log should contain complete
        audit information including transaction_id, both timestamps, winner,
        and resolution strategy.
        
        **Validates: Requirements 4.5**
        """
        txn1, txn2 = conflict_pair
        assume(txn1.timestamp != txn2.timestamp)
        
        # Create temporary database path
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = os.path.join(tmpdir, "test_audit_info.db")
        
            # Create mock DynamoDB table
            mock_table = Mock()
            mock_table.table_status = 'ACTIVE'
            
            # Track conflict logs
            conflict_logs = []
            
            def track_put_item(Item):
                if Item.get('PK', '').startswith('CONFLICT#'):
                    conflict_logs.append(Item.copy())
            
            mock_table.put_item = Mock(side_effect=track_put_item)
            
            # Create sync manager
            sync_manager = SyncManager(mock_table, "test_device_audit", temp_db)
            
            # Prepare data
            local_data = {
                'transaction_id': txn1.transaction_id,
                'timestamp': txn1.timestamp.isoformat(),
                'farmer_id': txn1.farmer_id
            }
            
            cloud_data = {
                'transaction_id': txn2.transaction_id,
                'timestamp': txn2.timestamp.isoformat(),
                'farmer_id': txn2.farmer_id
            }
            
            # Resolve conflict
            sync_manager.resolve_conflict(local_data, cloud_data)
            
            # Verify conflict log exists
            assert len(conflict_logs) >= 1, \
                "Conflict log should be created"
            
            log = conflict_logs[0]
            
            # Verify required audit fields
            assert 'transaction_id' in log, \
                "Conflict log should contain transaction_id"
            assert log['transaction_id'] == txn1.transaction_id, \
                "Conflict log should have correct transaction_id"
            
            assert 'local_timestamp' in log, \
                "Conflict log should contain local_timestamp"
            assert log['local_timestamp'] == local_data['timestamp'], \
                "Conflict log should have correct local_timestamp"
            
            assert 'cloud_timestamp' in log, \
                "Conflict log should contain cloud_timestamp"
            assert log['cloud_timestamp'] == cloud_data['timestamp'], \
                "Conflict log should have correct cloud_timestamp"
            
            assert 'winner' in log, \
                "Conflict log should contain winner"
            assert log['winner'] in ['local', 'cloud'], \
                "Winner should be either 'local' or 'cloud'"
            
            assert 'resolution_strategy' in log, \
                "Conflict log should contain resolution_strategy"
            assert log['resolution_strategy'] == 'last_write_wins', \
                "Resolution strategy should be 'last_write_wins'"
            
            assert 'device_id' in log, \
                "Conflict log should contain device_id"
            
            # Verify PK and SK format for audit trail
            assert log['PK'].startswith('CONFLICT#'), \
                "Conflict log PK should start with 'CONFLICT#'"
            assert log['SK'].startswith('LOG#'), \
                "Conflict log SK should start with 'LOG#'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
