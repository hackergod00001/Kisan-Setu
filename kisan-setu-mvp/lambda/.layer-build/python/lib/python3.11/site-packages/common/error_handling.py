"""
Error Handling and Retry Logic for Kisan-Setu System.

This module provides:
- ErrorResponse dataclass for structured error responses
- Exponential backoff retry logic for external service calls
- Localized error messages for Hindi, Marathi, Tamil
- Circuit breaker pattern for external services
- Critical error alerting via SNS
- Batch processing resilience

Validates Requirements: 10.1, 10.2, 10.3, 10.4, 10.5
"""

import time
import logging
import boto3
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Callable, Any, Dict, List
from enum import Enum
from functools import wraps

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ErrorCategory(Enum):
    """Error categories for classification."""
    USER_INPUT = "user_input"
    EXTERNAL_SERVICE = "external_service"
    DATA_ERROR = "data_error"
    SYSTEM_ERROR = "system_error"


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorResponse:
    """
    Structured error response with localized messages.
    
    Attributes:
        error_code: Machine-readable error code (e.g., "INVALID_GPS", "SERVICE_UNAVAILABLE")
        user_message: Localized, user-friendly message
        technical_details: Technical error details for logging and debugging
        suggested_action: What user should do next
        retry_after: Seconds to wait before retry (if applicable)
        timestamp: When the error occurred
        category: Error category for classification
        severity: Error severity level
    """
    error_code: str
    user_message: str
    technical_details: str
    suggested_action: str
    retry_after: Optional[int] = None
    timestamp: Optional[datetime] = None
    category: ErrorCategory = ErrorCategory.SYSTEM_ERROR
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat() if self.timestamp else None
        result['category'] = self.category.value
        result['severity'] = self.severity.value
        return result


# Localized error messages for Hindi, Marathi, Tamil
ERROR_MESSAGES = {
    'INVALID_GPS': {
        'en': 'Invalid GPS coordinates. Please provide valid latitude and longitude.',
        'hi-IN': 'अमान्य GPS निर्देशांक। कृपया मान्य अक्षांश और देशांतर प्रदान करें।',
        'mr-IN': 'अवैध GPS निर्देशांक. कृपया वैध अक्षांश आणि रेखांश प्रदान करा.',
        'ta-IN': 'தவறான GPS ஆயத்தொலைவுகள். சரியான அட்சரேகை மற்றும் தீர்க்கரேகையை வழங்கவும்.'
    },
    'SERVICE_UNAVAILABLE': {
        'en': 'Service temporarily unavailable. Please try again in a few moments.',
        'hi-IN': 'सेवा अस्थायी रूप से अनुपलब्ध है। कृपया कुछ क्षणों में पुनः प्रयास करें।',
        'mr-IN': 'सेवा तात्पुरती अनुपलब्ध आहे. कृपया काही क्षणांनंतर पुन्हा प्रयत्न करा.',
        'ta-IN': 'சேவை தற்காலிகமாக கிடைக்கவில்லை. சிறிது நேரத்தில் மீண்டும் முயற்சிக்கவும்.'
    },
    'AUDIO_QUALITY_POOR': {
        'en': 'Audio quality is too poor. Please record in a quieter environment.',
        'hi-IN': 'ऑडियो गुणवत्ता बहुत खराब है। कृपया शांत वातावरण में रिकॉर्ड करें।',
        'mr-IN': 'ऑडिओ गुणवत्ता खूप खराब आहे. कृपया शांत वातावरणात रेकॉर्ड करा.',
        'ta-IN': 'ஆடியோ தரம் மிகவும் மோசமாக உள்ளது. அமைதியான சூழலில் பதிவு செய்யவும்.'
    },
    'EXTRACTION_FAILED': {
        'en': 'Could not extract data from image. Please ensure the image is clear and well-lit.',
        'hi-IN': 'छवि से डेटा निकाला नहीं जा सका। कृपया सुनिश्चित करें कि छवि स्पष्ट और अच्छी तरह से प्रकाशित है।',
        'mr-IN': 'प्रतिमेतून डेटा काढता आला नाही. कृपया प्रतिमा स्पष्ट आणि चांगल्या प्रकाशात असल्याची खात्री करा.',
        'ta-IN': 'படத்திலிருந்து தரவை பிரித்தெடுக்க முடியவில்லை. படம் தெளிவாகவும் நன்கு ஒளிரும் வகையிலும் இருப்பதை உறுதிப்படுத்தவும்.'
    },
    'SATELLITE_DATA_UNAVAILABLE': {
        'en': 'Satellite data not available for this location. Cloud cover may be blocking the view.',
        'hi-IN': 'इस स्थान के लिए उपग्रह डेटा उपलब्ध नहीं है। बादल दृश्य को अवरुद्ध कर सकते हैं।',
        'mr-IN': 'या स्थानासाठी उपग्रह डेटा उपलब्ध नाही. ढग दृश्य अवरोधित करू शकतात.',
        'ta-IN': 'இந்த இடத்திற்கு செயற்கைக்கோள் தரவு கிடைக்கவில்லை. மேகங்கள் காட்சியைத் தடுக்கலாம்.'
    },
    'BATCH_PROCESSING_PARTIAL': {
        'en': 'Some documents could not be processed. Successfully processed: {success_count}, Failed: {failure_count}',
        'hi-IN': 'कुछ दस्तावेज़ संसाधित नहीं किए जा सके। सफलतापूर्वक संसाधित: {success_count}, विफल: {failure_count}',
        'mr-IN': 'काही दस्तऐवज प्रक्रिया करता आले नाहीत. यशस्वीरित्या प्रक्रिया केली: {success_count}, अयशस्वी: {failure_count}',
        'ta-IN': 'சில ஆவணங்களை செயலாக்க முடியவில்லை. வெற்றிகரமாக செயலாக்கப்பட்டது: {success_count}, தோல்வி: {failure_count}'
    },
    'SYSTEM_ERROR': {
        'en': 'An unexpected error occurred. Our team has been notified.',
        'hi-IN': 'एक अप्रत्याशित त्रुटि हुई। हमारी टीम को सूचित कर दिया गया है।',
        'mr-IN': 'एक अनपेक्षित त्रुटी आली. आमच्या टीमला सूचित केले गेले आहे.',
        'ta-IN': 'எதிர்பாராத பிழை ஏற்பட்டது. எங்கள் குழுவிற்கு அறிவிக்கப்பட்டுள்ளது.'
    }
}


def get_localized_message(error_code: str, language: str = 'en', **kwargs) -> str:
    """
    Get localized error message for the given error code and language.
    
    Args:
        error_code: Error code (e.g., 'INVALID_GPS')
        language: Language code (en, hi-IN, mr-IN, ta-IN)
        **kwargs: Format parameters for message templates
        
    Returns:
        Localized error message
    """
    messages = ERROR_MESSAGES.get(error_code, ERROR_MESSAGES['SYSTEM_ERROR'])
    message = messages.get(language, messages.get('en', 'An error occurred'))
    
    # Format message with kwargs if provided
    try:
        return message.format(**kwargs)
    except KeyError:
        return message


class CircuitBreaker:
    """
    Circuit breaker pattern for external services.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, reject requests immediately
    - HALF_OPEN: Testing if service recovered, allow limited requests
    """
    
    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        success_threshold: int = 2
    ):
        """
        Initialize circuit breaker.
        
        Args:
            service_name: Name of the external service
            failure_threshold: Number of failures before opening circuit
            timeout_seconds: Seconds to keep circuit open
            success_threshold: Successes needed in HALF_OPEN to close circuit
        """
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.success_threshold = success_threshold
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'
        
        logger.info(f"Circuit breaker initialized for {service_name}")
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is OPEN or function fails
        """
        if self.state == 'OPEN':
            # Check if timeout has elapsed
            if self.last_failure_time:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.timeout_seconds:
                    logger.info(f"Circuit breaker for {self.service_name} entering HALF_OPEN state")
                    self.state = 'HALF_OPEN'
                    self.success_count = 0
                else:
                    raise Exception(
                        f"Circuit breaker OPEN for {self.service_name}. "
                        f"Retry after {int(self.timeout_seconds - elapsed)} seconds."
                    )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call."""
        if self.state == 'HALF_OPEN':
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                logger.info(f"Circuit breaker for {self.service_name} closing (recovered)")
                self.state = 'CLOSED'
                self.failure_count = 0
        elif self.state == 'CLOSED':
            self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == 'HALF_OPEN':
            logger.warning(f"Circuit breaker for {self.service_name} opening (still failing)")
            self.state = 'OPEN'
        elif self.state == 'CLOSED' and self.failure_count >= self.failure_threshold:
            logger.warning(
                f"Circuit breaker for {self.service_name} opening "
                f"(threshold {self.failure_threshold} reached)"
            )
            self.state = 'OPEN'


# Global circuit breakers for external services
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """
    Get or create circuit breaker for a service.
    
    Args:
        service_name: Name of the external service
        
    Returns:
        CircuitBreaker instance
    """
    if service_name not in _circuit_breakers:
        _circuit_breakers[service_name] = CircuitBreaker(service_name)
    return _circuit_breakers[service_name]


def retry_with_exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    service_name: Optional[str] = None,
    use_circuit_breaker: bool = True
):
    """
    Decorator for retrying functions with exponential backoff.
    
    Implements retry logic with delays: 1s, 2s, 4s (for default parameters).
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        backoff_factor: Multiplier for delay on each retry (default: 2.0)
        service_name: Name of external service (for circuit breaker)
        use_circuit_breaker: Whether to use circuit breaker pattern
        
    Returns:
        Decorated function with retry logic
        
    Example:
        @retry_with_exponential_backoff(max_retries=3, service_name='textract')
        def call_textract(image_url):
            return textract.analyze_document(...)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            circuit_breaker = None
            if use_circuit_breaker and service_name:
                circuit_breaker = get_circuit_breaker(service_name)
            
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    if circuit_breaker:
                        return circuit_breaker.call(func, *args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                
                except Exception as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"All {max_retries + 1} attempts failed for {func.__name__}: {str(e)}"
                        )
            
            # All retries exhausted
            raise last_exception
        
        return wrapper
    return decorator


class CriticalErrorAlerter:
    """
    Sends critical error alerts to administrators via SNS.
    """
    
    def __init__(self, sns_topic_arn: Optional[str] = None):
        """
        Initialize critical error alerter.
        
        Args:
            sns_topic_arn: SNS topic ARN for alerts (from environment if not provided)
        """
        self.sns_topic_arn = sns_topic_arn or os.environ.get('SNS_ALERT_TOPIC_ARN')
        self.sns = boto3.client('sns') if self.sns_topic_arn else None
        
        if not self.sns_topic_arn:
            logger.warning("SNS_ALERT_TOPIC_ARN not configured. Critical alerts will only be logged.")
    
    def send_alert(
        self,
        error: ErrorResponse,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Send critical error alert to administrators.
        
        Args:
            error: ErrorResponse object
            context: Additional context information
        """
        if error.severity != ErrorSeverity.CRITICAL:
            logger.debug(f"Skipping alert for non-critical error: {error.error_code}")
            return
        
        # Build alert message
        alert_message = {
            'error_code': error.error_code,
            'technical_details': error.technical_details,
            'timestamp': error.timestamp.isoformat() if error.timestamp else None,
            'category': error.category.value,
            'severity': error.severity.value,
            'context': context or {}
        }
        
        # Log alert
        logger.critical(f"CRITICAL ERROR ALERT: {error.error_code} - {error.technical_details}")
        
        # Send SNS notification if configured
        if self.sns and self.sns_topic_arn:
            try:
                import json
                self.sns.publish(
                    TopicArn=self.sns_topic_arn,
                    Subject=f"[CRITICAL] Kisan-Setu Error: {error.error_code}",
                    Message=json.dumps(alert_message, indent=2)
                )
                logger.info(f"Critical alert sent to SNS: {error.error_code}")
            except Exception as e:
                logger.error(f"Failed to send SNS alert: {str(e)}")


# Global alerter instance
_alerter: Optional[CriticalErrorAlerter] = None


def get_alerter() -> CriticalErrorAlerter:
    """Get or create global alerter instance."""
    global _alerter
    if _alerter is None:
        _alerter = CriticalErrorAlerter()
    return _alerter


def process_batch_with_resilience(
    items: List[Any],
    process_func: Callable[[Any], Any],
    language: str = 'en'
) -> Dict[str, Any]:
    """
    Process batch of items with resilience (continue on individual failures).
    
    Args:
        items: List of items to process
        process_func: Function to process each item
        language: Language for error messages
        
    Returns:
        Dictionary with:
            - success_count: Number of successful items
            - failure_count: Number of failed items
            - results: List of successful results
            - errors: List of error details for failed items
    """
    results = []
    errors = []
    
    for i, item in enumerate(items):
        try:
            result = process_func(item)
            results.append(result)
        except Exception as e:
            logger.warning(f"Failed to process item {i}: {str(e)}")
            errors.append({
                'item_index': i,
                'item': str(item),
                'error': str(e)
            })
    
    success_count = len(results)
    failure_count = len(errors)
    
    logger.info(f"Batch processing complete: {success_count} succeeded, {failure_count} failed")
    
    return {
        'success_count': success_count,
        'failure_count': failure_count,
        'results': results,
        'errors': errors,
        'message': get_localized_message(
            'BATCH_PROCESSING_PARTIAL',
            language,
            success_count=success_count,
            failure_count=failure_count
        ) if failure_count > 0 else None
    }


def create_error_response(
    error_code: str,
    technical_details: str,
    language: str = 'en',
    category: ErrorCategory = ErrorCategory.SYSTEM_ERROR,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    retry_after: Optional[int] = None,
    **message_kwargs
) -> ErrorResponse:
    """
    Create a structured error response with localized message.
    
    Args:
        error_code: Machine-readable error code
        technical_details: Technical error details
        language: Language for user message
        category: Error category
        severity: Error severity
        retry_after: Seconds to wait before retry
        **message_kwargs: Additional parameters for message formatting
        
    Returns:
        ErrorResponse object
    """
    user_message = get_localized_message(error_code, language, **message_kwargs)
    
    # Determine suggested action based on category
    suggested_actions = {
        ErrorCategory.USER_INPUT: get_localized_message('INVALID_GPS', language).split('.')[1] if '.' in get_localized_message('INVALID_GPS', language) else 'Please check your input and try again.',
        ErrorCategory.EXTERNAL_SERVICE: 'Please try again in a few moments.',
        ErrorCategory.DATA_ERROR: 'Please verify your data and try again.',
        ErrorCategory.SYSTEM_ERROR: 'Our team has been notified and will investigate.'
    }
    
    suggested_action = suggested_actions.get(category, 'Please try again or contact support.')
    
    error_response = ErrorResponse(
        error_code=error_code,
        user_message=user_message,
        technical_details=technical_details,
        suggested_action=suggested_action,
        retry_after=retry_after,
        category=category,
        severity=severity
    )
    
    # Send alert if critical
    if severity == ErrorSeverity.CRITICAL:
        alerter = get_alerter()
        alerter.send_alert(error_response)
    
    return error_response
