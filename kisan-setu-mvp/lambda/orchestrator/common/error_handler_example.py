"""
Example usage of error handling infrastructure in Kisan-Setu components.

This file demonstrates how to integrate error handling, retry logic,
circuit breakers, and batch processing into Lambda handlers.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from error_handling import (
    retry_with_exponential_backoff,
    create_error_response,
    process_batch_with_resilience,
    get_circuit_breaker,
    ErrorCategory,
    ErrorSeverity,
    get_alerter
)


# Example 1: Using retry decorator for external service calls
@retry_with_exponential_backoff(max_retries=3, service_name='textract')
def call_textract_with_retry(image_url: str):
    """
    Call Textract with automatic retry and circuit breaker.
    
    This will retry up to 3 times with delays: 1s, 2s, 4s
    Circuit breaker will open after 5 consecutive failures.
    """
    import boto3
    textract = boto3.client('textract')
    
    # Parse S3 URL
    bucket, key = image_url.replace('s3://', '').split('/', 1)
    
    # Call Textract
    response = textract.analyze_document(
        Document={'S3Object': {'Bucket': bucket, 'Name': key}},
        FeatureTypes=['QUERIES']
    )
    
    return response


# Example 2: Creating localized error responses
def handle_invalid_gps(latitude: float, longitude: float, language: str = 'en'):
    """
    Handle invalid GPS coordinates with localized error message.
    """
    if not (-90 <= latitude <= 90):
        error = create_error_response(
            error_code='INVALID_GPS',
            technical_details=f"Invalid latitude: {latitude}",
            language=language,
            category=ErrorCategory.USER_INPUT,
            severity=ErrorSeverity.LOW
        )
        raise ValueError(error.user_message)
    
    if not (-180 <= longitude <= 180):
        error = create_error_response(
            error_code='INVALID_GPS',
            technical_details=f"Invalid longitude: {longitude}",
            language=language,
            category=ErrorCategory.USER_INPUT,
            severity=ErrorSeverity.LOW
        )
        raise ValueError(error.user_message)


# Example 3: Batch processing with resilience
def process_multiple_ledgers(image_urls: list, language: str = 'en'):
    """
    Process multiple ledger images, continuing even if some fail.
    
    Returns:
        Dictionary with success_count, failure_count, results, errors
    """
    def process_single_ledger(image_url: str):
        # Extract ledger data
        response = call_textract_with_retry(image_url)
        
        # Process response
        return {
            'image_url': image_url,
            'status': 'success',
            'data': response
        }
    
    return process_batch_with_resilience(
        items=image_urls,
        process_func=process_single_ledger,
        language=language
    )


# Example 4: Manual circuit breaker usage
def call_external_api_with_circuit_breaker(api_endpoint: str):
    """
    Call external API with circuit breaker protection.
    """
    circuit_breaker = get_circuit_breaker('external-api')
    
    def make_api_call():
        import requests
        response = requests.get(api_endpoint, timeout=10)
        response.raise_for_status()
        return response.json()
    
    try:
        return circuit_breaker.call(make_api_call)
    except Exception as e:
        error = create_error_response(
            error_code='SERVICE_UNAVAILABLE',
            technical_details=f"API call failed: {str(e)}",
            language='en',
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.HIGH,
            retry_after=60
        )
        raise RuntimeError(error.user_message)


# Example 5: Critical error with alerting
def handle_critical_system_error(error_details: str, context: dict):
    """
    Handle critical system error with automatic alerting.
    """
    error = create_error_response(
        error_code='SYSTEM_ERROR',
        technical_details=error_details,
        language='en',
        category=ErrorCategory.SYSTEM_ERROR,
        severity=ErrorSeverity.CRITICAL
    )
    
    # Alert will be sent automatically for CRITICAL severity
    alerter = get_alerter()
    alerter.send_alert(error, context=context)
    
    return error


# Example 6: Lambda handler with comprehensive error handling
def lambda_handler(event: dict, context):
    """
    Example Lambda handler with error handling.
    """
    try:
        # Extract parameters
        image_url = event.get('image_url')
        language = event.get('language', 'en')
        
        if not image_url:
            error = create_error_response(
                error_code='INVALID_INPUT',
                technical_details='Missing image_url parameter',
                language=language,
                category=ErrorCategory.USER_INPUT,
                severity=ErrorSeverity.LOW
            )
            return {
                'statusCode': 400,
                'body': error.to_dict()
            }
        
        # Process with retry logic
        result = call_textract_with_retry(image_url)
        
        return {
            'statusCode': 200,
            'body': {
                'status': 'success',
                'data': result
            }
        }
    
    except ValueError as e:
        # User input error
        return {
            'statusCode': 400,
            'body': {
                'status': 'error',
                'message': str(e)
            }
        }
    
    except RuntimeError as e:
        # External service error
        return {
            'statusCode': 503,
            'body': {
                'status': 'error',
                'message': str(e),
                'retry_after': 60
            }
        }
    
    except Exception as e:
        # Unexpected system error
        error = create_error_response(
            error_code='SYSTEM_ERROR',
            technical_details=f"Unexpected error: {str(e)}",
            language=event.get('language', 'en'),
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.CRITICAL
        )
        
        return {
            'statusCode': 500,
            'body': error.to_dict()
        }


# Example 7: Batch processing in Lambda
def batch_processing_handler(event: dict, context):
    """
    Lambda handler for batch processing with resilience.
    """
    try:
        image_urls = event.get('image_urls', [])
        language = event.get('language', 'en')
        
        if not image_urls:
            error = create_error_response(
                error_code='INVALID_INPUT',
                technical_details='No image URLs provided',
                language=language,
                category=ErrorCategory.USER_INPUT,
                severity=ErrorSeverity.LOW
            )
            return {
                'statusCode': 400,
                'body': error.to_dict()
            }
        
        # Process batch with resilience
        result = process_multiple_ledgers(image_urls, language)
        
        # Return appropriate status code
        if result['failure_count'] == 0:
            status_code = 200
        elif result['success_count'] > 0:
            status_code = 207  # Multi-Status (partial success)
        else:
            status_code = 500  # All failed
        
        return {
            'statusCode': status_code,
            'body': {
                'status': 'completed',
                'success_count': result['success_count'],
                'failure_count': result['failure_count'],
                'results': result['results'],
                'errors': result['errors'],
                'message': result.get('message')
            }
        }
    
    except Exception as e:
        error = create_error_response(
            error_code='SYSTEM_ERROR',
            technical_details=f"Batch processing error: {str(e)}",
            language=event.get('language', 'en'),
            category=ErrorCategory.SYSTEM_ERROR,
            severity=ErrorSeverity.CRITICAL
        )
        
        return {
            'statusCode': 500,
            'body': error.to_dict()
        }


if __name__ == '__main__':
    # Test examples
    print("Error Handling Examples")
    print("=" * 50)
    
    # Example 1: Invalid GPS
    print("\n1. Invalid GPS coordinates:")
    try:
        handle_invalid_gps(100, 50, language='hi-IN')
    except ValueError as e:
        print(f"   Error: {e}")
    
    # Example 2: Batch processing
    print("\n2. Batch processing:")
    result = process_multiple_ledgers(
        ['s3://bucket/image1.jpg', 's3://bucket/image2.jpg'],
        language='en'
    )
    print(f"   Success: {result['success_count']}, Failed: {result['failure_count']}")
    
    print("\n" + "=" * 50)
