"""
Unit tests for Document Processor Component.

Tests the DocumentProcessor class methods:
- extract_ledger_data
- validate_extraction
- aggregate_ledgers
"""

import pytest
import sys
import os
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from processor.processor import (
    DocumentProcessor,
    LedgerData,
    ValidationResult,
    AggregatedData,
    CONFIDENCE_THRESHOLD
)


class TestDocumentProcessor:
    """Test suite for DocumentProcessor class."""
    
    @pytest.fixture
    def mock_textract_client(self):
        """Create mock Textract client."""
        return Mock()
    
    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        return Mock()
    
    @pytest.fixture
    def mock_dynamodb_table(self):
        """Create mock DynamoDB table."""
        return Mock()
    
    @pytest.fixture
    def processor(self, mock_textract_client, mock_s3_client, mock_dynamodb_table):
        """Create DocumentProcessor instance with mocked clients."""
        return DocumentProcessor(
            textract_client=mock_textract_client,
            s3_client=mock_s3_client,
            dynamodb_table=mock_dynamodb_table,
            confidence_threshold=70.0
        )
    
    @pytest.fixture
    def sample_textract_response(self):
        """Sample Textract response with query results."""
        return {
            'Blocks': [
                {
                    'BlockType': 'QUERY',
                    'Id': 'query-1',
                    'Query': {'Text': 'What is the quantity?', 'Alias': 'QUANTITY'},
                    'Relationships': [{'Type': 'ANSWER', 'Ids': ['result-1']}]
                },
                {
                    'BlockType': 'QUERY_RESULT',
                    'Id': 'result-1',
                    'Text': '100',
                    'Confidence': 95.5
                },
                {
                    'BlockType': 'QUERY',
                    'Id': 'query-2',
                    'Query': {'Text': 'What is the moisture level?', 'Alias': 'MOISTURE'},
                    'Relationships': [{'Type': 'ANSWER', 'Ids': ['result-2']}]
                },
                {
                    'BlockType': 'QUERY_RESULT',
                    'Id': 'result-2',
                    'Text': '12.5',
                    'Confidence': 88.0
                },
                {
                    'BlockType': 'QUERY',
                    'Id': 'query-3',
                    'Query': {'Text': 'What is the price?', 'Alias': 'PRICE'},
                    'Relationships': [{'Type': 'ANSWER', 'Ids': ['result-3']}]
                },
                {
                    'BlockType': 'QUERY_RESULT',
                    'Id': 'result-3',
                    'Text': '2500',
                    'Confidence': 92.0
                },
                {
                    'BlockType': 'QUERY',
                    'Id': 'query-4',
                    'Query': {'Text': 'What is the crop type?', 'Alias': 'CROP_TYPE'},
                    'Relationships': [{'Type': 'ANSWER', 'Ids': ['result-4']}]
                },
                {
                    'BlockType': 'QUERY_RESULT',
                    'Id': 'result-4',
                    'Text': 'onion',
                    'Confidence': 85.0
                },
                {
                    'BlockType': 'QUERY',
                    'Id': 'query-5',
                    'Query': {'Text': 'What is the date?', 'Alias': 'DATE'},
                    'Relationships': [{'Type': 'ANSWER', 'Ids': ['result-5']}]
                },
                {
                    'BlockType': 'QUERY_RESULT',
                    'Id': 'result-5',
                    'Text': '2024-01-15',
                    'Confidence': 80.0
                },
                {
                    'BlockType': 'QUERY',
                    'Id': 'query-6',
                    'Query': {'Text': 'What is the farmer name?', 'Alias': 'FARMER_NAME'},
                    'Relationships': [{'Type': 'ANSWER', 'Ids': ['result-6']}]
                },
                {
                    'BlockType': 'QUERY_RESULT',
                    'Id': 'result-6',
                    'Text': 'Ramesh Kumar',
                    'Confidence': 75.0
                },
                {
                    'BlockType': 'QUERY',
                    'Id': 'query-7',
                    'Query': {'Text': 'What is the quality grade?', 'Alias': 'QUALITY_GRADE'},
                    'Relationships': [{'Type': 'ANSWER', 'Ids': ['result-7']}]
                },
                {
                    'BlockType': 'QUERY_RESULT',
                    'Id': 'result-7',
                    'Text': 'A',
                    'Confidence': 90.0
                }
            ]
        }
    
    @pytest.fixture
    def sample_ledger_data(self):
        """Sample LedgerData object."""
        return LedgerData(
            ledger_id='LEDGER#2024-01-15T10:00:00',
            farmer_id='FARMER#+919876543210',
            quantity=100.0,
            moisture=12.5,
            price=2500.0,
            date='2024-01-15',
            crop_type='onion',
            farmer_name='Ramesh Kumar',
            quality_grade='A',
            confidence_scores={
                'QUANTITY': 95.5,
                'MOISTURE': 88.0,
                'PRICE': 92.0,
                'CROP_TYPE': 85.0,
                'DATE': 80.0,
                'FARMER_NAME': 75.0,
                'QUALITY_GRADE': 90.0
            },
            image_url='s3://kisan-setu-raw/ledger-images/+919876543210/2024-01-15.jpg',
            fields_needing_review=[]
        )
    
    # ==================== Test extract_ledger_data ====================
    
    def test_extract_ledger_data_success(self, processor, mock_textract_client, sample_textract_response):
        """Test successful ledger data extraction."""
        # Setup mock
        mock_textract_client.analyze_document.return_value = sample_textract_response
        
        # Execute
        image_url = 's3://kisan-setu-raw/ledger-images/+919876543210/2024-01-15.jpg'
        result = processor.extract_ledger_data(image_url, language='en')
        
        # Verify
        assert result is not None
        assert result.quantity == 100.0
        assert result.moisture == 12.5
        assert result.price == 2500.0
        assert result.crop_type == 'onion'
        assert result.date == '2024-01-15'
        assert result.farmer_name == 'Ramesh Kumar'
        assert result.quality_grade == 'A'
        assert result.farmer_id == 'FARMER#+919876543210'
        assert result.image_url == image_url
        
        # Verify confidence scores
        assert result.confidence_scores['QUANTITY'] == 95.5
        assert result.confidence_scores['MOISTURE'] == 88.0
        assert result.confidence_scores['PRICE'] == 92.0
        assert result.confidence_scores['CROP_TYPE'] == 85.0
        
        # Verify Textract was called correctly
        mock_textract_client.analyze_document.assert_called_once()
        call_args = mock_textract_client.analyze_document.call_args[1]
        assert call_args['Document']['S3Object']['Bucket'] == 'kisan-setu-raw'
        assert call_args['FeatureTypes'] == ['QUERIES']
    
    def test_extract_ledger_data_hindi_script(self, processor, mock_textract_client, sample_textract_response):
        """Test extraction with Hindi script."""
        mock_textract_client.analyze_document.return_value = sample_textract_response
        
        image_url = 's3://kisan-setu-raw/ledger-images/+919876543210/hindi-ledger.jpg'
        result = processor.extract_ledger_data(image_url, language='hi-IN')
        
        assert result is not None
        assert result.quantity == 100.0
        # Textract automatically detects Hindi script
        mock_textract_client.analyze_document.assert_called_once()
    
    def test_extract_ledger_data_textract_failure(self, processor, mock_textract_client):
        """Test handling of Textract API failure."""
        mock_textract_client.analyze_document.side_effect = Exception("Textract API error")
        
        image_url = 's3://kisan-setu-raw/ledger-images/+919876543210/2024-01-15.jpg'
        
        with pytest.raises(Exception) as exc_info:
            processor.extract_ledger_data(image_url)
        
        assert "Could not extract data from image" in str(exc_info.value)
    
    def test_extract_ledger_data_with_s3_key_only(self, processor, mock_textract_client, sample_textract_response):
        """Test extraction with S3 key instead of full URL."""
        mock_textract_client.analyze_document.return_value = sample_textract_response
        
        s3_key = 'ledger-images/+919876543210/2024-01-15.jpg'
        result = processor.extract_ledger_data(s3_key)
        
        assert result is not None
        assert result.quantity == 100.0
    
    def test_extract_ledger_data_missing_fields(self, processor, mock_textract_client):
        """Test extraction with missing fields."""
        # Response with only some fields
        partial_response = {
            'Blocks': [
                {
                    'BlockType': 'QUERY',
                    'Id': 'query-1',
                    'Query': {'Text': 'What is the quantity?', 'Alias': 'QUANTITY'},
                    'Relationships': [{'Type': 'ANSWER', 'Ids': ['result-1']}]
                },
                {
                    'BlockType': 'QUERY_RESULT',
                    'Id': 'result-1',
                    'Text': '100',
                    'Confidence': 95.5
                }
            ]
        }
        mock_textract_client.analyze_document.return_value = partial_response
        
        image_url = 's3://kisan-setu-raw/ledger-images/+919876543210/2024-01-15.jpg'
        result = processor.extract_ledger_data(image_url)
        
        # Should still return result with default values for missing fields
        assert result is not None
        assert result.quantity == 100.0
        assert result.crop_type == 'unknown'  # default value
        assert result.moisture == 0.0  # default value
    
    # ==================== Test validate_extraction ====================
    
    def test_validate_extraction_all_valid(self, processor, sample_ledger_data):
        """Test validation with all fields valid and high confidence."""
        result = processor.validate_extraction(sample_ledger_data)
        
        assert result.is_valid is True
        assert len(result.missing_fields) == 0
        assert len(result.low_confidence_fields) == 0
        assert len(result.fields_needing_review) == 0
    
    def test_validate_extraction_low_confidence_required_field(self, processor, sample_ledger_data):
        """Test validation with low confidence in required field."""
        # Set QUANTITY confidence below threshold
        sample_ledger_data.confidence_scores['QUANTITY'] = 65.0
        
        result = processor.validate_extraction(sample_ledger_data)
        
        assert 'QUANTITY' in result.low_confidence_fields
        assert 'QUANTITY' in result.fields_needing_review
    
    def test_validate_extraction_missing_required_field(self, processor):
        """Test validation with missing required field."""
        ledger_data = LedgerData(
            ledger_id='LEDGER#2024-01-15T10:00:00',
            farmer_id='FARMER#+919876543210',
            quantity=0.0,  # Missing/zero quantity
            moisture=12.5,
            price=2500.0,
            date='2024-01-15',
            crop_type='',  # Missing crop type
            farmer_name='Ramesh Kumar',
            quality_grade='A',
            confidence_scores={
                'MOISTURE': 88.0,
                'PRICE': 92.0,
                'DATE': 80.0
            },
            image_url='s3://kisan-setu-raw/test.jpg',
            fields_needing_review=[]
        )
        
        result = processor.validate_extraction(ledger_data)
        
        assert result.is_valid is False
        assert 'QUANTITY' in result.missing_fields
        assert 'CROP_TYPE' in result.missing_fields
    
    def test_validate_extraction_low_confidence_optional_field(self, processor, sample_ledger_data):
        """Test validation with low confidence in optional field."""
        # Set MOISTURE confidence below threshold
        sample_ledger_data.confidence_scores['MOISTURE'] = 60.0
        
        result = processor.validate_extraction(sample_ledger_data)
        
        # Should still be valid (MOISTURE is optional)
        assert result.is_valid is True
        assert 'MOISTURE' in result.low_confidence_fields
        assert 'MOISTURE' in result.fields_needing_review
    
    def test_validate_extraction_updates_ledger_data(self, processor, sample_ledger_data):
        """Test that validation updates fields_needing_review in ledger_data."""
        sample_ledger_data.confidence_scores['QUANTITY'] = 65.0
        
        result = processor.validate_extraction(sample_ledger_data)
        
        # Check that ledger_data was updated
        assert 'QUANTITY' in sample_ledger_data.fields_needing_review
    
    def test_validate_extraction_custom_threshold(self, mock_textract_client, mock_s3_client, mock_dynamodb_table):
        """Test validation with custom confidence threshold."""
        processor = DocumentProcessor(
            textract_client=mock_textract_client,
            s3_client=mock_s3_client,
            dynamodb_table=mock_dynamodb_table,
            confidence_threshold=90.0  # Higher threshold
        )
        
        ledger_data = LedgerData(
            ledger_id='LEDGER#2024-01-15T10:00:00',
            farmer_id='FARMER#+919876543210',
            quantity=100.0,
            moisture=12.5,
            price=2500.0,
            date='2024-01-15',
            crop_type='onion',
            farmer_name='Ramesh Kumar',
            quality_grade='A',
            confidence_scores={
                'QUANTITY': 85.0,  # Below 90 threshold
                'MOISTURE': 88.0,
                'PRICE': 92.0,
                'CROP_TYPE': 85.0
            },
            image_url='s3://kisan-setu-raw/test.jpg',
            fields_needing_review=[]
        )
        
        result = processor.validate_extraction(ledger_data)
        
        assert 'QUANTITY' in result.low_confidence_fields
        assert 'CROP_TYPE' in result.low_confidence_fields
    
    # ==================== Test aggregate_ledgers ====================
    
    def test_aggregate_ledgers_single_ledger(self, processor, sample_ledger_data):
        """Test aggregation with single ledger."""
        result = processor.aggregate_ledgers([sample_ledger_data])
        
        assert result.farmer_id == sample_ledger_data.farmer_id
        assert result.total_records == 1
        assert len(result.ledger_ids) == 1
        assert len(result.transactions) == 1
        assert result.transactions[0]['quantity'] == 100.0
        assert result.transactions[0]['crop_type'] == 'onion'
    
    def test_aggregate_ledgers_multiple_ledgers(self, processor):
        """Test aggregation with multiple ledgers."""
        ledgers = []
        for i in range(3):
            ledger = LedgerData(
                ledger_id=f'LEDGER#2024-01-{15+i}T10:00:00',
                farmer_id='FARMER#+919876543210',
                quantity=100.0 + i * 10,
                moisture=12.5,
                price=2500.0 + i * 100,
                date=f'2024-01-{15+i}',
                crop_type='onion',
                farmer_name='Ramesh Kumar',
                quality_grade='A',
                confidence_scores={'QUANTITY': 95.0, 'PRICE': 92.0, 'CROP_TYPE': 85.0},
                image_url=f's3://kisan-setu-raw/ledger-{i}.jpg',
                fields_needing_review=[]
            )
            ledgers.append(ledger)
        
        result = processor.aggregate_ledgers(ledgers)
        
        assert result.total_records == 3
        assert len(result.ledger_ids) == 3
        assert len(result.transactions) == 3
        assert result.transactions[0]['quantity'] == 100.0
        assert result.transactions[1]['quantity'] == 110.0
        assert result.transactions[2]['quantity'] == 120.0
    
    def test_aggregate_ledgers_empty_list(self, processor):
        """Test aggregation with empty list."""
        with pytest.raises(ValueError) as exc_info:
            processor.aggregate_ledgers([])
        
        assert "Cannot aggregate empty ledger list" in str(exc_info.value)
    
    def test_aggregate_ledgers_preserves_all_fields(self, processor, sample_ledger_data):
        """Test that aggregation preserves all ledger fields."""
        result = processor.aggregate_ledgers([sample_ledger_data])
        
        transaction = result.transactions[0]
        assert transaction['ledger_id'] == sample_ledger_data.ledger_id
        assert transaction['quantity'] == sample_ledger_data.quantity
        assert transaction['moisture'] == sample_ledger_data.moisture
        assert transaction['price'] == sample_ledger_data.price
        assert transaction['date'] == sample_ledger_data.date
        assert transaction['crop_type'] == sample_ledger_data.crop_type
        assert transaction['farmer_name'] == sample_ledger_data.farmer_name
        assert transaction['quality_grade'] == sample_ledger_data.quality_grade
        assert transaction['image_url'] == sample_ledger_data.image_url
        assert transaction['confidence_scores'] == sample_ledger_data.confidence_scores
        assert transaction['fields_needing_review'] == sample_ledger_data.fields_needing_review
    
    # ==================== Test store_ledger_data ====================
    
    def test_store_ledger_data_success(self, processor, mock_dynamodb_table, sample_ledger_data):
        """Test successful storage of ledger data."""
        validation_result = ValidationResult(
            is_valid=True,
            fields_needing_review=[],
            missing_fields=[],
            low_confidence_fields=[]
        )
        
        transaction_id = processor.store_ledger_data(sample_ledger_data, validation_result)
        
        assert transaction_id.startswith('TXN#')
        mock_dynamodb_table.put_item.assert_called_once()
        
        # Verify stored item structure
        call_args = mock_dynamodb_table.put_item.call_args[1]
        item = call_args['Item']
        assert item['PK'] == sample_ledger_data.farmer_id
        assert item['SK'] == transaction_id
        assert item['entity_type'] == 'Transaction'
        assert item['quantity'] == Decimal('100.0')
        assert item['crop_type'] == 'onion'
        assert item['validation_status'] == 'valid'
    
    def test_store_ledger_data_needs_review(self, processor, mock_dynamodb_table, sample_ledger_data):
        """Test storage with validation issues."""
        validation_result = ValidationResult(
            is_valid=False,
            fields_needing_review=['QUANTITY', 'MOISTURE'],
            missing_fields=[],
            low_confidence_fields=['QUANTITY', 'MOISTURE']
        )
        
        transaction_id = processor.store_ledger_data(sample_ledger_data, validation_result)
        
        # Verify validation status
        call_args = mock_dynamodb_table.put_item.call_args[1]
        item = call_args['Item']
        assert item['validation_status'] == 'needs_review'
        assert 'QUANTITY' in item['fields_needing_review']
        assert 'MOISTURE' in item['fields_needing_review']
    
    def test_store_ledger_data_dynamodb_error(self, processor, mock_dynamodb_table, sample_ledger_data):
        """Test handling of DynamoDB error."""
        mock_dynamodb_table.put_item.side_effect = Exception("DynamoDB error")
        
        validation_result = ValidationResult(
            is_valid=True,
            fields_needing_review=[],
            missing_fields=[],
            low_confidence_fields=[]
        )
        
        with pytest.raises(Exception) as exc_info:
            processor.store_ledger_data(sample_ledger_data, validation_result)
        
        assert "DynamoDB error" in str(exc_info.value)
    
    # ==================== Test helper methods ====================
    
    def test_parse_s3_url_full_url(self, processor):
        """Test parsing full S3 URL."""
        url = 's3://my-bucket/path/to/file.jpg'
        bucket, key = processor._parse_s3_url(url)
        
        assert bucket == 'my-bucket'
        assert key == 'path/to/file.jpg'
    
    def test_parse_s3_url_key_only(self, processor):
        """Test parsing S3 key without s3:// prefix."""
        key = 'path/to/file.jpg'
        bucket, result_key = processor._parse_s3_url(key)
        
        assert bucket == 'kisan-setu-raw'  # default bucket
        assert result_key == key
    
    def test_extract_farmer_id_from_url(self, processor):
        """Test extracting farmer ID from image URL."""
        url = 's3://bucket/ledger-images/+919876543210/2024-01-15.jpg'
        farmer_id = processor._extract_farmer_id_from_url(url)
        
        assert farmer_id == 'FARMER#+919876543210'
    
    def test_extract_farmer_id_from_url_invalid_format(self, processor):
        """Test extracting farmer ID from invalid URL format."""
        url = 's3://bucket/some/other/path.jpg'
        farmer_id = processor._extract_farmer_id_from_url(url)
        
        assert farmer_id == 'FARMER#unknown'
    
    def test_safe_float_valid_number(self, processor):
        """Test safe float conversion with valid number."""
        assert processor._safe_float('123.45') == 123.45
        assert processor._safe_float('100') == 100.0
    
    def test_safe_float_with_non_numeric_chars(self, processor):
        """Test safe float conversion with non-numeric characters."""
        assert processor._safe_float('Rs. 2500') == 2500.0
        assert processor._safe_float('100 kg') == 100.0
        assert processor._safe_float('12.5%') == 12.5
    
    def test_safe_float_invalid_input(self, processor):
        """Test safe float conversion with invalid input."""
        assert processor._safe_float('') == 0.0
        assert processor._safe_float('abc') == 0.0
        assert processor._safe_float(None) == 0.0
    
    def test_safe_float_custom_default(self, processor):
        """Test safe float conversion with custom default value."""
        assert processor._safe_float('', default=99.9) == 99.9
        assert processor._safe_float('invalid', default=-1.0) == -1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
