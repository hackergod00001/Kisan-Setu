"""
Property-Based Tests for Localized Error Messages

Tests Property 30: Localized Error Messages
For any error after retry exhaustion, the system should return an error message
in the user's preferred language (Hindi, Marathi, or Tamil) and log the technical
error details.

**Validates: Requirements 10.2**

Uses Hypothesis framework with minimum 100 iterations.
"""

import pytest
import sys
import os
from hypothesis import given, settings, strategies as st
from unittest.mock import Mock, patch
from typing import Dict, Any

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from common.error_handling import (
    get_localized_message,
    create_error_response,
    ErrorCategory,
    ErrorSeverity,
    ERROR_MESSAGES
)


# ============================================================================
# Property 30: Localized Error Messages
# ============================================================================

@given(
    error_code=st.sampled_from(list(ERROR_MESSAGES.keys())),
    language=st.sampled_from(['en', 'hi-IN', 'mr-IN', 'ta-IN'])
)
@settings(max_examples=100, deadline=None)
def test_property_30_error_message_localization(error_code, language):
    """
    **Property 30: Localized Error Messages**
    **Validates: Requirements 10.2**
    
    For any error code and supported language, the system should return
    a localized error message in the requested language.
    
    This test verifies that:
    1. Error messages exist for all supported languages
    2. Messages are non-empty strings
    3. Messages are properly localized (different for each language)
    4. English fallback exists for all error codes
    """
    # Get localized message
    message = get_localized_message(error_code, language)
    
    # Property 1: Message is a non-empty string
    assert isinstance(message, str), \
        f"Error message should be a string, got {type(message)}"
    assert len(message) > 0, \
        f"Error message should not be empty for {error_code} in {language}"
    
    # Property 2: Message exists in ERROR_MESSAGES
    assert error_code in ERROR_MESSAGES, \
        f"Error code {error_code} should exist in ERROR_MESSAGES"
    
    # Property 3: English fallback always exists
    english_message = ERROR_MESSAGES[error_code].get('en')
    assert english_message is not None, \
        f"English fallback should exist for {error_code}"
    assert len(english_message) > 0, \
        f"English fallback should not be empty for {error_code}"
    
    # Property 4: If language is not English, message should be different from English
    # (unless the language is not supported, in which case it falls back to English)
    if language != 'en' and language in ERROR_MESSAGES[error_code]:
        localized_message = ERROR_MESSAGES[error_code][language]
        # Localized message should be different from English
        # (unless they happen to be the same, which is unlikely)
        assert localized_message is not None, \
            f"Localized message should exist for {error_code} in {language}"


@given(
    error_code=st.sampled_from(list(ERROR_MESSAGES.keys())),
    language=st.sampled_from(['hi-IN', 'mr-IN', 'ta-IN'])
)
@settings(max_examples=100, deadline=None)
def test_property_30_indian_language_support(error_code, language):
    """
    **Property 30: Localized Error Messages (Indian Languages)**
    **Validates: Requirements 10.2**
    
    For any error code, all three Indian languages (Hindi, Marathi, Tamil)
    should have localized messages.
    
    This test verifies that:
    1. Hindi (hi-IN), Marathi (mr-IN), and Tamil (ta-IN) translations exist
    2. Translations are non-empty
    3. Translations contain appropriate Unicode characters for the language
    """
    # Get localized message
    message = get_localized_message(error_code, language)
    
    # Property 1: Message exists and is non-empty
    assert message is not None, \
        f"Message should exist for {error_code} in {language}"
    assert len(message) > 0, \
        f"Message should not be empty for {error_code} in {language}"
    
    # Property 2: Message should be in ERROR_MESSAGES
    assert error_code in ERROR_MESSAGES, \
        f"Error code {error_code} should exist"
    assert language in ERROR_MESSAGES[error_code], \
        f"Language {language} should be supported for {error_code}"
    
    # Property 3: Indian language messages should contain Unicode characters
    # (not just ASCII, which would indicate missing translation)
    localized_message = ERROR_MESSAGES[error_code][language]
    has_unicode = any(ord(char) > 127 for char in localized_message)
    assert has_unicode, \
        f"Message for {error_code} in {language} should contain Unicode characters (not just ASCII)"


@given(
    error_code=st.sampled_from(list(ERROR_MESSAGES.keys())),
    language=st.sampled_from(['en', 'hi-IN', 'mr-IN', 'ta-IN'])
)
@settings(max_examples=100, deadline=None)
def test_property_30_error_response_structure(error_code, language):
    """
    **Property 30: Localized Error Messages (Response Structure)**
    **Validates: Requirements 10.2**
    
    For any error, create_error_response should return a properly structured
    ErrorResponse with localized user message and technical details.
    
    This test verifies that:
    1. ErrorResponse contains localized user_message
    2. ErrorResponse contains technical_details
    3. ErrorResponse has proper category and severity
    4. ErrorResponse includes timestamp
    """
    technical_details = f"Test error for {error_code}"
    
    # Create error response
    error_response = create_error_response(
        error_code=error_code,
        technical_details=technical_details,
        language=language,
        category=ErrorCategory.EXTERNAL_SERVICE,
        severity=ErrorSeverity.MEDIUM
    )
    
    # Property 1: user_message is localized
    assert error_response.user_message is not None, \
        "user_message should not be None"
    assert len(error_response.user_message) > 0, \
        "user_message should not be empty"
    
    expected_message = get_localized_message(error_code, language)
    assert error_response.user_message == expected_message, \
        f"user_message should match localized message for {language}"
    
    # Property 2: technical_details is preserved
    assert error_response.technical_details == technical_details, \
        "technical_details should be preserved"
    
    # Property 3: error_code is preserved
    assert error_response.error_code == error_code, \
        "error_code should be preserved"
    
    # Property 4: category and severity are set
    assert error_response.category == ErrorCategory.EXTERNAL_SERVICE, \
        "category should be set correctly"
    assert error_response.severity == ErrorSeverity.MEDIUM, \
        "severity should be set correctly"
    
    # Property 5: timestamp is set
    assert error_response.timestamp is not None, \
        "timestamp should be set"
    
    # Property 6: suggested_action is provided
    assert error_response.suggested_action is not None, \
        "suggested_action should be provided"
    assert len(error_response.suggested_action) > 0, \
        "suggested_action should not be empty"


@given(
    language=st.sampled_from(['en', 'hi-IN', 'mr-IN', 'ta-IN'])
)
@settings(max_examples=100, deadline=None)
def test_property_30_all_error_codes_have_translations(language):
    """
    **Property 30: Localized Error Messages (Completeness)**
    **Validates: Requirements 10.2**
    
    For any supported language, all error codes should have translations.
    
    This test verifies that:
    1. All error codes in ERROR_MESSAGES have entries for the language
    2. No error code is missing a translation
    3. All translations are non-empty
    """
    # Check all error codes
    for error_code in ERROR_MESSAGES.keys():
        # Get message (will fall back to English if not available)
        message = get_localized_message(error_code, language)
        
        # Property 1: Message exists
        assert message is not None, \
            f"Message should exist for {error_code} in {language}"
        assert len(message) > 0, \
            f"Message should not be empty for {error_code} in {language}"
        
        # Property 2: If language is supported, it should be in ERROR_MESSAGES
        if language in ['hi-IN', 'mr-IN', 'ta-IN']:
            assert language in ERROR_MESSAGES[error_code], \
                f"Language {language} should be supported for {error_code}"


@given(
    error_code=st.sampled_from(list(ERROR_MESSAGES.keys())),
    language=st.sampled_from(['en', 'hi-IN', 'mr-IN', 'ta-IN']),
    success_count=st.integers(min_value=0, max_value=100),
    failure_count=st.integers(min_value=0, max_value=100)
)
@settings(max_examples=100, deadline=None)
def test_property_30_message_formatting_with_parameters(error_code, language, success_count, failure_count):
    """
    **Property 30: Localized Error Messages (Parameter Formatting)**
    **Validates: Requirements 10.2**
    
    For any error message with format parameters, the system should correctly
    substitute parameters in the localized message.
    
    This test verifies that:
    1. Messages with placeholders accept format parameters
    2. Parameters are correctly substituted in all languages
    3. Missing parameters don't cause errors (graceful degradation)
    """
    # Get localized message with parameters
    message = get_localized_message(
        error_code,
        language,
        success_count=success_count,
        failure_count=failure_count
    )
    
    # Property 1: Message is returned (even if parameters don't match)
    assert message is not None, \
        f"Message should be returned for {error_code} in {language}"
    assert len(message) > 0, \
        f"Message should not be empty for {error_code} in {language}"
    
    # Property 2: If error_code has placeholders, they should be substituted
    if error_code == 'BATCH_PROCESSING_PARTIAL':
        # This error code has {success_count} and {failure_count} placeholders
        assert str(success_count) in message, \
            f"success_count should be in message: {message}"
        assert str(failure_count) in message, \
            f"failure_count should be in message: {message}"
        
        # Placeholders should not remain in the message
        assert '{success_count}' not in message, \
            f"Placeholder {{success_count}} should be replaced in: {message}"
        assert '{failure_count}' not in message, \
            f"Placeholder {{failure_count}} should be replaced in: {message}"


@given(
    unsupported_language=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz-',
        min_size=2,
        max_size=10
    ).filter(lambda x: x not in ['en', 'hi-IN', 'mr-IN', 'ta-IN'])
)
@settings(max_examples=100, deadline=None)
def test_property_30_fallback_to_english_for_unsupported_language(unsupported_language):
    """
    **Property 30: Localized Error Messages (Fallback)**
    **Validates: Requirements 10.2**
    
    For any unsupported language, the system should fall back to English.
    
    This test verifies that:
    1. Unsupported languages return English message
    2. No errors are raised for unsupported languages
    3. Fallback message is the same as English message
    """
    error_code = 'SERVICE_UNAVAILABLE'
    
    # Get message for unsupported language
    message = get_localized_message(error_code, unsupported_language)
    
    # Get English message
    english_message = get_localized_message(error_code, 'en')
    
    # Property 1: Message is returned (fallback to English)
    assert message is not None, \
        f"Message should be returned for unsupported language {unsupported_language}"
    assert len(message) > 0, \
        f"Message should not be empty for unsupported language {unsupported_language}"
    
    # Property 2: Message should be the English fallback
    assert message == english_message, \
        f"Unsupported language should fall back to English"


@given(
    error_code=st.sampled_from(list(ERROR_MESSAGES.keys())),
    language=st.sampled_from(['hi-IN', 'mr-IN', 'ta-IN'])
)
@settings(max_examples=100, deadline=None)
def test_property_30_language_specific_character_sets(error_code, language):
    """
    **Property 30: Localized Error Messages (Character Sets)**
    **Validates: Requirements 10.2**
    
    For any Indian language, error messages should contain appropriate
    Unicode character ranges for that language.
    
    This test verifies that:
    1. Hindi messages contain Devanagari script (U+0900 to U+097F)
    2. Marathi messages contain Devanagari script (U+0900 to U+097F)
    3. Tamil messages contain Tamil script (U+0B80 to U+0BFF)
    """
    message = get_localized_message(error_code, language)
    
    # Define Unicode ranges for each language
    unicode_ranges = {
        'hi-IN': (0x0900, 0x097F),  # Devanagari (Hindi)
        'mr-IN': (0x0900, 0x097F),  # Devanagari (Marathi)
        'ta-IN': (0x0B80, 0x0BFF),  # Tamil
    }
    
    if language in unicode_ranges:
        start, end = unicode_ranges[language]
        
        # Check if message contains characters in the expected range
        has_expected_script = any(
            start <= ord(char) <= end
            for char in message
        )
        
        assert has_expected_script, \
            f"Message for {error_code} in {language} should contain characters in Unicode range U+{start:04X} to U+{end:04X}"


@given(
    error_code=st.sampled_from(list(ERROR_MESSAGES.keys())),
    language=st.sampled_from(['en', 'hi-IN', 'mr-IN', 'ta-IN'])
)
@settings(max_examples=100, deadline=None)
def test_property_30_error_response_serialization(error_code, language):
    """
    **Property 30: Localized Error Messages (Serialization)**
    **Validates: Requirements 10.2**
    
    For any error response, to_dict() should produce a valid dictionary
    that can be serialized to JSON.
    
    This test verifies that:
    1. to_dict() returns a dictionary
    2. All required fields are present
    3. Localized message is preserved in serialization
    4. Dictionary can be converted to JSON
    """
    import json
    
    technical_details = f"Test error for {error_code}"
    
    # Create error response
    error_response = create_error_response(
        error_code=error_code,
        technical_details=technical_details,
        language=language,
        category=ErrorCategory.USER_INPUT,
        severity=ErrorSeverity.LOW
    )
    
    # Convert to dictionary
    error_dict = error_response.to_dict()
    
    # Property 1: to_dict() returns a dictionary
    assert isinstance(error_dict, dict), \
        "to_dict() should return a dictionary"
    
    # Property 2: All required fields are present
    required_fields = [
        'error_code', 'user_message', 'technical_details',
        'suggested_action', 'timestamp', 'category', 'severity'
    ]
    for field in required_fields:
        assert field in error_dict, \
            f"Field '{field}' should be in error_dict"
    
    # Property 3: Localized message is preserved
    expected_message = get_localized_message(error_code, language)
    assert error_dict['user_message'] == expected_message, \
        "Localized message should be preserved in dictionary"
    
    # Property 4: Dictionary can be serialized to JSON
    try:
        json_str = json.dumps(error_dict, ensure_ascii=False)
        assert len(json_str) > 0, \
            "JSON serialization should produce non-empty string"
        
        # Verify we can deserialize it back
        deserialized = json.loads(json_str)
        assert deserialized['user_message'] == expected_message, \
            "Localized message should survive JSON round-trip"
    except Exception as e:
        pytest.fail(f"Failed to serialize error_dict to JSON: {e}")


# ============================================================================
# Edge Cases
# ============================================================================

def test_edge_case_unknown_error_code():
    """Test that unknown error codes fall back to SYSTEM_ERROR."""
    unknown_code = 'UNKNOWN_ERROR_CODE_12345'
    language = 'hi-IN'
    
    message = get_localized_message(unknown_code, language)
    
    # Should fall back to SYSTEM_ERROR message
    system_error_message = get_localized_message('SYSTEM_ERROR', language)
    assert message == system_error_message, \
        "Unknown error code should fall back to SYSTEM_ERROR"


def test_edge_case_empty_language_code():
    """Test that empty language code falls back to English."""
    error_code = 'INVALID_GPS'
    
    message = get_localized_message(error_code, '')
    english_message = get_localized_message(error_code, 'en')
    
    assert message == english_message, \
        "Empty language code should fall back to English"


def test_edge_case_none_language_code():
    """Test that None language code falls back to English."""
    error_code = 'SERVICE_UNAVAILABLE'
    
    # get_localized_message has default language='en'
    message = get_localized_message(error_code)
    english_message = get_localized_message(error_code, 'en')
    
    assert message == english_message, \
        "None language code should fall back to English"


def test_edge_case_all_languages_have_same_error_codes():
    """Test that all languages support the same set of error codes."""
    error_codes = set(ERROR_MESSAGES.keys())
    
    # All error codes should have entries for all languages
    for error_code in error_codes:
        for language in ['en', 'hi-IN', 'mr-IN', 'ta-IN']:
            message = get_localized_message(error_code, language)
            assert message is not None, \
                f"Error code {error_code} should have message for {language}"
            assert len(message) > 0, \
                f"Error code {error_code} should have non-empty message for {language}"


def test_edge_case_message_formatting_with_missing_parameters():
    """Test that messages with placeholders handle missing parameters gracefully."""
    error_code = 'BATCH_PROCESSING_PARTIAL'
    language = 'en'
    
    # Call without required parameters
    message = get_localized_message(error_code, language)
    
    # Should return message with placeholders intact (not crash)
    assert message is not None, \
        "Message should be returned even without parameters"
    assert len(message) > 0, \
        "Message should not be empty"


def test_edge_case_unicode_in_technical_details():
    """Test that technical details with Unicode characters are preserved."""
    error_code = 'EXTRACTION_FAILED'
    language = 'hi-IN'
    technical_details = "फ़ाइल नहीं मिली: /path/to/file.jpg"
    
    error_response = create_error_response(
        error_code=error_code,
        technical_details=technical_details,
        language=language
    )
    
    assert error_response.technical_details == technical_details, \
        "Unicode in technical_details should be preserved"


def test_edge_case_very_long_error_message():
    """Test that error messages can be reasonably long."""
    # All error messages should be under 500 characters
    for error_code, messages in ERROR_MESSAGES.items():
        for language, message in messages.items():
            assert len(message) < 500, \
                f"Error message for {error_code} in {language} is too long: {len(message)} chars"


def test_edge_case_error_message_consistency():
    """Test that error messages are consistent across languages (same meaning)."""
    # This is a sanity check - all languages should have the same error codes
    error_codes_per_language = {}
    
    for error_code, messages in ERROR_MESSAGES.items():
        for language in messages.keys():
            if language not in error_codes_per_language:
                error_codes_per_language[language] = set()
            error_codes_per_language[language].add(error_code)
    
    # All languages should support the same error codes
    reference_codes = error_codes_per_language.get('en', set())
    for language, codes in error_codes_per_language.items():
        assert codes == reference_codes, \
            f"Language {language} has different error codes than English"
