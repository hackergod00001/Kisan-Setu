"""
AppSync Sync Handler Lambda
Handles syncOfflineTransactions mutation with conflict resolution
"""

import json
import os
import boto3
from datetime import datetime
from typing import List, Dict, Any
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE', 'KisanSetuData')
table = dynamodb.Table(table_name)

def handler(event, context):
    """
    AppSync Lambda resolver for syncOfflineTransactions mutation
    Implements last-write-wins conflict resolution
    """
    print(f"Sync handler invoked with event: {json.dumps(event)}")
    
    # Extract transactions from AppSync event
    transactions = event.get('arguments', {}).get('transactions', [])
    
    if not transactions:
        return {
            'successCount': 0,
            'failureCount': 0,
            'conflicts': []
        }
    
    # Sort transactions by timestamp (chronological order)
    sorted_transactions = sorted(transactions, key=lambda t: t['timestamp'])
    
    success_count = 0
    failure_count = 0
    conflicts = []
    
    for txn in sorted_transactions:
        try:
            result = sync_transaction(txn)
            if result['status'] == 'success':
                success_count += 1
            elif result['status'] == 'conflict':
                success_count += 1  # Conflict resolved, still counts as success
                conflicts.append(result['conflict_info'])
            else:
                failure_count += 1
        except Exception as e:
            print(f"Error syncing transaction {txn.get('transactionId')}: {str(e)}")
            failure_count += 1
    
    return {
        'successCount': success_count,
        'failureCount': failure_count,
        'conflicts': conflicts
    }

def sync_transaction(txn: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sync a single transaction with conflict resolution
    Implements last-write-wins strategy
    """
    pk = f"FARMER#{txn['farmerId']}"
    sk = f"TXN#{txn['timestamp']}"
    
    # Check if transaction already exists
    try:
        response = table.get_item(
            Key={'PK': pk, 'SK': sk}
        )
        
        existing_item = response.get('Item')
        
        if existing_item:
            # Conflict detected - compare versions
            existing_version = existing_item.get('version', 0)
            new_version = txn.get('version', 0)
            
            # Last-write-wins: use the transaction with higher version
            if new_version > existing_version:
                # New transaction wins
                put_transaction(pk, sk, txn)
                return {
                    'status': 'conflict',
                    'conflict_info': {
                        'transactionId': txn['transactionId'],
                        'localVersion': new_version,
                        'cloudVersion': existing_version,
                        'resolution': 'local_wins'
                    }
                }
            else:
                # Existing transaction wins (cloud version is newer or equal)
                return {
                    'status': 'conflict',
                    'conflict_info': {
                        'transactionId': txn['transactionId'],
                        'localVersion': new_version,
                        'cloudVersion': existing_version,
                        'resolution': 'cloud_wins'
                    }
                }
        else:
            # No conflict - new transaction
            put_transaction(pk, sk, txn)
            return {'status': 'success'}
            
    except Exception as e:
        print(f"Error checking/syncing transaction: {str(e)}")
        return {'status': 'failure', 'error': str(e)}

def put_transaction(pk: str, sk: str, txn: Dict[str, Any]):
    """
    Put transaction into DynamoDB
    """
    item = {
        'PK': pk,
        'SK': sk,
        'transactionId': txn['transactionId'],
        'farmerId': txn['farmerId'],
        'fpoId': txn['fpoId'],
        'quantity': Decimal(str(txn['quantity'])),
        'cropType': txn['cropType'],
        'qualityGrade': txn['qualityGrade'],
        'moisture': Decimal(str(txn['moisture'])),
        'price': Decimal(str(txn['price'])),
        'timestamp': txn['timestamp'],
        'syncStatus': 'SYNCED',  # Mark as synced
        'version': txn['version'],
        'lastModified': datetime.utcnow().isoformat()
    }
    
    # Add optional fields
    if 'ledgerImageUrl' in txn and txn['ledgerImageUrl']:
        item['ledgerImageUrl'] = txn['ledgerImageUrl']
    
    table.put_item(Item=item)
    print(f"Successfully synced transaction {txn['transactionId']}")
