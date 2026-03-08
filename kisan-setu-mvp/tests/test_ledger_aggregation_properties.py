"""
Property-Based Tests for Ledger Aggregation Completeness

Tests Property 6: Ledger Aggregation Completeness
For any list of ledger extractions from the same farmer, aggregating them
should produce a dataset where the total record count equals the sum of
records from all individual ledgers.

**Validates: Requirements 2.6**

Uses Hypothesis framework with minimum 100 iterations.
"""

import pytest
import sys
import os
from datetime import date
from hypothesis import given, settings, strategies as st
from unittest.mock import Mock

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'processor'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from processor.processor import DocumentProcessor, AggregatedData

# Import test data generators
from generators import ledger_batch, ledger_data, uuid_string, crop_type, quality_grade, s3_url


# ============================================================================
# Property 6: Ledger Aggregation Completeness
# ============================================================================

@given(ledgers=ledger_batch(min_ledgers=1, max_ledgers=10))
@settings(max_examples=100, deadline=None)
def test_property_6_ledger_aggregation_completeness(ledgers):
    """
    **Property 6: Ledger Aggregation Completeness**
    **Validates: Requirements 2.6**
    
    For any list of ledger extractions from the same farmer, aggregating them
    should produce a dataset where the total record count equals the sum of
    records from all individual ledgers.
    
    This test verifies that:
    1. The aggregated dataset contains all records from individual ledgers
    2. The total_records field equals the number of input ledgers
    3. All ledger IDs are preserved in the aggregated data
    4. All transaction data is preserved
    5. The farmer_id is consistent across all ledgers
    """
    # Create DocumentProcessor
    processor = DocumentProcessor(
        textract_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Aggregate the ledgers
    aggregated = processor.aggregate_ledgers(ledgers)
    
    # Property 1: Output is an AggregatedData object
    assert isinstance(aggregated, AggregatedData), \
        "Output should be an AggregatedData object"
    
    # Property 2: Total record count equals the number of input ledgers
    assert aggregated.total_records == len(ledgers), \
        f"total_records should equal the number of input ledgers: expected {len(ledgers)}, got {aggregated.total_records}"
    
    # Property 3: Number of transactions equals the number of input ledgers
    assert len(aggregated.transactions) == len(ledgers), \
        f"Number of transactions should equal the number of input ledgers: expected {len(ledgers)}, got {len(aggregated.transactions)}"
    
    # Property 4: All ledger IDs are preserved
    input_ledger_ids = {ledger.ledger_id for ledger in ledgers}
    output_ledger_ids = set(aggregated.ledger_ids)
    assert input_ledger_ids == output_ledger_ids, \
        f"All ledger IDs should be preserved in aggregated data"
    
    # Property 5: Each transaction has a corresponding ledger_id
    transaction_ledger_ids = {txn['ledger_id'] for txn in aggregated.transactions}
    assert transaction_ledger_ids == input_ledger_ids, \
        "Each transaction should have a ledger_id from the input ledgers"
    
    # Property 6: Farmer ID is consistent (all ledgers from same farmer)
    farmer_ids = {ledger.farmer_id for ledger in ledgers}
    assert len(farmer_ids) == 1, \
        "All ledgers should be from the same farmer"
    assert aggregated.farmer_id == ledgers[0].farmer_id, \
        "Aggregated farmer_id should match the input ledgers"
    
    # Property 7: All transaction data is preserved
    for i, ledger in enumerate(ledgers):
        # Find the corresponding transaction
        matching_txn = None
        for txn in aggregated.transactions:
            if txn['ledger_id'] == ledger.ledger_id:
                matching_txn = txn
                break
        
        assert matching_txn is not None, \
            f"Transaction for ledger {ledger.ledger_id} should exist in aggregated data"
        
        # Verify all fields are preserved
        assert matching_txn['quantity'] == ledger.quantity, \
            f"Quantity should be preserved for ledger {ledger.ledger_id}"
        assert matching_txn['moisture'] == ledger.moisture, \
            f"Moisture should be preserved for ledger {ledger.ledger_id}"
        assert matching_txn['price'] == ledger.price, \
            f"Price should be preserved for ledger {ledger.ledger_id}"
        assert matching_txn['date'] == ledger.date, \
            f"Date should be preserved for ledger {ledger.ledger_id}"
        assert matching_txn['crop_type'] == ledger.crop_type, \
            f"Crop type should be preserved for ledger {ledger.ledger_id}"
        assert matching_txn['confidence_scores'] == ledger.confidence_scores, \
            f"Confidence scores should be preserved for ledger {ledger.ledger_id}"
        assert matching_txn['image_url'] == ledger.image_url, \
            f"Image URL should be preserved for ledger {ledger.ledger_id}"
        assert matching_txn['fields_needing_review'] == ledger.fields_needing_review, \
            f"Fields needing review should be preserved for ledger {ledger.ledger_id}"
    
    # Property 8: Aggregation date is set
    assert aggregated.aggregation_date is not None, \
        "Aggregation date should be set"
    assert len(aggregated.aggregation_date) > 0, \
        "Aggregation date should be non-empty"


@given(ledgers=ledger_batch(min_ledgers=2, max_ledgers=5))
@settings(max_examples=100, deadline=None)
def test_property_6_aggregation_preserves_order(ledgers):
    """
    **Property 6: Ledger Aggregation Completeness (Order Preservation)**
    **Validates: Requirements 2.6**
    
    Verify that the order of ledgers is preserved in the aggregated data.
    The transactions should appear in the same order as the input ledgers.
    """
    # Create DocumentProcessor
    processor = DocumentProcessor(
        textract_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Aggregate the ledgers
    aggregated = processor.aggregate_ledgers(ledgers)
    
    # Property: Order is preserved
    for i, ledger in enumerate(ledgers):
        assert aggregated.transactions[i]['ledger_id'] == ledger.ledger_id, \
            f"Transaction at index {i} should correspond to ledger at index {i}"
        assert aggregated.ledger_ids[i] == ledger.ledger_id, \
            f"Ledger ID at index {i} should match input ledger at index {i}"


@given(ledger=ledger_data())
@settings(max_examples=100, deadline=None)
def test_property_6_single_ledger_aggregation(ledger):
    """
    **Property 6: Ledger Aggregation Completeness (Single Ledger)**
    **Validates: Requirements 2.6**
    
    Verify that aggregating a single ledger produces correct results.
    This is an edge case where the list contains only one ledger.
    """
    # Create DocumentProcessor
    processor = DocumentProcessor(
        textract_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Aggregate a single ledger
    aggregated = processor.aggregate_ledgers([ledger])
    
    # Property 1: Total records is 1
    assert aggregated.total_records == 1, \
        "total_records should be 1 for a single ledger"
    
    # Property 2: One transaction
    assert len(aggregated.transactions) == 1, \
        "Should have exactly one transaction"
    
    # Property 3: Ledger ID is preserved
    assert aggregated.ledger_ids[0] == ledger.ledger_id, \
        "Ledger ID should be preserved"
    
    # Property 4: Farmer ID matches
    assert aggregated.farmer_id == ledger.farmer_id, \
        "Farmer ID should match"
    
    # Property 5: All data is preserved
    txn = aggregated.transactions[0]
    assert txn['ledger_id'] == ledger.ledger_id
    assert txn['quantity'] == ledger.quantity
    assert txn['moisture'] == ledger.moisture
    assert txn['price'] == ledger.price
    assert txn['date'] == ledger.date
    assert txn['crop_type'] == ledger.crop_type


@given(
    num_ledgers=st.integers(min_value=1, max_value=20),
    farmer_id=uuid_string(),
    data=st.data()
)
@settings(max_examples=100, deadline=None)
def test_property_6_aggregation_count_invariant(num_ledgers, farmer_id, data):
    """
    **Property 6: Ledger Aggregation Completeness (Count Invariant)**
    **Validates: Requirements 2.6**
    
    For any number of ledgers N, the aggregated dataset should have exactly N records.
    This is the core completeness property: no records are lost or duplicated.
    """
    # Import processor LedgerData
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'processor'))
    from processor.processor import LedgerData as ProcessorLedgerData
    
    # Generate N ledgers with the same farmer_id using data.draw()
    ledgers = []
    for i in range(num_ledgers):
        # Generate confidence scores
        fields = ['quantity', 'moisture', 'price', 'date', 'farmer_name', 'crop_type', 'quality_grade']
        confidence_scores = {
            field.upper(): data.draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
            for field in fields
        }
        
        # Fields with confidence < 70 need review
        fields_needing_review = [field for field, conf in confidence_scores.items() if conf < 70.0]
        
        ledger = ProcessorLedgerData(
            ledger_id=data.draw(uuid_string()),
            farmer_id=farmer_id,
            quantity=data.draw(st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False)),
            moisture=data.draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)),
            price=data.draw(st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False)),
            date=data.draw(st.dates(min_value=date(2020, 1, 1), max_value=date.today())).isoformat(),
            crop_type=data.draw(crop_type()),
            farmer_name=data.draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ', min_size=3, max_size=50)),
            quality_grade=data.draw(quality_grade()),
            confidence_scores=confidence_scores,
            image_url=data.draw(s3_url()),
            fields_needing_review=fields_needing_review
        )
        ledgers.append(ledger)
    
    # Create DocumentProcessor
    processor = DocumentProcessor(
        textract_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Aggregate the ledgers
    aggregated = processor.aggregate_ledgers(ledgers)
    
    # Core Property: Count invariant
    assert aggregated.total_records == num_ledgers, \
        f"Aggregated total_records should equal input count: expected {num_ledgers}, got {aggregated.total_records}"
    
    assert len(aggregated.transactions) == num_ledgers, \
        f"Number of transactions should equal input count: expected {num_ledgers}, got {len(aggregated.transactions)}"
    
    assert len(aggregated.ledger_ids) == num_ledgers, \
        f"Number of ledger IDs should equal input count: expected {num_ledgers}, got {len(aggregated.ledger_ids)}"
    
    # No duplicates
    assert len(set(aggregated.ledger_ids)) == num_ledgers, \
        "All ledger IDs should be unique (no duplicates)"


# ============================================================================
# Edge Cases
# ============================================================================

def test_empty_ledger_list_raises_error():
    """
    Test that aggregating an empty list raises an appropriate error.
    """
    processor = DocumentProcessor(
        textract_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    with pytest.raises(ValueError) as exc_info:
        processor.aggregate_ledgers([])
    
    assert "Cannot aggregate empty ledger list" in str(exc_info.value)


def test_aggregation_with_duplicate_ledger_ids():
    """
    Test that aggregation handles duplicate ledger IDs correctly.
    Even if ledger IDs are duplicated, all records should be preserved.
    """
    # Import processor LedgerData
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'processor'))
    from processor.processor import LedgerData as ProcessorLedgerData
    from datetime import date
    
    # Create two ledgers with the same ledger_id
    ledger1 = ProcessorLedgerData(
        ledger_id='LEDGER#123',
        farmer_id='FARMER#456',
        quantity=100.0,
        moisture=12.0,
        price=2500.0,
        date='2024-01-15',
        crop_type='wheat',
        farmer_name='Rajesh Kumar',
        quality_grade='A',
        confidence_scores={'QUANTITY': 95.0, 'MOISTURE': 90.0, 'PRICE': 92.0, 'DATE': 85.0, 'FARMER_NAME': 88.0, 'CROP_TYPE': 93.0, 'QUALITY_GRADE': 87.0},
        image_url='s3://test/image1.jpg',
        fields_needing_review=[]
    )
    
    ledger2 = ProcessorLedgerData(
        ledger_id='LEDGER#123',  # Duplicate ID
        farmer_id='FARMER#456',  # Same farmer
        quantity=150.0,
        moisture=13.0,
        price=3000.0,
        date='2024-01-16',
        crop_type='rice',
        farmer_name='Rajesh Kumar',
        quality_grade='B',
        confidence_scores={'QUANTITY': 90.0, 'MOISTURE': 88.0, 'PRICE': 91.0, 'DATE': 86.0, 'FARMER_NAME': 89.0, 'CROP_TYPE': 92.0, 'QUALITY_GRADE': 85.0},
        image_url='s3://test/image2.jpg',
        fields_needing_review=[]
    )
    
    processor = DocumentProcessor(
        textract_client=Mock(),
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    aggregated = processor.aggregate_ledgers([ledger1, ledger2])
    
    # Both records should be preserved
    assert aggregated.total_records == 2, \
        "Both ledgers should be counted even with duplicate IDs"
    assert len(aggregated.transactions) == 2, \
        "Both transactions should be preserved"
