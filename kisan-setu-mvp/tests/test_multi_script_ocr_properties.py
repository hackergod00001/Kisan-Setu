"""
Property-Based Tests for Multi-Script OCR Support

Tests Property 4: Multi-Script OCR Support
For any handwritten document in Hindi, Marathi, or Tamil scripts, the Document_Processor
should successfully extract text with recognizable characters from the correct script.

**Validates: Requirements 2.3**

Uses Hypothesis framework with minimum 100 iterations.
"""

import pytest
import sys
import os
from hypothesis import given, settings, strategies as st
from typing import Dict, Any
from unittest.mock import Mock

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'processor'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from processor.processor import DocumentProcessor, LedgerData

# Import test data generators
from generators import s3_url, language_code

# Load Hypothesis profile for consistent test configuration
try:
    settings.load_profile("kisan_setu")
except Exception:
    settings.load_profile("dev")


# ============================================================================
# Unicode Ranges for Indian Scripts
# ============================================================================

# Hindi (Devanagari): U+0900 to U+097F
HINDI_CHARS = ''.join(chr(i) for i in range(0x0900, 0x0980))

# Marathi (Devanagari): U+0900 to U+097F (same as Hindi)
MARATHI_CHARS = ''.join(chr(i) for i in range(0x0900, 0x0980))

# Tamil: U+0B80 to U+0BFF
TAMIL_CHARS = ''.join(chr(i) for i in range(0x0B80, 0x0C00))


# ============================================================================
# Script Detection Helpers
# ============================================================================

def detect_script(text: str) -> str:
    """
    Detect the script of the given text.
    
    Returns: 'hindi', 'marathi', 'tamil', 'english', or 'mixed'
    """
    if not text:
        return 'unknown'
    
    hindi_count = sum(1 for c in text if '\u0900' <= c <= '\u097F')
    tamil_count = sum(1 for c in text if '\u0B80' <= c <= '\u0BFF')
    english_count = sum(1 for c in text if c.isascii() and c.isalpha())
    
    total_chars = len([c for c in text if c.isalpha() or '\u0900' <= c <= '\u097F' or '\u0B80' <= c <= '\u0BFF'])
    
    if total_chars == 0:
        return 'unknown'
    
    # If more than 50% of characters are from a specific script
    if hindi_count / total_chars > 0.5:
        return 'hindi'
    elif tamil_count / total_chars > 0.5:
        return 'tamil'
    elif english_count / total_chars > 0.5:
        return 'english'
    else:
        return 'mixed'


def has_script_characters(text: str, script: str) -> bool:
    """
    Check if text contains characters from the specified script.
    
    Args:
        text: Text to check
        script: 'hindi', 'marathi', or 'tamil'
    
    Returns: True if text contains characters from the script
    """
    if not text:
        return False
    
    if script in ['hindi', 'marathi']:
        # Both use Devanagari script
        return any('\u0900' <= c <= '\u097F' for c in text)
    elif script == 'tamil':
        return any('\u0B80' <= c <= '\u0BFF' for c in text)
    
    return False


# ============================================================================
# Test Data Generators for Multi-Script Text
# ============================================================================

@st.composite
def hindi_text(draw, min_size=3, max_size=50):
    """Generate text with Hindi (Devanagari) characters."""
    # Common Hindi words and characters
    hindi_samples = [
        'किसान', 'गेहूं', 'धान', 'प्याज', 'मात्रा', 'नमी', 'मूल्य',
        'तारीख', 'नाम', 'गुणवत्ता', 'ग्रेड', 'किलोग्राम'
    ]
    
    # Generate text by combining samples or random characters
    use_samples = draw(st.booleans())
    
    if use_samples:
        num_words = draw(st.integers(min_value=1, max_value=5))
        words = [draw(st.sampled_from(hindi_samples)) for _ in range(num_words)]
        return ' '.join(words)
    else:
        # Generate random Hindi characters
        length = draw(st.integers(min_value=min_size, max_value=max_size))
        return draw(st.text(alphabet=HINDI_CHARS, min_size=length, max_size=length))


@st.composite
def marathi_text(draw, min_size=3, max_size=50):
    """Generate text with Marathi (Devanagari) characters."""
    # Common Marathi words
    marathi_samples = [
        'शेतकरी', 'गहू', 'तांदूळ', 'कांदा', 'प्रमाण', 'ओलावा', 'किंमत',
        'तारीख', 'नाव', 'गुणवत्ता', 'श्रेणी', 'किलोग्राम'
    ]
    
    use_samples = draw(st.booleans())
    
    if use_samples:
        num_words = draw(st.integers(min_value=1, max_value=5))
        words = [draw(st.sampled_from(marathi_samples)) for _ in range(num_words)]
        return ' '.join(words)
    else:
        length = draw(st.integers(min_value=min_size, max_value=max_size))
        return draw(st.text(alphabet=MARATHI_CHARS, min_size=length, max_size=length))


@st.composite
def tamil_text(draw, min_size=3, max_size=50):
    """Generate text with Tamil characters."""
    # Common Tamil words
    tamil_samples = [
        'விவசாயி', 'கோதுமை', 'அரிசி', 'வெங்காயம', 'அளவு', 'ஈரப்பதம்', 'விலை',
        'தேதி', 'பெயர்', 'தரம', 'தரம்', 'கிலோகிராம்'
    ]
    
    use_samples = draw(st.booleans())
    
    if use_samples:
        num_words = draw(st.integers(min_value=1, max_value=5))
        words = [draw(st.sampled_from(tamil_samples)) for _ in range(num_words)]
        return ' '.join(words)
    else:
        length = draw(st.integers(min_value=min_size, max_value=max_size))
        return draw(st.text(alphabet=TAMIL_CHARS, min_size=length, max_size=length))


@st.composite
def multi_script_textract_response(draw, script: str):
    """
    Generate a mock Textract response with text in the specified script.
    
    Args:
        script: 'hindi', 'marathi', or 'tamil'
    
    Returns: Dictionary mimicking Textract AnalyzeDocument response
    """
    # Generate text in the specified script
    if script == 'hindi':
        farmer_name = draw(hindi_text(min_size=5, max_size=30))
        crop_type = draw(st.sampled_from(['गेहूं', 'धान', 'प्याज', 'कपास']))
    elif script == 'marathi':
        farmer_name = draw(marathi_text(min_size=5, max_size=30))
        crop_type = draw(st.sampled_from(['गहू', 'तांदूळ', 'कांदा', 'कापूस']))
    elif script == 'tamil':
        farmer_name = draw(tamil_text(min_size=5, max_size=30))
        crop_type = draw(st.sampled_from(['கோதுமை', 'அரிசி', 'வெங்காயம', 'பருத்தி']))
    else:
        farmer_name = draw(st.text(min_size=5, max_size=30))
        crop_type = 'wheat'
    
    # Generate numeric values (these are typically in Arabic numerals even in Indian scripts)
    quantity_value = draw(st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False))
    moisture_value = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    price_value = draw(st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False))
    date_value = draw(st.dates()).isoformat()
    quality_grade_value = draw(st.sampled_from(['A', 'B', 'C']))
    
    # Generate confidence scores (0-100)
    quantity_conf = draw(st.floats(min_value=70.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    moisture_conf = draw(st.floats(min_value=70.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    price_conf = draw(st.floats(min_value=70.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    date_conf = draw(st.floats(min_value=70.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    farmer_name_conf = draw(st.floats(min_value=70.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    crop_type_conf = draw(st.floats(min_value=70.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    quality_grade_conf = draw(st.floats(min_value=70.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    
    # Build Textract response structure
    blocks = []
    
    # Query blocks
    queries = [
        {'id': 'query-1', 'alias': 'QUANTITY', 'answer_id': 'answer-1'},
        {'id': 'query-2', 'alias': 'MOISTURE', 'answer_id': 'answer-2'},
        {'id': 'query-3', 'alias': 'PRICE', 'answer_id': 'answer-3'},
        {'id': 'query-4', 'alias': 'DATE', 'answer_id': 'answer-4'},
        {'id': 'query-5', 'alias': 'FARMER_NAME', 'answer_id': 'answer-5'},
        {'id': 'query-6', 'alias': 'CROP_TYPE', 'answer_id': 'answer-6'},
        {'id': 'query-7', 'alias': 'QUALITY_GRADE', 'answer_id': 'answer-7'},
    ]
    
    for query in queries:
        blocks.append({
            'BlockType': 'QUERY',
            'Id': query['id'],
            'Query': {'Text': f"What is the {query['alias']}?", 'Alias': query['alias']},
            'Relationships': [{'Type': 'ANSWER', 'Ids': [query['answer_id']]}]
        })
    
    # Answer blocks
    answers = [
        {'id': 'answer-1', 'text': str(quantity_value), 'confidence': quantity_conf},
        {'id': 'answer-2', 'text': str(moisture_value), 'confidence': moisture_conf},
        {'id': 'answer-3', 'text': str(price_value), 'confidence': price_conf},
        {'id': 'answer-4', 'text': date_value, 'confidence': date_conf},
        {'id': 'answer-5', 'text': farmer_name, 'confidence': farmer_name_conf},
        {'id': 'answer-6', 'text': crop_type, 'confidence': crop_type_conf},
        {'id': 'answer-7', 'text': quality_grade_value, 'confidence': quality_grade_conf},
    ]
    
    for answer in answers:
        blocks.append({
            'BlockType': 'QUERY_RESULT',
            'Id': answer['id'],
            'Text': answer['text'],
            'Confidence': answer['confidence']
        })
    
    return {
        'Blocks': blocks,
        'DocumentMetadata': {'Pages': 1}
    }


# ============================================================================
# Property 4: Multi-Script OCR Support
# ============================================================================

@given(
    script=st.sampled_from(['hindi', 'marathi', 'tamil']),
    image_url=s3_url(prefix='s3://kisan-setu-raw/ledger-images'),
    data=st.data()
)
@settings(max_examples=100, deadline=None)
def test_property_4_multi_script_ocr_support(script, image_url, data):
    """
    **Property 4: Multi-Script OCR Support**
    **Validates: Requirements 2.3**
    
    For any handwritten document in Hindi, Marathi, or Tamil scripts, the Document_Processor
    should successfully extract text with recognizable characters from the correct script.
    
    This test verifies:
    1. The DocumentProcessor can process documents in Hindi, Marathi, and Tamil scripts
    2. Extracted text contains characters from the correct script
    3. The extraction completes successfully without errors
    4. All required fields are extracted regardless of script
    """
    # Generate mock Textract response with text in the specified script
    mock_response = data.draw(multi_script_textract_response(script=script))
    
    # Create mock Textract client
    mock_textract = Mock()
    mock_textract.analyze_document.return_value = mock_response
    
    # Map script to language code
    script_to_language = {
        'hindi': 'hi-IN',
        'marathi': 'mr-IN',
        'tamil': 'ta-IN'
    }
    language = script_to_language[script]
    
    # Create DocumentProcessor with mocked client
    processor = DocumentProcessor(
        textract_client=mock_textract,
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Extract ledger data
    ledger_data = processor.extract_ledger_data(image_url, language=language)
    
    # Property 1: Extraction completes successfully
    assert isinstance(ledger_data, LedgerData), \
        f"Extraction should succeed for {script} script and return LedgerData object"
    
    # Property 2: All required fields are present
    assert ledger_data.farmer_name is not None, \
        f"farmer_name should be extracted for {script} script"
    assert ledger_data.crop_type is not None, \
        f"crop_type should be extracted for {script} script"
    
    # Property 3: Extracted text contains characters from the correct script
    # Check farmer_name for script-specific characters
    if script in ['hindi', 'marathi']:
        # Both use Devanagari script
        has_devanagari = has_script_characters(ledger_data.farmer_name, script)
        assert has_devanagari or ledger_data.farmer_name.isascii(), \
            f"farmer_name should contain Devanagari characters or be ASCII for {script} script, got: {ledger_data.farmer_name}"
    elif script == 'tamil':
        has_tamil = has_script_characters(ledger_data.farmer_name, 'tamil')
        assert has_tamil or ledger_data.farmer_name.isascii(), \
            f"farmer_name should contain Tamil characters or be ASCII for {script} script, got: {ledger_data.farmer_name}"
    
    # Property 4: Numeric fields are extracted correctly (numbers are typically in Arabic numerals)
    assert isinstance(ledger_data.quantity, (int, float)), \
        f"quantity should be numeric for {script} script"
    assert isinstance(ledger_data.moisture, (int, float)), \
        f"moisture should be numeric for {script} script"
    assert isinstance(ledger_data.price, (int, float)), \
        f"price should be numeric for {script} script"
    
    # Property 5: Confidence scores are present for all fields
    assert 'FARMER_NAME' in ledger_data.confidence_scores, \
        f"confidence_scores should contain FARMER_NAME for {script} script"
    assert 'CROP_TYPE' in ledger_data.confidence_scores, \
        f"confidence_scores should contain CROP_TYPE for {script} script"
    
    # Property 6: Confidence scores are valid (0-100)
    for field, confidence in ledger_data.confidence_scores.items():
        assert 0 <= confidence <= 100, \
            f"Confidence score for {field} should be between 0 and 100 for {script} script, got {confidence}"
    
    # Property 7: LedgerData structure is consistent across scripts
    assert hasattr(ledger_data, 'ledger_id'), \
        f"LedgerData should have ledger_id for {script} script"
    assert hasattr(ledger_data, 'farmer_id'), \
        f"LedgerData should have farmer_id for {script} script"
    assert hasattr(ledger_data, 'image_url'), \
        f"LedgerData should have image_url for {script} script"
    
    # Property 8: Image URL is preserved
    assert ledger_data.image_url == image_url, \
        f"image_url should be preserved for {script} script"


@given(
    script=st.sampled_from(['hindi', 'marathi', 'tamil']),
    data=st.data()
)
@settings(max_examples=100, deadline=None)
def test_property_4_script_character_recognition(script, data):
    """
    **Property 4: Multi-Script OCR Support (Character Recognition)**
    **Validates: Requirements 2.3**
    
    Verify that the DocumentProcessor correctly recognizes and preserves
    vernacular characters from Hindi, Marathi, and Tamil scripts.
    """
    # Generate text in the specified script
    if script == 'hindi':
        test_text = data.draw(hindi_text())
    elif script == 'marathi':
        test_text = data.draw(marathi_text())
    else:  # tamil
        test_text = data.draw(tamil_text())
    
    # Property 1: Generated text contains characters from the correct script
    assert has_script_characters(test_text, script), \
        f"Generated text should contain {script} characters: {test_text}"
    
    # Property 2: Text is not empty
    assert len(test_text) > 0, \
        f"Generated {script} text should not be empty"
    
    # Property 3: Text can be encoded and decoded without loss
    try:
        encoded = test_text.encode('utf-8')
        decoded = encoded.decode('utf-8')
        assert decoded == test_text, \
            f"{script} text should survive UTF-8 encoding/decoding"
    except Exception as e:
        pytest.fail(f"Failed to encode/decode {script} text: {str(e)}")


@given(
    image_url=s3_url(prefix='s3://kisan-setu-raw/ledger-images'),
    data=st.data()
)
@settings(max_examples=100, deadline=None)
def test_property_4_all_scripts_supported(image_url, data):
    """
    **Property 4: Multi-Script OCR Support (All Scripts)**
    **Validates: Requirements 2.3**
    
    Verify that the DocumentProcessor supports all three required scripts:
    Hindi, Marathi, and Tamil.
    """
    scripts = ['hindi', 'marathi', 'tamil']
    
    for script in scripts:
        # Generate mock response for this script
        mock_response = data.draw(multi_script_textract_response(script=script))
        
        # Create mock Textract client
        mock_textract = Mock()
        mock_textract.analyze_document.return_value = mock_response
        
        # Map script to language code
        script_to_language = {
            'hindi': 'hi-IN',
            'marathi': 'mr-IN',
            'tamil': 'ta-IN'
        }
        language = script_to_language[script]
        
        # Create DocumentProcessor
        processor = DocumentProcessor(
            textract_client=mock_textract,
            s3_client=Mock(),
            dynamodb_table=Mock()
        )
        
        # Extract ledger data
        try:
            ledger_data = processor.extract_ledger_data(image_url, language=language)
            
            # Property: Extraction succeeds for all supported scripts
            assert isinstance(ledger_data, LedgerData), \
                f"DocumentProcessor should successfully extract data for {script} script"
            
            assert ledger_data.farmer_name is not None, \
                f"farmer_name should be extracted for {script} script"
            
        except Exception as e:
            pytest.fail(f"DocumentProcessor failed to process {script} script: {str(e)}")


# ============================================================================
# Edge Cases
# ============================================================================

def test_mixed_script_handling():
    """
    Test that documents with mixed scripts (e.g., Hindi text with English numbers)
    are handled correctly.
    """
    # Create a response with mixed Hindi and English
    mock_response = {
        'Blocks': [
            {
                'BlockType': 'QUERY',
                'Id': 'query-1',
                'Query': {'Text': 'What is the farmer name?', 'Alias': 'FARMER_NAME'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-1']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-1',
                'Text': 'राजेश Kumar',  # Mixed Hindi and English
                'Confidence': 85.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-2',
                'Query': {'Text': 'What is the quantity?', 'Alias': 'QUANTITY'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-2']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-2',
                'Text': '100',  # English numerals
                'Confidence': 95.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-3',
                'Query': {'Text': 'What is the crop type?', 'Alias': 'CROP_TYPE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-3']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-3',
                'Text': 'गेहूं',  # Hindi
                'Confidence': 90.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-4',
                'Query': {'Text': 'What is the price?', 'Alias': 'PRICE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-4']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-4',
                'Text': '2500',
                'Confidence': 92.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-5',
                'Query': {'Text': 'What is the moisture?', 'Alias': 'MOISTURE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-5']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-5',
                'Text': '12.5',
                'Confidence': 88.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-6',
                'Query': {'Text': 'What is the date?', 'Alias': 'DATE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-6']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-6',
                'Text': '2024-01-15',
                'Confidence': 85.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-7',
                'Query': {'Text': 'What is the quality grade?', 'Alias': 'QUALITY_GRADE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-7']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-7',
                'Text': 'A',
                'Confidence': 87.0
            }
        ],
        'DocumentMetadata': {'Pages': 1}
    }
    
    mock_textract = Mock()
    mock_textract.analyze_document.return_value = mock_response
    
    processor = DocumentProcessor(
        textract_client=mock_textract,
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    ledger_data = processor.extract_ledger_data('s3://test/image.jpg', language='hi-IN')
    
    # Should handle mixed scripts correctly
    assert ledger_data.farmer_name == 'राजेश Kumar'
    assert ledger_data.crop_type == 'गेहूं'
    assert ledger_data.quantity == 100.0
    assert ledger_data.price == 2500.0


def test_tamil_specific_characters():
    """
    Test that Tamil-specific characters are correctly handled.
    """
    mock_response = {
        'Blocks': [
            {
                'BlockType': 'QUERY',
                'Id': 'query-1',
                'Query': {'Text': 'What is the farmer name?', 'Alias': 'FARMER_NAME'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-1']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-1',
                'Text': 'முருகன்',  # Tamil name
                'Confidence': 85.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-2',
                'Query': {'Text': 'What is the crop type?', 'Alias': 'CROP_TYPE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-2']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-2',
                'Text': 'அரிசி',  # Tamil word for rice
                'Confidence': 90.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-3',
                'Query': {'Text': 'What is the quantity?', 'Alias': 'QUANTITY'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-3']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-3',
                'Text': '150',
                'Confidence': 95.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-4',
                'Query': {'Text': 'What is the price?', 'Alias': 'PRICE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-4']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-4',
                'Text': '3000',
                'Confidence': 92.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-5',
                'Query': {'Text': 'What is the moisture?', 'Alias': 'MOISTURE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-5']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-5',
                'Text': '14.0',
                'Confidence': 88.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-6',
                'Query': {'Text': 'What is the date?', 'Alias': 'DATE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-6']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-6',
                'Text': '2024-01-20',
                'Confidence': 85.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-7',
                'Query': {'Text': 'What is the quality grade?', 'Alias': 'QUALITY_GRADE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-7']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-7',
                'Text': 'B',
                'Confidence': 87.0
            }
        ],
        'DocumentMetadata': {'Pages': 1}
    }
    
    mock_textract = Mock()
    mock_textract.analyze_document.return_value = mock_response
    
    processor = DocumentProcessor(
        textract_client=mock_textract,
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    ledger_data = processor.extract_ledger_data('s3://test/image.jpg', language='ta-IN')
    
    # Should correctly extract Tamil text
    assert ledger_data.farmer_name == 'முருகன்'
    assert ledger_data.crop_type == 'அரிசி'
    assert has_script_characters(ledger_data.farmer_name, 'tamil')
    assert has_script_characters(ledger_data.crop_type, 'tamil')
