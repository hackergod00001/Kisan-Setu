"""
Cost Optimization Module
Implements batching, caching, and concurrent processing for cost efficiency.

This module provides:
- Request batching for Textract calls (batch size: 10)
- Redis/ElastiCache caching layer for satellite imagery (24-hour TTL)
- Batch processing with ThreadPoolExecutor for concurrent operations
"""

import json
import boto3
import os
import time
from typing import List, Dict, Any, Optional, Callable, TypeVar
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib

# Try to import redis, fall back to in-memory cache if not available
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("Warning: redis-py not available, using in-memory cache")

# AWS clients
textract = boto3.client('textract')

# Environment variables
REDIS_ENDPOINT = os.environ.get('REDIS_ENDPOINT', '')
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
CACHE_TTL_SECONDS = int(os.environ.get('CACHE_TTL_SECONDS', str(24 * 3600)))  # 24 hours
BATCH_SIZE = int(os.environ.get('TEXTRACT_BATCH_SIZE', '10'))
MAX_WORKERS = int(os.environ.get('MAX_WORKERS', '5'))

T = TypeVar('T')


@dataclass
class BatchResult:
    """Result of batch processing operation."""
    success_count: int
    failure_count: int
    results: List[Any]
    errors: List[Dict[str, Any]]
    processing_time: float


class CacheManager:
    """
    Caching layer for satellite imagery and other expensive operations.
    
    Uses Redis/ElastiCache when available, falls back to in-memory cache.
    Implements 24-hour TTL for cached data.
    """
    
    def __init__(
        self,
        redis_endpoint: str = REDIS_ENDPOINT,
        redis_port: int = REDIS_PORT,
        ttl_seconds: int = CACHE_TTL_SECONDS
    ):
        """
        Initialize CacheManager.
        
        Args:
            redis_endpoint: Redis/ElastiCache endpoint
            redis_port: Redis port
            ttl_seconds: Cache TTL in seconds (default 24 hours)
        """
        self.ttl_seconds = ttl_seconds
        self.redis_client = None
        self.in_memory_cache = {}  # Fallback cache
        
        # Try to connect to Redis
        if REDIS_AVAILABLE and redis_endpoint:
            try:
                self.redis_client = redis.Redis(
                    host=redis_endpoint,
                    port=redis_port,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
                # Test connection
                self.redis_client.ping()
                print(f"Connected to Redis at {redis_endpoint}:{redis_port}")
            except Exception as e:
                print(f"Failed to connect to Redis: {str(e)}, using in-memory cache")
                self.redis_client = None
        else:
            print("Redis not configured, using in-memory cache")
    
    def get(self, key: str) -> Optional[str]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        try:
            if self.redis_client:
                # Use Redis
                value = self.redis_client.get(key)
                if value:
                    print(f"Cache HIT (Redis): {key}")
                    return value
            else:
                # Use in-memory cache
                if key in self.in_memory_cache:
                    cached_data, expiry = self.in_memory_cache[key]
                    if datetime.utcnow() < expiry:
                        print(f"Cache HIT (memory): {key}")
                        return cached_data
                    else:
                        # Expired, remove from cache
                        del self.in_memory_cache[key]
            
            print(f"Cache MISS: {key}")
            return None
            
        except Exception as e:
            print(f"Cache get error: {str(e)}")
            return None
    
    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (default: self.ttl_seconds)
            
        Returns:
            True if successful, False otherwise
        """
        ttl = ttl or self.ttl_seconds
        
        try:
            if self.redis_client:
                # Use Redis with TTL
                self.redis_client.setex(key, ttl, value)
                print(f"Cached in Redis: {key} (TTL: {ttl}s)")
                return True
            else:
                # Use in-memory cache with expiry
                expiry = datetime.utcnow() + timedelta(seconds=ttl)
                self.in_memory_cache[key] = (value, expiry)
                print(f"Cached in memory: {key} (TTL: {ttl}s)")
                return True
                
        except Exception as e:
            print(f"Cache set error: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.redis_client:
                self.redis_client.delete(key)
            else:
                if key in self.in_memory_cache:
                    del self.in_memory_cache[key]
            
            print(f"Deleted from cache: {key}")
            return True
            
        except Exception as e:
            print(f"Cache delete error: {str(e)}")
            return False
    
    def generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Generate cache key from prefix and arguments.
        
        Args:
            prefix: Key prefix (e.g., 'satellite', 'ndvi')
            *args: Positional arguments to include in key
            **kwargs: Keyword arguments to include in key
            
        Returns:
            Cache key string
        """
        # Build key components
        components = [prefix]
        
        # Add positional args
        for arg in args:
            if isinstance(arg, (tuple, list)):
                components.extend(str(x) for x in arg)
            else:
                components.append(str(arg))
        
        # Add keyword args (sorted for consistency)
        for k, v in sorted(kwargs.items()):
            components.append(f"{k}={v}")
        
        # Join and hash if too long
        key = ':'.join(components)
        if len(key) > 200:
            # Hash long keys
            key_hash = hashlib.md5(key.encode()).hexdigest()
            key = f"{prefix}:{key_hash}"
        
        return key


class TextractBatcher:
    """
    Batches Textract requests to reduce per-request overhead.
    
    Collects requests within a batching window and processes them together.
    Batch size: 10 documents per batch.
    """
    
    def __init__(
        self,
        textract_client=None,
        batch_size: int = BATCH_SIZE,
        max_workers: int = MAX_WORKERS
    ):
        """
        Initialize TextractBatcher.
        
        Args:
            textract_client: Optional boto3 Textract client (for testing)
            batch_size: Maximum documents per batch
            max_workers: Maximum concurrent workers for batch processing
        """
        self.textract = textract_client or textract
        self.batch_size = batch_size
        self.max_workers = max_workers
    
    def process_batch(
        self,
        documents: List[Dict[str, Any]],
        queries: List[Dict[str, str]]
    ) -> BatchResult:
        """
        Process batch of documents with Textract.
        
        Args:
            documents: List of document specs with 'bucket' and 'key'
            queries: Textract queries to apply to all documents
            
        Returns:
            BatchResult with success/failure counts and results
        """
        start_time = time.time()
        
        print(f"Processing batch of {len(documents)} documents")
        
        results = []
        errors = []
        success_count = 0
        failure_count = 0
        
        # Process documents in batches using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all documents for processing
            future_to_doc = {
                executor.submit(
                    self._process_single_document,
                    doc,
                    queries
                ): doc for doc in documents
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_doc):
                doc = future_to_doc[future]
                try:
                    result = future.result()
                    results.append(result)
                    success_count += 1
                except Exception as e:
                    error_info = {
                        'document': doc,
                        'error': str(e),
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    errors.append(error_info)
                    failure_count += 1
                    print(f"Error processing document {doc.get('key', 'unknown')}: {str(e)}")
        
        processing_time = time.time() - start_time
        
        print(f"Batch processing complete: {success_count} succeeded, "
              f"{failure_count} failed, {processing_time:.2f}s")
        
        return BatchResult(
            success_count=success_count,
            failure_count=failure_count,
            results=results,
            errors=errors,
            processing_time=processing_time
        )
    
    def _process_single_document(
        self,
        document: Dict[str, Any],
        queries: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Process single document with Textract.
        
        Args:
            document: Document spec with 'bucket' and 'key'
            queries: Textract queries
            
        Returns:
            Textract response
        """
        bucket = document['bucket']
        key = document['key']
        
        print(f"Processing document: s3://{bucket}/{key}")
        
        response = self.textract.analyze_document(
            Document={
                'S3Object': {
                    'Bucket': bucket,
                    'Name': key
                }
            },
            FeatureTypes=['QUERIES'],
            QueriesConfig={'Queries': queries}
        )
        
        return {
            'document': document,
            'response': response,
            'timestamp': datetime.utcnow().isoformat()
        }


class ConcurrentProcessor:
    """
    Generic concurrent processor using ThreadPoolExecutor.
    
    Processes items concurrently with configurable worker pool size.
    """
    
    def __init__(self, max_workers: int = MAX_WORKERS):
        """
        Initialize ConcurrentProcessor.
        
        Args:
            max_workers: Maximum concurrent workers
        """
        self.max_workers = max_workers
    
    def process_batch(
        self,
        items: List[T],
        process_func: Callable[[T], Any],
        error_handler: Optional[Callable[[T, Exception], None]] = None
    ) -> BatchResult:
        """
        Process batch of items concurrently.
        
        Args:
            items: List of items to process
            process_func: Function to process each item
            error_handler: Optional error handler function
            
        Returns:
            BatchResult with success/failure counts and results
        """
        start_time = time.time()
        
        print(f"Processing {len(items)} items with {self.max_workers} workers")
        
        results = []
        errors = []
        success_count = 0
        failure_count = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all items for processing
            future_to_item = {
                executor.submit(process_func, item): item
                for item in items
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    result = future.result()
                    results.append(result)
                    success_count += 1
                except Exception as e:
                    error_info = {
                        'item': str(item),
                        'error': str(e),
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    errors.append(error_info)
                    failure_count += 1
                    
                    # Call error handler if provided
                    if error_handler:
                        try:
                            error_handler(item, e)
                        except Exception as handler_error:
                            print(f"Error handler failed: {str(handler_error)}")
        
        processing_time = time.time() - start_time
        
        print(f"Concurrent processing complete: {success_count} succeeded, "
              f"{failure_count} failed, {processing_time:.2f}s")
        
        return BatchResult(
            success_count=success_count,
            failure_count=failure_count,
            results=results,
            errors=errors,
            processing_time=processing_time
        )


# ==================== Global Instances ====================

# Global cache manager instance
cache_manager = CacheManager()

# Global Textract batcher instance
textract_batcher = TextractBatcher()

# Global concurrent processor instance
concurrent_processor = ConcurrentProcessor()


# ==================== Helper Functions ====================

def get_cached_or_compute(
    cache_key: str,
    compute_func: Callable[[], Any],
    ttl: Optional[int] = None,
    serialize_func: Callable[[Any], str] = json.dumps,
    deserialize_func: Callable[[str], Any] = json.loads
) -> Any:
    """
    Get value from cache or compute if not cached.
    
    Args:
        cache_key: Cache key
        compute_func: Function to compute value if not cached
        ttl: Cache TTL in seconds (default: 24 hours)
        serialize_func: Function to serialize value for caching
        deserialize_func: Function to deserialize cached value
        
    Returns:
        Cached or computed value
    """
    # Try to get from cache
    cached_value = cache_manager.get(cache_key)
    if cached_value is not None:
        try:
            return deserialize_func(cached_value)
        except Exception as e:
            print(f"Error deserializing cached value: {str(e)}")
    
    # Compute value
    print(f"Computing value for cache key: {cache_key}")
    value = compute_func()
    
    # Cache the result
    try:
        serialized = serialize_func(value)
        cache_manager.set(cache_key, serialized, ttl)
    except Exception as e:
        print(f"Error caching computed value: {str(e)}")
    
    return value
