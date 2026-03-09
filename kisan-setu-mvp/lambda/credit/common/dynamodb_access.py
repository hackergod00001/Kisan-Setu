"""
DynamoDB access patterns for Kisan-Setu system.

This module implements the single-table design access patterns with PK/SK
structure as defined in the design document.
"""

import boto3
import os
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr

from .models import (
    Farmer, FPO, Transaction, ReliabilityScore, 
    NDVIResult, Message, AuditTrail, SyncStatus
)
from .validation import validate_gps_coordinates, validate_phone_number


# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'KisanSetuData')
table = dynamodb.Table(table_name)


class DynamoDBAccess:
    """Provides access patterns for DynamoDB single-table design."""
    
    def __init__(self, table_name: Optional[str] = None):
        """
        Initialize DynamoDB access.
        
        Args:
            table_name: Optional table name override
        """
        self.table_name = table_name or os.environ.get('DYNAMODB_TABLE_NAME', 'KisanSetuData')
        self.table = dynamodb.Table(self.table_name)
    
    # ==================== FPO Operations ====================
    
    def create_fpo(self, fpo: FPO, user_id: str) -> bool:
        """
        Create a new FPO record.
        
        Args:
            fpo: FPO object
            user_id: User creating the record
            
        Returns:
            True if successful, False otherwise
        """
        try:
            item = {
                'PK': f'FPO#{fpo.fpo_id}',
                'SK': 'METADATA',
                'entity_type': 'FPO',
                'fpo_id': fpo.fpo_id,
                'name': fpo.name,
                'location': fpo.location,
                'manager_contact': fpo.manager_contact,
                'created_date': fpo.created_date.isoformat(),
                'member_count': fpo.member_count,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            self.table.put_item(Item=item)
            
            # Create audit trail
            self._create_audit_trail(
                entity_type='FPO',
                entity_id=fpo.fpo_id,
                operation='create',
                user_id=user_id,
                changed_fields=item
            )
            
            return True
        except Exception as e:
            print(f"Error creating FPO: {e}")
            return False
    
    def get_fpo(self, fpo_id: str) -> Optional[FPO]:
        """
        Retrieve FPO by ID.
        
        Args:
            fpo_id: FPO identifier
            
        Returns:
            FPO object or None if not found
        """
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'FPO#{fpo_id}',
                    'SK': 'METADATA'
                }
            )
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            return FPO(
                fpo_id=item['fpo_id'],
                name=item['name'],
                location=item['location'],
                manager_contact=item['manager_contact'],
                created_date=date.fromisoformat(item['created_date']),
                member_count=int(item['member_count'])
            )
        except Exception as e:
            print(f"Error getting FPO: {e}")
            return None
    
    # ==================== Farmer Operations ====================
    
    def create_farmer(self, farmer: Farmer, user_id: str) -> bool:
        """
        Create a new farmer record.
        
        Args:
            farmer: Farmer object
            user_id: User creating the record
            
        Returns:
            True if successful, False otherwise
        """
        if not validate_gps_coordinates(farmer.gps_coords):
            print(f"Invalid GPS coordinates: {farmer.gps_coords}")
            return False
        
        if not validate_phone_number(farmer.phone):
            print(f"Invalid phone number: {farmer.phone}")
            return False
        
        try:
            item = {
                'PK': f'FARMER#{farmer.farmer_id}',
                'SK': 'METADATA',
                'entity_type': 'Farmer',
                'farmer_id': farmer.farmer_id,
                'name': farmer.name,
                'phone': farmer.phone,
                'fpo_id': farmer.fpo_id,
                'gps_latitude': Decimal(str(farmer.gps_coords[0])),
                'gps_longitude': Decimal(str(farmer.gps_coords[1])),
                'preferred_language': farmer.preferred_language,
                'join_date': farmer.join_date.isoformat(),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            self.table.put_item(Item=item)
            
            # Create GSI-1 entry for querying farmers by FPO
            gsi_item = {
                'PK': f'FARMER#{farmer.farmer_id}',
                'SK': 'GSI1',
                'fpo_id': farmer.fpo_id,
                'farmer_id': farmer.farmer_id
            }
            self.table.put_item(Item=gsi_item)
            
            # Create audit trail
            self._create_audit_trail(
                entity_type='Farmer',
                entity_id=farmer.farmer_id,
                operation='create',
                user_id=user_id,
                changed_fields=item
            )
            
            return True
        except Exception as e:
            print(f"Error creating farmer: {e}")
            return False
    
    def get_farmer(self, farmer_id: str) -> Optional[Farmer]:
        """
        Retrieve farmer by ID.
        
        Args:
            farmer_id: Farmer identifier
            
        Returns:
            Farmer object or None if not found
        """
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'FARMER#{farmer_id}',
                    'SK': 'METADATA'
                }
            )
            
            if 'Item' not in response:
                return None
            
            item = response['Item']
            return Farmer(
                farmer_id=item['farmer_id'],
                name=item['name'],
                phone=item['phone'],
                fpo_id=item['fpo_id'],
                gps_coords=(float(item['gps_latitude']), float(item['gps_longitude'])),
                preferred_language=item['preferred_language'],
                join_date=date.fromisoformat(item['join_date'])
            )
        except Exception as e:
            print(f"Error getting farmer: {e}")
            return None
    
    def get_farmers_by_fpo(self, fpo_id: str) -> List[Farmer]:
        """
        Retrieve all farmers belonging to an FPO.
        
        Args:
            fpo_id: FPO identifier
            
        Returns:
            List of Farmer objects
        """
        farmers = []
        try:
            # Query GSI-1 to get farmer IDs
            response = self.table.query(
                IndexName='GSI1',
                KeyConditionExpression=Key('fpo_id').eq(fpo_id)
            )
            
            # Fetch full farmer details
            for item in response.get('Items', []):
                farmer = self.get_farmer(item['farmer_id'])
                if farmer:
                    farmers.append(farmer)
            
            return farmers
        except Exception as e:
            print(f"Error getting farmers by FPO: {e}")
            return []
    
    # ==================== Transaction Operations ====================
    
    def create_transaction(self, transaction: Transaction, user_id: str) -> bool:
        """
        Create a new transaction record.
        
        Args:
            transaction: Transaction object
            user_id: User creating the record
            
        Returns:
            True if successful, False otherwise
        """
        try:
            timestamp_str = transaction.timestamp.isoformat()
            
            item = {
                'PK': f'FARMER#{transaction.farmer_id}',
                'SK': f'TXN#{timestamp_str}',
                'entity_type': 'Transaction',
                'transaction_id': transaction.transaction_id,
                'farmer_id': transaction.farmer_id,
                'fpo_id': transaction.fpo_id,
                'quantity': Decimal(str(transaction.quantity)),
                'crop_type': transaction.crop_type,
                'quality_grade': transaction.quality_grade,
                'moisture': Decimal(str(transaction.moisture)),
                'price': Decimal(str(transaction.price)),
                'timestamp': timestamp_str,
                'sync_status': transaction.sync_status.value,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if transaction.ledger_image_url:
                item['ledger_image_url'] = transaction.ledger_image_url
            
            self.table.put_item(Item=item)
            
            # Create GSI-2 entry for querying transactions by FPO and date
            gsi_item = {
                'PK': f'FARMER#{transaction.farmer_id}',
                'SK': f'GSI2#{timestamp_str}',
                'fpo_id': transaction.fpo_id,
                'timestamp': timestamp_str,
                'transaction_id': transaction.transaction_id
            }
            self.table.put_item(Item=gsi_item)
            
            # Create audit trail
            self._create_audit_trail(
                entity_type='Transaction',
                entity_id=transaction.transaction_id,
                operation='create',
                user_id=user_id,
                changed_fields=item
            )
            
            return True
        except Exception as e:
            print(f"Error creating transaction: {e}")
            return False
    
    def get_transactions(self, farmer_id: str, limit: int = 100) -> List[Transaction]:
        """
        Retrieve transactions for a farmer.
        
        Args:
            farmer_id: Farmer identifier
            limit: Maximum number of transactions to retrieve
            
        Returns:
            List of Transaction objects
        """
        transactions = []
        try:
            response = self.table.query(
                KeyConditionExpression=Key('PK').eq(f'FARMER#{farmer_id}') & 
                                     Key('SK').begins_with('TXN#'),
                Limit=limit,
                ScanIndexForward=False  # Most recent first
            )
            
            for item in response.get('Items', []):
                transactions.append(Transaction(
                    transaction_id=item['transaction_id'],
                    farmer_id=item['farmer_id'],
                    fpo_id=item['fpo_id'],
                    quantity=float(item['quantity']),
                    crop_type=item['crop_type'],
                    quality_grade=item['quality_grade'],
                    moisture=float(item['moisture']),
                    price=float(item['price']),
                    timestamp=datetime.fromisoformat(item['timestamp']),
                    ledger_image_url=item.get('ledger_image_url'),
                    sync_status=SyncStatus(item['sync_status'])
                ))
            
            return transactions
        except Exception as e:
            print(f"Error getting transactions: {e}")
            return []

    
    def get_transactions_by_date_range(
        self, 
        farmer_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Transaction]:
        """
        Retrieve transactions within a date range.
        
        Args:
            farmer_id: Farmer identifier
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            
        Returns:
            List of Transaction objects
        """
        transactions = []
        try:
            response = self.table.query(
                KeyConditionExpression=Key('PK').eq(f'FARMER#{farmer_id}') & 
                                     Key('SK').between(
                                         f'TXN#{start_date.isoformat()}',
                                         f'TXN#{end_date.isoformat()}'
                                     )
            )
            
            for item in response.get('Items', []):
                transactions.append(Transaction(
                    transaction_id=item['transaction_id'],
                    farmer_id=item['farmer_id'],
                    fpo_id=item['fpo_id'],
                    quantity=float(item['quantity']),
                    crop_type=item['crop_type'],
                    quality_grade=item['quality_grade'],
                    moisture=float(item['moisture']),
                    price=float(item['price']),
                    timestamp=datetime.fromisoformat(item['timestamp']),
                    ledger_image_url=item.get('ledger_image_url'),
                    sync_status=SyncStatus(item['sync_status'])
                ))
            
            return transactions
        except Exception as e:
            print(f"Error getting transactions by date range: {e}")
            return []
    
    # ==================== Credit Score Operations ====================
    
    def save_credit_score(self, score: ReliabilityScore, user_id: str) -> bool:
        """
        Save a reliability score for a farmer.
        
        Args:
            score: ReliabilityScore object
            user_id: User creating the record
            
        Returns:
            True if successful, False otherwise
        """
        try:
            date_str = score.calculation_date.isoformat()
            
            item = {
                'PK': f'FARMER#{score.farmer_id}',
                'SK': f'SCORE#{date_str}',
                'entity_type': 'ReliabilityScore',
                'farmer_id': score.farmer_id,
                'total_score': Decimal(str(score.total_score)),
                'supply_consistency': Decimal(str(score.supply_consistency)),
                'quality_metrics': Decimal(str(score.quality_metrics)),
                'transaction_history': Decimal(str(score.transaction_history)),
                'financial_behavior': Decimal(str(score.financial_behavior)),
                'operational_transparency': Decimal(str(score.operational_transparency)),
                'calculation_date': date_str,
                'score_change': Decimal(str(score.score_change)),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            self.table.put_item(Item=item)
            
            # Create audit trail
            self._create_audit_trail(
                entity_type='ReliabilityScore',
                entity_id=f'{score.farmer_id}#{date_str}',
                operation='create',
                user_id=user_id,
                changed_fields=item
            )
            
            return True
        except Exception as e:
            print(f"Error saving credit score: {e}")
            return False
    
    def get_credit_score(self, farmer_id: str) -> Optional[ReliabilityScore]:
        """
        Retrieve the most recent credit score for a farmer.
        
        Args:
            farmer_id: Farmer identifier
            
        Returns:
            ReliabilityScore object or None if not found
        """
        try:
            response = self.table.query(
                KeyConditionExpression=Key('PK').eq(f'FARMER#{farmer_id}') & 
                                     Key('SK').begins_with('SCORE#'),
                Limit=1,
                ScanIndexForward=False  # Most recent first
            )
            
            items = response.get('Items', [])
            if not items:
                return None
            
            item = items[0]
            return ReliabilityScore(
                farmer_id=item['farmer_id'],
                total_score=float(item['total_score']),
                supply_consistency=float(item['supply_consistency']),
                quality_metrics=float(item['quality_metrics']),
                transaction_history=float(item['transaction_history']),
                financial_behavior=float(item['financial_behavior']),
                operational_transparency=float(item['operational_transparency']),
                calculation_date=datetime.fromisoformat(item['calculation_date']),
                score_change=float(item['score_change'])
            )
        except Exception as e:
            print(f"Error getting credit score: {e}")
            return None
    
    def get_credit_score_history(self, farmer_id: str, limit: int = 10) -> List[ReliabilityScore]:
        """
        Retrieve credit score history for a farmer.
        
        Args:
            farmer_id: Farmer identifier
            limit: Maximum number of scores to retrieve
            
        Returns:
            List of ReliabilityScore objects
        """
        scores = []
        try:
            response = self.table.query(
                KeyConditionExpression=Key('PK').eq(f'FARMER#{farmer_id}') & 
                                     Key('SK').begins_with('SCORE#'),
                Limit=limit,
                ScanIndexForward=False  # Most recent first
            )
            
            for item in response.get('Items', []):
                scores.append(ReliabilityScore(
                    farmer_id=item['farmer_id'],
                    total_score=float(item['total_score']),
                    supply_consistency=float(item['supply_consistency']),
                    quality_metrics=float(item['quality_metrics']),
                    transaction_history=float(item['transaction_history']),
                    financial_behavior=float(item['financial_behavior']),
                    operational_transparency=float(item['operational_transparency']),
                    calculation_date=datetime.fromisoformat(item['calculation_date']),
                    score_change=float(item['score_change'])
                ))
            
            return scores
        except Exception as e:
            print(f"Error getting credit score history: {e}")
            return []
    
    # ==================== NDVI/Satellite Operations ====================
    
    def save_ndvi_result(self, ndvi: NDVIResult, user_id: str) -> bool:
        """
        Save an NDVI analysis result.
        
        Args:
            ndvi: NDVIResult object
            user_id: User creating the record
            
        Returns:
            True if successful, False otherwise
        """
        if not validate_gps_coordinates(ndvi.gps_coords):
            print(f"Invalid GPS coordinates: {ndvi.gps_coords}")
            return False
        
        try:
            # Create a hash of GPS coordinates for the field ID
            coords_hash = f"{ndvi.gps_coords[0]:.6f}_{ndvi.gps_coords[1]:.6f}"
            timestamp_str = ndvi.timestamp.isoformat()
            
            item = {
                'PK': f'FIELD#{coords_hash}',
                'SK': f'NDVI#{timestamp_str}',
                'entity_type': 'NDVIResult',
                'field_id': ndvi.field_id,
                'gps_latitude': Decimal(str(ndvi.gps_coords[0])),
                'gps_longitude': Decimal(str(ndvi.gps_coords[1])),
                'ndvi_value': Decimal(str(ndvi.ndvi_value)),
                'timestamp': timestamp_str,
                'confidence': Decimal(str(ndvi.confidence)),
                'satellite_image_url': ndvi.satellite_image_url,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            self.table.put_item(Item=item)
            
            # Create audit trail
            self._create_audit_trail(
                entity_type='NDVIResult',
                entity_id=f'{ndvi.field_id}#{timestamp_str}',
                operation='create',
                user_id=user_id,
                changed_fields=item
            )
            
            return True
        except Exception as e:
            print(f"Error saving NDVI result: {e}")
            return False
    
    def get_ndvi_results(self, gps_coords: tuple, limit: int = 10) -> List[NDVIResult]:
        """
        Retrieve NDVI results for a field location.
        
        Args:
            gps_coords: Tuple of (latitude, longitude)
            limit: Maximum number of results to retrieve
            
        Returns:
            List of NDVIResult objects
        """
        if not validate_gps_coordinates(gps_coords):
            print(f"Invalid GPS coordinates: {gps_coords}")
            return []
        
        results = []
        try:
            coords_hash = f"{gps_coords[0]:.6f}_{gps_coords[1]:.6f}"
            
            response = self.table.query(
                KeyConditionExpression=Key('PK').eq(f'FIELD#{coords_hash}') & 
                                     Key('SK').begins_with('NDVI#'),
                Limit=limit,
                ScanIndexForward=False  # Most recent first
            )
            
            for item in response.get('Items', []):
                results.append(NDVIResult(
                    field_id=item['field_id'],
                    gps_coords=(float(item['gps_latitude']), float(item['gps_longitude'])),
                    ndvi_value=float(item['ndvi_value']),
                    timestamp=datetime.fromisoformat(item['timestamp']),
                    confidence=float(item['confidence']),
                    satellite_image_url=item['satellite_image_url']
                ))
            
            return results
        except Exception as e:
            print(f"Error getting NDVI results: {e}")
            return []
    
    # ==================== Conversation History Operations ====================
    
    def save_message(self, message: Message) -> bool:
        """
        Save a conversation message.
        
        Args:
            message: Message object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            timestamp_str = message.timestamp.isoformat()
            
            item = {
                'PK': f'CONVERSATION#{message.sender_id}',
                'SK': f'MSG#{timestamp_str}',
                'entity_type': 'Message',
                'message_id': message.message_id,
                'sender_id': message.sender_id,
                'message_type': message.message_type.value,
                'content': message.content,
                'timestamp': timestamp_str,
                'language': message.language,
                'created_at': datetime.utcnow().isoformat()
            }
            
            self.table.put_item(Item=item)
            return True
        except Exception as e:
            print(f"Error saving message: {e}")
            return False
    
    def get_conversation_history(self, sender_id: str, limit: int = 20) -> List[Message]:
        """
        Retrieve conversation history for a user.
        
        Args:
            sender_id: User identifier
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of Message objects
        """
        messages = []
        try:
            response = self.table.query(
                KeyConditionExpression=Key('PK').eq(f'CONVERSATION#{sender_id}') & 
                                     Key('SK').begins_with('MSG#'),
                Limit=limit,
                ScanIndexForward=False  # Most recent first
            )
            
            for item in response.get('Items', []):
                from .models import MessageType
                messages.append(Message(
                    message_id=item['message_id'],
                    sender_id=item['sender_id'],
                    message_type=MessageType(item['message_type']),
                    content=item['content'],
                    timestamp=datetime.fromisoformat(item['timestamp']),
                    language=item['language']
                ))
            
            return messages
        except Exception as e:
            print(f"Error getting conversation history: {e}")
            return []
    
    # ==================== Audit Trail Operations ====================
    
    def _create_audit_trail(
        self,
        entity_type: str,
        entity_id: str,
        operation: str,
        user_id: str,
        changed_fields: Dict[str, Any],
        previous_values: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create an audit trail record for a data operation.
        
        Args:
            entity_type: Type of entity (Farmer, Transaction, etc.)
            entity_id: Entity identifier
            operation: Operation type (create, update, delete)
            user_id: User performing the operation
            changed_fields: Dictionary of changed fields
            previous_values: Optional dictionary of previous values
            
        Returns:
            True if successful, False otherwise
        """
        try:
            timestamp = datetime.utcnow()
            timestamp_str = timestamp.isoformat()
            audit_id = f'{entity_type}#{entity_id}#{timestamp_str}'
            
            item = {
                'PK': f'AUDIT#{entity_type}#{entity_id}',
                'SK': f'AUDIT#{timestamp_str}',
                'entity_type': 'AuditTrail',
                'audit_id': audit_id,
                'audited_entity_type': entity_type,
                'audited_entity_id': entity_id,
                'operation': operation,
                'timestamp': timestamp_str,
                'user_id': user_id,
                'changed_fields': changed_fields,
                'created_at': timestamp_str
            }
            
            if previous_values:
                item['previous_values'] = previous_values
            
            self.table.put_item(Item=item)
            return True
        except Exception as e:
            print(f"Error creating audit trail: {e}")
            return False
    
    def get_audit_trail(self, entity_type: str, entity_id: str, limit: int = 50) -> List[AuditTrail]:
        """
        Retrieve audit trail for an entity.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            limit: Maximum number of audit records to retrieve
            
        Returns:
            List of AuditTrail objects
        """
        trails = []
        try:
            response = self.table.query(
                KeyConditionExpression=Key('PK').eq(f'AUDIT#{entity_type}#{entity_id}') & 
                                     Key('SK').begins_with('AUDIT#'),
                Limit=limit,
                ScanIndexForward=False  # Most recent first
            )
            
            for item in response.get('Items', []):
                trails.append(AuditTrail(
                    audit_id=item['audit_id'],
                    entity_type=item['audited_entity_type'],
                    entity_id=item['audited_entity_id'],
                    operation=item['operation'],
                    timestamp=datetime.fromisoformat(item['timestamp']),
                    user_id=item['user_id'],
                    changed_fields=item['changed_fields'],
                    previous_values=item.get('previous_values')
                ))
            
            return trails
        except Exception as e:
            print(f"Error getting audit trail: {e}")
            return []
    
    # ==================== Offline Sync Operations ====================
    
    def save_pending_sync(self, device_id: str, transaction: Transaction) -> bool:
        """
        Save a transaction to the pending sync queue.
        
        Args:
            device_id: Device identifier
            transaction: Transaction object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            timestamp_str = transaction.timestamp.isoformat()
            
            item = {
                'PK': f'SYNC#{device_id}',
                'SK': f'PENDING#{timestamp_str}',
                'entity_type': 'PendingSync',
                'device_id': device_id,
                'transaction_id': transaction.transaction_id,
                'transaction_data': {
                    'farmer_id': transaction.farmer_id,
                    'fpo_id': transaction.fpo_id,
                    'quantity': str(transaction.quantity),
                    'crop_type': transaction.crop_type,
                    'quality_grade': transaction.quality_grade,
                    'moisture': str(transaction.moisture),
                    'price': str(transaction.price),
                    'timestamp': timestamp_str
                },
                'sync_status': 'pending',
                'retry_count': 0,
                'created_at': datetime.utcnow().isoformat()
            }
            
            self.table.put_item(Item=item)
            return True
        except Exception as e:
            print(f"Error saving pending sync: {e}")
            return False
    
    def get_pending_syncs(self, device_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve pending sync items for a device.
        
        Args:
            device_id: Device identifier
            
        Returns:
            List of pending sync items
        """
        items = []
        try:
            response = self.table.query(
                KeyConditionExpression=Key('PK').eq(f'SYNC#{device_id}') & 
                                     Key('SK').begins_with('PENDING#')
            )
            
            return response.get('Items', [])
        except Exception as e:
            print(f"Error getting pending syncs: {e}")
            return []
    
    def delete_pending_sync(self, device_id: str, timestamp: str) -> bool:
        """
        Delete a pending sync item after successful sync.
        
        Args:
            device_id: Device identifier
            timestamp: Transaction timestamp
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.table.delete_item(
                Key={
                    'PK': f'SYNC#{device_id}',
                    'SK': f'PENDING#{timestamp}'
                }
            )
            return True
        except Exception as e:
            print(f"Error deleting pending sync: {e}")
            return False
