"""
Property-Based Tests for Critical Error Alerting

Tests Property 32: Critical Error Alerting
For any error classified as critical (system failure, data corruption, security breach),
an alert should be sent to administrators within 60 seconds containing error type,
timestamp, and context.

**Validates: Requirements 10.5**

Uses Hypothesis framework with minimum 100 iterations.
"""

import pytest
import sys
import os
from hypothesis import given, settings, strategies as st
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from common.error_handling import (
    ErrorResponse,
    ErrorCategory,
    ErrorSeverity,
    CriticalErrorAlerter,
    create_error_response,
    get_alerter
)


# ============================================================================
# Property 32: Critical Error Alerting
# ============================================================================

@given(
    error_code=st.sampled_from([
        'SYSTEM_FAILURE',
        'DATA_CORRUPTION',
        'SECURITY_BREACH',
        'DATABASE_ERROR',
        'CRITICAL_SERVICE_FAILURE'
    ]),
    technical_details=st.text(min_size=10, max_size=200),
    category=st.sampled_from(list(ErrorCategory))
)
@settings(max_examples=100, deadline=None)
def test_property_32_critical_errors_trigger_sns_alerts(error_code, technical_details, category):
    """
    **Property 32: Critical Error Alerting**
    **Validates: Requirements 10.5**
    
    For any error with severity CRITICAL, an SNS notification should be sent
    to administrators containing:
    - Error code
    - Technical details
    - Timestamp
    - Error category
    - Severity level
    - Context information
    
    This test verifies that:
    1. Critical errors trigger SNS publish calls
    2. Alert message contains all required information
    3. SNS topic ARN is used correctly
    4. Alert is logged even if SNS fails
    """
    mock_sns = MagicMock()
    mock_topic_arn = 'arn:aws:sns:ap-south-1:123456789012:kisan-setu-critical-alerts'
    
    # Create alerter with mock SNS
    alerter = CriticalErrorAlerter(sns_topic_arn=mock_topic_arn)
    alerter.sns = mock_sns
    
    # Create critical error
    error = ErrorResponse(
        error_code=error_code,
        user_message="Critical error occurred",
        technical_details=technical_details,
        suggested_action="Contact system administrator",
        category=category,
        severity=ErrorSeverity.CRITICAL,
        timestamp=datetime.utcnow()
    )
    
    # Send alert
    with patch('common.error_handling.logger') as mock_logger:
        alerter.send_alert(error)
    
    # Property 1: SNS publish should be called for critical errors
    assert mock_sns.publish.called, \
        "SNS publish should be called for critical errors"
    
    # Property 2: SNS publish called exactly once
    assert mock_sns.publish.call_count == 1, \
        f"Expected 1 SNS publish call, got {mock_sns.publish.call_count}"
    
    # Property 3: Correct topic ARN is used
    call_kwargs = mock_sns.publish.call_args[1]
    assert call_kwargs['TopicArn'] == mock_topic_arn, \
        f"Expected topic ARN {mock_topic_arn}, got {call_kwargs['TopicArn']}"
    
    # Property 4: Subject contains error code
    subject = call_kwargs['Subject']
    assert error_code in subject, \
        f"Subject should contain error code {error_code}, got: {subject}"
    
    # Property 5: Subject indicates criticality
    assert 'CRITICAL' in subject, \
        f"Subject should indicate CRITICAL severity, got: {subject}"
    
    # Property 6: Message is valid JSON
    message = call_kwargs['Message']
    try:
        message_data = json.loads(message)
    except json.JSONDecodeError:
        pytest.fail(f"Message should be valid JSON, got: {message}")
    
    # Property 7: Message contains error code
    assert message_data['error_code'] == error_code, \
        f"Message should contain error_code {error_code}"
    
    # Property 8: Message contains technical details
    assert message_data['technical_details'] == technical_details, \
        "Message should contain technical details"
    
    # Property 9: Message contains timestamp
    assert 'timestamp' in message_data, \
        "Message should contain timestamp"
    assert message_data['timestamp'] is not None, \
        "Timestamp should not be None"
    
    # Property 10: Message contains category
    assert message_data['category'] == category.value, \
        f"Message should contain category {category.value}"
    
    # Property 11: Message contains severity
    assert message_data['severity'] == ErrorSeverity.CRITICAL.value, \
        "Message should contain CRITICAL severity"
    
    # Property 12: Critical error is logged
    mock_logger.critical.assert_called_once()
    log_message = mock_logger.critical.call_args[0][0]
    assert error_code in log_message, \
        f"Log message should contain error code {error_code}"


@given(
    error_code=st.text(min_size=5, max_size=50),
    technical_details=st.text(min_size=10, max_size=200),
    severity=st.sampled_from([ErrorSeverity.LOW, ErrorSeverity.MEDIUM, ErrorSeverity.HIGH])
)
@settings(max_examples=100, deadline=None)
def test_property_32_non_critical_errors_do_not_trigger_alerts(error_code, technical_details, severity):
    """
    **Property 32: Critical Error Alerting (Non-Critical Filtering)**
    **Validates: Requirements 10.5**
    
    For any error with severity LOW, MEDIUM, or HIGH (not CRITICAL),
    no SNS notification should be sent.
    
    This test verifies that:
    1. Non-critical errors do not trigger SNS publish
    2. Alerter correctly filters by severity
    3. Only CRITICAL severity triggers alerts
    """
    mock_sns = MagicMock()
    mock_topic_arn = 'arn:aws:sns:ap-south-1:123456789012:kisan-setu-critical-alerts'
    
    # Create alerter with mock SNS
    alerter = CriticalErrorAlerter(sns_topic_arn=mock_topic_arn)
    alerter.sns = mock_sns
    
    # Create non-critical error
    error = ErrorResponse(
        error_code=error_code,
        user_message="Non-critical error occurred",
        technical_details=technical_details,
        suggested_action="Please try again",
        category=ErrorCategory.EXTERNAL_SERVICE,
        severity=severity,
        timestamp=datetime.utcnow()
    )
    
    # Send alert (should be skipped)
    alerter.send_alert(error)
    
    # Property 1: SNS publish should NOT be called for non-critical errors
    assert not mock_sns.publish.called, \
        f"SNS publish should not be called for {severity.value} errors"
    
    # Property 2: No SNS calls at all
    assert mock_sns.publish.call_count == 0, \
        f"Expected 0 SNS publish calls for {severity.value} errors, got {mock_sns.publish.call_count}"


@given(
    error_code=st.text(min_size=5, max_size=50),
    technical_details=st.text(min_size=10, max_size=200),
    context_keys=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5),
    context_values=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=5)
)
@settings(max_examples=100, deadline=None)
def test_property_32_alert_includes_context_information(error_code, technical_details, context_keys, context_values):
    """
    **Property 32: Critical Error Alerting (Context Inclusion)**
    **Validates: Requirements 10.5**
    
    For any critical error with additional context information,
    the alert message should include the context data.
    
    This test verifies that:
    1. Context dictionary is included in alert message
    2. All context keys and values are preserved
    3. Context is properly serialized to JSON
    """
    mock_sns = MagicMock()
    mock_topic_arn = 'arn:aws:sns:ap-south-1:123456789012:kisan-setu-critical-alerts'
    
    # Create alerter with mock SNS
    alerter = CriticalErrorAlerter(sns_topic_arn=mock_topic_arn)
    alerter.sns = mock_sns
    
    # Create context dictionary
    context = {key: value for key, value in zip(context_keys[:len(context_values)], context_values)}
    
    # Create critical error
    error = ErrorResponse(
        error_code=error_code,
        user_message="Critical error with context",
        technical_details=technical_details,
        suggested_action="Contact administrator",
        category=ErrorCategory.SYSTEM_ERROR,
        severity=ErrorSeverity.CRITICAL,
        timestamp=datetime.utcnow()
    )
    
    # Send alert with context
    alerter.send_alert(error, context=context)
    
    # Property 1: SNS publish should be called
    assert mock_sns.publish.called, \
        "SNS publish should be called for critical errors with context"
    
    # Property 2: Message contains context
    call_kwargs = mock_sns.publish.call_args[1]
    message = call_kwargs['Message']
    message_data = json.loads(message)
    
    assert 'context' in message_data, \
        "Message should contain context field"
    
    # Property 3: Context data is preserved
    alert_context = message_data['context']
    for key in context:
        assert key in alert_context, \
            f"Context should contain key {key}"
        assert alert_context[key] == context[key], \
            f"Context value for {key} should be {context[key]}, got {alert_context[key]}"


@given(
    error_code=st.text(min_size=5, max_size=50),
    technical_details=st.text(min_size=10, max_size=200)
)
@settings(max_examples=100, deadline=None)
def test_property_32_alert_fails_gracefully_when_sns_unavailable(error_code, technical_details):
    """
    **Property 32: Critical Error Alerting (Graceful Failure)**
    **Validates: Requirements 10.5**
    
    For any critical error, if SNS is unavailable or fails,
    the error should still be logged and the system should continue.
    
    This test verifies that:
    1. SNS failures are caught and logged
    2. System continues operating after SNS failure
    3. Critical error is still logged even if SNS fails
    4. No exception is raised to caller
    """
    mock_sns = MagicMock()
    mock_sns.publish.side_effect = Exception("SNS service unavailable")
    mock_topic_arn = 'arn:aws:sns:ap-south-1:123456789012:kisan-setu-critical-alerts'
    
    # Create alerter with failing SNS
    alerter = CriticalErrorAlerter(sns_topic_arn=mock_topic_arn)
    alerter.sns = mock_sns
    
    # Create critical error
    error = ErrorResponse(
        error_code=error_code,
        user_message="Critical error",
        technical_details=technical_details,
        suggested_action="Contact administrator",
        category=ErrorCategory.SYSTEM_ERROR,
        severity=ErrorSeverity.CRITICAL,
        timestamp=datetime.utcnow()
    )
    
    # Send alert (should not raise exception)
    with patch('common.error_handling.logger') as mock_logger:
        try:
            alerter.send_alert(error)
        except Exception as e:
            pytest.fail(f"send_alert should not raise exception, got: {e}")
    
    # Property 1: SNS publish was attempted
    assert mock_sns.publish.called, \
        "SNS publish should be attempted"
    
    # Property 2: Critical error was logged
    mock_logger.critical.assert_called_once()
    
    # Property 3: SNS failure was logged
    mock_logger.error.assert_called_once()
    error_log = mock_logger.error.call_args[0][0]
    assert 'Failed to send SNS alert' in error_log, \
        "SNS failure should be logged"


@given(
    language=st.sampled_from(['en', 'hi-IN', 'mr-IN', 'ta-IN'])
)
@settings(max_examples=100, deadline=None)
def test_property_32_create_error_response_triggers_alert_for_critical(language):
    """
    **Property 32: Critical Error Alerting (Integration with create_error_response)**
    **Validates: Requirements 10.5**
    
    For any critical error created via create_error_response helper,
    the alert should be automatically triggered.
    
    This test verifies that:
    1. create_error_response with CRITICAL severity triggers alert
    2. Alert is sent automatically without explicit call
    3. Integration between error creation and alerting works
    """
    mock_sns = MagicMock()
    mock_topic_arn = 'arn:aws:sns:ap-south-1:123456789012:kisan-setu-critical-alerts'
    
    with patch('common.error_handling.get_alerter') as mock_get_alerter:
        mock_alerter = MagicMock()
        mock_get_alerter.return_value = mock_alerter
        
        # Create critical error using helper
        error = create_error_response(
            error_code='SYSTEM_ERROR',
            technical_details='Critical system failure',
            language=language,
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.CRITICAL
        )
        
        # Property 1: Alerter was retrieved
        mock_get_alerter.assert_called_once()
        
        # Property 2: send_alert was called
        mock_alerter.send_alert.assert_called_once()
        
        # Property 3: Error passed to send_alert
        call_args = mock_alerter.send_alert.call_args[0]
        assert call_args[0] == error, \
            "Error should be passed to send_alert"


@settings(max_examples=100, deadline=None)
@given(st.integers(min_value=1, max_value=10))
def test_property_32_alerter_without_sns_topic_logs_only(seed):
    """
    **Property 32: Critical Error Alerting (No SNS Configuration)**
    **Validates: Requirements 10.5**
    
    For any critical error when SNS topic ARN is not configured,
    the error should be logged but no SNS call should be attempted.
    
    This test verifies that:
    1. Alerter works without SNS configuration
    2. Critical errors are still logged
    3. No SNS calls are attempted
    4. Warning is logged about missing configuration
    """
    # Create alerter without SNS topic
    with patch('common.error_handling.logger') as mock_logger:
        alerter = CriticalErrorAlerter(sns_topic_arn=None)
        
        # Property 1: Warning logged about missing SNS configuration
        warning_calls = [call for call in mock_logger.warning.call_args_list 
                        if 'SNS_ALERT_TOPIC_ARN not configured' in str(call)]
        assert len(warning_calls) > 0, \
            "Warning should be logged when SNS topic ARN is not configured"
    
    # Property 2: SNS client should not be initialized
    assert alerter.sns is None, \
        "SNS client should be None when topic ARN is not configured"
    
    # Create critical error
    error = ErrorResponse(
        error_code='SYSTEM_ERROR',
        user_message="Critical error",
        technical_details="System failure",
        suggested_action="Contact administrator",
        category=ErrorCategory.SYSTEM_ERROR,
        severity=ErrorSeverity.CRITICAL,
        timestamp=datetime.utcnow()
    )
    
    # Send alert (should only log)
    with patch('common.error_handling.logger') as mock_logger:
        alerter.send_alert(error)
        
        # Property 3: Critical error is logged
        mock_logger.critical.assert_called_once()
        log_message = mock_logger.critical.call_args[0][0]
        assert 'SYSTEM_ERROR' in log_message, \
            "Critical error should be logged"


@given(
    num_errors=st.integers(min_value=2, max_value=10)
)
@settings(max_examples=100, deadline=None)
def test_property_32_multiple_critical_errors_trigger_multiple_alerts(num_errors):
    """
    **Property 32: Critical Error Alerting (Multiple Errors)**
    **Validates: Requirements 10.5**
    
    For any sequence of critical errors, each error should trigger
    a separate alert.
    
    This test verifies that:
    1. Each critical error triggers its own alert
    2. Alerts are independent
    3. All errors are properly alerted
    """
    mock_sns = MagicMock()
    mock_topic_arn = 'arn:aws:sns:ap-south-1:123456789012:kisan-setu-critical-alerts'
    
    # Create alerter with mock SNS
    alerter = CriticalErrorAlerter(sns_topic_arn=mock_topic_arn)
    alerter.sns = mock_sns
    
    # Create and send multiple critical errors
    for i in range(num_errors):
        error = ErrorResponse(
            error_code=f'CRITICAL_ERROR_{i}',
            user_message=f"Critical error {i}",
            technical_details=f"Error details {i}",
            suggested_action="Contact administrator",
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.CRITICAL,
            timestamp=datetime.utcnow()
        )
        
        alerter.send_alert(error)
    
    # Property 1: SNS publish called for each error
    assert mock_sns.publish.call_count == num_errors, \
        f"Expected {num_errors} SNS publish calls, got {mock_sns.publish.call_count}"
    
    # Property 2: Each alert has unique error code
    error_codes_in_alerts = []
    for call in mock_sns.publish.call_args_list:
        message = call[1]['Message']
        message_data = json.loads(message)
        error_codes_in_alerts.append(message_data['error_code'])
    
    assert len(error_codes_in_alerts) == num_errors, \
        f"Expected {num_errors} unique alerts"
    
    # Property 3: All error codes are present
    for i in range(num_errors):
        expected_code = f'CRITICAL_ERROR_{i}'
        assert expected_code in error_codes_in_alerts, \
            f"Alert for {expected_code} should be sent"


# ============================================================================
# Edge Cases
# ============================================================================

def test_edge_case_critical_error_with_empty_context():
    """Test that critical errors with empty context still trigger alerts."""
    mock_sns = MagicMock()
    mock_topic_arn = 'arn:aws:sns:ap-south-1:123456789012:kisan-setu-critical-alerts'
    
    alerter = CriticalErrorAlerter(sns_topic_arn=mock_topic_arn)
    alerter.sns = mock_sns
    
    error = ErrorResponse(
        error_code='SYSTEM_ERROR',
        user_message="Critical error",
        technical_details="System failure",
        suggested_action="Contact administrator",
        category=ErrorCategory.SYSTEM_ERROR,
        severity=ErrorSeverity.CRITICAL,
        timestamp=datetime.utcnow()
    )
    
    # Send alert with empty context
    alerter.send_alert(error, context={})
    
    # Should still trigger alert
    assert mock_sns.publish.called, \
        "Alert should be sent even with empty context"
    
    # Context should be empty dict in message
    message = mock_sns.publish.call_args[1]['Message']
    message_data = json.loads(message)
    assert message_data['context'] == {}, \
        "Context should be empty dict"


def test_edge_case_critical_error_with_none_timestamp():
    """Test that critical errors with None timestamp get auto-generated timestamp."""
    mock_sns = MagicMock()
    mock_topic_arn = 'arn:aws:sns:ap-south-1:123456789012:kisan-setu-critical-alerts'
    
    alerter = CriticalErrorAlerter(sns_topic_arn=mock_topic_arn)
    alerter.sns = mock_sns
    
    error = ErrorResponse(
        error_code='SYSTEM_ERROR',
        user_message="Critical error",
        technical_details="System failure",
        suggested_action="Contact administrator",
        category=ErrorCategory.SYSTEM_ERROR,
        severity=ErrorSeverity.CRITICAL,
        timestamp=None
    )
    
    # Send alert
    alerter.send_alert(error)
    
    # Should still trigger alert
    assert mock_sns.publish.called, \
        "Alert should be sent even with None timestamp"
    
    # Timestamp should be auto-generated (not None)
    message = mock_sns.publish.call_args[1]['Message']
    message_data = json.loads(message)
    assert message_data['timestamp'] is not None, \
        "Timestamp should be auto-generated when None is provided"
    
    # Timestamp should be a valid ISO format string
    try:
        datetime.fromisoformat(message_data['timestamp'])
    except (ValueError, TypeError):
        pytest.fail(f"Timestamp should be valid ISO format, got: {message_data['timestamp']}")


def test_edge_case_very_long_technical_details():
    """Test that critical errors with very long technical details are handled."""
    mock_sns = MagicMock()
    mock_topic_arn = 'arn:aws:sns:ap-south-1:123456789012:kisan-setu-critical-alerts'
    
    alerter = CriticalErrorAlerter(sns_topic_arn=mock_topic_arn)
    alerter.sns = mock_sns
    
    # Create error with very long technical details
    long_details = "Error: " + "x" * 10000
    error = ErrorResponse(
        error_code='SYSTEM_ERROR',
        user_message="Critical error",
        technical_details=long_details,
        suggested_action="Contact administrator",
        category=ErrorCategory.SYSTEM_ERROR,
        severity=ErrorSeverity.CRITICAL,
        timestamp=datetime.utcnow()
    )
    
    # Send alert
    alerter.send_alert(error)
    
    # Should still trigger alert
    assert mock_sns.publish.called, \
        "Alert should be sent even with very long technical details"
    
    # Technical details should be preserved
    message = mock_sns.publish.call_args[1]['Message']
    message_data = json.loads(message)
    assert message_data['technical_details'] == long_details, \
        "Long technical details should be preserved"


def test_edge_case_special_characters_in_error_code():
    """Test that error codes with special characters are handled correctly."""
    mock_sns = MagicMock()
    mock_topic_arn = 'arn:aws:sns:ap-south-1:123456789012:kisan-setu-critical-alerts'
    
    alerter = CriticalErrorAlerter(sns_topic_arn=mock_topic_arn)
    alerter.sns = mock_sns
    
    # Error code with special characters
    error_code = 'SYSTEM_ERROR_[CRITICAL]_#123'
    error = ErrorResponse(
        error_code=error_code,
        user_message="Critical error",
        technical_details="System failure",
        suggested_action="Contact administrator",
        category=ErrorCategory.SYSTEM_ERROR,
        severity=ErrorSeverity.CRITICAL,
        timestamp=datetime.utcnow()
    )
    
    # Send alert
    alerter.send_alert(error)
    
    # Should trigger alert
    assert mock_sns.publish.called, \
        "Alert should be sent with special characters in error code"
    
    # Error code should be preserved
    message = mock_sns.publish.call_args[1]['Message']
    message_data = json.loads(message)
    assert message_data['error_code'] == error_code, \
        "Error code with special characters should be preserved"
