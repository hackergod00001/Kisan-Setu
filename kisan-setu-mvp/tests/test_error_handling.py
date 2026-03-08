"""
Unit tests for error handling and retry logic.

Tests the error handling infrastructure including:
- ErrorResponse dataclass
- Exponential backoff retry logic
- Localized error messages
- Circuit breaker pattern
- Batch processing resilience
- Critical error alerting
"""

import pytest
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from common.error_handling import (
    ErrorResponse,
    ErrorCategory,
    ErrorSeverity,
    get_localized_message,
    CircuitBreaker,
    retry_with_exponential_backoff,
    process_batch_with_resilience,
    create_error_response,
    CriticalErrorAlerter
)


class TestErrorResponse:
    """Test ErrorResponse dataclass."""
    
    def test_error_response_creation(self):
        """Test creating an ErrorResponse."""
        error = ErrorResponse(
            error_code='TEST_ERROR',
            user_message='Test error message',
            technical_details='Technical details',
            suggested_action='Try again',
            category=ErrorCategory.USER_INPUT,
            severity=ErrorSeverity.LOW
        )
        
        assert error.error_code == 'TEST_ERROR'
        assert error.user_message == 'Test error message'
        assert error.technical_details == 'Technical details'
        assert error.suggested_action == 'Try again'
        assert error.category == ErrorCategory.USER_INPUT
        assert error.severity == ErrorSeverity.LOW
        assert error.timestamp is not None
    
    def test_error_response_to_dict(self):
        """Test converting ErrorResponse to dictionary."""
        error = ErrorResponse(
            error_code='TEST_ERROR',
            user_message='Test message',
            technical_details='Details',
            suggested_action='Action',
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.CRITICAL
        )
        
        error_dict = error.to_dict()
        
        assert error_dict['error_code'] == 'TEST_ERROR'
        assert error_dict['category'] == 'system_error'
        assert error_dict['severity'] == 'critical'
        assert 'timestamp' in error_dict


class TestLocalizedMessages:
    """Test localized error messages."""
    
    def test_get_english_message(self):
        """Test getting English error message."""
        message = get_localized_message('INVALID_GPS', 'en')
        assert 'Invalid GPS coordinates' in message
        assert 'latitude' in message.lower()
    
    def test_get_hindi_message(self):
        """Test getting Hindi error message."""
        message = get_localized_message('INVALID_GPS', 'hi-IN')
        assert 'GPS' in message
        # Hindi text should be present
        assert len(message) > 0
    
    def test_get_marathi_message(self):
        """Test getting Marathi error message."""
        message = get_localized_message('SERVICE_UNAVAILABLE', 'mr-IN')
        assert len(message) > 0
    
    def test_get_tamil_message(self):
        """Test getting Tamil error message."""
        message = get_localized_message('AUDIO_QUALITY_POOR', 'ta-IN')
        assert len(message) > 0
    
    def test_fallback_to_english(self):
        """Test fallback to English for unsupported language."""
        message = get_localized_message('INVALID_GPS', 'fr-FR')
        assert 'Invalid GPS coordinates' in message
    
    def test_message_formatting(self):
        """Test message formatting with parameters."""
        message = get_localized_message(
            'BATCH_PROCESSING_PARTIAL',
            'en',
            success_count=5,
            failure_count=2
        )
        assert '5' in message
        assert '2' in message


class TestCircuitBreaker:
    """Test circuit breaker pattern."""
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in CLOSED state (normal operation)."""
        cb = CircuitBreaker('test-service', failure_threshold=3)
        
        def successful_func():
            return 'success'
        
        result = cb.call(successful_func)
        assert result == 'success'
        assert cb.state == 'CLOSED'
        assert cb.failure_count == 0
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        cb = CircuitBreaker('test-service', failure_threshold=3)
        
        def failing_func():
            raise Exception('Service error')
        
        # Trigger failures
        for i in range(3):
            with pytest.raises(Exception):
                cb.call(failing_func)
        
        assert cb.state == 'OPEN'
        assert cb.failure_count >= 3
    
    def test_circuit_breaker_rejects_when_open(self):
        """Test circuit breaker rejects calls when OPEN."""
        cb = CircuitBreaker('test-service', failure_threshold=2, timeout_seconds=10)
        
        def failing_func():
            raise Exception('Service error')
        
        # Open the circuit
        for i in range(2):
            with pytest.raises(Exception):
                cb.call(failing_func)
        
        assert cb.state == 'OPEN'
        
        # Next call should be rejected immediately
        with pytest.raises(Exception) as exc_info:
            cb.call(failing_func)
        
        assert 'Circuit breaker OPEN' in str(exc_info.value)
    
    def test_circuit_breaker_half_open_after_timeout(self):
        """Test circuit breaker enters HALF_OPEN after timeout."""
        cb = CircuitBreaker('test-service', failure_threshold=2, timeout_seconds=1)
        
        def failing_func():
            raise Exception('Service error')
        
        # Open the circuit
        for i in range(2):
            with pytest.raises(Exception):
                cb.call(failing_func)
        
        assert cb.state == 'OPEN'
        
        # Wait for timeout
        time.sleep(1.1)
        
        # Next call should transition to HALF_OPEN
        with pytest.raises(Exception):
            cb.call(failing_func)
        
        # State should have been HALF_OPEN during the call
        assert cb.state == 'OPEN'  # Back to OPEN after failure in HALF_OPEN
    
    def test_circuit_breaker_closes_after_success_in_half_open(self):
        """Test circuit breaker closes after successes in HALF_OPEN."""
        cb = CircuitBreaker('test-service', failure_threshold=2, timeout_seconds=1, success_threshold=2)
        
        call_count = [0]
        
        def sometimes_failing_func():
            call_count[0] += 1
            if call_count[0] <= 2:
                raise Exception('Service error')
            return 'success'
        
        # Open the circuit
        for i in range(2):
            with pytest.raises(Exception):
                cb.call(sometimes_failing_func)
        
        assert cb.state == 'OPEN'
        
        # Wait for timeout
        time.sleep(1.1)
        
        # Successful calls should close the circuit
        result1 = cb.call(sometimes_failing_func)
        result2 = cb.call(sometimes_failing_func)
        
        assert result1 == 'success'
        assert result2 == 'success'
        assert cb.state == 'CLOSED'


class TestRetryWithExponentialBackoff:
    """Test exponential backoff retry logic."""
    
    def test_successful_call_no_retry(self):
        """Test successful call doesn't retry."""
        call_count = [0]
        
        @retry_with_exponential_backoff(max_retries=3, initial_delay=0.1)
        def successful_func():
            call_count[0] += 1
            return 'success'
        
        result = successful_func()
        
        assert result == 'success'
        assert call_count[0] == 1  # Called only once
    
    def test_retry_on_failure(self):
        """Test retry on failure with exponential backoff."""
        call_count = [0]
        
        @retry_with_exponential_backoff(max_retries=3, initial_delay=0.1)
        def failing_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception('Temporary error')
            return 'success'
        
        start_time = time.time()
        result = failing_func()
        elapsed = time.time() - start_time
        
        assert result == 'success'
        assert call_count[0] == 3  # Called 3 times
        # Should have delays: 0.1s, 0.2s = 0.3s total minimum
        assert elapsed >= 0.3
    
    def test_all_retries_exhausted(self):
        """Test all retries exhausted raises exception."""
        call_count = [0]
        
        @retry_with_exponential_backoff(max_retries=2, initial_delay=0.1)
        def always_failing_func():
            call_count[0] += 1
            raise Exception('Permanent error')
        
        with pytest.raises(Exception) as exc_info:
            always_failing_func()
        
        assert 'Permanent error' in str(exc_info.value)
        assert call_count[0] == 3  # Initial + 2 retries
    
    def test_exponential_backoff_delays(self):
        """Test exponential backoff delay progression."""
        call_times = []
        
        @retry_with_exponential_backoff(max_retries=3, initial_delay=0.1, backoff_factor=2.0)
        def failing_func():
            call_times.append(time.time())
            if len(call_times) < 4:
                raise Exception('Error')
            return 'success'
        
        result = failing_func()
        
        assert result == 'success'
        assert len(call_times) == 4
        
        # Check delays: ~0.1s, ~0.2s, ~0.4s
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        delay3 = call_times[3] - call_times[2]
        
        assert 0.09 <= delay1 <= 0.15
        assert 0.18 <= delay2 <= 0.25
        assert 0.35 <= delay3 <= 0.45


class TestBatchProcessingResilience:
    """Test batch processing with resilience."""
    
    def test_all_items_succeed(self):
        """Test batch processing when all items succeed."""
        items = [1, 2, 3, 4, 5]
        
        def process_func(item):
            return item * 2
        
        result = process_batch_with_resilience(items, process_func)
        
        assert result['success_count'] == 5
        assert result['failure_count'] == 0
        assert result['results'] == [2, 4, 6, 8, 10]
        assert len(result['errors']) == 0
        assert result['message'] is None
    
    def test_some_items_fail(self):
        """Test batch processing continues when some items fail."""
        items = [1, 2, 3, 4, 5]
        
        def process_func(item):
            if item == 2 or item == 4:
                raise Exception(f'Failed to process {item}')
            return item * 2
        
        result = process_batch_with_resilience(items, process_func, language='en')
        
        assert result['success_count'] == 3
        assert result['failure_count'] == 2
        assert result['results'] == [2, 6, 10]
        assert len(result['errors']) == 2
        assert result['message'] is not None
        assert '3' in result['message']  # success_count
        assert '2' in result['message']  # failure_count
    
    def test_all_items_fail(self):
        """Test batch processing when all items fail."""
        items = [1, 2, 3]
        
        def process_func(item):
            raise Exception(f'Failed {item}')
        
        result = process_batch_with_resilience(items, process_func)
        
        assert result['success_count'] == 0
        assert result['failure_count'] == 3
        assert len(result['results']) == 0
        assert len(result['errors']) == 3


class TestCreateErrorResponse:
    """Test create_error_response helper function."""
    
    def test_create_user_input_error(self):
        """Test creating user input error."""
        error = create_error_response(
            error_code='INVALID_GPS',
            technical_details='Latitude out of range',
            language='en',
            category=ErrorCategory.USER_INPUT,
            severity=ErrorSeverity.LOW
        )
        
        assert error.error_code == 'INVALID_GPS'
        assert 'Invalid GPS' in error.user_message
        assert error.category == ErrorCategory.USER_INPUT
        assert error.severity == ErrorSeverity.LOW
    
    def test_create_service_error_with_retry(self):
        """Test creating service error with retry_after."""
        error = create_error_response(
            error_code='SERVICE_UNAVAILABLE',
            technical_details='Textract timeout',
            language='hi-IN',
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.HIGH,
            retry_after=60
        )
        
        assert error.error_code == 'SERVICE_UNAVAILABLE'
        assert error.retry_after == 60
        assert error.category == ErrorCategory.EXTERNAL_SERVICE
        # Hindi message should be present
        assert len(error.user_message) > 0


class TestCriticalErrorAlerter:
    """Test critical error alerting."""
    
    @patch('boto3.client')
    def test_alerter_initialization(self, mock_boto_client):
        """Test alerter initialization."""
        alerter = CriticalErrorAlerter(sns_topic_arn='arn:aws:sns:region:account:topic')
        
        assert alerter.sns_topic_arn == 'arn:aws:sns:region:account:topic'
        assert alerter.sns is not None
    
    def test_alerter_without_sns_topic(self):
        """Test alerter without SNS topic configured."""
        alerter = CriticalErrorAlerter(sns_topic_arn=None)
        
        assert alerter.sns_topic_arn is None
        assert alerter.sns is None
    
    @patch('boto3.client')
    def test_send_critical_alert(self, mock_boto_client):
        """Test sending critical alert."""
        mock_sns = MagicMock()
        mock_boto_client.return_value = mock_sns
        
        alerter = CriticalErrorAlerter(sns_topic_arn='arn:aws:sns:region:account:topic')
        
        error = ErrorResponse(
            error_code='SYSTEM_ERROR',
            user_message='System error',
            technical_details='Database connection failed',
            suggested_action='Contact support',
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.CRITICAL
        )
        
        alerter.send_alert(error, context={'user_id': '123'})
        
        # Verify SNS publish was called
        mock_sns.publish.assert_called_once()
        call_args = mock_sns.publish.call_args
        assert 'TopicArn' in call_args[1]
        assert 'CRITICAL' in call_args[1]['Subject']
    
    @patch('boto3.client')
    def test_skip_non_critical_alert(self, mock_boto_client):
        """Test skipping non-critical alerts."""
        mock_sns = MagicMock()
        mock_boto_client.return_value = mock_sns
        
        alerter = CriticalErrorAlerter(sns_topic_arn='arn:aws:sns:region:account:topic')
        
        error = ErrorResponse(
            error_code='USER_ERROR',
            user_message='User error',
            technical_details='Invalid input',
            suggested_action='Check input',
            category=ErrorCategory.USER_INPUT,
            severity=ErrorSeverity.LOW
        )
        
        alerter.send_alert(error)
        
        # Verify SNS publish was NOT called
        mock_sns.publish.assert_not_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
