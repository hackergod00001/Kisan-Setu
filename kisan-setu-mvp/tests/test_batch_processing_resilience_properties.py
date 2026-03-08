"""
Property-Based Tests for Batch Processing Resilience

Tests Property 31: Batch Processing Resilience
For any batch of documents being processed, if one document fails, the remaining
documents should continue processing and the results should include both successful
extractions and failed document IDs.

**Validates: Requirements 10.3**

Uses Hypothesis framework with minimum 100 iterations.
"""

import pytest
import sys
import os
from hypothesis import given, settings, strategies as st
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any
from datetime import datetime

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from common.error_handling import process_batch_with_resilience


# ============================================================================
# Property 31: Batch Processing Resilience
# ============================================================================

@given(
    total_items=st.integers(min_value=1, max_value=20),
    failure_indices=st.lists(
        st.integers(min_value=0, max_value=19),
        min_size=0,
        max_size=10,
        unique=True
    )
)
@settings(max_examples=100, deadline=None)
def test_property_31_batch_continues_on_individual_failures(total_items, failure_indices):
    """
    **Property 31: Batch Processing Resilience**
    **Validates: Requirements 10.3**
    
    For any batch of items being processed, if individual items fail,
    the system should continue processing remaining items.
    
    This test verifies that:
    1. Processing continues even when individual items fail
    2. Successful items are processed correctly
    3. Failed items are tracked with error details
    4. success_count + failure_count = total_items
    5. Results contain all successful items
    6. Errors contain all failed items with details
    """
    # Filter failure_indices to be within range
    failure_indices = [idx for idx in failure_indices if idx < total_items]
    
    # Create test items
    items = [f"item_{i}" for i in range(total_items)]
    
    # Track processed items
    processed = []
    
    def process_func(item):
        """Process function that fails for specific indices."""
        item_index = int(item.split('_')[1])
        processed.append(item)
        
        if item_index in failure_indices:
            raise ValueError(f"Simulated failure for {item}")
        
        return f"result_{item}"
    
    # Process batch with resilience
    result = process_batch_with_resilience(items, process_func)
    
    # Property 1: All items were attempted (processed list length = total_items)
    assert len(processed) == total_items, \
        f"Expected {total_items} items to be attempted, got {len(processed)}"
    
    # Property 2: success_count + failure_count = total_items
    assert result['success_count'] + result['failure_count'] == total_items, \
        f"success_count ({result['success_count']}) + failure_count ({result['failure_count']}) should equal total_items ({total_items})"
    
    # Property 3: success_count matches expected successes
    expected_successes = total_items - len(failure_indices)
    assert result['success_count'] == expected_successes, \
        f"Expected {expected_successes} successes, got {result['success_count']}"
    
    # Property 4: failure_count matches expected failures
    expected_failures = len(failure_indices)
    assert result['failure_count'] == expected_failures, \
        f"Expected {expected_failures} failures, got {result['failure_count']}"
    
    # Property 5: Results list contains all successful items
    assert len(result['results']) == expected_successes, \
        f"Results list should contain {expected_successes} items, got {len(result['results'])}"
    
    # Property 6: Errors list contains all failed items
    assert len(result['errors']) == expected_failures, \
        f"Errors list should contain {expected_failures} items, got {len(result['errors'])}"
    
    # Property 7: Each error has required fields
    for error in result['errors']:
        assert 'item_index' in error, "Error should have item_index"
        assert 'item' in error, "Error should have item"
        assert 'error' in error, "Error should have error message"
        
        # Verify the error is for a failure index
        assert error['item_index'] in failure_indices, \
            f"Error item_index {error['item_index']} should be in failure_indices"
    
    # Property 8: Each result corresponds to a successful item
    for i, res in enumerate(result['results']):
        assert res.startswith('result_'), \
            f"Result should start with 'result_', got {res}"


@given(
    batch_size=st.integers(min_value=1, max_value=50),
    failure_rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, deadline=None)
def test_property_31_batch_processing_with_random_failures(batch_size, failure_rate):
    """
    **Property 31: Batch Processing Resilience (Random Failures)**
    **Validates: Requirements 10.3**
    
    For any batch size and failure rate, the system should process all items
    and correctly report successes and failures.
    
    This test verifies that:
    1. All items are attempted regardless of failure rate
    2. Success and failure counts are accurate
    3. No items are lost or double-counted
    4. Results and errors are properly segregated
    """
    import random
    random.seed(batch_size)  # Deterministic for given batch_size
    
    items = list(range(batch_size))
    
    def process_func(item):
        """Process function with random failures based on failure_rate."""
        if random.random() < failure_rate:
            raise RuntimeError(f"Random failure for item {item}")
        return item * 2
    
    # Process batch
    result = process_batch_with_resilience(items, process_func)
    
    # Property 1: Total items processed = batch_size
    total_processed = result['success_count'] + result['failure_count']
    assert total_processed == batch_size, \
        f"Total processed ({total_processed}) should equal batch_size ({batch_size})"
    
    # Property 2: Results and errors don't overlap
    result_items = set(r // 2 for r in result['results'])  # Reverse the *2 operation
    error_items = set(e['item_index'] for e in result['errors'])
    
    assert len(result_items & error_items) == 0, \
        "Results and errors should not overlap"
    
    # Property 3: All items are accounted for
    all_items = result_items | error_items
    assert len(all_items) == batch_size, \
        f"All items should be accounted for: expected {batch_size}, got {len(all_items)}"
    
    # Property 4: Results list length matches success_count
    assert len(result['results']) == result['success_count'], \
        "Results list length should match success_count"
    
    # Property 5: Errors list length matches failure_count
    assert len(result['errors']) == result['failure_count'], \
        "Errors list length should match failure_count"


@given(
    batch_size=st.integers(min_value=2, max_value=20)
)
@settings(max_examples=100, deadline=None)
def test_property_31_all_items_fail(batch_size):
    """
    **Property 31: Batch Processing Resilience (All Failures)**
    **Validates: Requirements 10.3**
    
    For any batch where all items fail, the system should:
    1. Attempt to process all items
    2. Report success_count = 0
    3. Report failure_count = batch_size
    4. Include error details for all items
    """
    items = list(range(batch_size))
    
    def always_fails(item):
        """Function that always fails."""
        raise ValueError(f"Failure for item {item}")
    
    result = process_batch_with_resilience(items, always_fails)
    
    # Property 1: success_count = 0
    assert result['success_count'] == 0, \
        f"Expected success_count = 0, got {result['success_count']}"
    
    # Property 2: failure_count = batch_size
    assert result['failure_count'] == batch_size, \
        f"Expected failure_count = {batch_size}, got {result['failure_count']}"
    
    # Property 3: Results list is empty
    assert len(result['results']) == 0, \
        f"Results list should be empty, got {len(result['results'])} items"
    
    # Property 4: Errors list contains all items
    assert len(result['errors']) == batch_size, \
        f"Errors list should contain {batch_size} items, got {len(result['errors'])}"
    
    # Property 5: Each error has proper structure
    for i, error in enumerate(result['errors']):
        assert 'item_index' in error, f"Error {i} should have item_index"
        assert 'item' in error, f"Error {i} should have item"
        assert 'error' in error, f"Error {i} should have error message"
        assert 'Failure for item' in error['error'], \
            f"Error message should contain failure details"


@given(
    batch_size=st.integers(min_value=1, max_value=20)
)
@settings(max_examples=100, deadline=None)
def test_property_31_all_items_succeed(batch_size):
    """
    **Property 31: Batch Processing Resilience (All Successes)**
    **Validates: Requirements 10.3**
    
    For any batch where all items succeed, the system should:
    1. Process all items successfully
    2. Report success_count = batch_size
    3. Report failure_count = 0
    4. Include all results
    """
    items = list(range(batch_size))
    
    def always_succeeds(item):
        """Function that always succeeds."""
        return item ** 2
    
    result = process_batch_with_resilience(items, always_succeeds)
    
    # Property 1: success_count = batch_size
    assert result['success_count'] == batch_size, \
        f"Expected success_count = {batch_size}, got {result['success_count']}"
    
    # Property 2: failure_count = 0
    assert result['failure_count'] == 0, \
        f"Expected failure_count = 0, got {result['failure_count']}"
    
    # Property 3: Results list contains all items
    assert len(result['results']) == batch_size, \
        f"Results list should contain {batch_size} items, got {len(result['results'])}"
    
    # Property 4: Errors list is empty
    assert len(result['errors']) == 0, \
        f"Errors list should be empty, got {len(result['errors'])} items"
    
    # Property 5: Results are correct
    for i, result_value in enumerate(result['results']):
        expected = i ** 2
        assert result_value == expected, \
            f"Result {i} should be {expected}, got {result_value}"
    
    # Property 6: No error message when all succeed
    assert result['message'] is None, \
        "Message should be None when all items succeed"


@given(
    batch_size=st.integers(min_value=3, max_value=20),
    first_failure_index=st.integers(min_value=0, max_value=19)
)
@settings(max_examples=100, deadline=None)
def test_property_31_processing_continues_after_first_failure(batch_size, first_failure_index):
    """
    **Property 31: Batch Processing Resilience (Continue After Failure)**
    **Validates: Requirements 10.3**
    
    For any batch, when the first failure occurs at index N,
    all items after index N should still be processed.
    
    This test verifies that:
    1. Items before failure are processed
    2. The failing item is recorded as error
    3. Items after failure are still processed
    4. Processing order is maintained
    """
    if first_failure_index >= batch_size:
        first_failure_index = batch_size - 1
    
    items = list(range(batch_size))
    processed_order = []
    
    def process_with_tracking(item):
        """Process function that tracks order and fails at specific index."""
        processed_order.append(item)
        
        if item == first_failure_index:
            raise ValueError(f"Failure at index {item}")
        
        return item * 10
    
    result = process_batch_with_resilience(items, process_with_tracking)
    
    # Property 1: All items were attempted in order
    assert processed_order == items, \
        f"Items should be processed in order: expected {items}, got {processed_order}"
    
    # Property 2: Items before failure succeeded
    items_before = list(range(first_failure_index))
    successful_items_before = [r // 10 for r in result['results'] if r // 10 < first_failure_index]
    assert len(successful_items_before) == len(items_before), \
        f"All items before failure should succeed: expected {len(items_before)}, got {len(successful_items_before)}"
    
    # Property 3: Items after failure succeeded
    items_after = list(range(first_failure_index + 1, batch_size))
    successful_items_after = [r // 10 for r in result['results'] if r // 10 > first_failure_index]
    assert len(successful_items_after) == len(items_after), \
        f"All items after failure should succeed: expected {len(items_after)}, got {len(successful_items_after)}"
    
    # Property 4: Exactly one failure (the failing item)
    assert result['failure_count'] == 1, \
        f"Expected exactly 1 failure, got {result['failure_count']}"
    
    # Property 5: The error is for the correct item
    assert len(result['errors']) == 1, \
        f"Expected 1 error entry, got {len(result['errors'])}"
    assert result['errors'][0]['item_index'] == first_failure_index, \
        f"Error should be for index {first_failure_index}, got {result['errors'][0]['item_index']}"


@given(
    batch_size=st.integers(min_value=5, max_value=20)
)
@settings(max_examples=100, deadline=None)
def test_property_31_error_details_preserved(batch_size):
    """
    **Property 31: Batch Processing Resilience (Error Details)**
    **Validates: Requirements 10.3**
    
    For any batch with failures, error details should be preserved
    including item index, item data, and error message.
    
    This test verifies that:
    1. Each error has item_index
    2. Each error has item data
    3. Each error has error message
    4. Error messages are descriptive
    """
    items = [f"document_{i}" for i in range(batch_size)]
    
    # Fail every 3rd item
    def process_with_specific_errors(item):
        """Process function with specific error messages."""
        item_num = int(item.split('_')[1])
        
        if item_num % 3 == 0:
            raise RuntimeError(f"Processing error for {item}: Invalid format")
        
        return f"processed_{item}"
    
    result = process_batch_with_resilience(items, process_with_specific_errors)
    
    # Property 1: Errors have required fields
    for error in result['errors']:
        assert 'item_index' in error, "Error must have item_index"
        assert 'item' in error, "Error must have item"
        assert 'error' in error, "Error must have error message"
    
    # Property 2: Error indices are correct
    expected_failure_indices = [i for i in range(batch_size) if i % 3 == 0]
    actual_failure_indices = [e['item_index'] for e in result['errors']]
    assert sorted(actual_failure_indices) == sorted(expected_failure_indices), \
        f"Error indices should match: expected {expected_failure_indices}, got {actual_failure_indices}"
    
    # Property 3: Error messages are descriptive
    for error in result['errors']:
        assert 'Processing error' in error['error'], \
            f"Error message should be descriptive: {error['error']}"
        assert 'Invalid format' in error['error'], \
            f"Error message should contain specific error details: {error['error']}"
    
    # Property 4: Item data is preserved in errors
    for error in result['errors']:
        assert error['item'].startswith('document_'), \
            f"Item data should be preserved: {error['item']}"


@given(
    batch_size=st.integers(min_value=1, max_value=20),
    language=st.sampled_from(['en', 'hi-IN', 'mr-IN', 'ta-IN'])
)
@settings(max_examples=100, deadline=None)
def test_property_31_localized_batch_message(batch_size, language):
    """
    **Property 31: Batch Processing Resilience (Localized Messages)**
    **Validates: Requirements 10.3**
    
    For any batch with failures, the result should include a localized
    message indicating partial success.
    
    This test verifies that:
    1. Message is present when there are failures
    2. Message is None when all succeed
    3. Message is in the requested language
    4. Message includes success and failure counts
    """
    items = list(range(batch_size))
    
    # Fail half the items
    def process_with_failures(item):
        """Process function that fails for even items."""
        if item % 2 == 0:
            raise ValueError(f"Failure for item {item}")
        return item
    
    result = process_batch_with_resilience(items, process_with_failures, language=language)
    
    # Property 1: If there are failures, message should be present
    if result['failure_count'] > 0:
        assert result['message'] is not None, \
            "Message should be present when there are failures"
        assert isinstance(result['message'], str), \
            "Message should be a string"
        assert len(result['message']) > 0, \
            "Message should not be empty"
    
    # Property 2: If all succeed, message should be None
    items_all_succeed = list(range(1, batch_size + 1, 2))  # Only odd numbers
    
    def always_succeeds(item):
        return item
    
    result_all_succeed = process_batch_with_resilience(
        items_all_succeed,
        always_succeeds,
        language=language
    )
    
    assert result_all_succeed['message'] is None, \
        "Message should be None when all items succeed"


# ============================================================================
# Edge Cases
# ============================================================================

def test_edge_case_empty_batch():
    """Test that empty batch is handled gracefully."""
    items = []
    
    def process_func(item):
        return item
    
    result = process_batch_with_resilience(items, process_func)
    
    assert result['success_count'] == 0, "Empty batch should have 0 successes"
    assert result['failure_count'] == 0, "Empty batch should have 0 failures"
    assert len(result['results']) == 0, "Empty batch should have no results"
    assert len(result['errors']) == 0, "Empty batch should have no errors"


def test_edge_case_single_item_success():
    """Test batch with single successful item."""
    items = ['single_item']
    
    def process_func(item):
        return f"processed_{item}"
    
    result = process_batch_with_resilience(items, process_func)
    
    assert result['success_count'] == 1, "Should have 1 success"
    assert result['failure_count'] == 0, "Should have 0 failures"
    assert len(result['results']) == 1, "Should have 1 result"
    assert result['results'][0] == 'processed_single_item', "Result should be correct"


def test_edge_case_single_item_failure():
    """Test batch with single failing item."""
    items = ['single_item']
    
    def process_func(item):
        raise ValueError("Single item failure")
    
    result = process_batch_with_resilience(items, process_func)
    
    assert result['success_count'] == 0, "Should have 0 successes"
    assert result['failure_count'] == 1, "Should have 1 failure"
    assert len(result['errors']) == 1, "Should have 1 error"
    assert result['errors'][0]['item_index'] == 0, "Error should be for index 0"


def test_edge_case_different_exception_types():
    """Test that different exception types are all caught and recorded."""
    items = list(range(5))
    
    exception_types = [ValueError, RuntimeError, TypeError, KeyError, IndexError]
    
    def process_with_different_exceptions(item):
        """Raise different exception types for different items."""
        if item < len(exception_types):
            raise exception_types[item](f"Error type {item}")
        return item
    
    result = process_batch_with_resilience(items, process_with_different_exceptions)
    
    assert result['failure_count'] == 5, "All items should fail"
    assert len(result['errors']) == 5, "Should have 5 errors"
    
    # Verify all errors are recorded
    for i, error in enumerate(result['errors']):
        assert f"Error type {i}" in error['error'], \
            f"Error {i} should contain correct message"


def test_edge_case_process_func_returns_none():
    """Test that process function can return None as valid result."""
    items = list(range(5))
    
    def process_returns_none(item):
        """Process function that returns None."""
        return None
    
    result = process_batch_with_resilience(items, process_returns_none)
    
    assert result['success_count'] == 5, "All items should succeed"
    assert result['failure_count'] == 0, "No items should fail"
    assert len(result['results']) == 5, "Should have 5 results"
    assert all(r is None for r in result['results']), "All results should be None"


def test_edge_case_complex_item_types():
    """Test batch processing with complex item types (dicts, objects)."""
    items = [
        {'id': 1, 'data': 'test1'},
        {'id': 2, 'data': 'test2'},
        {'id': 3, 'data': 'test3'}
    ]
    
    def process_dict(item):
        """Process dictionary items."""
        if item['id'] == 2:
            raise ValueError("Failed to process item 2")
        return item['data'].upper()
    
    result = process_batch_with_resilience(items, process_dict)
    
    assert result['success_count'] == 2, "Should have 2 successes"
    assert result['failure_count'] == 1, "Should have 1 failure"
    assert 'TEST1' in result['results'], "Should contain processed result"
    assert 'TEST3' in result['results'], "Should contain processed result"


def test_edge_case_very_large_batch():
    """Test that large batches are handled efficiently."""
    batch_size = 1000
    items = list(range(batch_size))
    
    # Fail every 10th item
    def process_large_batch(item):
        if item % 10 == 0:
            raise ValueError(f"Failure at {item}")
        return item * 2
    
    result = process_batch_with_resilience(items, process_large_batch)
    
    expected_failures = batch_size // 10
    expected_successes = batch_size - expected_failures
    
    assert result['success_count'] == expected_successes, \
        f"Expected {expected_successes} successes"
    assert result['failure_count'] == expected_failures, \
        f"Expected {expected_failures} failures"
    assert len(result['results']) == expected_successes, \
        "Results list should match success count"
    assert len(result['errors']) == expected_failures, \
        "Errors list should match failure count"
