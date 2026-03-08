"""
Sync Manager Component
Handles offline-first data synchronization for tablet applications
"""

import json
import boto3
import os
import sqlite3
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from common.models import Transaction, SyncStatus

# AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'KisanSetuData')
REGION = os.environ.get('REGION', 'ap-south-1')
LOCAL_DB_PATH = os.environ.get('LOCAL_DB_PATH', '/tmp/offline_sync.db')

table = dynamodb.Table(DYNAMODB_TABLE)


@dataclass
class SyncResult:
    """Result of a synchronization operation."""
    success_count: int
    failure_count: int
    conflicts: List[Dict[str, Any]]
    sync_timestamp: datetime


@dataclass
class OfflineTransaction:
    """Transaction stored locally during offline mode."""
    local_id: str
    transaction_data: Dict[str, Any]
    timestamp: datetime
    sync_status: str
    retry_count: int


class SyncManager:
    """
    Sync Manager Component for offline-first data synchronization.
    
    Responsibilities:
    - Manage offline data storage on tablets
    - Detect connectivity changes
    - Synchronize offline data to cloud
    - Resolve conflicts using last-write-wins strategy
    """
    
    def __init__(self, dynamodb_table, device_id: str, local_db_path: str = LOCAL_DB_PATH):
        """
        Initialize Sync Manager.
        
        Args:
            dynamodb_table: DynamoDB table resource
            device_id: Unique identifier for the device
            local_db_path: Path to local SQLite database
        """
        self.table = dynamodb_table
        self.device_id = device_id
        self.local_db_path = local_db_path
        self.offline_mode = False
        self._init_local_db()
    
    def _init_local_db(self):
        """Initialize local SQLite database for offline storage."""
        conn = sqlite3.connect(self.local_db_path)
        cursor = conn.cursor()
        
        # Create offline transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS offline_transactions (
                local_id TEXT PRIMARY KEY,
                transaction_data TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                sync_status TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0
            )
        ''')
        
        # Create sync metadata table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def enable_offline_mode(self) -> bool:
        """
        Switch to offline mode, enable local storage.
        
        Returns:
            Success status
        """
        try:
            self.offline_mode = True
            
            # Store offline mode status in local DB
            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO sync_metadata (key, value) VALUES (?, ?)',
                ('offline_mode', 'true')
            )
            conn.commit()
            conn.close()
            
            print(f"Offline mode enabled for device {self.device_id}")
            return True
        except Exception as e:
            print(f"Error enabling offline mode: {str(e)}")
            return False
    
    def store_offline_transaction(self, transaction: Transaction) -> str:
        """
        Store transaction locally with timestamp.
        
        Args:
            transaction: Transaction object to store
            
        Returns:
            Local transaction ID
        """
        try:
            # Generate local ID
            local_id = f"{self.device_id}#{transaction.transaction_id}#{int(datetime.utcnow().timestamp())}"
            
            # Convert transaction to dict
            transaction_data = {
                'transaction_id': transaction.transaction_id,
                'farmer_id': transaction.farmer_id,
                'fpo_id': transaction.fpo_id,
                'quantity': float(transaction.quantity),
                'crop_type': transaction.crop_type,
                'quality_grade': transaction.quality_grade,
                'moisture': float(transaction.moisture),
                'price': float(transaction.price),
                'timestamp': transaction.timestamp.isoformat(),
                'ledger_image_url': transaction.ledger_image_url,
                'sync_status': transaction.sync_status.value
            }
            
            # Store in local database
            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO offline_transactions 
                   (local_id, transaction_data, timestamp, sync_status, retry_count)
                   VALUES (?, ?, ?, ?, ?)''',
                (local_id, json.dumps(transaction_data), transaction.timestamp.isoformat(), 
                 'pending', 0)
            )
            conn.commit()
            conn.close()
            
            print(f"Stored offline transaction: {local_id}")
            return local_id
        except Exception as e:
            print(f"Error storing offline transaction: {str(e)}")
            raise
    
    def detect_connectivity(self) -> bool:
        """
        Check for internet connectivity.
        
        Returns:
            True if connected, False otherwise
        """
        try:
            # Try to describe the DynamoDB table
            self.table.table_status
            return True
        except Exception as e:
            print(f"No connectivity detected: {str(e)}")
            return False
    
    def synchronize_data(self) -> SyncResult:
        """
        Upload all offline transactions to cloud via DynamoDB.
        
        Returns:
            SyncResult with success_count, failure_count, conflicts
        """
        success_count = 0
        failure_count = 0
        conflicts = []
        
        try:
            # Check connectivity
            if not self.detect_connectivity():
                print("Cannot synchronize: No connectivity")
                return SyncResult(
                    success_count=0,
                    failure_count=0,
                    conflicts=[],
                    sync_timestamp=datetime.utcnow()
                )
            
            # Get all pending transactions from local DB
            pending_transactions = self._get_pending_transactions()
            
            if not pending_transactions:
                print("No pending transactions to sync")
                return SyncResult(
                    success_count=0,
                    failure_count=0,
                    conflicts=[],
                    sync_timestamp=datetime.utcnow()
                )
            
            # Sort by timestamp (chronological order)
            pending_transactions.sort(key=lambda x: x.timestamp)
            
            print(f"Synchronizing {len(pending_transactions)} transactions...")
            
            # Upload each transaction
            for offline_txn in pending_transactions:
                try:
                    transaction_data = offline_txn.transaction_data
                    
                    # Check for conflicts
                    cloud_data = self._get_cloud_transaction(transaction_data['transaction_id'])
                    
                    if cloud_data:
                        # Conflict detected - resolve using last-write-wins
                        resolved_data = self.resolve_conflict(transaction_data, cloud_data)
                        
                        # Log conflict
                        conflict_info = {
                            'transaction_id': transaction_data['transaction_id'],
                            'local_timestamp': transaction_data['timestamp'],
                            'cloud_timestamp': cloud_data.get('timestamp'),
                            'resolution': 'last_write_wins',
                            'winner': 'local' if resolved_data == transaction_data else 'cloud'
                        }
                        conflicts.append(conflict_info)
                        
                        # Use resolved data
                        transaction_data = resolved_data
                    
                    # Upload to DynamoDB
                    self._upload_transaction(transaction_data)
                    
                    # Mark as synced in local DB
                    self._update_local_sync_status(offline_txn.local_id, 'synced')
                    
                    success_count += 1
                    print(f"Synced transaction: {transaction_data['transaction_id']}")
                    
                except Exception as e:
                    print(f"Error syncing transaction {offline_txn.local_id}: {str(e)}")
                    
                    # Increment retry count
                    self._increment_retry_count(offline_txn.local_id)
                    
                    failure_count += 1
            
            # Disable offline mode if sync successful
            if success_count > 0 and failure_count == 0:
                self.offline_mode = False
                self._update_offline_mode_status(False)
            
            sync_result = SyncResult(
                success_count=success_count,
                failure_count=failure_count,
                conflicts=conflicts,
                sync_timestamp=datetime.utcnow()
            )
            
            # Notify user of sync status
            self._notify_sync_status(sync_result)
            
            return sync_result
            
        except Exception as e:
            print(f"Error during synchronization: {str(e)}")
            return SyncResult(
                success_count=success_count,
                failure_count=failure_count,
                conflicts=conflicts,
                sync_timestamp=datetime.utcnow()
            )
    
    def resolve_conflict(self, local_data: Dict[str, Any], 
                        cloud_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve conflicts using last-write-wins strategy.
        
        Args:
            local_data: Transaction data from local storage
            cloud_data: Transaction data from cloud
            
        Returns:
            Resolved transaction data
        """
        try:
            # Parse timestamps
            local_timestamp = datetime.fromisoformat(local_data['timestamp'])
            cloud_timestamp = datetime.fromisoformat(cloud_data.get('timestamp', '1970-01-01T00:00:00'))
            
            # Last-write-wins: choose the most recent
            if local_timestamp >= cloud_timestamp:
                winner = local_data
                winner_source = 'local'
            else:
                winner = cloud_data
                winner_source = 'cloud'
            
            # Log conflict resolution
            print(f"Conflict resolved for transaction {local_data['transaction_id']}: "
                  f"{winner_source} data wins (local: {local_timestamp}, cloud: {cloud_timestamp})")
            
            # Store conflict log in DynamoDB
            self._log_conflict(local_data, cloud_data, winner_source)
            
            return winner
            
        except Exception as e:
            print(f"Error resolving conflict: {str(e)}")
            # Default to local data if error
            return local_data
    
    # Private helper methods
    
    def _get_pending_transactions(self) -> List[OfflineTransaction]:
        """Get all pending transactions from local database."""
        try:
            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT local_id, transaction_data, timestamp, sync_status, retry_count '
                'FROM offline_transactions WHERE sync_status = ?',
                ('pending',)
            )
            rows = cursor.fetchall()
            conn.close()
            
            transactions = []
            for row in rows:
                transactions.append(OfflineTransaction(
                    local_id=row[0],
                    transaction_data=json.loads(row[1]),
                    timestamp=datetime.fromisoformat(row[2]),
                    sync_status=row[3],
                    retry_count=row[4]
                ))
            
            return transactions
        except Exception as e:
            print(f"Error getting pending transactions: {str(e)}")
            return []
    
    def _get_cloud_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Check if transaction exists in cloud."""
        try:
            # Extract farmer_id from transaction_id (assuming format: FARMER#xxx)
            # For now, we'll query using GSI or scan (not optimal, but works for MVP)
            # In production, we'd need the farmer_id to construct the PK
            
            # This is a simplified implementation
            # In production, transaction_id should include farmer_id
            return None
        except Exception as e:
            print(f"Error checking cloud transaction: {str(e)}")
            return None
    
    def _upload_transaction(self, transaction_data: Dict[str, Any]):
        """Upload transaction to DynamoDB."""
        try:
            # Convert to DynamoDB format
            item = {
                'PK': transaction_data['farmer_id'],
                'SK': f"TXN#{transaction_data['timestamp']}",
                'transaction_id': transaction_data['transaction_id'],
                'fpo_id': transaction_data['fpo_id'],
                'quantity': Decimal(str(transaction_data['quantity'])),
                'crop_type': transaction_data['crop_type'],
                'quality_grade': transaction_data['quality_grade'],
                'moisture': Decimal(str(transaction_data['moisture'])),
                'price': Decimal(str(transaction_data['price'])),
                'timestamp': transaction_data['timestamp'],
                'sync_status': 'synced'
            }
            
            if transaction_data.get('ledger_image_url'):
                item['ledger_image_url'] = transaction_data['ledger_image_url']
            
            self.table.put_item(Item=item)
        except Exception as e:
            print(f"Error uploading transaction: {str(e)}")
            raise
    
    def _update_local_sync_status(self, local_id: str, status: str):
        """Update sync status in local database."""
        try:
            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE offline_transactions SET sync_status = ? WHERE local_id = ?',
                (status, local_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error updating sync status: {str(e)}")
    
    def _increment_retry_count(self, local_id: str):
        """Increment retry count for failed transaction."""
        try:
            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE offline_transactions SET retry_count = retry_count + 1 WHERE local_id = ?',
                (local_id,)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error incrementing retry count: {str(e)}")
    
    def _update_offline_mode_status(self, offline: bool):
        """Update offline mode status in local database."""
        try:
            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO sync_metadata (key, value) VALUES (?, ?)',
                ('offline_mode', 'true' if offline else 'false')
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error updating offline mode status: {str(e)}")
    
    def _log_conflict(self, local_data: Dict[str, Any], cloud_data: Dict[str, Any], 
                     winner: str):
        """Log conflict to DynamoDB for audit purposes."""
        try:
            conflict_log = {
                'PK': f"CONFLICT#{self.device_id}",
                'SK': f"LOG#{datetime.utcnow().isoformat()}",
                'transaction_id': local_data['transaction_id'],
                'local_timestamp': local_data['timestamp'],
                'cloud_timestamp': cloud_data.get('timestamp'),
                'winner': winner,
                'resolution_strategy': 'last_write_wins',
                'device_id': self.device_id
            }
            
            self.table.put_item(Item=conflict_log)
        except Exception as e:
            print(f"Error logging conflict: {str(e)}")
    
    def _notify_sync_status(self, sync_result: SyncResult):
        """Notify user of sync status."""
        # TODO: Implement notification (SNS, WhatsApp, etc.)
        print(f"SYNC COMPLETE: {sync_result.success_count} succeeded, "
              f"{sync_result.failure_count} failed, "
              f"{len(sync_result.conflicts)} conflicts resolved")


def handler(event, context):
    """Lambda handler for sync operations"""
    
    try:
        print(f"Sync operation: {json.dumps(event)}")
        
        # Parse request
        body = json.loads(event.get('body', '{}'))
        operation = body.get('operation')
        device_id = body.get('device_id')
        
        if not device_id:
            return response(400, {'error': 'device_id required'})
        
        # Initialize Sync Manager
        sync_manager = SyncManager(table, device_id)
        
        # Handle different operations
        if operation == 'enable_offline':
            success = sync_manager.enable_offline_mode()
            return response(200, {'success': success, 'offline_mode': True})
        
        elif operation == 'store_transaction':
            transaction_data = body.get('transaction')
            if not transaction_data:
                return response(400, {'error': 'transaction data required'})
            
            # Create Transaction object
            transaction = Transaction(
                transaction_id=transaction_data['transaction_id'],
                farmer_id=transaction_data['farmer_id'],
                fpo_id=transaction_data['fpo_id'],
                quantity=transaction_data['quantity'],
                crop_type=transaction_data['crop_type'],
                quality_grade=transaction_data['quality_grade'],
                moisture=transaction_data['moisture'],
                price=transaction_data['price'],
                timestamp=datetime.fromisoformat(transaction_data['timestamp']),
                ledger_image_url=transaction_data.get('ledger_image_url'),
                sync_status=SyncStatus.PENDING
            )
            
            local_id = sync_manager.store_offline_transaction(transaction)
            return response(200, {'local_id': local_id})
        
        elif operation == 'check_connectivity':
            connected = sync_manager.detect_connectivity()
            return response(200, {'connected': connected})
        
        elif operation == 'synchronize':
            sync_result = sync_manager.synchronize_data()
            return response(200, {
                'success_count': sync_result.success_count,
                'failure_count': sync_result.failure_count,
                'conflicts': sync_result.conflicts,
                'sync_timestamp': sync_result.sync_timestamp.isoformat()
            })
        
        else:
            return response(400, {'error': f'Unknown operation: {operation}'})
    
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return response(500, {'error': str(e)})


def response(status_code: int, body: Any) -> Dict[str, Any]:
    """Format API Gateway response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body, default=str)
    }
