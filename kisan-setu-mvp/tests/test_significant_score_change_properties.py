"""
Property-Based Tests for Significant Score Change Notification

Tests Property 16: Significant Score Change Notification
For any farmer whose reliability score changes by more than 10 points between
calculations, the score_change field must be set to a non-zero value indicating
the magnitude of change.

**Validates: Requirements 5.8**

Uses Hypothesis framework with minimum 100 iterations.
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from hypothesis import given, settings, strategies as st, assume
from unittest.mock import Mock, call
from decimal import Decimal

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from credit.credit import CreditEngine
from common.models import ReliabilityScore

# Import test data generators
from generators import farmer_with_transactions, farmer_data, uuid_string


# ============================================================================
# Property 16: Significant Score Change Notification
# ============================================================================

@given(
    farmer_and_txns=farmer_with_transactions(min_transactions=5, max_transactions=30),
    previous_score=st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False),
    data=st.data()
)
@settings(max_examples=100, deadline=None)
def test_property_16_significant_score_change_detection(farmer_and_txns, previous_score, data):
    """
    **Property 16: Significant Score Change Notification**
    **Validates: Requirements 5.8**
    
    For any farmer whose reliability score changes by more than 10 points,
    the score_change field must be set to a non-zero value indicating the
    magnitude of change.
    """
    farmer, transactions = farmer_and_txns
    
    # Create mock DynamoDB table
    mock_table = Mock()
    
    # Track if notification was called
    notification_called = False
    
    # Mock query to return transactions and previous score
    def mock_query(**kwargs):
        pk = kwargs.get('ExpressionAttributeValues', {}).get(':pk')
        sk_prefix = kwargs.get('ExpressionAttributeValues', {}).get(':sk')
        
        if sk_prefix == 'TXN#':
            # Return transactions
            items = []
            for txn in transactions:
                items.append({
                    'PK': txn.farmer_id,
                    'SK': f"TXN#{txn.timestamp.isoformat()}",
                    'transaction_id': txn.transaction_id,
                    'farmer_id': txn.farmer_id,
                    'fpo_id': txn.fpo_id,
                    'quantity': Decimal(str(txn.quantity)),
                    'crop_type': txn.crop_type,
                    'quality_grade': txn.quality_grade,
                    'moisture': Decimal(str(txn.moisture)),
                    'price': Decimal(str(txn.price)),
                    'timestamp': txn.timestamp.isoformat(),
                    'ledger_image_url': txn.ledger_image_url,
                    'sync_status': str(txn.sync_status.value)
                })
            return {'Items': items}
        elif sk_prefix == 'SCORE#':
            # Return previous score
            if previous_score is not None:
                return {
                    'Items': [{
                        'PK': pk,
                        'SK': f"SCORE#{(datetime.utcnow() - timedelta(days=30)).isoformat()}",
                        'total_score': Decimal(str(previous_score))
                    }]
                }
            return {'Items': []}
        
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query)
    mock_table.put_item = Mock()
    
    # Create CreditEngine
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    
    # Mock the notification method to track if it was called
    def mock_notify(score):
        nonlocal notification_called
        notification_called = True
    
    credit_engine._notify_significant_change = Mock(side_effect=mock_notify)
    
    # Calculate reliability score
    score = credit_engine.calculate_reliability_score(farmer.farmer_id)
    
    # Property 1: score_change field is set
    assert hasattr(score, 'score_change'), \
        "ReliabilityScore should have score_change field"
    
    # Property 2: score_change reflects the difference from previous score
    expected_change = score.total_score - previous_score
    assert abs(score.score_change - expected_change) < 0.01, \
        f"score_change should be {expected_change:.2f}, got {score.score_change:.2f}"
    
    # Property 3: If change > 10 points, notification should be triggered
    if abs(score.score_change) > 10:
        assert notification_called or credit_engine._notify_significant_change.called, \
            f"Notification should be triggered for score change of {score.score_change:.2f} points"
        
        # Verify notification was called with the correct score
        if credit_engine._notify_significant_change.called:
            call_args = credit_engine._notify_significant_change.call_args
            assert call_args is not None, "Notification should have been called with arguments"
            notified_score = call_args[0][0]
            assert notified_score.farmer_id == farmer.farmer_id, \
                "Notification should be for the correct farmer"
            assert abs(notified_score.score_change) > 10, \
                "Notified score should have significant change"
    
    # Property 4: If change <= 10 points, notification should NOT be triggered
    if abs(score.score_change) <= 10:
        assert not notification_called and not credit_engine._notify_significant_change.called, \
            f"Notification should NOT be triggered for score change of {score.score_change:.2f} points"
    
    # Property 5: score_change is non-zero when there's a previous score
    if previous_score is not None:
        # Only check if scores are actually different
        if abs(score.total_score - previous_score) > 0.01:
            assert abs(score.score_change) > 0, \
                "score_change should be non-zero when score differs from previous"


@given(
    farmer_and_txns=farmer_with_transactions(min_transactions=5, max_transactions=30),
    score_delta=st.floats(min_value=10.1, max_value=50.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, deadline=None)
def test_property_16_positive_significant_change(farmer_and_txns, score_delta):
    """
    **Property 16: Significant Score Change Notification (Positive Change)**
    **Validates: Requirements 5.8**
    
    Test that positive score changes > 10 points trigger notification.
    """
    farmer, transactions = farmer_and_txns
    
    # Create mock DynamoDB table
    mock_table = Mock()
    
    # Calculate what the current score will be
    temp_engine = CreditEngine(dynamodb_table=Mock())
    temp_engine._get_farmer_transactions = Mock(return_value=[
        {
            'transaction_id': txn.transaction_id,
            'farmer_id': txn.farmer_id,
            'fpo_id': txn.fpo_id,
            'quantity': float(txn.quantity),
            'crop_type': txn.crop_type,
            'quality_grade': txn.quality_grade,
            'moisture': float(txn.moisture),
            'price': float(txn.price),
            'timestamp': txn.timestamp.isoformat(),
            'ledger_image_url': txn.ledger_image_url,
            'sync_status': str(txn.sync_status.value)
        }
        for txn in transactions
    ])
    temp_engine._get_previous_score = Mock(return_value=None)
    temp_engine._store_score = Mock()
    temp_engine._notify_significant_change = Mock()
    temp_score = temp_engine.calculate_reliability_score(farmer.farmer_id)
    current_score = temp_score.total_score
    
    # Set previous score to be score_delta less than current
    previous_score = max(0.0, current_score - score_delta)
    
    # Skip if previous_score ends up being 0 (edge case that's hard to distinguish from no previous score)
    assume(previous_score > 0.1)
    
    # Mock query to return transactions and previous score
    def mock_query(**kwargs):
        pk = kwargs.get('ExpressionAttributeValues', {}).get(':pk')
        sk_prefix = kwargs.get('ExpressionAttributeValues', {}).get(':sk')
        
        if sk_prefix == 'TXN#':
            items = []
            for txn in transactions:
                items.append({
                    'PK': txn.farmer_id,
                    'SK': f"TXN#{txn.timestamp.isoformat()}",
                    'transaction_id': txn.transaction_id,
                    'farmer_id': txn.farmer_id,
                    'fpo_id': txn.fpo_id,
                    'quantity': Decimal(str(txn.quantity)),
                    'crop_type': txn.crop_type,
                    'quality_grade': txn.quality_grade,
                    'moisture': Decimal(str(txn.moisture)),
                    'price': Decimal(str(txn.price)),
                    'timestamp': txn.timestamp.isoformat(),
                    'ledger_image_url': txn.ledger_image_url,
                    'sync_status': str(txn.sync_status.value)
                })
            return {'Items': items}
        elif sk_prefix == 'SCORE#':
            return {
                'Items': [{
                    'PK': pk,
                    'SK': f"SCORE#{(datetime.utcnow() - timedelta(days=30)).isoformat()}",
                    'total_score': Decimal(str(previous_score))
                }]
            }
        
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query)
    mock_table.put_item = Mock()
    
    # Create CreditEngine
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    credit_engine._notify_significant_change = Mock()
    
    # Calculate reliability score
    score = credit_engine.calculate_reliability_score(farmer.farmer_id)
    
    # Property 1: score_change should be positive and > 10
    assert score.score_change > 10, \
        f"score_change should be > 10 for positive significant change, got {score.score_change:.2f}"
    
    # Property 2: Notification should be triggered
    assert credit_engine._notify_significant_change.called, \
        "Notification should be triggered for positive significant change"


@given(
    farmer_and_txns=farmer_with_transactions(min_transactions=5, max_transactions=30),
    score_delta=st.floats(min_value=10.1, max_value=50.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, deadline=None)
def test_property_16_negative_significant_change(farmer_and_txns, score_delta):
    """
    **Property 16: Significant Score Change Notification (Negative Change)**
    **Validates: Requirements 5.8**
    
    Test that negative score changes > 10 points trigger notification.
    """
    farmer, transactions = farmer_and_txns
    
    # Create mock DynamoDB table
    mock_table = Mock()
    
    # Calculate what the current score will be
    temp_engine = CreditEngine(dynamodb_table=Mock())
    temp_engine._get_farmer_transactions = Mock(return_value=[
        {
            'transaction_id': txn.transaction_id,
            'farmer_id': txn.farmer_id,
            'fpo_id': txn.fpo_id,
            'quantity': float(txn.quantity),
            'crop_type': txn.crop_type,
            'quality_grade': txn.quality_grade,
            'moisture': float(txn.moisture),
            'price': float(txn.price),
            'timestamp': txn.timestamp.isoformat(),
            'ledger_image_url': txn.ledger_image_url,
            'sync_status': str(txn.sync_status.value)
        }
        for txn in transactions
    ])
    temp_engine._get_previous_score = Mock(return_value=None)
    temp_engine._store_score = Mock()
    temp_engine._notify_significant_change = Mock()
    temp_score = temp_engine.calculate_reliability_score(farmer.farmer_id)
    current_score = temp_score.total_score
    
    # Set previous score to be score_delta more than current
    previous_score = min(100.0, current_score + score_delta)
    
    # Mock query to return transactions and previous score
    def mock_query(**kwargs):
        pk = kwargs.get('ExpressionAttributeValues', {}).get(':pk')
        sk_prefix = kwargs.get('ExpressionAttributeValues', {}).get(':sk')
        
        if sk_prefix == 'TXN#':
            items = []
            for txn in transactions:
                items.append({
                    'PK': txn.farmer_id,
                    'SK': f"TXN#{txn.timestamp.isoformat()}",
                    'transaction_id': txn.transaction_id,
                    'farmer_id': txn.farmer_id,
                    'fpo_id': txn.fpo_id,
                    'quantity': Decimal(str(txn.quantity)),
                    'crop_type': txn.crop_type,
                    'quality_grade': txn.quality_grade,
                    'moisture': Decimal(str(txn.moisture)),
                    'price': Decimal(str(txn.price)),
                    'timestamp': txn.timestamp.isoformat(),
                    'ledger_image_url': txn.ledger_image_url,
                    'sync_status': str(txn.sync_status.value)
                })
            return {'Items': items}
        elif sk_prefix == 'SCORE#':
            return {
                'Items': [{
                    'PK': pk,
                    'SK': f"SCORE#{(datetime.utcnow() - timedelta(days=30)).isoformat()}",
                    'total_score': Decimal(str(previous_score))
                }]
            }
        
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query)
    mock_table.put_item = Mock()
    
    # Create CreditEngine
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    credit_engine._notify_significant_change = Mock()
    
    # Calculate reliability score
    score = credit_engine.calculate_reliability_score(farmer.farmer_id)
    
    # Property 1: score_change should be negative and < -10
    assert score.score_change < -10, \
        f"score_change should be < -10 for negative significant change, got {score.score_change:.2f}"
    
    # Property 2: Notification should be triggered (absolute value > 10)
    assert credit_engine._notify_significant_change.called, \
        "Notification should be triggered for negative significant change"


@given(
    farmer_and_txns=farmer_with_transactions(min_transactions=5, max_transactions=30),
    small_delta=st.floats(min_value=-9.9, max_value=9.9, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, deadline=None)
def test_property_16_insignificant_change_no_notification(farmer_and_txns, small_delta):
    """
    **Property 16: Significant Score Change Notification (No Notification)**
    **Validates: Requirements 5.8**
    
    Test that score changes <= 10 points do NOT trigger notification.
    """
    farmer, transactions = farmer_and_txns
    
    # Create mock DynamoDB table
    mock_table = Mock()
    
    # Calculate what the current score will be
    temp_engine = CreditEngine(dynamodb_table=Mock())
    temp_engine._get_farmer_transactions = Mock(return_value=[
        {
            'transaction_id': txn.transaction_id,
            'farmer_id': txn.farmer_id,
            'fpo_id': txn.fpo_id,
            'quantity': float(txn.quantity),
            'crop_type': txn.crop_type,
            'quality_grade': txn.quality_grade,
            'moisture': float(txn.moisture),
            'price': float(txn.price),
            'timestamp': txn.timestamp.isoformat(),
            'ledger_image_url': txn.ledger_image_url,
            'sync_status': str(txn.sync_status.value)
        }
        for txn in transactions
    ])
    temp_engine._get_previous_score = Mock(return_value=None)
    temp_engine._store_score = Mock()
    temp_engine._notify_significant_change = Mock()
    temp_score = temp_engine.calculate_reliability_score(farmer.farmer_id)
    current_score = temp_score.total_score
    
    # Set previous score to be small_delta different from current
    previous_score = max(0.0, min(100.0, current_score - small_delta))
    
    # Mock query to return transactions and previous score
    def mock_query(**kwargs):
        pk = kwargs.get('ExpressionAttributeValues', {}).get(':pk')
        sk_prefix = kwargs.get('ExpressionAttributeValues', {}).get(':sk')
        
        if sk_prefix == 'TXN#':
            items = []
            for txn in transactions:
                items.append({
                    'PK': txn.farmer_id,
                    'SK': f"TXN#{txn.timestamp.isoformat()}",
                    'transaction_id': txn.transaction_id,
                    'farmer_id': txn.farmer_id,
                    'fpo_id': txn.fpo_id,
                    'quantity': Decimal(str(txn.quantity)),
                    'crop_type': txn.crop_type,
                    'quality_grade': txn.quality_grade,
                    'moisture': Decimal(str(txn.moisture)),
                    'price': Decimal(str(txn.price)),
                    'timestamp': txn.timestamp.isoformat(),
                    'ledger_image_url': txn.ledger_image_url,
                    'sync_status': str(txn.sync_status.value)
                })
            return {'Items': items}
        elif sk_prefix == 'SCORE#':
            return {
                'Items': [{
                    'PK': pk,
                    'SK': f"SCORE#{(datetime.utcnow() - timedelta(days=30)).isoformat()}",
                    'total_score': Decimal(str(previous_score))
                }]
            }
        
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query)
    mock_table.put_item = Mock()
    
    # Create CreditEngine
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    credit_engine._notify_significant_change = Mock()
    
    # Calculate reliability score
    score = credit_engine.calculate_reliability_score(farmer.farmer_id)
    
    # Property 1: score_change should be <= 10 in absolute value
    assert abs(score.score_change) <= 10.0, \
        f"score_change should be <= 10 for insignificant change, got {score.score_change:.2f}"
    
    # Property 2: Notification should NOT be triggered
    assert not credit_engine._notify_significant_change.called, \
        f"Notification should NOT be triggered for insignificant change of {score.score_change:.2f} points"


@given(farmer=farmer_data())
@settings(max_examples=100, deadline=None)
def test_property_16_first_score_no_change(farmer):
    """
    **Property 16: Significant Score Change Notification (First Score)**
    **Validates: Requirements 5.8**
    
    Test that the first score calculation (no previous score) has score_change = 0
    and does not trigger notification.
    """
    # Create mock DynamoDB table
    mock_table = Mock()
    
    # Create a single transaction
    transaction = {
        'PK': farmer.farmer_id,
        'SK': 'TXN#2024-01-15T10:00:00',
        'transaction_id': 'TXN#001',
        'farmer_id': farmer.farmer_id,
        'fpo_id': farmer.fpo_id,
        'quantity': Decimal('100.0'),
        'crop_type': 'wheat',
        'quality_grade': 'A',
        'moisture': Decimal('12.0'),
        'price': Decimal('2500.0'),
        'timestamp': '2024-01-15T10:00:00',
        'ledger_image_url': 's3://test/image.jpg',
        'sync_status': 'SYNCED'
    }
    
    # Mock query to return transaction but no previous score
    def mock_query(**kwargs):
        sk_prefix = kwargs.get('ExpressionAttributeValues', {}).get(':sk')
        
        if sk_prefix == 'TXN#':
            return {'Items': [transaction]}
        elif sk_prefix == 'SCORE#':
            return {'Items': []}  # No previous score
        
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query)
    mock_table.put_item = Mock()
    
    # Create CreditEngine
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    credit_engine._notify_significant_change = Mock()
    
    # Calculate reliability score
    score = credit_engine.calculate_reliability_score(farmer.farmer_id)
    
    # Property 1: score_change should be 0 for first calculation
    assert score.score_change == 0.0, \
        f"score_change should be 0 for first score calculation, got {score.score_change:.2f}"
    
    # Property 2: Notification should NOT be triggered
    assert not credit_engine._notify_significant_change.called, \
        "Notification should NOT be triggered for first score calculation"


# ============================================================================
# Edge Cases
# ============================================================================

def test_edge_case_exactly_10_point_change():
    """
    Test that exactly 10 point change does NOT trigger notification.
    The requirement states > 10 points.
    """
    farmer_id = 'FARMER#test123'
    
    # Create transactions
    transactions = []
    base_date = datetime(2024, 1, 1)
    
    for i in range(10):
        txn = {
            'PK': farmer_id,
            'SK': f"TXN#{(base_date + timedelta(days=i*7)).isoformat()}",
            'transaction_id': f'TXN#{i:03d}',
            'farmer_id': farmer_id,
            'fpo_id': 'FPO#001',
            'quantity': Decimal('100.0'),
            'crop_type': 'wheat',
            'quality_grade': 'A',
            'moisture': Decimal('12.0'),
            'price': Decimal('2500.0'),
            'timestamp': (base_date + timedelta(days=i*7)).isoformat(),
            'ledger_image_url': 's3://test/image.jpg',
            'sync_status': 'SYNCED'
        }
        transactions.append(txn)
    
    # Create mock DynamoDB table
    mock_table = Mock()
    
    # First, calculate the current score
    def mock_query_first(**kwargs):
        sk_prefix = kwargs.get('ExpressionAttributeValues', {}).get(':sk')
        
        if sk_prefix == 'TXN#':
            return {'Items': transactions}
        elif sk_prefix == 'SCORE#':
            return {'Items': []}
        
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query_first)
    mock_table.put_item = Mock()
    
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    credit_engine._notify_significant_change = Mock()
    current_score_obj = credit_engine.calculate_reliability_score(farmer_id)
    current_score = current_score_obj.total_score
    
    # Set previous score to be exactly 10 points different
    previous_score = current_score - 10.0
    
    # Now test with previous score
    def mock_query_second(**kwargs):
        pk = kwargs.get('ExpressionAttributeValues', {}).get(':pk')
        sk_prefix = kwargs.get('ExpressionAttributeValues', {}).get(':sk')
        
        if sk_prefix == 'TXN#':
            return {'Items': transactions}
        elif sk_prefix == 'SCORE#':
            return {
                'Items': [{
                    'PK': pk,
                    'SK': f"SCORE#{(datetime.utcnow() - timedelta(days=30)).isoformat()}",
                    'total_score': Decimal(str(previous_score))
                }]
            }
        
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query_second)
    mock_table.put_item = Mock()
    
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    credit_engine._notify_significant_change = Mock()
    score = credit_engine.calculate_reliability_score(farmer_id)
    
    # Assertions
    assert abs(score.score_change - 10.0) < 0.01, \
        f"score_change should be exactly 10, got {score.score_change:.2f}"
    
    # Notification should NOT be triggered (requirement is > 10, not >= 10)
    assert not credit_engine._notify_significant_change.called, \
        "Notification should NOT be triggered for exactly 10 point change"


def test_edge_case_10_01_point_change():
    """
    Test that 10.01 point change DOES trigger notification.
    """
    farmer_id = 'FARMER#test456'
    
    # Create transactions
    transactions = []
    base_date = datetime(2024, 1, 1)
    
    for i in range(10):
        txn = {
            'PK': farmer_id,
            'SK': f"TXN#{(base_date + timedelta(days=i*7)).isoformat()}",
            'transaction_id': f'TXN#{i:03d}',
            'farmer_id': farmer_id,
            'fpo_id': 'FPO#001',
            'quantity': Decimal('100.0'),
            'crop_type': 'wheat',
            'quality_grade': 'A',
            'moisture': Decimal('12.0'),
            'price': Decimal('2500.0'),
            'timestamp': (base_date + timedelta(days=i*7)).isoformat(),
            'ledger_image_url': 's3://test/image.jpg',
            'sync_status': 'SYNCED'
        }
        transactions.append(txn)
    
    # Create mock DynamoDB table
    mock_table = Mock()
    
    # First, calculate the current score
    def mock_query_first(**kwargs):
        sk_prefix = kwargs.get('ExpressionAttributeValues', {}).get(':sk')
        
        if sk_prefix == 'TXN#':
            return {'Items': transactions}
        elif sk_prefix == 'SCORE#':
            return {'Items': []}
        
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query_first)
    mock_table.put_item = Mock()
    
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    credit_engine._notify_significant_change = Mock()
    current_score_obj = credit_engine.calculate_reliability_score(farmer_id)
    current_score = current_score_obj.total_score
    
    # Set previous score to be 10.01 points different
    previous_score = current_score - 10.01
    
    # Now test with previous score
    def mock_query_second(**kwargs):
        pk = kwargs.get('ExpressionAttributeValues', {}).get(':pk')
        sk_prefix = kwargs.get('ExpressionAttributeValues', {}).get(':sk')
        
        if sk_prefix == 'TXN#':
            return {'Items': transactions}
        elif sk_prefix == 'SCORE#':
            return {
                'Items': [{
                    'PK': pk,
                    'SK': f"SCORE#{(datetime.utcnow() - timedelta(days=30)).isoformat()}",
                    'total_score': Decimal(str(previous_score))
                }]
            }
        
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query_second)
    mock_table.put_item = Mock()
    
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    credit_engine._notify_significant_change = Mock()
    score = credit_engine.calculate_reliability_score(farmer_id)
    
    # Assertions
    assert abs(score.score_change - 10.01) < 0.01, \
        f"score_change should be 10.01, got {score.score_change:.2f}"
    
    # Notification SHOULD be triggered (> 10)
    assert credit_engine._notify_significant_change.called, \
        "Notification SHOULD be triggered for 10.01 point change"
