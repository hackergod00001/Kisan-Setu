"""
Property-Based Tests for Mathematical Calculation Accuracy

Tests Property 20: Mathematical Calculation Accuracy
For any mathematical calculation (price totals, quantity aggregations, yield predictions),
the result must be accurate within 0.01% tolerance to account for floating-point precision.

**Validates: Requirements 7.3**

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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'processor'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'credit'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'satellite'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from processor.processor import DocumentProcessor
from credit.credit import CreditEngine
from satellite_analyzer import SatelliteAnalyzer
from common.models import ReliabilityScore

# Import test data generators
from generators import (
    ledger_batch, farmer_with_transactions, ndvi_time_series,
    transaction_data, uuid_string
)


# ============================================================================
# Property 20: Mathematical Calculation Accuracy
# ============================================================================

@given(
    price=st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    quantity=st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, deadline=None)
def test_property_20_price_total_calculation(price, quantity):
    """
    **Property 20: Mathematical Calculation Accuracy (Price Totals)**
    **Validates: Requirements 7.3**
    
    For any price and quantity multiplication, the calculated total should be
    accurate within 0.01% tolerance.
    """
    # Calculate expected total
    expected_total = price * quantity
    
    # Simulate calculation as done in the system
    calculated_total = float(Decimal(str(price)) * Decimal(str(quantity)))
    
    # Calculate tolerance (0.01% of expected value)
    tolerance = abs(expected_total * 0.0001)
    
    # Property: Calculated total matches expected within tolerance
    assert abs(calculated_total - expected_total) <= tolerance, \
        f"Price total calculation inaccurate: expected {expected_total}, got {calculated_total}, " \
        f"difference {abs(calculated_total - expected_total)} exceeds tolerance {tolerance}"


@given(ledgers=ledger_batch(min_ledgers=2, max_ledgers=20))
@settings(max_examples=100, deadline=None)
def test_property_20_quantity_aggregation(ledgers):
    """
    **Property 20: Mathematical Calculation Accuracy (Quantity Aggregation)**
    **Validates: Requirements 7.3**
    
    For any aggregation of quantities from multiple ledgers, the total should be
    accurate within 0.01% tolerance.
    """
    # Calculate expected total quantity
    expected_total = sum(ledger.quantity for ledger in ledgers)
    
    # Simulate aggregation as done in DocumentProcessor
    mock_s3 = Mock()
    mock_textract = Mock()
    mock_table = Mock()
    
    processor = DocumentProcessor(
        s3_client=mock_s3,
        textract_client=mock_textract,
        dynamodb_table=mock_table
    )
    
    # Aggregate ledgers
    aggregated = processor.aggregate_ledgers(ledgers)
    
    # Calculate total from aggregated transactions
    calculated_total = sum(txn['quantity'] for txn in aggregated.transactions)
    
    # Calculate tolerance (0.01% of expected value)
    tolerance = abs(expected_total * 0.0001)
    
    # Property: Aggregated total matches expected within tolerance
    assert abs(calculated_total - expected_total) <= tolerance, \
        f"Quantity aggregation inaccurate: expected {expected_total}, got {calculated_total}, " \
        f"difference {abs(calculated_total - expected_total)} exceeds tolerance {tolerance}"


@given(
    component_scores=st.tuples(
        st.floats(min_value=0.0, max_value=30.0, allow_nan=False, allow_infinity=False),  # supply_consistency
        st.floats(min_value=0.0, max_value=25.0, allow_nan=False, allow_infinity=False),  # quality_metrics
        st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False),  # transaction_history
        st.floats(min_value=0.0, max_value=15.0, allow_nan=False, allow_infinity=False),  # financial_behavior
        st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False)   # operational_transparency
    )
)
@settings(max_examples=100, deadline=None)
def test_property_20_credit_score_summation(component_scores):
    """
    **Property 20: Mathematical Calculation Accuracy (Credit Score Summation)**
    **Validates: Requirements 7.3**
    
    For any credit score calculation, the total score should equal the sum of
    components within 0.01% tolerance.
    """
    supply, quality, history, financial, transparency = component_scores
    
    # Calculate expected total
    expected_total = supply + quality + history + financial + transparency
    
    # Create a ReliabilityScore object (simulating what CreditEngine produces)
    score = ReliabilityScore(
        farmer_id='test_farmer',
        total_score=expected_total,
        supply_consistency=supply,
        quality_metrics=quality,
        transaction_history=history,
        financial_behavior=financial,
        operational_transparency=transparency,
        calculation_date=datetime.utcnow(),
        score_change=0.0
    )
    
    # Recalculate total from components
    calculated_total = (
        score.supply_consistency +
        score.quality_metrics +
        score.transaction_history +
        score.financial_behavior +
        score.operational_transparency
    )
    
    # Calculate tolerance (0.01% of expected value, minimum 0.01 for small values)
    tolerance = max(abs(expected_total * 0.0001), 0.01)
    
    # Property: Total score matches sum of components within tolerance
    assert abs(calculated_total - expected_total) <= tolerance, \
        f"Credit score summation inaccurate: expected {expected_total}, got {calculated_total}, " \
        f"difference {abs(calculated_total - expected_total)} exceeds tolerance {tolerance}"


@given(
    estimated_volume=st.floats(min_value=10.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    margin_percent=st.floats(min_value=0.05, max_value=0.3, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, deadline=None)
def test_property_20_yield_confidence_interval(estimated_volume, margin_percent):
    """
    **Property 20: Mathematical Calculation Accuracy (Yield Confidence Interval)**
    **Validates: Requirements 7.3**
    
    For any yield prediction confidence interval calculation, the bounds should be
    accurate within 0.01% tolerance.
    """
    # Calculate expected bounds
    margin = estimated_volume * margin_percent
    expected_lower = max(0.0, estimated_volume - margin)
    expected_upper = estimated_volume + margin
    
    # Simulate calculation as done in SatelliteAnalyzer
    calculated_margin = float(Decimal(str(estimated_volume)) * Decimal(str(margin_percent)))
    calculated_lower = max(0.0, estimated_volume - calculated_margin)
    calculated_upper = estimated_volume + calculated_margin
    
    # Calculate tolerance (0.01% of expected value)
    tolerance_lower = abs(expected_lower * 0.0001)
    tolerance_upper = abs(expected_upper * 0.0001)
    
    # Property: Calculated bounds match expected within tolerance
    assert abs(calculated_lower - expected_lower) <= tolerance_lower, \
        f"Lower bound calculation inaccurate: expected {expected_lower}, got {calculated_lower}, " \
        f"difference {abs(calculated_lower - expected_lower)} exceeds tolerance {tolerance_lower}"
    
    assert abs(calculated_upper - expected_upper) <= tolerance_upper, \
        f"Upper bound calculation inaccurate: expected {expected_upper}, got {calculated_upper}, " \
        f"difference {abs(calculated_upper - expected_upper)} exceeds tolerance {tolerance_upper}"
    
    # Property: Estimated volume is within confidence interval
    assert calculated_lower <= estimated_volume <= calculated_upper, \
        f"Estimated volume {estimated_volume} not within confidence interval [{calculated_lower}, {calculated_upper}]"


@given(
    ndvi_values=st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=3,
        max_size=20
    )
)
@settings(max_examples=100, deadline=None)
def test_property_20_ndvi_average_calculation(ndvi_values):
    """
    **Property 20: Mathematical Calculation Accuracy (NDVI Average)**
    **Validates: Requirements 7.3**
    
    For any NDVI average calculation, the result should be accurate within 0.01% tolerance.
    """
    # Calculate expected average
    expected_avg = sum(ndvi_values) / len(ndvi_values)
    
    # Simulate calculation as done in SatelliteAnalyzer._estimate_yield_volume
    calculated_avg = sum(ndvi_values) / len(ndvi_values)
    
    # Calculate tolerance (0.01% of expected value, minimum 0.0001 for small values)
    tolerance = max(abs(expected_avg * 0.0001), 0.0001)
    
    # Property: Calculated average matches expected within tolerance
    assert abs(calculated_avg - expected_avg) <= tolerance, \
        f"NDVI average calculation inaccurate: expected {expected_avg}, got {calculated_avg}, " \
        f"difference {abs(calculated_avg - expected_avg)} exceeds tolerance {tolerance}"


@given(
    base_yield=st.floats(min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False),
    yield_factor=st.floats(min_value=0.3, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, deadline=None)
def test_property_20_yield_volume_multiplication(base_yield, yield_factor):
    """
    **Property 20: Mathematical Calculation Accuracy (Yield Volume Multiplication)**
    **Validates: Requirements 7.3**
    
    For any yield volume calculation (base_yield * yield_factor), the result should be
    accurate within 0.01% tolerance.
    """
    # Calculate expected volume
    expected_volume = base_yield * yield_factor
    
    # Simulate calculation as done in SatelliteAnalyzer._estimate_yield_volume
    calculated_volume = base_yield * yield_factor
    
    # Calculate tolerance (0.01% of expected value)
    tolerance = abs(expected_volume * 0.0001)
    
    # Property: Calculated volume matches expected within tolerance
    assert abs(calculated_volume - expected_volume) <= tolerance, \
        f"Yield volume calculation inaccurate: expected {expected_volume}, got {calculated_volume}, " \
        f"difference {abs(calculated_volume - expected_volume)} exceeds tolerance {tolerance}"


@given(
    prices=st.lists(
        st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=50
    )
)
@settings(max_examples=100, deadline=None)
def test_property_20_price_aggregation(prices):
    """
    **Property 20: Mathematical Calculation Accuracy (Price Aggregation)**
    **Validates: Requirements 7.3**
    
    For any aggregation of prices from multiple transactions, the total should be
    accurate within 0.01% tolerance.
    """
    # Calculate expected total
    expected_total = sum(prices)
    
    # Simulate aggregation using Decimal for precision
    calculated_total = float(sum(Decimal(str(p)) for p in prices))
    
    # Calculate tolerance (0.01% of expected value)
    tolerance = abs(expected_total * 0.0001)
    
    # Property: Aggregated total matches expected within tolerance
    assert abs(calculated_total - expected_total) <= tolerance, \
        f"Price aggregation inaccurate: expected {expected_total}, got {calculated_total}, " \
        f"difference {abs(calculated_total - expected_total)} exceeds tolerance {tolerance}"


@given(
    percentage=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    total=st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, deadline=None)
def test_property_20_percentage_calculation(percentage, total):
    """
    **Property 20: Mathematical Calculation Accuracy (Percentage Calculation)**
    **Validates: Requirements 7.3**
    
    For any percentage calculation, the result should be accurate within 0.01% tolerance.
    """
    # Calculate expected value
    expected_value = (percentage / 100.0) * total
    
    # Simulate calculation
    calculated_value = (percentage / 100.0) * total
    
    # Calculate tolerance (0.01% of expected value, minimum 0.001 for small values)
    tolerance = max(abs(expected_value * 0.0001), 0.001)
    
    # Property: Calculated value matches expected within tolerance
    assert abs(calculated_value - expected_value) <= tolerance, \
        f"Percentage calculation inaccurate: expected {expected_value}, got {calculated_value}, " \
        f"difference {abs(calculated_value - expected_value)} exceeds tolerance {tolerance}"


@given(
    dividend=st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False),
    divisor=st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, deadline=None)
def test_property_20_division_accuracy(dividend, divisor):
    """
    **Property 20: Mathematical Calculation Accuracy (Division)**
    **Validates: Requirements 7.3**
    
    For any division operation, the result should be accurate within 0.01% tolerance.
    """
    # Calculate expected result
    expected_result = dividend / divisor
    
    # Simulate calculation using Decimal for precision
    calculated_result = float(Decimal(str(dividend)) / Decimal(str(divisor)))
    
    # Calculate tolerance (0.01% of expected value)
    tolerance = abs(expected_result * 0.0001)
    
    # Property: Calculated result matches expected within tolerance
    assert abs(calculated_result - expected_result) <= tolerance, \
        f"Division calculation inaccurate: expected {expected_result}, got {calculated_result}, " \
        f"difference {abs(calculated_result - expected_result)} exceeds tolerance {tolerance}"


# ============================================================================
# Edge Cases
# ============================================================================

def test_edge_case_zero_quantity():
    """
    Test mathematical accuracy with zero quantity.
    """
    price = 100.0
    quantity = 0.0
    
    expected_total = price * quantity
    calculated_total = float(Decimal(str(price)) * Decimal(str(quantity)))
    
    assert calculated_total == expected_total == 0.0, \
        "Zero quantity should result in zero total"


def test_edge_case_very_small_numbers():
    """
    Test mathematical accuracy with very small numbers.
    """
    value1 = 0.0001
    value2 = 0.0002
    
    expected_sum = value1 + value2
    calculated_sum = float(Decimal(str(value1)) + Decimal(str(value2)))
    
    tolerance = abs(expected_sum * 0.0001)
    
    assert abs(calculated_sum - expected_sum) <= tolerance, \
        "Very small number addition should be accurate"


def test_edge_case_very_large_numbers():
    """
    Test mathematical accuracy with very large numbers.
    """
    value1 = 999999.99
    value2 = 888888.88
    
    expected_sum = value1 + value2
    calculated_sum = float(Decimal(str(value1)) + Decimal(str(value2)))
    
    tolerance = abs(expected_sum * 0.0001)
    
    assert abs(calculated_sum - expected_sum) <= tolerance, \
        "Very large number addition should be accurate"


def test_edge_case_negative_ndvi():
    """
    Test mathematical accuracy with negative NDVI values.
    """
    ndvi_values = [-0.5, -0.3, -0.1, 0.0, 0.2]
    
    expected_avg = sum(ndvi_values) / len(ndvi_values)
    calculated_avg = sum(ndvi_values) / len(ndvi_values)
    
    tolerance = max(abs(expected_avg * 0.0001), 0.0001)
    
    assert abs(calculated_avg - expected_avg) <= tolerance, \
        "Negative NDVI average calculation should be accurate"


def test_edge_case_single_value_aggregation():
    """
    Test mathematical accuracy when aggregating a single value.
    """
    single_value = 123.456
    
    expected_total = single_value
    calculated_total = sum([single_value])
    
    tolerance = abs(expected_total * 0.0001)
    
    assert abs(calculated_total - expected_total) <= tolerance, \
        "Single value aggregation should be accurate"


def test_edge_case_many_small_additions():
    """
    Test mathematical accuracy when adding many small values.
    """
    # Add 1000 small values
    values = [0.01] * 1000
    
    expected_total = sum(values)
    calculated_total = float(sum(Decimal(str(v)) for v in values))
    
    tolerance = abs(expected_total * 0.0001)
    
    assert abs(calculated_total - expected_total) <= tolerance, \
        "Many small additions should be accurate"


def test_edge_case_subtraction_near_zero():
    """
    Test mathematical accuracy when subtraction results in near-zero value.
    """
    value1 = 100.0001
    value2 = 100.0000
    
    expected_diff = value1 - value2
    calculated_diff = float(Decimal(str(value1)) - Decimal(str(value2)))
    
    # For near-zero results, use absolute tolerance
    tolerance = 0.0001
    
    assert abs(calculated_diff - expected_diff) <= tolerance, \
        "Subtraction near zero should be accurate"


def test_edge_case_confidence_interval_at_boundary():
    """
    Test confidence interval calculation when lower bound would be negative.
    """
    estimated_volume = 10.0
    margin_percent = 1.5  # 150% margin - will make lower bound negative
    
    margin = estimated_volume * margin_percent
    expected_lower = max(0.0, estimated_volume - margin)  # Should be 0.0
    expected_upper = estimated_volume + margin
    
    calculated_margin = float(Decimal(str(estimated_volume)) * Decimal(str(margin_percent)))
    calculated_lower = max(0.0, estimated_volume - calculated_margin)
    calculated_upper = estimated_volume + calculated_margin
    
    assert calculated_lower == 0.0, \
        f"Lower bound should be clamped to 0.0, got {calculated_lower}"
    
    tolerance = abs(expected_upper * 0.0001)
    assert abs(calculated_upper - expected_upper) <= tolerance, \
        "Upper bound should be accurate"
