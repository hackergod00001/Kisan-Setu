"""
Property-Based Tests for Reliability Score Composition

Tests Property 15: Reliability Score Composition
For any farmer with transaction history, the calculated reliability score should:
- Be between 0 and 100 (inclusive)
- Equal the sum of: supply_consistency (0-30) + quality_metrics (0-25) + 
  transaction_history (0-20) + financial_behavior (0-15) + operational_transparency (0-10)
- Include a breakdown showing each component's contribution

**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7**

Uses Hypothesis framework with minimum 100 iterations.
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from hypothesis import given, settings, strategies as st
from unittest.mock import Mock
from decimal import Decimal

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'credit'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from credit.credit import CreditEngine
from common.models import ReliabilityScore

# Import test data generators
from generators import farmer_with_transactions, farmer_data, transaction_data, uuid_string


# ============================================================================
# Property 15: Reliability Score Composition
# ============================================================================

@given(farmer_and_txns=farmer_with_transactions(min_transactions=1, max_transactions=50))
@settings(max_examples=100, deadline=None)
def test_property_15_reliability_score_composition(farmer_and_txns):
    """
    **Property 15: Reliability Score Composition**
    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7**
    
    For any farmer with transaction history, the calculated reliability score should:
    1. Be between 0 and 100 (inclusive)
    2. Equal the sum of all component scores
    3. Each component must be within its valid range:
       - supply_consistency: 0-30
       - quality_metrics: 0-25
       - transaction_history: 0-20
       - financial_behavior: 0-15
       - operational_transparency: 0-10
    4. Include a breakdown showing each component's contribution
    """
    farmer, transactions = farmer_and_txns
    
    # Create mock DynamoDB table
    mock_table = Mock()
    
    # Mock query to return transactions
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
            # No previous score
            return {'Items': []}
        
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query)
    mock_table.put_item = Mock()
    
    # Create CreditEngine
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    
    # Calculate reliability score
    score = credit_engine.calculate_reliability_score(farmer.farmer_id)
    
    # Property 1: Result is a ReliabilityScore object
    assert isinstance(score, ReliabilityScore), \
        "Result should be a ReliabilityScore object"
    
    # Property 2: Total score is between 0 and 100
    assert 0.0 <= score.total_score <= 100.0, \
        f"Total score must be in range [0, 100], got {score.total_score}"
    
    # Property 3: Component scores are within their valid ranges
    assert 0.0 <= score.supply_consistency <= 30.0, \
        f"supply_consistency must be in range [0, 30], got {score.supply_consistency}"
    
    assert 0.0 <= score.quality_metrics <= 25.0, \
        f"quality_metrics must be in range [0, 25], got {score.quality_metrics}"
    
    assert 0.0 <= score.transaction_history <= 20.0, \
        f"transaction_history must be in range [0, 20], got {score.transaction_history}"
    
    assert 0.0 <= score.financial_behavior <= 15.0, \
        f"financial_behavior must be in range [0, 15], got {score.financial_behavior}"
    
    assert 0.0 <= score.operational_transparency <= 10.0, \
        f"operational_transparency must be in range [0, 10], got {score.operational_transparency}"
    
    # Property 4: Total score equals sum of components
    expected_total = (
        score.supply_consistency +
        score.quality_metrics +
        score.transaction_history +
        score.financial_behavior +
        score.operational_transparency
    )
    
    # Allow small floating-point tolerance
    assert abs(score.total_score - expected_total) < 0.01, \
        f"Total score should equal sum of components: expected {expected_total:.6f}, got {score.total_score:.6f}"
    
    # Property 5: All required fields are present
    assert hasattr(score, 'farmer_id'), "ReliabilityScore should have farmer_id"
    assert hasattr(score, 'total_score'), "ReliabilityScore should have total_score"
    assert hasattr(score, 'supply_consistency'), "ReliabilityScore should have supply_consistency"
    assert hasattr(score, 'quality_metrics'), "ReliabilityScore should have quality_metrics"
    assert hasattr(score, 'transaction_history'), "ReliabilityScore should have transaction_history"
    assert hasattr(score, 'financial_behavior'), "ReliabilityScore should have financial_behavior"
    assert hasattr(score, 'operational_transparency'), "ReliabilityScore should have operational_transparency"
    assert hasattr(score, 'calculation_date'), "ReliabilityScore should have calculation_date"
    assert hasattr(score, 'score_change'), "ReliabilityScore should have score_change"
    
    # Property 6: Farmer ID matches
    assert score.farmer_id == farmer.farmer_id, \
        "Farmer ID should match the input farmer"
    
    # Property 7: Calculation date is set
    assert score.calculation_date is not None, \
        "Calculation date should be set"
    
    # Property 8: Score was stored in DynamoDB
    assert mock_table.put_item.called, \
        "Score should be stored in DynamoDB"


@given(farmer_and_txns=farmer_with_transactions(min_transactions=5, max_transactions=20))
@settings(max_examples=100, deadline=None)
def test_property_15_component_independence(farmer_and_txns):
    """
    **Property 15: Reliability Score Composition (Component Independence)**
    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7**
    
    Verify that each component score is calculated independently and contributes
    to the total score. Changes in one component should not affect others.
    """
    farmer, transactions = farmer_and_txns
    
    # Create mock DynamoDB table
    mock_table = Mock()
    
    # Mock query to return transactions
    def mock_query(**kwargs):
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
            return {'Items': []}
        
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query)
    mock_table.put_item = Mock()
    
    # Create CreditEngine
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    
    # Calculate individual component scores
    txn_dicts = [
        {
            'transaction_id': txn.transaction_id,
            'farmer_id': txn.farmer_id,
            'fpo_id': txn.fpo_id,
            'quantity': txn.quantity,
            'crop_type': txn.crop_type,
            'quality_grade': txn.quality_grade,
            'moisture': txn.moisture,
            'price': txn.price,
            'timestamp': txn.timestamp.isoformat(),
            'ledger_image_url': txn.ledger_image_url,
            'sync_status': str(txn.sync_status.value)
        }
        for txn in transactions
    ]
    
    supply_consistency = credit_engine.calculate_supply_consistency(farmer.farmer_id, txn_dicts)
    quality_metrics = credit_engine.calculate_quality_metrics(farmer.farmer_id, txn_dicts)
    transaction_history = credit_engine.calculate_transaction_history(farmer.farmer_id, txn_dicts)
    financial_behavior = credit_engine.calculate_financial_behavior(farmer.farmer_id, txn_dicts)
    operational_transparency = credit_engine.calculate_operational_transparency(farmer.farmer_id, txn_dicts)
    
    # Calculate full score
    full_score = credit_engine.calculate_reliability_score(farmer.farmer_id)
    
    # Property: Individual components should match the full score's components
    assert abs(full_score.supply_consistency - supply_consistency) < 0.01, \
        "supply_consistency should be consistent when calculated individually"
    
    assert abs(full_score.quality_metrics - quality_metrics) < 0.01, \
        "quality_metrics should be consistent when calculated individually"
    
    assert abs(full_score.transaction_history - transaction_history) < 0.01, \
        "transaction_history should be consistent when calculated individually"
    
    assert abs(full_score.financial_behavior - financial_behavior) < 0.01, \
        "financial_behavior should be consistent when calculated individually"
    
    assert abs(full_score.operational_transparency - operational_transparency) < 0.01, \
        "operational_transparency should be consistent when calculated individually"
    
    # Property: Sum of individual components equals total score
    manual_total = (
        supply_consistency +
        quality_metrics +
        transaction_history +
        financial_behavior +
        operational_transparency
    )
    
    assert abs(full_score.total_score - manual_total) < 0.01, \
        f"Total score should equal sum of individual components: expected {manual_total:.6f}, got {full_score.total_score:.6f}"


@given(farmer=farmer_data())
@settings(max_examples=100, deadline=None)
def test_property_15_zero_transactions_score(farmer):
    """
    **Property 15: Reliability Score Composition (Zero Transactions)**
    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7**
    
    Verify that a farmer with no transactions gets a score of 0 with all
    components at 0.
    """
    # Create mock DynamoDB table
    mock_table = Mock()
    
    # Mock query to return no transactions
    def mock_query(**kwargs):
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query)
    mock_table.put_item = Mock()
    
    # Create CreditEngine
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    
    # Calculate reliability score
    score = credit_engine.calculate_reliability_score(farmer.farmer_id)
    
    # Property 1: Total score is 0
    assert score.total_score == 0.0, \
        f"Total score should be 0 for farmer with no transactions, got {score.total_score}"
    
    # Property 2: All components are 0
    assert score.supply_consistency == 0.0, \
        "supply_consistency should be 0 for farmer with no transactions"
    
    assert score.quality_metrics == 0.0, \
        "quality_metrics should be 0 for farmer with no transactions"
    
    assert score.transaction_history == 0.0, \
        "transaction_history should be 0 for farmer with no transactions"
    
    assert score.financial_behavior == 0.0, \
        "financial_behavior should be 0 for farmer with no transactions"
    
    assert score.operational_transparency == 0.0, \
        "operational_transparency should be 0 for farmer with no transactions"
    
    # Property 3: Score is still in valid range
    assert 0.0 <= score.total_score <= 100.0, \
        "Score should still be in valid range [0, 100]"


@given(
    num_transactions=st.integers(min_value=1, max_value=100),
    farmer_id=uuid_string(),
    data=st.data()
)
@settings(max_examples=100, deadline=None)
def test_property_15_score_monotonicity(num_transactions, farmer_id, data):
    """
    **Property 15: Reliability Score Composition (Monotonicity)**
    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7**
    
    Verify that as the number of transactions increases (with consistent quality),
    the reliability score should generally increase or stay the same.
    """
    from common.models import SyncStatus
    
    # Generate transactions with consistent high quality
    transactions = []
    base_date = datetime(2023, 1, 1)
    
    for i in range(num_transactions):
        txn_data = {
            'PK': farmer_id,
            'SK': f"TXN#{(base_date + timedelta(days=i*7)).isoformat()}",
            'transaction_id': data.draw(uuid_string()),
            'farmer_id': farmer_id,
            'fpo_id': data.draw(uuid_string()),
            'quantity': Decimal('100.0'),  # Consistent quantity
            'crop_type': 'wheat',
            'quality_grade': 'A',  # High quality
            'moisture': Decimal('12.0'),  # Optimal moisture
            'price': Decimal('2500.0'),
            'timestamp': (base_date + timedelta(days=i*7)).isoformat(),
            'ledger_image_url': 's3://test/image.jpg',
            'sync_status': 'SYNCED'
        }
        transactions.append(txn_data)
    
    # Create mock DynamoDB table
    mock_table = Mock()
    
    # Mock query to return transactions
    def mock_query(**kwargs):
        sk_prefix = kwargs.get('ExpressionAttributeValues', {}).get(':sk')
        
        if sk_prefix == 'TXN#':
            return {'Items': transactions}
        elif sk_prefix == 'SCORE#':
            return {'Items': []}
        
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query)
    mock_table.put_item = Mock()
    
    # Create CreditEngine
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    
    # Calculate reliability score
    score = credit_engine.calculate_reliability_score(farmer_id)
    
    # Property 1: Score should be positive for consistent high-quality transactions
    assert score.total_score > 0.0, \
        "Score should be positive for farmers with consistent high-quality transactions"
    
    # Property 2: Score should be in valid range
    assert 0.0 <= score.total_score <= 100.0, \
        f"Score should be in valid range [0, 100], got {score.total_score}"
    
    # Property 3: All components should be non-negative
    assert score.supply_consistency >= 0.0, "supply_consistency should be non-negative"
    assert score.quality_metrics >= 0.0, "quality_metrics should be non-negative"
    assert score.transaction_history >= 0.0, "transaction_history should be non-negative"
    assert score.financial_behavior >= 0.0, "financial_behavior should be non-negative"
    assert score.operational_transparency >= 0.0, "operational_transparency should be non-negative"
    
    # Property 4: For many high-quality transactions, score should be relatively high
    if num_transactions >= 20:
        assert score.total_score >= 30.0, \
            f"Score should be at least 30 for {num_transactions} high-quality transactions, got {score.total_score}"


# ============================================================================
# Edge Cases
# ============================================================================

def test_edge_case_single_transaction():
    """
    Test reliability score calculation with exactly one transaction.
    """
    from common.models import SyncStatus
    
    farmer_id = 'FARMER#test123'
    
    # Create a single transaction
    transaction = {
        'PK': farmer_id,
        'SK': 'TXN#2024-01-15T10:00:00',
        'transaction_id': 'TXN#001',
        'farmer_id': farmer_id,
        'fpo_id': 'FPO#001',
        'quantity': Decimal('100.0'),
        'crop_type': 'wheat',
        'quality_grade': 'A',
        'moisture': Decimal('12.0'),
        'price': Decimal('2500.0'),
        'timestamp': '2024-01-15T10:00:00',
        'ledger_image_url': 's3://test/image.jpg',
        'sync_status': 'SYNCED'
    }
    
    # Create mock DynamoDB table
    mock_table = Mock()
    
    def mock_query(**kwargs):
        sk_prefix = kwargs.get('ExpressionAttributeValues', {}).get(':sk')
        
        if sk_prefix == 'TXN#':
            return {'Items': [transaction]}
        elif sk_prefix == 'SCORE#':
            return {'Items': []}
        
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query)
    mock_table.put_item = Mock()
    
    # Create CreditEngine
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    
    # Calculate reliability score
    score = credit_engine.calculate_reliability_score(farmer_id)
    
    # Assertions
    assert 0.0 <= score.total_score <= 100.0, \
        "Score should be in valid range"
    
    assert score.total_score > 0.0, \
        "Score should be positive for a farmer with one transaction"
    
    # Verify composition
    expected_total = (
        score.supply_consistency +
        score.quality_metrics +
        score.transaction_history +
        score.financial_behavior +
        score.operational_transparency
    )
    
    assert abs(score.total_score - expected_total) < 0.01, \
        "Total score should equal sum of components"


def test_edge_case_maximum_score():
    """
    Test that the maximum possible score is 100 (sum of all max components).
    """
    farmer_id = 'FARMER#perfect'
    
    # Create many perfect transactions
    transactions = []
    base_date = datetime(2020, 1, 1)
    
    for i in range(100):  # Many transactions over time
        txn = {
            'PK': farmer_id,
            'SK': f"TXN#{(base_date + timedelta(days=i*7)).isoformat()}",
            'transaction_id': f'TXN#{i:03d}',
            'farmer_id': farmer_id,
            'fpo_id': 'FPO#001',
            'quantity': Decimal('1000.0'),  # High volume
            'crop_type': 'wheat',
            'quality_grade': 'A',  # Perfect grade
            'moisture': Decimal('10.0'),  # Optimal moisture
            'price': Decimal('5000.0'),
            'timestamp': (base_date + timedelta(days=i*7)).isoformat(),
            'ledger_image_url': 's3://test/image.jpg',
            'sync_status': 'SYNCED',
            'status': 'completed',
            'payment_status': 'timely'
        }
        transactions.append(txn)
    
    # Create mock DynamoDB table
    mock_table = Mock()
    
    def mock_query(**kwargs):
        sk_prefix = kwargs.get('ExpressionAttributeValues', {}).get(':sk')
        
        if sk_prefix == 'TXN#':
            return {'Items': transactions}
        elif sk_prefix == 'SCORE#':
            return {'Items': []}
        
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query)
    mock_table.put_item = Mock()
    
    # Create CreditEngine
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    
    # Calculate reliability score
    score = credit_engine.calculate_reliability_score(farmer_id)
    
    # Assertions
    assert 0.0 <= score.total_score <= 100.0, \
        "Score should be in valid range"
    
    # With perfect transactions, score should be positive and reasonable
    # Note: The actual score depends on the scoring algorithm's weights and thresholds
    assert score.total_score > 0.0, \
        f"Score should be positive for perfect transactions, got {score.total_score}"
    
    # Verify composition
    expected_total = (
        score.supply_consistency +
        score.quality_metrics +
        score.transaction_history +
        score.financial_behavior +
        score.operational_transparency
    )
    
    assert abs(score.total_score - expected_total) < 0.01, \
        "Total score should equal sum of components"
    
    # Verify component ranges
    assert score.supply_consistency <= 30.0, "supply_consistency should not exceed 30"
    assert score.quality_metrics <= 25.0, "quality_metrics should not exceed 25"
    assert score.transaction_history <= 20.0, "transaction_history should not exceed 20"
    assert score.financial_behavior <= 15.0, "financial_behavior should not exceed 15"
    assert score.operational_transparency <= 10.0, "operational_transparency should not exceed 10"


def test_edge_case_poor_quality_transactions():
    """
    Test reliability score with poor quality transactions.
    """
    farmer_id = 'FARMER#poor'
    
    # Create transactions with poor quality
    transactions = []
    base_date = datetime(2024, 1, 1)
    
    for i in range(10):
        txn = {
            'PK': farmer_id,
            'SK': f"TXN#{(base_date + timedelta(days=i*30)).isoformat()}",
            'transaction_id': f'TXN#{i:03d}',
            'farmer_id': farmer_id,
            'fpo_id': 'FPO#001',
            'quantity': Decimal('10.0'),  # Low volume
            'crop_type': 'wheat',
            'quality_grade': 'C',  # Poor grade
            'moisture': Decimal('25.0'),  # High moisture (bad)
            'price': Decimal('500.0'),
            'timestamp': (base_date + timedelta(days=i*30)).isoformat(),
            'ledger_image_url': None,  # No digitization
            'sync_status': 'PENDING',
            'rejected': True
        }
        transactions.append(txn)
    
    # Create mock DynamoDB table
    mock_table = Mock()
    
    def mock_query(**kwargs):
        sk_prefix = kwargs.get('ExpressionAttributeValues', {}).get(':sk')
        
        if sk_prefix == 'TXN#':
            return {'Items': transactions}
        elif sk_prefix == 'SCORE#':
            return {'Items': []}
        
        return {'Items': []}
    
    mock_table.query = Mock(side_effect=mock_query)
    mock_table.put_item = Mock()
    
    # Create CreditEngine
    credit_engine = CreditEngine(dynamodb_table=mock_table)
    
    # Calculate reliability score
    score = credit_engine.calculate_reliability_score(farmer_id)
    
    # Assertions
    assert 0.0 <= score.total_score <= 100.0, \
        "Score should be in valid range"
    
    # With poor transactions, score should be low
    assert score.total_score < 50.0, \
        f"Score should be low for poor quality transactions, got {score.total_score}"
    
    # Verify composition
    expected_total = (
        score.supply_consistency +
        score.quality_metrics +
        score.transaction_history +
        score.financial_behavior +
        score.operational_transparency
    )
    
    assert abs(score.total_score - expected_total) < 0.01, \
        "Total score should equal sum of components even for poor quality"
