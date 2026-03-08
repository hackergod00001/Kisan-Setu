"""
Property-Based Tests for Exponential Backoff Retry Logic

Tests Property 29: Exponential Backoff Retry Logic
For any failed external service call, retry attempts must use exponential backoff
with delays of 1s, 2s, 4s (doubling each time) up to a maximum of 3 retries.

**Validates: Requirements 10.1**

Uses Hypothesis framework with minimum 100 iterations.
"""

import pytest
import sys
import os
from hypothesis import given, settings, strategies as st
from unittest.mock import Mock, patch, call
import time
from typing import List

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from common.error_handling import retry_with_exponential_backoff


# ============================================================================
# Property 29: Exponential Backoff Retry Logic
# ============================================================================

@given(
    max_retries=st.integers(min_value=1, max_value=5),
    initial_delay=st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False),
    backoff_factor=st.floats(min_value=1.5, max_value=3.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, deadline=None)
def test_property_29_exponential_backoff_delays(max_retries, initial_delay, backoff_factor):
    """
    **Property 29: Exponential Backoff Retry Logic**
    **Validates: Requirements 10.1**
    
    For any failed external service call, the system should retry up to max_retries times
    with exponentially increasing delays (initial_delay * backoff_factor^attempt).
    
    This test verifies that:
    1. Retry attempts occur exactly max_retries times before giving up
    2. Delays between retries follow exponential backoff pattern
    3. Each delay is approximately initial_delay * (backoff_factor ^ attempt_number)
    4. Total attempts = max_retries + 1 (initial attempt + retries)
    5. Final exception is raised after all retries are exhausted
    """
    # Track function calls and sleep times using dict to avoid closure issues
    state = {'call_times': [], 'sleep_times': []}
    
    # Create a function that always fails
    @retry_with_exponential_backoff(
        max_retries=max_retries,
        initial_delay=initial_delay,
        backoff_factor=backoff_factor,
        use_circuit_breaker=False
    )
    def failing_function():
        """Function that always raises an exception."""
        state['call_times'].append(time.time())
        raise ValueError("Simulated service failure")
    
    def mock_sleep(seconds):
        """Track sleep duration without actually sleeping."""
        state['sleep_times'].append(seconds)
    
    with patch('common.error_handling.time.sleep', side_effect=mock_sleep):
        # Execute and expect failure
        with pytest.raises(ValueError, match="Simulated service failure"):
            failing_function()
    
    # Property 1: Total attempts = max_retries + 1 (initial + retries)
    expected_attempts = max_retries + 1
    assert len(state['call_times']) == expected_attempts, \
        f"Expected {expected_attempts} attempts, got {len(state['call_times'])}"
    
    # Property 2: Number of sleeps = max_retries (no sleep after last attempt)
    assert len(state['sleep_times']) == max_retries, \
        f"Expected {max_retries} sleep calls, got {len(state['sleep_times'])}"
    
    # Property 3: Each delay follows exponential backoff pattern
    for attempt in range(max_retries):
        expected_delay = initial_delay * (backoff_factor ** attempt)
        actual_delay = state['sleep_times'][attempt]
        
        # Allow 1% tolerance for floating point precision
        tolerance = expected_delay * 0.01
        assert abs(actual_delay - expected_delay) <= tolerance, \
            f"Attempt {attempt}: Expected delay ~{expected_delay}s, got {actual_delay}s"
    
    # Property 4: Delays are monotonically increasing (each delay > previous)
    for i in range(1, len(state['sleep_times'])):
        assert state['sleep_times'][i] > state['sleep_times'][i-1], \
            f"Delay {i} ({state['sleep_times'][i]}s) should be greater than delay {i-1} ({state['sleep_times'][i-1]}s)"
    
    # Property 5: First delay equals initial_delay
    if len(state['sleep_times']) > 0:
        tolerance = initial_delay * 0.01
        assert abs(state['sleep_times'][0] - initial_delay) <= tolerance, \
            f"First delay should be {initial_delay}s, got {state['sleep_times'][0]}s"


@given(
    failure_count=st.integers(min_value=1, max_value=3)
)
@settings(max_examples=100, deadline=None)
def test_property_29_retry_success_before_max_attempts(failure_count):
    """
    **Property 29: Exponential Backoff Retry Logic (Early Success)**
    **Validates: Requirements 10.1**
    
    For any external service call that succeeds before max_retries is reached,
    the retry logic should stop immediately and return the successful result.
    
    This test verifies that:
    1. If function succeeds on attempt N (where N <= max_retries), no further retries occur
    2. The successful result is returned
    3. Total attempts = failure_count + 1 (failures + success)
    4. Delays follow exponential backoff for failed attempts only
    """
    max_retries = 3
    initial_delay = 1.0
    backoff_factor = 2.0
    
    # Use list to track state (avoid closure issues)
    state = {'call_count': 0, 'sleep_times': []}
    
    @retry_with_exponential_backoff(
        max_retries=max_retries,
        initial_delay=initial_delay,
        backoff_factor=backoff_factor,
        use_circuit_breaker=False
    )
    def eventually_succeeds():
        """Function that fails failure_count times, then succeeds."""
        state['call_count'] += 1
        
        if state['call_count'] <= failure_count:
            raise ValueError(f"Failure {state['call_count']}")
        
        return "SUCCESS"
    
    def mock_sleep(seconds):
        """Track sleep duration."""
        state['sleep_times'].append(seconds)
        # Don't actually sleep to avoid issues
    
    with patch('time.sleep', side_effect=mock_sleep):
        with patch('common.error_handling.time.sleep', side_effect=mock_sleep):
            result = eventually_succeeds()
    
    # Property 1: Function returns successful result
    assert result == "SUCCESS", \
        "Function should return successful result"
    
    # Property 2: Total attempts = failure_count + 1
    expected_attempts = failure_count + 1
    assert state['call_count'] == expected_attempts, \
        f"Expected {expected_attempts} attempts, got {state['call_count']}"
    
    # Property 3: Number of sleeps = failure_count (sleep after each failure)
    assert len(state['sleep_times']) == failure_count, \
        f"Expected {failure_count} sleep calls, got {len(state['sleep_times'])}"
    
    # Property 4: Delays follow exponential backoff pattern
    for attempt in range(failure_count):
        expected_delay = initial_delay * (backoff_factor ** attempt)
        actual_delay = state['sleep_times'][attempt]
        
        tolerance = expected_delay * 0.01
        assert abs(actual_delay - expected_delay) <= tolerance, \
            f"Attempt {attempt}: Expected delay ~{expected_delay}s, got {actual_delay}s"


@settings(max_examples=100, deadline=None)
@given(st.integers(min_value=0, max_value=10))
def test_property_29_default_retry_parameters(seed):
    """
    **Property 29: Exponential Backoff Retry Logic (Default Parameters)**
    **Validates: Requirements 10.1**
    
    For any external service call using default retry parameters,
    the system should use:
    - max_retries = 3
    - initial_delay = 1.0s
    - backoff_factor = 2.0
    - Resulting in delays: 1s, 2s, 4s
    
    This test verifies the default configuration matches requirements.
    """
    state = {'call_count': 0, 'sleep_times': []}
    
    @retry_with_exponential_backoff(use_circuit_breaker=False)
    def failing_function():
        """Function that always fails."""
        state['call_count'] += 1
        raise ValueError("Service failure")
    
    def mock_sleep(seconds):
        """Track sleep duration."""
        state['sleep_times'].append(seconds)
    
    with patch('common.error_handling.time.sleep', side_effect=mock_sleep):
        with pytest.raises(ValueError):
            failing_function()
    
    # Property 1: Default max_retries = 3, so 4 total attempts
    assert state['call_count'] == 4, \
        f"Expected 4 attempts with default max_retries=3, got {state['call_count']}"
    
    # Property 2: Default delays are 1s, 2s, 4s
    expected_delays = [1.0, 2.0, 4.0]
    assert len(state['sleep_times']) == 3, \
        f"Expected 3 sleep calls, got {len(state['sleep_times'])}"
    
    for i, expected_delay in enumerate(expected_delays):
        actual_delay = state['sleep_times'][i]
        tolerance = expected_delay * 0.01
        assert abs(actual_delay - expected_delay) <= tolerance, \
            f"Delay {i}: Expected {expected_delay}s, got {actual_delay}s"
    
    # Property 3: Delays double each time (exponential with factor 2.0)
    for i in range(1, len(state['sleep_times'])):
        ratio = state['sleep_times'][i] / state['sleep_times'][i-1]
        assert abs(ratio - 2.0) < 0.01, \
            f"Delay ratio should be 2.0, got {ratio}"


@given(
    exception_type=st.sampled_from([
        ValueError,
        RuntimeError,
        ConnectionError,
        TimeoutError,
        Exception
    ])
)
@settings(max_examples=100, deadline=None)
def test_property_29_exception_propagation(exception_type):
    """
    **Property 29: Exponential Backoff Retry Logic (Exception Propagation)**
    **Validates: Requirements 10.1**
    
    For any type of exception raised by the external service,
    after all retries are exhausted, the original exception should be propagated.
    
    This test verifies that:
    1. The exception type is preserved
    2. The exception message is preserved
    3. All retries are attempted before raising
    """
    max_retries = 3
    error_message = "Specific error message"
    state = {'call_count': 0}
    
    @retry_with_exponential_backoff(
        max_retries=max_retries,
        use_circuit_breaker=False
    )
    def failing_function():
        """Function that raises specific exception."""
        state['call_count'] += 1
        raise exception_type(error_message)
    
    with patch('common.error_handling.time.sleep'):
        # Property 1: Exception is raised after retries
        with pytest.raises(exception_type) as exc_info:
            failing_function()
        
        # Property 2: Exception message is preserved
        assert error_message in str(exc_info.value), \
            f"Exception message should contain '{error_message}'"
        
        # Property 3: All retries were attempted
        assert state['call_count'] == max_retries + 1, \
            f"Expected {max_retries + 1} attempts, got {state['call_count']}"


@given(
    max_retries=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=100, deadline=None)
def test_property_29_no_retry_on_success(max_retries):
    """
    **Property 29: Exponential Backoff Retry Logic (No Retry on Success)**
    **Validates: Requirements 10.1**
    
    For any external service call that succeeds on the first attempt,
    no retries should occur and no delays should be introduced.
    
    This test verifies that:
    1. Successful first attempt returns immediately
    2. No sleep calls are made
    3. Function is called exactly once
    """
    state = {'call_count': 0, 'sleep_called': False}
    
    @retry_with_exponential_backoff(
        max_retries=max_retries,
        use_circuit_breaker=False
    )
    def successful_function():
        """Function that succeeds immediately."""
        state['call_count'] += 1
        return "SUCCESS"
    
    def mock_sleep(seconds):
        """Track if sleep is called."""
        state['sleep_called'] = True
    
    with patch('common.error_handling.time.sleep', side_effect=mock_sleep):
        result = successful_function()
    
    # Property 1: Function returns successful result
    assert result == "SUCCESS", \
        "Function should return successful result"
    
    # Property 2: Function called exactly once
    assert state['call_count'] == 1, \
        f"Expected 1 call for immediate success, got {state['call_count']}"
    
    # Property 3: No sleep calls made
    assert not state['sleep_called'], \
        "No sleep should occur for immediate success"


@given(
    max_retries=st.integers(min_value=1, max_value=5),
    initial_delay=st.floats(min_value=0.1, max_value=2.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, deadline=None)
def test_property_29_total_retry_time_bounds(max_retries, initial_delay):
    """
    **Property 29: Exponential Backoff Retry Logic (Time Bounds)**
    **Validates: Requirements 10.1**
    
    For any retry configuration, the total time spent in retries should be
    bounded by the sum of all exponential delays.
    
    This test verifies that:
    1. Total delay time = sum of all exponential delays
    2. Total delay follows the formula: initial_delay * (backoff_factor^(max_retries) - 1) / (backoff_factor - 1)
    """
    backoff_factor = 2.0
    state = {'sleep_times': []}
    
    @retry_with_exponential_backoff(
        max_retries=max_retries,
        initial_delay=initial_delay,
        backoff_factor=backoff_factor,
        use_circuit_breaker=False
    )
    def failing_function():
        """Function that always fails."""
        raise ValueError("Service failure")
    
    def mock_sleep(seconds):
        """Track sleep duration."""
        state['sleep_times'].append(seconds)
    
    with patch('common.error_handling.time.sleep', side_effect=mock_sleep):
        with pytest.raises(ValueError):
            failing_function()
    
    # Property 1: Total delay equals sum of individual delays
    total_delay = sum(state['sleep_times'])
    
    # Property 2: Total delay matches exponential series formula
    # Sum = a * (r^n - 1) / (r - 1) where a=initial_delay, r=backoff_factor, n=max_retries
    expected_total = initial_delay * ((backoff_factor ** max_retries) - 1) / (backoff_factor - 1)
    
    tolerance = expected_total * 0.01
    assert abs(total_delay - expected_total) <= tolerance, \
        f"Total delay should be ~{expected_total}s, got {total_delay}s"
    
    # Property 3: Each individual delay contributes to total
    reconstructed_total = sum(
        initial_delay * (backoff_factor ** i)
        for i in range(max_retries)
    )
    
    tolerance = reconstructed_total * 0.01
    assert abs(total_delay - reconstructed_total) <= tolerance, \
        f"Total delay should match sum of exponential delays: {reconstructed_total}s, got {total_delay}s"


# ============================================================================
# Edge Cases
# ============================================================================

def test_edge_case_zero_retries():
    """Test that max_retries=0 means no retries (only initial attempt)."""
    state = {'call_count': 0}
    
    @retry_with_exponential_backoff(max_retries=0, use_circuit_breaker=False)
    def failing_function():
        state['call_count'] += 1
        raise ValueError("Failure")
    
    with patch('common.error_handling.time.sleep'):
        with pytest.raises(ValueError):
            failing_function()
    
    # Should be called exactly once (no retries)
    assert state['call_count'] == 1, \
        f"With max_retries=0, expected 1 call, got {state['call_count']}"


def test_edge_case_very_small_initial_delay():
    """Test that very small initial delays still follow exponential pattern."""
    initial_delay = 0.01
    max_retries = 3
    backoff_factor = 2.0
    state = {'sleep_times': []}
    
    @retry_with_exponential_backoff(
        max_retries=max_retries,
        initial_delay=initial_delay,
        backoff_factor=backoff_factor,
        use_circuit_breaker=False
    )
    def failing_function():
        raise ValueError("Failure")
    
    def mock_sleep(seconds):
        state['sleep_times'].append(seconds)
    
    with patch('common.error_handling.time.sleep', side_effect=mock_sleep):
        with pytest.raises(ValueError):
            failing_function()
    
    # Verify exponential pattern even with tiny delays
    expected_delays = [0.01, 0.02, 0.04]
    for i, expected in enumerate(expected_delays):
        assert abs(state['sleep_times'][i] - expected) < 0.001, \
            f"Delay {i}: Expected {expected}s, got {state['sleep_times'][i]}s"


def test_edge_case_large_backoff_factor():
    """Test that large backoff factors create rapidly increasing delays."""
    initial_delay = 1.0
    max_retries = 3
    backoff_factor = 10.0
    state = {'sleep_times': []}
    
    @retry_with_exponential_backoff(
        max_retries=max_retries,
        initial_delay=initial_delay,
        backoff_factor=backoff_factor,
        use_circuit_breaker=False
    )
    def failing_function():
        raise ValueError("Failure")
    
    def mock_sleep(seconds):
        state['sleep_times'].append(seconds)
    
    with patch('common.error_handling.time.sleep', side_effect=mock_sleep):
        with pytest.raises(ValueError):
            failing_function()
    
    # Verify rapid exponential growth: 1s, 10s, 100s
    expected_delays = [1.0, 10.0, 100.0]
    for i, expected in enumerate(expected_delays):
        assert abs(state['sleep_times'][i] - expected) < 0.01, \
            f"Delay {i}: Expected {expected}s, got {state['sleep_times'][i]}s"


def test_edge_case_function_with_return_value():
    """Test that successful function return values are preserved through decorator."""
    expected_result = {"data": "test_value", "count": 42}
    
    @retry_with_exponential_backoff(use_circuit_breaker=False)
    def successful_function():
        return expected_result
    
    result = successful_function()
    
    assert result == expected_result, \
        "Return value should be preserved through decorator"


def test_edge_case_function_with_arguments():
    """Test that function arguments are correctly passed through decorator."""
    state = {'call_args': []}
    
    @retry_with_exponential_backoff(max_retries=2, use_circuit_breaker=False)
    def function_with_args(a, b, c=None):
        state['call_args'].append((a, b, c))
        if len(state['call_args']) < 2:
            raise ValueError("Fail first time")
        return a + b
    
    with patch('common.error_handling.time.sleep'):
        result = function_with_args(10, 20, c="test")
    
    # Verify arguments passed correctly on all attempts
    assert len(state['call_args']) == 2
    assert state['call_args'][0] == (10, 20, "test")
    assert state['call_args'][1] == (10, 20, "test")
    assert result == 30
