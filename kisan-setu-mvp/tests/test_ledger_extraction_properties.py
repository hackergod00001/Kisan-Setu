"""
Property-Based Tests for Structured Ledger Extraction

Tests Property 3: Structured Ledger Extraction
For any ledger image extraction, the output should be valid JSON containing
all required fields (quantity, moisture, price, date, farmer_name) with their
corresponding confidence scores.

**Validates: Requirements 2.2, 2.4**

Uses Hypothesis framework with minimum 100 iterations.
"""

import pytest
import json
import sys
import os
import importlib.util
from hypothesis import given, settings, strategies as st
from typing import Dict, Any
from unittest.mock import Mock, MagicMock, patch

# Load processor module directly via importlib (avoids package name collision)
_processor_path = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'processor', 'processor.py')
_spec = importlib.util.spec_from_file_location("processor_module", os.path.abspath(_processor_path))
_processor_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_processor_mod)
DocumentProcessor = _processor_mod.DocumentProcessor
LedgerData = _processor_mod.LedgerData

# Add lambda directories to path for generators
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'processor'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

# Import test data generators
from generators import ledger_data, s3_url


# ============================================================================
# Mock Textract Response Generator
# ============================================================================

@st.composite
def textract_response(draw):
    """
    Generate a mock Textract response with query results.
    
    Returns: Dictionary mimicking Textract AnalyzeDocument response
    """
    # Generate values for each field
    quantity_value = draw(st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False))
    moisture_value = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    price_value = draw(st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False))
    date_value = draw(st.dates()).isoformat()
    farmer_name_value = draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ', min_size=3, max_size=50))
    crop_type_value = draw(st.sampled_from(['onion', 'wheat', 'rice', 'cotton']))
    quality_grade_value = draw(st.sampled_from(['A', 'B', 'C']))
    
    # Generate confidence scores (0-100)
    quantity_conf = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    moisture_conf = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    price_conf = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    date_conf = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    farmer_name_conf = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    crop_type_conf = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    quality_grade_conf = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    
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
        {'id': 'answer-5', 'text': farmer_name_value, 'confidence': farmer_name_conf},
        {'id': 'answer-6', 'text': crop_type_value, 'confidence': crop_type_conf},
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
# Property 3: Structured Ledger Extraction
# ============================================================================

@given(
    image_url=s3_url(prefix='s3://kisan-setu-raw/ledger-images'),
    mock_response=textract_response()
)
@settings(max_examples=100, deadline=None)
def test_property_3_structured_ledger_extraction(image_url, mock_response):
    """
    **Property 3: Structured Ledger Extraction**
    **Validates: Requirements 2.2, 2.4**
    
    For any ledger image extraction, the output should be valid JSON containing
    all required fields (quantity, moisture, price, date, farmer_name) with their
    corresponding confidence scores.
    
    Required fields:
    - quantity (float)
    - moisture (float)
    - price (float)
    - date (string)
    - farmer_name (string)
    - crop_type (string)
    - quality_grade (string)
    - confidence_scores (dict with confidence for each field)
    """
    # Create mock Textract client
    mock_textract = Mock()
    mock_textract.analyze_document.return_value = mock_response
    
    # Create DocumentProcessor with mocked client
    processor = DocumentProcessor(
        textract_client=mock_textract,
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Extract ledger data
    ledger_data = processor.extract_ledger_data(image_url, language='en')
    
    # Property 1: Output is a LedgerData object (can be serialized to JSON)
    assert isinstance(ledger_data, LedgerData), \
        "Output should be a LedgerData object"
    
    # Property 2: All required fields are present
    required_fields = ['quantity', 'moisture', 'price', 'date', 'farmer_name', 
                      'crop_type', 'quality_grade']
    for field in required_fields:
        assert hasattr(ledger_data, field), \
            f"LedgerData should have field '{field}'"
        assert getattr(ledger_data, field) is not None, \
            f"Field '{field}' should not be None"
    
    # Property 3: Numeric fields have correct types
    assert isinstance(ledger_data.quantity, (int, float)), \
        "quantity should be numeric"
    assert isinstance(ledger_data.moisture, (int, float)), \
        "moisture should be numeric"
    assert isinstance(ledger_data.price, (int, float)), \
        "price should be numeric"
    
    # Property 4: String fields have correct types
    assert isinstance(ledger_data.date, str), \
        "date should be a string"
    assert isinstance(ledger_data.farmer_name, str), \
        "farmer_name should be a string"
    assert isinstance(ledger_data.crop_type, str), \
        "crop_type should be a string"
    assert isinstance(ledger_data.quality_grade, str), \
        "quality_grade should be a string"
    
    # Property 5: confidence_scores is a dictionary
    assert isinstance(ledger_data.confidence_scores, dict), \
        "confidence_scores should be a dictionary"
    
    # Property 6: confidence_scores contains all required fields
    expected_confidence_fields = ['QUANTITY', 'MOISTURE', 'PRICE', 'DATE', 
                                 'FARMER_NAME', 'CROP_TYPE', 'QUALITY_GRADE']
    for field in expected_confidence_fields:
        assert field in ledger_data.confidence_scores, \
            f"confidence_scores should contain '{field}'"
    
    # Property 7: All confidence scores are numeric and in valid range (0-100)
    for field, confidence in ledger_data.confidence_scores.items():
        assert isinstance(confidence, (int, float)), \
            f"Confidence score for '{field}' should be numeric"
        assert 0 <= confidence <= 100, \
            f"Confidence score for '{field}' should be between 0 and 100, got {confidence}"
    
    # Property 8: Numeric fields have valid ranges
    assert ledger_data.quantity >= 0, \
        "quantity should be non-negative"
    assert 0 <= ledger_data.moisture <= 100, \
        "moisture should be between 0 and 100"
    assert ledger_data.price >= 0, \
        "price should be non-negative"
    
    # Property 9: LedgerData can be serialized to JSON
    try:
        # Convert to dict (simulating JSON serialization)
        ledger_dict = {
            'ledger_id': ledger_data.ledger_id,
            'farmer_id': ledger_data.farmer_id,
            'quantity': float(ledger_data.quantity),
            'moisture': float(ledger_data.moisture),
            'price': float(ledger_data.price),
            'date': ledger_data.date,
            'farmer_name': ledger_data.farmer_name,
            'crop_type': ledger_data.crop_type,
            'quality_grade': ledger_data.quality_grade,
            'confidence_scores': {k: float(v) for k, v in ledger_data.confidence_scores.items()},
            'image_url': ledger_data.image_url,
            'fields_needing_review': ledger_data.fields_needing_review
        }
        
        # Attempt JSON serialization
        json_str = json.dumps(ledger_dict)
        assert len(json_str) > 0, "JSON serialization should produce non-empty string"
        
        # Verify it can be deserialized
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict), "Deserialized JSON should be a dictionary"
        
    except (TypeError, ValueError) as e:
        pytest.fail(f"LedgerData should be JSON-serializable: {str(e)}")
    
    # Property 10: image_url is preserved
    assert ledger_data.image_url == image_url, \
        "image_url should be preserved in the output"
    
    # Property 11: ledger_id is generated and non-empty
    assert ledger_data.ledger_id is not None, \
        "ledger_id should be generated"
    assert len(ledger_data.ledger_id) > 0, \
        "ledger_id should be non-empty"
    assert ledger_data.ledger_id.startswith('LEDGER#'), \
        "ledger_id should follow the format 'LEDGER#<timestamp>'"
    
    # Property 12: farmer_id is generated and non-empty
    assert ledger_data.farmer_id is not None, \
        "farmer_id should be generated"
    assert len(ledger_data.farmer_id) > 0, \
        "farmer_id should be non-empty"
    assert ledger_data.farmer_id.startswith('FARMER#'), \
        "farmer_id should follow the format 'FARMER#<identifier>'"


@given(
    image_url=s3_url(prefix='s3://kisan-setu-raw/ledger-images'),
    mock_response=textract_response()
)
@settings(max_examples=100, deadline=None)
def test_property_3_json_output_structure(image_url, mock_response):
    """
    **Property 3: Structured Ledger Extraction (JSON Structure)**
    **Validates: Requirements 2.2, 2.4**
    
    Verify that the JSON output has the correct structure and all required
    fields are present in the serialized format.
    """
    # Create mock Textract client
    mock_textract = Mock()
    mock_textract.analyze_document.return_value = mock_response
    
    # Create DocumentProcessor with mocked client
    processor = DocumentProcessor(
        textract_client=mock_textract,
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Extract ledger data
    ledger_data = processor.extract_ledger_data(image_url, language='en')
    
    # Convert to JSON
    ledger_dict = {
        'ledger_id': ledger_data.ledger_id,
        'farmer_id': ledger_data.farmer_id,
        'quantity': float(ledger_data.quantity),
        'moisture': float(ledger_data.moisture),
        'price': float(ledger_data.price),
        'date': ledger_data.date,
        'farmer_name': ledger_data.farmer_name,
        'crop_type': ledger_data.crop_type,
        'quality_grade': ledger_data.quality_grade,
        'confidence_scores': {k: float(v) for k, v in ledger_data.confidence_scores.items()},
        'image_url': ledger_data.image_url,
        'fields_needing_review': ledger_data.fields_needing_review
    }
    
    json_str = json.dumps(ledger_dict)
    parsed = json.loads(json_str)
    
    # Property 1: JSON contains all required top-level fields
    required_top_level_fields = [
        'ledger_id', 'farmer_id', 'quantity', 'moisture', 'price', 
        'date', 'farmer_name', 'crop_type', 'quality_grade',
        'confidence_scores', 'image_url', 'fields_needing_review'
    ]
    
    for field in required_top_level_fields:
        assert field in parsed, \
            f"JSON output should contain field '{field}'"
    
    # Property 2: confidence_scores is a nested object with all required fields
    assert isinstance(parsed['confidence_scores'], dict), \
        "confidence_scores should be a dictionary in JSON"
    
    expected_confidence_fields = ['QUANTITY', 'MOISTURE', 'PRICE', 'DATE', 
                                 'FARMER_NAME', 'CROP_TYPE', 'QUALITY_GRADE']
    for field in expected_confidence_fields:
        assert field in parsed['confidence_scores'], \
            f"confidence_scores in JSON should contain '{field}'"
    
    # Property 3: fields_needing_review is an array
    assert isinstance(parsed['fields_needing_review'], list), \
        "fields_needing_review should be an array in JSON"
    
    # Property 4: All confidence scores in JSON are numeric
    for field, confidence in parsed['confidence_scores'].items():
        assert isinstance(confidence, (int, float)), \
            f"Confidence score for '{field}' in JSON should be numeric"


@given(
    image_url=s3_url(prefix='s3://kisan-setu-raw/ledger-images')
)
@settings(max_examples=100, deadline=None)
def test_property_3_confidence_score_completeness(image_url):
    """
    **Property 3: Structured Ledger Extraction (Confidence Completeness)**
    **Validates: Requirements 2.2, 2.4**
    
    For any ledger extraction, every extracted field should have a corresponding
    confidence score in the confidence_scores dictionary.
    """
    # Generate a mock response with all fields
    mock_response = {
        'Blocks': [
            # QUANTITY query and answer
            {
                'BlockType': 'QUERY',
                'Id': 'query-1',
                'Query': {'Text': 'What is the quantity?', 'Alias': 'QUANTITY'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-1']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-1',
                'Text': '100.5',
                'Confidence': 95.5
            },
            # MOISTURE query and answer
            {
                'BlockType': 'QUERY',
                'Id': 'query-2',
                'Query': {'Text': 'What is the moisture?', 'Alias': 'MOISTURE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-2']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-2',
                'Text': '12.3',
                'Confidence': 88.2
            },
            # PRICE query and answer
            {
                'BlockType': 'QUERY',
                'Id': 'query-3',
                'Query': {'Text': 'What is the price?', 'Alias': 'PRICE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-3']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-3',
                'Text': '2500',
                'Confidence': 92.0
            },
            # DATE query and answer
            {
                'BlockType': 'QUERY',
                'Id': 'query-4',
                'Query': {'Text': 'What is the date?', 'Alias': 'DATE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-4']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-4',
                'Text': '2024-01-15',
                'Confidence': 85.0
            },
            # FARMER_NAME query and answer
            {
                'BlockType': 'QUERY',
                'Id': 'query-5',
                'Query': {'Text': 'What is the farmer name?', 'Alias': 'FARMER_NAME'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-5']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-5',
                'Text': 'Rajesh Kumar',
                'Confidence': 90.0
            },
            # CROP_TYPE query and answer
            {
                'BlockType': 'QUERY',
                'Id': 'query-6',
                'Query': {'Text': 'What is the crop type?', 'Alias': 'CROP_TYPE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-6']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-6',
                'Text': 'wheat',
                'Confidence': 93.5
            },
            # QUALITY_GRADE query and answer
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
    
    # Create mock Textract client
    mock_textract = Mock()
    mock_textract.analyze_document.return_value = mock_response
    
    # Create DocumentProcessor with mocked client
    processor = DocumentProcessor(
        textract_client=mock_textract,
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Extract ledger data
    ledger_data = processor.extract_ledger_data(image_url, language='en')
    
    # Property: Every field should have a confidence score
    field_mapping = {
        'quantity': 'QUANTITY',
        'moisture': 'MOISTURE',
        'price': 'PRICE',
        'date': 'DATE',
        'farmer_name': 'FARMER_NAME',
        'crop_type': 'CROP_TYPE',
        'quality_grade': 'QUALITY_GRADE'
    }
    
    for field_name, confidence_key in field_mapping.items():
        # Check that the field exists
        assert hasattr(ledger_data, field_name), \
            f"LedgerData should have field '{field_name}'"
        
        # Check that there's a corresponding confidence score
        assert confidence_key in ledger_data.confidence_scores, \
            f"confidence_scores should contain '{confidence_key}' for field '{field_name}'"
        
        # Check that the confidence score is valid
        confidence = ledger_data.confidence_scores[confidence_key]
        assert isinstance(confidence, (int, float)), \
            f"Confidence for '{confidence_key}' should be numeric"
        assert 0 <= confidence <= 100, \
            f"Confidence for '{confidence_key}' should be between 0 and 100"


# ============================================================================
# Edge Cases
# ============================================================================

def test_empty_textract_response():
    """
    Test that empty Textract responses are handled gracefully.
    """
    mock_response = {
        'Blocks': [],
        'DocumentMetadata': {'Pages': 1}
    }
    
    mock_textract = Mock()
    mock_textract.analyze_document.return_value = mock_response
    
    processor = DocumentProcessor(
        textract_client=mock_textract,
        s3_client=Mock(),
        dynamodb_table=Mock()
    )
    
    # Extract ledger data
    ledger_data = processor.extract_ledger_data('s3://test/image.jpg', language='en')
    
    # Should still return a LedgerData object with default values
    assert isinstance(ledger_data, LedgerData)
    assert ledger_data.quantity == 0.0
    assert ledger_data.moisture == 0.0
    assert ledger_data.price == 0.0


def test_missing_confidence_scores():
    """
    Test that missing confidence scores are handled (default to 0).
    """
    mock_response = {
        'Blocks': [
            {
                'BlockType': 'QUERY',
                'Id': 'query-1',
                'Query': {'Text': 'What is the quantity?', 'Alias': 'QUANTITY'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-1']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-1',
                'Text': '100',
                # Missing Confidence field
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
    
    ledger_data = processor.extract_ledger_data('s3://test/image.jpg', language='en')
    
    # Should have a confidence score (default to 0)
    assert 'QUANTITY' in ledger_data.confidence_scores
    assert ledger_data.confidence_scores['QUANTITY'] == 0


def test_non_numeric_values():
    """
    Test that non-numeric values in numeric fields are handled (converted to 0).
    """
    mock_response = {
        'Blocks': [
            {
                'BlockType': 'QUERY',
                'Id': 'query-1',
                'Query': {'Text': 'What is the quantity?', 'Alias': 'QUANTITY'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-1']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-1',
                'Text': 'not a number',
                'Confidence': 50.0
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
    
    ledger_data = processor.extract_ledger_data('s3://test/image.jpg', language='en')
    
    # Should convert to 0.0 for non-numeric values
    assert ledger_data.quantity == 0.0


# ============================================================================
# Property 5: Low-Confidence Field Flagging
# ============================================================================

@st.composite
def textract_response_with_confidence(draw, confidence_threshold=70.0):
    """
    Generate a mock Textract response with controlled confidence scores.
    Some fields will have confidence below threshold to test flagging.
    
    Args:
        confidence_threshold: Threshold for low confidence (default 70.0)
    
    Returns: Dictionary mimicking Textract AnalyzeDocument response with
             at least one field having confidence below threshold
    """
    # Generate values for each field
    quantity_value = draw(st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False))
    moisture_value = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    price_value = draw(st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False))
    date_value = draw(st.dates()).isoformat()
    farmer_name_value = draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ ', min_size=3, max_size=50))
    crop_type_value = draw(st.sampled_from(['onion', 'wheat', 'rice', 'cotton']))
    quality_grade_value = draw(st.sampled_from(['A', 'B', 'C']))
    
    # Generate confidence scores - ensure at least one is below threshold
    # We'll randomly assign confidence scores, with some below threshold
    all_fields = ['QUANTITY', 'MOISTURE', 'PRICE', 'DATE', 'FARMER_NAME', 'CROP_TYPE', 'QUALITY_GRADE']
    
    # Randomly select 1-4 fields to have low confidence
    num_low_confidence = draw(st.integers(min_value=1, max_value=4))
    low_confidence_fields = draw(st.lists(
        st.sampled_from(all_fields),
        min_size=num_low_confidence,
        max_size=num_low_confidence,
        unique=True
    ))
    
    # Generate confidence scores
    confidence_scores = {}
    for field in all_fields:
        if field in low_confidence_fields:
            # Low confidence: 0 to threshold-1
            confidence_scores[field] = draw(st.floats(
                min_value=0.0,
                max_value=confidence_threshold - 0.1,
                allow_nan=False,
                allow_infinity=False
            ))
        else:
            # High confidence: threshold to 100
            confidence_scores[field] = draw(st.floats(
                min_value=confidence_threshold,
                max_value=100.0,
                allow_nan=False,
                allow_infinity=False
            ))
    
    # Build Textract response structure
    blocks = []
    
    # Query blocks and answers
    field_data = {
        'QUANTITY': (quantity_value, confidence_scores['QUANTITY']),
        'MOISTURE': (moisture_value, confidence_scores['MOISTURE']),
        'PRICE': (price_value, confidence_scores['PRICE']),
        'DATE': (date_value, confidence_scores['DATE']),
        'FARMER_NAME': (farmer_name_value, confidence_scores['FARMER_NAME']),
        'CROP_TYPE': (crop_type_value, confidence_scores['CROP_TYPE']),
        'QUALITY_GRADE': (quality_grade_value, confidence_scores['QUALITY_GRADE']),
    }
    
    query_id = 1
    for alias, (value, confidence) in field_data.items():
        # Query block
        blocks.append({
            'BlockType': 'QUERY',
            'Id': f'query-{query_id}',
            'Query': {'Text': f'What is the {alias}?', 'Alias': alias},
            'Relationships': [{'Type': 'ANSWER', 'Ids': [f'answer-{query_id}']}]
        })
        
        # Answer block
        blocks.append({
            'BlockType': 'QUERY_RESULT',
            'Id': f'answer-{query_id}',
            'Text': str(value),
            'Confidence': confidence
        })
        
        query_id += 1
    
    return {
        'Blocks': blocks,
        'DocumentMetadata': {'Pages': 1},
        'expected_low_confidence_fields': low_confidence_fields  # For test verification
    }


@given(
    image_url=s3_url(prefix='s3://kisan-setu-raw/ledger-images'),
    mock_response=textract_response_with_confidence(confidence_threshold=70.0)
)
@settings(max_examples=100, deadline=None)
def test_property_5_low_confidence_field_flagging(image_url, mock_response):
    """
    **Property 5: Low-Confidence Field Flagging**
    **Validates: Requirements 2.5**
    
    For any extracted field with confidence score below threshold (e.g., 0.7 or 70%),
    the field should be included in the fields_needing_review list and flagged
    for manual verification.
    
    This test verifies that:
    1. Fields with confidence < 70% are flagged for review
    2. Fields with confidence >= 70% are NOT flagged
    3. The fields_needing_review list contains exactly the low-confidence fields
    4. The validation result correctly identifies low-confidence fields
    """
    # Extract expected low confidence fields from mock response
    expected_low_confidence = mock_response.pop('expected_low_confidence_fields')
    
    # Create mock Textract client
    mock_textract = Mock()
    mock_textract.analyze_document.return_value = mock_response
    
    # Create DocumentProcessor with confidence threshold of 70.0
    processor = DocumentProcessor(
        textract_client=mock_textract,
        s3_client=Mock(),
        dynamodb_table=Mock(),
        confidence_threshold=70.0
    )
    
    # Extract ledger data
    ledger_data = processor.extract_ledger_data(image_url, language='en')
    
    # Validate extraction (this populates fields_needing_review)
    validation_result = processor.validate_extraction(ledger_data)
    
    # Property 1: All fields with confidence < 70% should be in fields_needing_review
    for field in expected_low_confidence:
        confidence = ledger_data.confidence_scores.get(field, 100)
        assert confidence < 70.0, \
            f"Expected field '{field}' to have low confidence, got {confidence}"
        assert field in ledger_data.fields_needing_review, \
            f"Field '{field}' with confidence {confidence} should be in fields_needing_review"
        assert field in validation_result.fields_needing_review, \
            f"Field '{field}' with confidence {confidence} should be in validation_result.fields_needing_review"
        assert field in validation_result.low_confidence_fields, \
            f"Field '{field}' with confidence {confidence} should be in validation_result.low_confidence_fields"
    
    # Property 2: All fields in fields_needing_review should have confidence < 70%
    for field in ledger_data.fields_needing_review:
        confidence = ledger_data.confidence_scores.get(field, 100)
        assert confidence < 70.0, \
            f"Field '{field}' in fields_needing_review should have confidence < 70%, got {confidence}"
    
    # Property 3: Fields with confidence >= 70% should NOT be in fields_needing_review
    for field, confidence in ledger_data.confidence_scores.items():
        if confidence >= 70.0:
            assert field not in ledger_data.fields_needing_review, \
                f"Field '{field}' with confidence {confidence} should NOT be in fields_needing_review"
    
    # Property 4: fields_needing_review should be a list
    assert isinstance(ledger_data.fields_needing_review, list), \
        "fields_needing_review should be a list"
    
    # Property 5: All items in fields_needing_review should be strings
    for field in ledger_data.fields_needing_review:
        assert isinstance(field, str), \
            f"Field in fields_needing_review should be a string, got {type(field)}"
    
    # Property 6: fields_needing_review should not contain duplicates
    assert len(ledger_data.fields_needing_review) == len(set(ledger_data.fields_needing_review)), \
        "fields_needing_review should not contain duplicates"
    
    # Property 7: validation_result.low_confidence_fields should match fields_needing_review
    assert set(validation_result.low_confidence_fields) == set(ledger_data.fields_needing_review), \
        "validation_result.low_confidence_fields should match ledger_data.fields_needing_review"
    
    # Property 8: If any required field has low confidence, validation should still succeed
    # (low confidence doesn't mean invalid, just needs review)
    required_fields = ['QUANTITY', 'PRICE', 'CROP_TYPE']
    has_low_confidence_required = any(
        field in ledger_data.fields_needing_review for field in required_fields
    )
    # Validation can still be valid even with low confidence fields
    # (as long as the fields are present and not empty)
    if has_low_confidence_required:
        # Just verify that the field is flagged
        for field in required_fields:
            if field in ledger_data.fields_needing_review:
                assert ledger_data.confidence_scores[field] < 70.0, \
                    f"Required field '{field}' in fields_needing_review should have confidence < 70%"


@given(
    image_url=s3_url(prefix='s3://kisan-setu-raw/ledger-images')
)
@settings(max_examples=100, deadline=None)
def test_property_5_exact_threshold_boundary(image_url):
    """
    **Property 5: Low-Confidence Field Flagging (Boundary Test)**
    **Validates: Requirements 2.5**
    
    Test the exact boundary condition: fields with confidence exactly at 70.0
    should NOT be flagged, while fields at 69.9 should be flagged.
    """
    # Create a response with fields at exact boundary
    mock_response = {
        'Blocks': [
            # QUANTITY at exactly 70.0 (should NOT be flagged)
            {
                'BlockType': 'QUERY',
                'Id': 'query-1',
                'Query': {'Text': 'What is the quantity?', 'Alias': 'QUANTITY'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-1']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-1',
                'Text': '100.0',
                'Confidence': 70.0  # Exactly at threshold
            },
            # MOISTURE at 69.9 (should be flagged)
            {
                'BlockType': 'QUERY',
                'Id': 'query-2',
                'Query': {'Text': 'What is the moisture?', 'Alias': 'MOISTURE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-2']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-2',
                'Text': '12.0',
                'Confidence': 69.9  # Just below threshold
            },
            # PRICE at 70.1 (should NOT be flagged)
            {
                'BlockType': 'QUERY',
                'Id': 'query-3',
                'Query': {'Text': 'What is the price?', 'Alias': 'PRICE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-3']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-3',
                'Text': '2500',
                'Confidence': 70.1  # Just above threshold
            },
            # DATE at 0.0 (should be flagged)
            {
                'BlockType': 'QUERY',
                'Id': 'query-4',
                'Query': {'Text': 'What is the date?', 'Alias': 'DATE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-4']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-4',
                'Text': '2024-01-15',
                'Confidence': 0.0  # Minimum confidence
            },
            # FARMER_NAME at 100.0 (should NOT be flagged)
            {
                'BlockType': 'QUERY',
                'Id': 'query-5',
                'Query': {'Text': 'What is the farmer name?', 'Alias': 'FARMER_NAME'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-5']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-5',
                'Text': 'Rajesh Kumar',
                'Confidence': 100.0  # Maximum confidence
            },
            # CROP_TYPE at 85.0 (should NOT be flagged)
            {
                'BlockType': 'QUERY',
                'Id': 'query-6',
                'Query': {'Text': 'What is the crop type?', 'Alias': 'CROP_TYPE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-6']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-6',
                'Text': 'wheat',
                'Confidence': 85.0
            },
            # QUALITY_GRADE at 50.0 (should be flagged)
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
                'Confidence': 50.0
            }
        ],
        'DocumentMetadata': {'Pages': 1}
    }
    
    # Create mock Textract client
    mock_textract = Mock()
    mock_textract.analyze_document.return_value = mock_response
    
    # Create DocumentProcessor with confidence threshold of 70.0
    processor = DocumentProcessor(
        textract_client=mock_textract,
        s3_client=Mock(),
        dynamodb_table=Mock(),
        confidence_threshold=70.0
    )
    
    # Extract ledger data
    ledger_data = processor.extract_ledger_data(image_url, language='en')
    
    # Validate extraction
    validation_result = processor.validate_extraction(ledger_data)
    
    # Property 1: Fields at exactly 70.0 should NOT be flagged
    assert 'QUANTITY' not in ledger_data.fields_needing_review, \
        "QUANTITY with confidence 70.0 should NOT be flagged"
    assert ledger_data.confidence_scores['QUANTITY'] == 70.0
    
    # Property 2: Fields at 69.9 should be flagged
    assert 'MOISTURE' in ledger_data.fields_needing_review, \
        "MOISTURE with confidence 69.9 should be flagged"
    assert ledger_data.confidence_scores['MOISTURE'] == 69.9
    
    # Property 3: Fields above 70.0 should NOT be flagged
    assert 'PRICE' not in ledger_data.fields_needing_review, \
        "PRICE with confidence 70.1 should NOT be flagged"
    assert 'FARMER_NAME' not in ledger_data.fields_needing_review, \
        "FARMER_NAME with confidence 100.0 should NOT be flagged"
    assert 'CROP_TYPE' not in ledger_data.fields_needing_review, \
        "CROP_TYPE with confidence 85.0 should NOT be flagged"
    
    # Property 4: Fields below 70.0 should be flagged
    assert 'DATE' in ledger_data.fields_needing_review, \
        "DATE with confidence 0.0 should be flagged"
    assert 'QUALITY_GRADE' in ledger_data.fields_needing_review, \
        "QUALITY_GRADE with confidence 50.0 should be flagged"
    
    # Property 5: Exactly 3 fields should be flagged (MOISTURE, DATE, QUALITY_GRADE)
    assert len(ledger_data.fields_needing_review) == 3, \
        f"Expected 3 fields to be flagged, got {len(ledger_data.fields_needing_review)}: {ledger_data.fields_needing_review}"
    
    # Property 6: The flagged fields should be exactly MOISTURE, DATE, QUALITY_GRADE
    expected_flagged = {'MOISTURE', 'DATE', 'QUALITY_GRADE'}
    actual_flagged = set(ledger_data.fields_needing_review)
    assert actual_flagged == expected_flagged, \
        f"Expected flagged fields {expected_flagged}, got {actual_flagged}"


@given(
    image_url=s3_url(prefix='s3://kisan-setu-raw/ledger-images')
)
@settings(max_examples=100, deadline=None)
def test_property_5_all_fields_low_confidence(image_url):
    """
    **Property 5: Low-Confidence Field Flagging (All Low)**
    **Validates: Requirements 2.5**
    
    Test the edge case where ALL fields have low confidence.
    All fields should be flagged for review.
    """
    # Create a response where all fields have low confidence
    mock_response = {
        'Blocks': [
            # All fields with confidence < 70
            {
                'BlockType': 'QUERY',
                'Id': 'query-1',
                'Query': {'Text': 'What is the quantity?', 'Alias': 'QUANTITY'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-1']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-1',
                'Text': '100.0',
                'Confidence': 45.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-2',
                'Query': {'Text': 'What is the moisture?', 'Alias': 'MOISTURE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-2']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-2',
                'Text': '12.0',
                'Confidence': 50.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-3',
                'Query': {'Text': 'What is the price?', 'Alias': 'PRICE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-3']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-3',
                'Text': '2500',
                'Confidence': 55.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-4',
                'Query': {'Text': 'What is the date?', 'Alias': 'DATE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-4']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-4',
                'Text': '2024-01-15',
                'Confidence': 60.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-5',
                'Query': {'Text': 'What is the farmer name?', 'Alias': 'FARMER_NAME'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-5']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-5',
                'Text': 'Rajesh Kumar',
                'Confidence': 65.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-6',
                'Query': {'Text': 'What is the crop type?', 'Alias': 'CROP_TYPE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-6']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-6',
                'Text': 'wheat',
                'Confidence': 40.0
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
                'Confidence': 35.0
            }
        ],
        'DocumentMetadata': {'Pages': 1}
    }
    
    # Create mock Textract client
    mock_textract = Mock()
    mock_textract.analyze_document.return_value = mock_response
    
    # Create DocumentProcessor
    processor = DocumentProcessor(
        textract_client=mock_textract,
        s3_client=Mock(),
        dynamodb_table=Mock(),
        confidence_threshold=70.0
    )
    
    # Extract and validate
    ledger_data = processor.extract_ledger_data(image_url, language='en')
    validation_result = processor.validate_extraction(ledger_data)
    
    # Property 1: All 7 fields should be flagged
    all_fields = {'QUANTITY', 'MOISTURE', 'PRICE', 'DATE', 'FARMER_NAME', 'CROP_TYPE', 'QUALITY_GRADE'}
    assert len(ledger_data.fields_needing_review) == 7, \
        f"Expected all 7 fields to be flagged, got {len(ledger_data.fields_needing_review)}"
    
    # Property 2: fields_needing_review should contain all fields
    assert set(ledger_data.fields_needing_review) == all_fields, \
        f"Expected all fields to be flagged: {all_fields}, got {set(ledger_data.fields_needing_review)}"
    
    # Property 3: All confidence scores should be < 70
    for field, confidence in ledger_data.confidence_scores.items():
        assert confidence < 70.0, \
            f"Field '{field}' should have confidence < 70, got {confidence}"
    
    # Property 4: validation_result should reflect all low confidence fields
    assert len(validation_result.low_confidence_fields) == 7, \
        f"Expected 7 low confidence fields, got {len(validation_result.low_confidence_fields)}"


@given(
    image_url=s3_url(prefix='s3://kisan-setu-raw/ledger-images')
)
@settings(max_examples=100, deadline=None)
def test_property_5_no_fields_low_confidence(image_url):
    """
    **Property 5: Low-Confidence Field Flagging (All High)**
    **Validates: Requirements 2.5**
    
    Test the edge case where NO fields have low confidence.
    fields_needing_review should be empty.
    """
    # Create a response where all fields have high confidence
    mock_response = {
        'Blocks': [
            # All fields with confidence >= 70
            {
                'BlockType': 'QUERY',
                'Id': 'query-1',
                'Query': {'Text': 'What is the quantity?', 'Alias': 'QUANTITY'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-1']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-1',
                'Text': '100.0',
                'Confidence': 95.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-2',
                'Query': {'Text': 'What is the moisture?', 'Alias': 'MOISTURE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-2']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-2',
                'Text': '12.0',
                'Confidence': 88.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-3',
                'Query': {'Text': 'What is the price?', 'Alias': 'PRICE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-3']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-3',
                'Text': '2500',
                'Confidence': 92.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-4',
                'Query': {'Text': 'What is the date?', 'Alias': 'DATE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-4']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-4',
                'Text': '2024-01-15',
                'Confidence': 85.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-5',
                'Query': {'Text': 'What is the farmer name?', 'Alias': 'FARMER_NAME'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-5']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-5',
                'Text': 'Rajesh Kumar',
                'Confidence': 90.0
            },
            {
                'BlockType': 'QUERY',
                'Id': 'query-6',
                'Query': {'Text': 'What is the crop type?', 'Alias': 'CROP_TYPE'},
                'Relationships': [{'Type': 'ANSWER', 'Ids': ['answer-6']}]
            },
            {
                'BlockType': 'QUERY_RESULT',
                'Id': 'answer-6',
                'Text': 'wheat',
                'Confidence': 93.0
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
    
    # Create mock Textract client
    mock_textract = Mock()
    mock_textract.analyze_document.return_value = mock_response
    
    # Create DocumentProcessor
    processor = DocumentProcessor(
        textract_client=mock_textract,
        s3_client=Mock(),
        dynamodb_table=Mock(),
        confidence_threshold=70.0
    )
    
    # Extract and validate
    ledger_data = processor.extract_ledger_data(image_url, language='en')
    validation_result = processor.validate_extraction(ledger_data)
    
    # Property 1: fields_needing_review should be empty
    assert len(ledger_data.fields_needing_review) == 0, \
        f"Expected no fields to be flagged, got {ledger_data.fields_needing_review}"
    
    # Property 2: low_confidence_fields should be empty
    assert len(validation_result.low_confidence_fields) == 0, \
        f"Expected no low confidence fields, got {validation_result.low_confidence_fields}"
    
    # Property 3: All confidence scores should be >= 70
    for field, confidence in ledger_data.confidence_scores.items():
        assert confidence >= 70.0, \
            f"Field '{field}' should have confidence >= 70, got {confidence}"
    
    # Property 4: Validation should be successful
    assert validation_result.is_valid == True, \
        "Validation should be successful when all fields have high confidence"
