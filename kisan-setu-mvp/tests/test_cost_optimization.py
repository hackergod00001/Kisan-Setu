"""
Unit tests for cost optimization module.

Tests caching, batching, and concurrent processing functionality.
"""

import pytest
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from common.cost_optimization import (
    CacheManager,
    TextractBatcher,
    ConcurrentProcessor,
    BatchResult,
    get_cached_or_compute
)


class TestCacheManager:
    """Tests for CacheManager class."""
    
    def test_cache_manager_initialization(self):
        """Test CacheManager initializes correctly."""
        cache = CacheManager(redis_endpoint='', ttl_seconds=3600)
        assert cache.ttl_seconds == 3600
        assert cache.redis_client is None  # No Redis endpoint
        assert isinstance(cache.in_memory_cache, dict)
    
    def test_in_memory_cache_set_get(self):
        """Test in-memory cache set and get operations."""
        cache = CacheManager(redis_endpoint='', ttl_seconds=10)
        
        # Set value
        result = cache.set('test_key', 'test_value')
        assert result is True
        
        # Get value
        value = cache.get('test_key')
        assert value == 'test_value'
    
    def test_in_memory_cache_expiry(self):
        """Test in-memory cache expiry."""
        cache = CacheManager(redis_endpoint='', ttl_seconds=1)
        
        # Set value with 1 second TTL
        cache.set('test_key', 'test_value')
        
        # Should be available immediately
        assert cache.get('test_key') == 'test_value'
        
        # Wait for expiry
        time.sleep(1.5)
        
        # Should be expired
        assert cache.get('test_key') is None
    
    def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = CacheManager(redis_endpoint='')
        
        value = cache.get('nonexistent_key')
        assert value is None
    
    def test_cache_delete(self):
        """Test cache delete operation."""
        cache = CacheManager(redis_endpoint='')
        
        # Set and verify
        cache.set('test_key', 'test_value')
        assert cache.get('test_key') == 'test_value'
        
        # Delete
        result = cache.delete('test_key')
        assert result is True
        
        # Verify deleted
        assert cache.get('test_key') is None
    
    def test_generate_cache_key(self):
        """Test cache key generation."""
        cache = CacheManager(redis_endpoint='')
        
        # Simple key
        key1 = cache.generate_cache_key('prefix', 'arg1', 'arg2')
        assert key1 == 'prefix:arg1:arg2'
        
        # Key with kwargs
        key2 = cache.generate_cache_key('prefix', lat=12.34, lon=56.78)
        assert 'prefix' in key2
        assert 'lat=12.34' in key2
        assert 'lon=56.78' in key2
        
        # Key with tuple
        key3 = cache.generate_cache_key('prefix', (12.34, 56.78))
        assert 'prefix' in key3
        assert '12.34' in key3
        assert '56.78' in key3


class TestTextractBatcher:
    """Tests for TextractBatcher class."""
    
    def test_textract_batcher_initialization(self):
        """Test TextractBatcher initializes correctly."""
        batcher = TextractBatcher(batch_size=5, max_workers=3)
        assert batcher.batch_size == 5
        assert batcher.max_workers == 3
    
    @patch('common.cost_optimization.textract')
    def test_process_single_document(self, mock_textract):
        """Test processing single document."""
        # Mock Textract response
        mock_textract.analyze_document.return_value = {
            'Blocks': [
                {
                    'BlockType': 'QUERY',
                    'Id': 'query1',
                    'Query': {'Alias': 'QUANTITY'}
                },
                {
                    'BlockType': 'QUERY_RESULT',
                    'Id': 'result1',
                    'Text': '100',
                    'Confidence': 95.0
                }
            ]
        }
        
        batcher = TextractBatcher(textract_client=mock_textract)
        
        document = {'bucket': 'test-bucket', 'key': 'test-key'}
        queries = [{'Text': 'What is the quantity?', 'Alias': 'QUANTITY'}]
        
        result = batcher._process_single_document(document, queries)
        
        assert result['document'] == document
        assert 'response' in result
        assert 'timestamp' in result
        
        # Verify Textract was called
        mock_textract.analyze_document.assert_called_once()
    
    @patch('common.cost_optimization.textract')
    def test_process_batch(self, mock_textract):
        """Test batch processing of documents."""
        # Mock Textract response
        mock_textract.analyze_document.return_value = {
            'Blocks': []
        }
        
        batcher = TextractBatcher(textract_client=mock_textract, max_workers=2)
        
        documents = [
            {'bucket': 'test-bucket', 'key': 'doc1.jpg'},
            {'bucket': 'test-bucket', 'key': 'doc2.jpg'},
            {'bucket': 'test-bucket', 'key': 'doc3.jpg'}
        ]
        queries = [{'Text': 'What is the quantity?', 'Alias': 'QUANTITY'}]
        
        result = batcher.process_batch(documents, queries)
        
        assert isinstance(result, BatchResult)
        assert result.success_count == 3
        assert result.failure_count == 0
        assert len(result.results) == 3
        assert len(result.errors) == 0
        assert result.processing_time > 0
        
        # Verify Textract was called for each document
        assert mock_textract.analyze_document.call_count == 3
    
    @patch('common.cost_optimization.textract')
    def test_process_batch_with_failures(self, mock_textract):
        """Test batch processing with some failures."""
        # Mock Textract to fail on second document
        call_count = [0]
        
        def mock_analyze(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Textract error")
            return {'Blocks': []}
        
        mock_textract.analyze_document.side_effect = mock_analyze
        
        batcher = TextractBatcher(textract_client=mock_textract, max_workers=1)
        
        documents = [
            {'bucket': 'test-bucket', 'key': 'doc1.jpg'},
            {'bucket': 'test-bucket', 'key': 'doc2.jpg'},
            {'bucket': 'test-bucket', 'key': 'doc3.jpg'}
        ]
        queries = []
        
        result = batcher.process_batch(documents, queries)
        
        assert result.success_count == 2
        assert result.failure_count == 1
        assert len(result.errors) == 1
        assert 'Textract error' in result.errors[0]['error']


class TestConcurrentProcessor:
    """Tests for ConcurrentProcessor class."""
    
    def test_concurrent_processor_initialization(self):
        """Test ConcurrentProcessor initializes correctly."""
        processor = ConcurrentProcessor(max_workers=4)
        assert processor.max_workers == 4
    
    def test_process_batch_success(self):
        """Test concurrent batch processing with all successes."""
        processor = ConcurrentProcessor(max_workers=2)
        
        def process_item(item):
            return item * 2
        
        items = [1, 2, 3, 4, 5]
        result = processor.process_batch(items, process_item)
        
        assert isinstance(result, BatchResult)
        assert result.success_count == 5
        assert result.failure_count == 0
        assert sorted(result.results) == [2, 4, 6, 8, 10]
        assert len(result.errors) == 0
    
    def test_process_batch_with_errors(self):
        """Test concurrent batch processing with some errors."""
        processor = ConcurrentProcessor(max_workers=2)
        
        def process_item(item):
            if item == 3:
                raise ValueError("Error on item 3")
            return item * 2
        
        items = [1, 2, 3, 4, 5]
        result = processor.process_batch(items, process_item)
        
        assert result.success_count == 4
        assert result.failure_count == 1
        assert len(result.errors) == 1
        assert 'Error on item 3' in result.errors[0]['error']
    
    def test_process_batch_with_error_handler(self):
        """Test concurrent batch processing with error handler."""
        processor = ConcurrentProcessor(max_workers=2)
        
        error_log = []
        
        def process_item(item):
            if item == 3:
                raise ValueError("Error on item 3")
            return item * 2
        
        def error_handler(item, error):
            error_log.append((item, str(error)))
        
        items = [1, 2, 3, 4, 5]
        result = processor.process_batch(items, process_item, error_handler)
        
        assert result.success_count == 4
        assert result.failure_count == 1
        assert len(error_log) == 1
        assert error_log[0][0] == 3


class TestGetCachedOrCompute:
    """Tests for get_cached_or_compute helper function."""
    
    def test_cache_hit(self):
        """Test cache hit returns cached value."""
        cache = CacheManager(redis_endpoint='')
        
        # Pre-populate cache
        cache.set('test_key', json.dumps({'value': 42}))
        
        compute_called = [False]
        
        def compute_func():
            compute_called[0] = True
            return {'value': 100}
        
        # Patch global cache_manager
        with patch('common.cost_optimization.cache_manager', cache):
            result = get_cached_or_compute('test_key', compute_func)
        
        assert result == {'value': 42}
        assert compute_called[0] is False  # Compute not called
    
    def test_cache_miss(self):
        """Test cache miss computes and caches value."""
        cache = CacheManager(redis_endpoint='')
        
        compute_called = [False]
        
        def compute_func():
            compute_called[0] = True
            return {'value': 100}
        
        # Patch global cache_manager
        with patch('common.cost_optimization.cache_manager', cache):
            result = get_cached_or_compute('test_key', compute_func)
        
        assert result == {'value': 100}
        assert compute_called[0] is True  # Compute was called
        
        # Verify value was cached
        cached_value = cache.get('test_key')
        assert cached_value is not None
        assert json.loads(cached_value) == {'value': 100}
    
    def test_custom_serialization(self):
        """Test custom serialization functions."""
        cache = CacheManager(redis_endpoint='')
        
        def compute_func():
            return datetime(2024, 1, 1, 12, 0, 0)
        
        def serialize(dt):
            return dt.isoformat()
        
        def deserialize(s):
            return datetime.fromisoformat(s)
        
        # Patch global cache_manager
        with patch('common.cost_optimization.cache_manager', cache):
            result = get_cached_or_compute(
                'test_key',
                compute_func,
                serialize_func=serialize,
                deserialize_func=deserialize
            )
        
        assert isinstance(result, datetime)
        assert result == datetime(2024, 1, 1, 12, 0, 0)
        
        # Verify cached value
        cached_value = cache.get('test_key')
        assert cached_value == '2024-01-01T12:00:00'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
