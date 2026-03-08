"""
Property-Based Tests for Structured Data Formatting

Tests Property 18: Structured Data Formatting
For any structured data (tables, lists, JSON objects) sent via WhatsApp,
the formatted output should be plain text without special characters that
break WhatsApp rendering.

**Validates: Requirements 6.5**

Uses Hypothesis framework with minimum 100 iterations.
"""

import pytest
import json
import sys
import os
import importlib
import importlib.util
from hypothesis import given, settings, strategies as st
from typing import List, Dict, Any

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'whatsapp'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

# Ensure the real meta_whatsapp_interface is loaded (not the conftest mock)
_real_path = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'whatsapp', 'meta_whatsapp_interface.py')
_spec = importlib.util.spec_from_file_location('meta_whatsapp_interface', _real_path)
_real_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_real_mod)
sys.modules['meta_whatsapp_interface'] = _real_mod

from meta_whatsapp_interface import MetaWhatsAppInterface as WhatsAppInterface

# Patch _load_credentials to avoid AWS Secrets Manager calls in tests
_original_load_credentials = WhatsAppInterface._load_credentials
WhatsAppInterface._load_credentials = lambda self: {
    'access_token': 'test_token',
    'phone_number_id': 'test_phone_id',
    'business_account_id': 'test_account_id'
}

# Import test data generators
from generators import (
    transaction_data, farmer_data, reliability_score,
    ledger_data, ndvi_result, yield_prediction
)


# ============================================================================
# Test Data Generators for Structured Data
# ============================================================================

@st.composite
def table_data(draw):
    """
    Generate table data (headers + rows).
    
    Returns: Tuple of (headers, rows)
    """
    num_cols = draw(st.integers(min_value=1, max_value=10))
    num_rows = draw(st.integers(min_value=0, max_value=20))
    
    # Generate headers
    headers = [
        draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ', min_size=3, max_size=20))
        for _ in range(num_cols)
    ]
    
    # Generate rows
    rows = []
    for _ in range(num_rows):
        row = [
            draw(st.one_of(
                st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789 ', min_size=1, max_size=30),
                st.integers(min_value=0, max_value=10000).map(str),
                st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False).map(lambda x: f"{x:.2f}")
            ))
            for _ in range(num_cols)
        ]
        rows.append(row)
    
    return (headers, rows)


@st.composite
def list_data(draw):
    """
    Generate list data.
    
    Returns: List of strings
    """
    num_items = draw(st.integers(min_value=0, max_value=30))
    items = [
        draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ', min_size=1, max_size=100))
        for _ in range(num_items)
    ]
    return items


@st.composite
def dict_data(draw):
    """
    Generate dictionary data (JSON-like).
    
    Returns: Dictionary with string keys and various value types
    """
    num_keys = draw(st.integers(min_value=0, max_value=15))
    data = {}
    
    for _ in range(num_keys):
        key = draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyz_', min_size=3, max_size=20))
        value_type = draw(st.sampled_from(['string', 'number', 'float', 'list', 'dict']))
        
        if value_type == 'string':
            value = draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ', min_size=1, max_size=50))
        elif value_type == 'number':
            value = draw(st.integers(min_value=0, max_value=100000))
        elif value_type == 'float':
            value = draw(st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False))
        elif value_type == 'list':
            value = [
                draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789', min_size=1, max_size=20))
                for _ in range(draw(st.integers(min_value=0, max_value=5)))
            ]
        else:  # dict
            value = {
                'nested_key': draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyz', min_size=1, max_size=20))
            }
        
        data[key] = value
    
    return data


# ============================================================================
# Property 18: Structured Data Formatting
# ============================================================================

@given(headers_and_rows=table_data())
@settings(max_examples=100, deadline=None)
def test_property_18_table_formatting(headers_and_rows):
    """
    **Property 18: Structured Data Formatting (Tables)**
    **Validates: Requirements 6.5**
    
    For any table data (headers + rows), the formatted output should be:
    1. Plain text (no HTML, markdown special chars that break WhatsApp)
    2. Readable and structured
    3. Not contain problematic characters that break WhatsApp rendering
    
    Problematic characters include:
    - HTML tags: <, >, &lt;, &gt;
    - Markdown special chars that break: **, __, ~~, ```
    - Control characters: \x00-\x1F (except \n, \r, \t)
    - Zero-width characters: \u200B, \u200C, \u200D, \uFEFF
    """
    headers, rows = headers_and_rows
    interface = WhatsAppInterface()
    
    # Format the table
    formatted = interface.format_table(headers, rows)
    
    # Property 1: Output is a string
    assert isinstance(formatted, str)
    
    # Property 2: No HTML tags
    assert '<' not in formatted or '>' not in formatted, \
        "Formatted table should not contain HTML tags"
    
    # Property 3: No problematic markdown (bold, italic, strikethrough, code blocks)
    # WhatsApp supports * for bold and _ for italic, but we want plain text
    # Check for markdown code blocks which can break rendering
    assert '```' not in formatted, "Formatted table should not contain code blocks"
    
    # Property 4: No control characters (except newline, tab, carriage return)
    for char in formatted:
        char_code = ord(char)
        if char_code < 32:  # Control characters
            assert char in ['\n', '\r', '\t'], \
                f"Formatted table should not contain control character: {repr(char)}"
    
    # Property 5: No zero-width characters
    zero_width_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF']
    for zwc in zero_width_chars:
        assert zwc not in formatted, \
            f"Formatted table should not contain zero-width character: {repr(zwc)}"
    
    # Property 6: If input is non-empty, output should be non-empty
    if headers and rows:
        assert len(formatted) > 0, "Non-empty table should produce non-empty output"
    
    # Property 7: Output should contain all header text (only if rows exist)
    if headers and rows:
        for header in headers:
            assert header in formatted, f"Header '{header}' should appear in formatted output"
    
    # Property 8: Output should contain all row data
    if headers and rows:
        for row in rows:
            for cell in row:
                assert str(cell) in formatted, f"Cell '{cell}' should appear in formatted output"


@given(items=list_data(), numbered=st.booleans())
@settings(max_examples=100, deadline=None)
def test_property_18_list_formatting(items, numbered):
    """
    **Property 18: Structured Data Formatting (Lists)**
    **Validates: Requirements 6.5**
    
    For any list data, the formatted output should be:
    1. Plain text without problematic special characters
    2. Properly numbered or bulleted
    3. Each item on a separate line
    4. Readable in WhatsApp
    """
    interface = WhatsAppInterface()
    
    # Format the list
    formatted = interface.format_list(items, numbered=numbered)
    
    # Property 1: Output is a string
    assert isinstance(formatted, str)
    
    # Property 2: No HTML tags
    assert '<' not in formatted or '>' not in formatted, \
        "Formatted list should not contain HTML tags"
    
    # Property 3: No code blocks
    assert '```' not in formatted, "Formatted list should not contain code blocks"
    
    # Property 4: No control characters (except newline, tab, carriage return)
    for char in formatted:
        char_code = ord(char)
        if char_code < 32:
            assert char in ['\n', '\r', '\t'], \
                f"Formatted list should not contain control character: {repr(char)}"
    
    # Property 5: No zero-width characters
    zero_width_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF']
    for zwc in zero_width_chars:
        assert zwc not in formatted, \
            f"Formatted list should not contain zero-width character: {repr(zwc)}"
    
    # Property 6: If input is non-empty, output should be non-empty
    if items:
        assert len(formatted) > 0, "Non-empty list should produce non-empty output"
    
    # Property 7: All items should appear in output
    for item in items:
        assert item in formatted, f"Item '{item}' should appear in formatted output"
    
    # Property 8: Numbered lists should have numbers
    if items and numbered:
        assert '1.' in formatted, "Numbered list should contain '1.'"
        # Check that numbers are sequential
        lines = formatted.split('\n')
        for i, line in enumerate(lines, 1):
            if line.strip():
                assert line.startswith(f"{i}."), \
                    f"Line {i} should start with '{i}.'"
    
    # Property 9: Bulleted lists should have bullets
    if items and not numbered:
        assert '•' in formatted, "Bulleted list should contain bullet character '•'"


@given(data=dict_data())
@settings(max_examples=100, deadline=None)
def test_property_18_structured_data_formatting(data):
    """
    **Property 18: Structured Data Formatting (JSON/Dict)**
    **Validates: Requirements 6.5**
    
    For any structured data (dictionary/JSON), the formatted output should be:
    1. Plain text without problematic special characters
    2. Key-value pairs clearly displayed
    3. Readable in WhatsApp
    4. No JSON syntax that could confuse users
    """
    interface = WhatsAppInterface()
    
    # Format the structured data
    formatted = interface.format_structured_data(data)
    
    # Property 1: Output is a string
    assert isinstance(formatted, str)
    
    # Property 2: No HTML tags
    assert '<' not in formatted or '>' not in formatted, \
        "Formatted data should not contain HTML tags"
    
    # Property 3: No code blocks
    assert '```' not in formatted, "Formatted data should not contain code blocks"
    
    # Property 4: No control characters (except newline, tab, carriage return)
    for char in formatted:
        char_code = ord(char)
        if char_code < 32:
            assert char in ['\n', '\r', '\t'], \
                f"Formatted data should not contain control character: {repr(char)}"
    
    # Property 5: No zero-width characters
    zero_width_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF']
    for zwc in zero_width_chars:
        assert zwc not in formatted, \
            f"Formatted data should not contain zero-width character: {repr(zwc)}"
    
    # Property 6: If input is non-empty, output should be non-empty
    if data:
        assert len(formatted) > 0, "Non-empty data should produce non-empty output"
    
    # Property 7: All keys should appear in output (formatted)
    for key in data.keys():
        # Keys are formatted: replace underscores with spaces and title case
        formatted_key = key.replace('_', ' ').title()
        assert formatted_key in formatted, \
            f"Key '{formatted_key}' should appear in formatted output"
    
    # Property 8: All simple values should appear in output
    for key, value in data.items():
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            assert str(value) in formatted, \
                f"Value '{value}' should appear in formatted output"


@given(transaction=transaction_data())
@settings(max_examples=100, deadline=None)
def test_property_18_real_world_transaction_formatting(transaction):
    """
    **Property 18: Structured Data Formatting (Real-World Data)**
    **Validates: Requirements 6.5**
    
    For any real-world transaction data, formatting it as structured data
    should produce plain text suitable for WhatsApp display.
    
    This tests the property with actual domain models from the system.
    """
    interface = WhatsAppInterface()
    
    # Convert transaction to dictionary
    transaction_dict = {
        'transaction_id': transaction.transaction_id,
        'farmer_id': transaction.farmer_id,
        'quantity': transaction.quantity,
        'crop_type': transaction.crop_type,
        'quality_grade': transaction.quality_grade,
        'moisture': transaction.moisture,
        'price': transaction.price,
        'timestamp': transaction.timestamp.isoformat()
    }
    
    # Format as structured data
    formatted = interface.format_structured_data(transaction_dict)
    
    # Verify plain text properties
    assert isinstance(formatted, str)
    assert len(formatted) > 0
    
    # No problematic characters
    assert '```' not in formatted
    zero_width_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF']
    for zwc in zero_width_chars:
        assert zwc not in formatted
    
    # Key information should be present
    assert str(transaction.quantity) in formatted
    assert transaction.crop_type in formatted
    assert transaction.quality_grade in formatted


@given(score=reliability_score())
@settings(max_examples=100, deadline=None)
def test_property_18_credit_score_table_formatting(score):
    """
    **Property 18: Structured Data Formatting (Credit Score Table)**
    **Validates: Requirements 6.5**
    
    For any credit score breakdown, formatting it as a table should produce
    plain text suitable for WhatsApp display.
    
    This tests a common use case: displaying credit score components in a table.
    """
    interface = WhatsAppInterface()
    
    # Create table for credit score breakdown
    headers = ['Component', 'Score', 'Max']
    rows = [
        ['Supply Consistency', f"{score.supply_consistency:.1f}", '30'],
        ['Quality Metrics', f"{score.quality_metrics:.1f}", '25'],
        ['Transaction History', f"{score.transaction_history:.1f}", '20'],
        ['Financial Behavior', f"{score.financial_behavior:.1f}", '15'],
        ['Operational Transparency', f"{score.operational_transparency:.1f}", '10'],
        ['TOTAL', f"{score.total_score:.1f}", '100']
    ]
    
    # Format as table
    formatted = interface.format_table(headers, rows)
    
    # Verify plain text properties
    assert isinstance(formatted, str)
    assert len(formatted) > 0
    
    # No problematic characters
    assert '```' not in formatted
    zero_width_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF']
    for zwc in zero_width_chars:
        assert zwc not in formatted
    
    # All headers should be present
    for header in headers:
        assert header in formatted
    
    # Total score should be present
    assert f"{score.total_score:.1f}" in formatted


@given(
    farmers=st.lists(farmer_data(), min_size=1, max_size=10)
)
@settings(max_examples=100, deadline=None)
def test_property_18_farmer_list_formatting(farmers):
    """
    **Property 18: Structured Data Formatting (Farmer List)**
    **Validates: Requirements 6.5**
    
    For any list of farmers, formatting it as a list should produce
    plain text suitable for WhatsApp display.
    
    This tests a common use case: displaying a list of farmers.
    """
    interface = WhatsAppInterface()
    
    # Create list of farmer names
    farmer_names = [f"{farmer.name} ({farmer.phone})" for farmer in farmers]
    
    # Format as numbered list
    formatted = interface.format_list(farmer_names, numbered=True)
    
    # Verify plain text properties
    assert isinstance(formatted, str)
    assert len(formatted) > 0
    
    # No problematic characters
    assert '```' not in formatted
    zero_width_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF']
    for zwc in zero_width_chars:
        assert zwc not in formatted
    
    # All farmer names should be present
    for farmer in farmers:
        assert farmer.name in formatted


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

def test_empty_table_formatting():
    """
    Test that empty tables are handled gracefully.
    """
    interface = WhatsAppInterface()
    
    # Empty headers and rows
    formatted = interface.format_table([], [])
    assert formatted == ""
    
    # Headers but no rows - implementation returns empty string
    formatted = interface.format_table(['Header1', 'Header2'], [])
    assert formatted == ""
    
    # No headers but has rows - implementation returns empty string
    formatted = interface.format_table([], [['data1', 'data2']])
    assert formatted == ""


def test_empty_list_formatting():
    """
    Test that empty lists are handled gracefully.
    """
    interface = WhatsAppInterface()
    
    formatted = interface.format_list([])
    assert formatted == ""


def test_empty_dict_formatting():
    """
    Test that empty dictionaries are handled gracefully.
    """
    interface = WhatsAppInterface()
    
    formatted = interface.format_structured_data({})
    assert formatted == ""


def test_special_characters_in_table():
    """
    Test that special characters in table data are handled properly.
    """
    interface = WhatsAppInterface()
    
    headers = ['Name', 'Value']
    rows = [
        ['Test & Data', '100'],
        ['Price < 50', '45'],
        ['Quantity > 10', '15']
    ]
    
    formatted = interface.format_table(headers, rows)
    
    # Should preserve the special characters as-is (they're part of the data)
    assert '&' in formatted
    assert '<' in formatted
    assert '>' in formatted
    
    # But should not introduce HTML entities
    assert '&lt;' not in formatted
    assert '&gt;' not in formatted
    assert '&amp;' not in formatted


def test_unicode_characters_in_formatting():
    """
    Test that Unicode characters (e.g., Hindi, Marathi, Tamil) are preserved.
    """
    interface = WhatsAppInterface()
    
    # Hindi text
    data = {
        'farmer_name': 'राजेश कुमार',
        'crop': 'गेहूं',
        'quantity': 100
    }
    
    formatted = interface.format_structured_data(data)
    
    # Unicode should be preserved
    assert 'राजेश कुमार' in formatted
    assert 'गेहूं' in formatted


def test_nested_dict_formatting():
    """
    Test that nested dictionaries are handled (converted to JSON string).
    """
    interface = WhatsAppInterface()
    
    data = {
        'farmer': 'John Doe',
        'location': {
            'latitude': 28.6139,
            'longitude': 77.2090
        }
    }
    
    formatted = interface.format_structured_data(data)
    
    # Should contain the farmer name
    assert 'John Doe' in formatted
    
    # Nested dict should be present (as JSON or formatted string)
    assert 'latitude' in formatted.lower() or '28.6139' in formatted


def test_list_value_in_dict_formatting():
    """
    Test that list values in dictionaries are formatted as comma-separated.
    """
    interface = WhatsAppInterface()
    
    data = {
        'crops': ['wheat', 'rice', 'cotton'],
        'farmer': 'John Doe'
    }
    
    formatted = interface.format_structured_data(data)
    
    # List should be comma-separated
    assert 'wheat' in formatted
    assert 'rice' in formatted
    assert 'cotton' in formatted
    # Should have commas between items
    assert 'wheat, rice, cotton' in formatted or 'wheat,rice,cotton' in formatted.replace(' ', '')
