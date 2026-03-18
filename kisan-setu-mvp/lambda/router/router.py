"""
Main Message Router Lambda Handler

This is the main entry point for all WhatsApp messages. It orchestrates all components:
- WhatsApp Interface for message parsing and response sending
- Document Processor for image/ledger processing
- Voice Agent for voice message transcription
- Bedrock Orchestrator for text message processing

Implements Requirements 6.1, 6.2, 7.1 with comprehensive logging and error handling.

Architecture:
    WhatsApp → Router → Component → Response → WhatsApp
    
Components:
    - DocumentProcessor: Handles image messages (ledgers)
    - VoiceAgent: Handles voice/audio messages
    - BedrockOrchestrator: Handles text messages and complex queries

AUDIT TRAIL GAP: This handler performs direct boto3 DynamoDB writes (message
metadata, dedup markers, rate-limit counters, status updates) that bypass the
centralised DynamoDBAccess class and its audit trails. To close this gap,
either migrate write paths to DynamoDBAccess or enable DynamoDB Streams on the
KisanSetuData table to capture all mutations for audit/compliance purposes.
"""

import json
import boto3
import os
import re
import sys
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from urllib.parse import parse_qs

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import common modules
try:
    from common.error_handling import (
        retry_with_exponential_backoff,
        create_error_response,
        ErrorCategory,
        ErrorSeverity
    )
    from common.cost_optimization import concurrent_processor
except ImportError:
    # Fallback if common modules not available
    pass

# Configure comprehensive logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3 = boto3.client('s3')
lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

# Environment variables - All service endpoints
S3_BUCKET_RAW = os.environ.get('S3_BUCKET_RAW', '')
S3_BUCKET_PROCESSED = os.environ.get('S3_BUCKET_PROCESSED', '')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'KisanSetuData')
REGION = os.environ.get('REGION', 'ap-south-1')

# Lambda function names for routing
PROCESSOR_FUNCTION_NAME = os.environ.get('PROCESSOR_FUNCTION_NAME', 'DocumentProcessor')
VOICE_AGENT_FUNCTION = os.environ.get('VOICE_AGENT_FUNCTION', 'VoiceHandler')
BEDROCK_ORCHESTRATOR_FUNCTION = os.environ.get('BEDROCK_ORCHESTRATOR_FUNCTION', 'BedrockOrchestrator')

# WhatsApp configuration
WEBHOOK_VERIFY_TOKEN = os.environ.get('WEBHOOK_VERIFY_TOKEN', 'kisan-setu-verify-token')
WHATSAPP_SECRET_NAME = os.environ.get('WHATSAPP_SECRET_NAME', 'kisan-setu/whatsapp/credentials')

# SNS for critical alerts
SNS_ALERT_TOPIC_ARN = os.environ.get('SNS_ALERT_TOPIC_ARN', '')

# DynamoDB table
table = dynamodb.Table(DYNAMODB_TABLE)

# Component initialization tracking
COMPONENTS_INITIALIZED = {
    'dynamodb': False,
    's3': False,
    'lambda': False,
    'sns': False
}

# Input sanitization constants
MAX_MESSAGE_LENGTH = 2000

# Rate limiting constants (Req 2.9)
RATE_LIMIT_MAX_MESSAGES = 10  # max messages per window
RATE_LIMIT_WINDOW_SECONDS = 60  # 1-minute window

# Prompt injection patterns (case-insensitive)
PROMPT_INJECTION_PATTERNS = [
    r'ignore\s+(all\s+)?previous\s+instructions',
    r'ignore\s+(all\s+)?prior\s+instructions',
    r'disregard\s+(all\s+)?previous\s+instructions',
    r'disregard\s+(all\s+)?prior\s+instructions',
    r'forget\s+your\s+instructions',
    r'forget\s+(all\s+)?previous\s+instructions',
    r'you\s+are\s+now\b',
    r'act\s+as\s+if\s+you\s+are',
    r'pretend\s+you\s+are',
    r'system\s*prompt',
    r'override\s+(your\s+)?(system|instructions)',
    r'new\s+instructions?\s*:',
    r'reveal\s+your\s+(system\s+)?prompt',
    r'show\s+your\s+(system\s+)?prompt',
    r'what\s+are\s+your\s+instructions',
]

# Compile patterns for efficiency
_INJECTION_REGEX = re.compile(
    '|'.join(PROMPT_INJECTION_PATTERNS),
    re.IGNORECASE
)


def validate_message_length(text: str) -> Tuple[bool, Optional[str]]:
    """
    Check that message text does not exceed the maximum allowed length.

    Args:
        text: The raw message text.

    Returns:
        Tuple of (is_valid, rejection_reason). rejection_reason is None when valid.
    """
    if len(text) > MAX_MESSAGE_LENGTH:
        return False, (
            f"Your message is too long ({len(text)} characters). "
            f"Please keep messages under {MAX_MESSAGE_LENGTH} characters."
        )
    return True, None


def detect_prompt_injection(text: str) -> Tuple[bool, Optional[str]]:
    """
    Detect known prompt injection patterns in the message text.

    Args:
        text: The raw message text.

    Returns:
        Tuple of (is_safe, rejection_reason). rejection_reason is None when safe.
    """
    if _INJECTION_REGEX.search(text):
        return False, "Sorry, your message could not be processed. Please rephrase and try again."
    return True, None


def sanitize_text(text: str) -> str:
    """
    Sanitize special characters in message text before passing to the orchestrator.

    Removes or escapes characters that could interfere with LLM prompt
    processing while preserving normal multilingual text (Devanagari, Tamil, etc.).

    Args:
        text: The raw message text.

    Returns:
        Sanitized text safe for LLM prompt inclusion.
    """
    # Remove null bytes
    text = text.replace('\0', '')

    # Remove other ASCII control characters (keep newline, tab, carriage return)
    text = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Collapse excessive whitespace (more than 3 consecutive newlines → 2)
    text = re.sub(r'\n{4,}', '\n\n\n', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def check_rate_limit(sender: str) -> Tuple[bool, Optional[str]]:
    """
    Check per-sender rate limit using DynamoDB atomic counters with TTL.

    Uses a single DynamoDB item per sender with an atomic counter that
    resets each minute via TTL. The counter is incremented atomically
    using ``ADD`` so concurrent requests are safe.

    Args:
        sender: Phone number (e.g. "+919876543210").

    Returns:
        Tuple of (is_allowed, rejection_message).
        ``rejection_message`` is ``None`` when the request is allowed.

    Implements: Requirement 2.9 — per-sender rate limiting.
    """
    import time
    import math

    now = time.time()
    # TTL: end of the current 60-second window
    window_start = int(now // RATE_LIMIT_WINDOW_SECONDS) * RATE_LIMIT_WINDOW_SECONDS
    window_ttl = int(window_start + RATE_LIMIT_WINDOW_SECONDS + RATE_LIMIT_WINDOW_SECONDS)
    # Use a partition key that includes the window so counters auto-reset
    window_key = str(int(window_start))

    try:
        # NOTE: Direct boto3 DynamoDB call — bypasses DynamoDBAccess audit trails.
        # Consider migrating to DynamoDBAccess for audit compliance.
        result = table.update_item(
            Key={
                'PK': f'RATELIMIT#{sender}',
                'SK': f'WINDOW#{window_key}',
            },
            UpdateExpression='ADD msg_count :inc SET #ttl = if_not_exists(#ttl, :ttl)',
            ExpressionAttributeNames={
                '#ttl': 'ttl',
            },
            ExpressionAttributeValues={
                ':inc': 1,
                ':ttl': window_ttl,
            },
            ReturnValues='ALL_NEW',
        )

        count = int(result['Attributes'].get('msg_count', 1))

        if count > RATE_LIMIT_MAX_MESSAGES:
            logger.warning(
                f"Rate limit exceeded for {sender}: {count}/{RATE_LIMIT_MAX_MESSAGES} in window {window_key}"
            )
            return False, (
                "You're sending messages too quickly. "
                "Please wait a moment before sending another message."
            )

        return True, None

    except Exception as e:
        # Fail open — if rate-limit check fails, allow the message through
        logger.error(f"Rate limit check failed for {sender}: {e}")
        return True, None


def initialize_components():
    """
    Initialize and verify all AWS service components.
    
    This ensures all required services are accessible before processing messages.
    Logs initialization status for debugging.
    """
    try:
        # Verify DynamoDB table access
        table.table_status
        COMPONENTS_INITIALIZED['dynamodb'] = True
        logger.info(f"✓ DynamoDB table initialized: {DYNAMODB_TABLE}")
        
        # Verify S3 bucket access
        if S3_BUCKET_RAW:
            bucket_name = S3_BUCKET_RAW.split('/')[-1]
            s3.head_bucket(Bucket=bucket_name)
            COMPONENTS_INITIALIZED['s3'] = True
            logger.info(f"✓ S3 buckets initialized: {S3_BUCKET_RAW}")
        
        # Lambda client is always available
        COMPONENTS_INITIALIZED['lambda'] = True
        logger.info(f"✓ Lambda client initialized")
        
        # SNS for alerts
        if SNS_ALERT_TOPIC_ARN:
            COMPONENTS_INITIALIZED['sns'] = True
            logger.info(f"✓ SNS alert topic initialized")
        
        logger.info("All components initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Component initialization failed: {str(e)}")
        return False


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler - Routes WhatsApp messages to appropriate processors.
    
    This is the central orchestration point for all incoming messages.
    
    Flow:
        1. Initialize components (first invocation only)
        2. Parse incoming message (Meta WhatsApp Business API format)
        3. Store message metadata in DynamoDB
        4. Route to appropriate component based on message type:
           - Images → DocumentProcessor (ledger extraction)
           - Voice → VoiceAgent (transcription + processing)
           - Text → BedrockOrchestrator (AI-powered responses)
        5. Log all actions to CloudWatch
        6. Handle errors gracefully with user-friendly messages
    
    Implements: Requirements 6.1, 6.2, 7.1
    
    Args:
        event: API Gateway event with WhatsApp webhook payload
        context: Lambda context object
        
    Returns:
        API Gateway response with status and routing information
    """
    
    # Initialize components on first invocation
    if not all(COMPONENTS_INITIALIZED.values()):
        initialize_components()
    
    # Log request details
    request_id = context.aws_request_id if context else 'local'
    logger.info(f"[{request_id}] Received webhook event")
    logger.debug(f"[{request_id}] Event: {json.dumps(event)}")
    
    try:
        # Handle webhook verification (GET request)
        if event.get('httpMethod') == 'GET':
            logger.info(f"[{request_id}] Webhook verification request")
            return verify_webhook(event)
        
        # Parse WhatsApp webhook payload
        body_str = event.get('body', '')
        headers = event.get('headers', {}) or {}
        # API Gateway may pass headers in different cases
        content_type = headers.get('Content-Type', '') or headers.get('content-type', '')
        
        logger.info(f"[{request_id}] Content-Type: {content_type}")
        
        # Meta WhatsApp Business API sends JSON
        # Also fallback to checking if body looks like JSON (API Gateway sometimes strips Content-Type)
        if 'application/json' in content_type or (body_str and body_str.strip().startswith('{')):
            try:
                body = json.loads(body_str) if body_str else {}
            except json.JSONDecodeError as e:
                logger.error(f"[{request_id}] JSON decode error: {str(e)}")
                return response(400, {'error': 'Invalid JSON payload'})
            
            logger.info(f"[{request_id}] Parsed Meta WhatsApp message")
            return handle_meta_message(body, request_id)
        
        else:
            logger.warning(f"[{request_id}] Unsupported content type: {content_type}")
            return response(400, {'error': 'Unsupported content type'})
    
    except Exception as e:
        logger.error(f"[{request_id}] Error in router: {str(e)}", exc_info=True)
        
        # Send critical alert for unexpected errors
        if SNS_ALERT_TOPIC_ARN:
            try:
                sns.publish(
                    TopicArn=SNS_ALERT_TOPIC_ARN,
                    Subject='Kisan-Setu Router Error',
                    Message=f"Request ID: {request_id}\nError: {str(e)}\nEvent: {json.dumps(event)}"
                )
            except:
                pass  # Don't fail if alert fails
        
        return response(500, {'error': 'Internal server error', 'request_id': request_id})


def handle_meta_message(body: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    """
    Handle Meta WhatsApp Business API message format.
    
    Meta sends JSON with nested structure containing message details.
    
    Args:
        body: Parsed JSON from Meta WhatsApp API
        request_id: Request ID for logging
        
    Returns:
        API Gateway response
    """
    
    try:
        # Extract message details from Meta format
        if 'entry' not in body or not body['entry']:
            logger.warning(f"[{request_id}] Invalid Meta webhook payload - no entry")
            return response(400, {'error': 'Invalid webhook payload'})
        
        entry = body['entry'][0]
        changes = entry.get('changes', [])
        
        if not changes:
            logger.warning(f"[{request_id}] No changes in Meta webhook")
            return response(400, {'error': 'No changes in webhook'})
        
        value = changes[0].get('value', {})
        messages = value.get('messages', [])
        
        if not messages:
            logger.info(f"[{request_id}] No messages in webhook (status update)")
            return response(200, {'status': 'no_messages'})
        
        message = messages[0]
        message_type = message.get('type')
        sender = message.get('from')
        message_id = message.get('id')
        
        logger.info(f"[{request_id}] Meta message - Type: {message_type}, Sender: {sender}")

        # Deduplication: skip if we've already processed this message
        try:
            # NOTE: Direct boto3 DynamoDB call — bypasses DynamoDBAccess audit trails.
            # Consider migrating to DynamoDBAccess for audit compliance.
            dedup_result = table.get_item(
                Key={'PK': f'MSGID#{message_id}', 'SK': 'DEDUP'},
                ProjectionExpression='PK'
            )
            if 'Item' in dedup_result:
                logger.info(f"[{request_id}] Duplicate message {message_id}, skipping")
                return response(200, {'status': 'duplicate'})
            # Mark as processing (24-hour TTL)
            # NOTE: Direct boto3 DynamoDB call — bypasses DynamoDBAccess audit trails.
            # Consider migrating to DynamoDBAccess for audit compliance.
            from datetime import timedelta
            table.put_item(Item={
                'PK': f'MSGID#{message_id}',
                'SK': 'DEDUP',
                'timestamp': datetime.utcnow().isoformat(),
                'ttl': int((datetime.utcnow() + timedelta(hours=24)).timestamp())
            })
        except Exception as dedup_err:
            logger.debug(f"Dedup check failed (non-blocking): {dedup_err}")

        # Per-sender rate limiting (Req 2.9)
        is_allowed, rate_limit_msg = check_rate_limit(sender)
        if not is_allowed:
            logger.warning(f"[{request_id}] Rate limit exceeded for {sender}")
            return response(200, {
                'status': 'rate_limited',
                'message': rate_limit_msg,
                'request_id': request_id
            })

        # Store message metadata
        timestamp = datetime.utcnow().isoformat()
        store_message_metadata(sender, message_id, timestamp, 'meta')
        
        # Route based on message type
        if message_type == 'image':
            image_data = message.get('image', {})
            image_id = image_data.get('id')
            mime_type = image_data.get('mime_type', 'image/jpeg')
            
            # Detect language from user profile
            detected_language = detect_user_language(sender)
            
            logger.info(f"[{request_id}] Routing image to DocumentProcessor: {image_id}, language: {detected_language}")
            return route_to_document_processor(
                sender=sender,
                message_id=message_id,
                media_url=image_id,  # Will be downloaded by processor
                media_type=mime_type,
                request_id=request_id,
                language=detected_language
            )
        
        elif message_type in ['audio', 'voice']:
            audio_data = message.get('audio') or message.get('voice', {})
            audio_id = audio_data.get('id')
            mime_type = audio_data.get('mime_type', 'audio/ogg')
            
            logger.info(f"[{request_id}] Routing voice to VoiceAgent: {audio_id}")
            return route_to_voice_agent(
                sender=sender,
                message_id=message_id,
                audio_url=audio_id,
                media_type=mime_type,
                request_id=request_id
            )
        
        elif message_type == 'text':
            text_data = message.get('text', {})
            text_body = text_data.get('body', '')
            
            logger.info(f"[{request_id}] Routing text to BedrockOrchestrator")
            return route_to_bedrock_orchestrator(
                sender=sender,
                message_id=message_id,
                text=text_body,
                request_id=request_id
            )
        
        else:
            logger.warning(f"[{request_id}] Unsupported message type: {message_type}")
            return response(200, {
                'status': 'unsupported_type',
                'message_type': message_type
            })
    
    except Exception as e:
        logger.error(f"[{request_id}] Error handling Meta message: {str(e)}", exc_info=True)
        return response(500, {'error': str(e), 'request_id': request_id})


def store_message_metadata(sender: str, message_id: str, timestamp: str, source: str = 'meta'):
    """
    Store message metadata in DynamoDB for conversation history.
    
    Args:
        sender: Phone number or user ID
        message_id: Unique message identifier
        timestamp: ISO format timestamp
        source: 'meta' (default)
    """
    try:
        conversation_key = f"CONVERSATION#{sender}"
        message_key = f"MSG#{timestamp}"
        
        # NOTE: Direct boto3 DynamoDB call — bypasses DynamoDBAccess audit trails.
        # Consider migrating to DynamoDBAccess for audit compliance.
        table.put_item(Item={
            'PK': conversation_key,
            'SK': message_key,
            'entity_type': 'Message',
            'message_id': message_id,
            'sender': sender,
            'source': source,
            'status': 'received',
            'timestamp': timestamp,
            'created_at': timestamp
        })
        
        logger.debug(f"Message metadata stored: {conversation_key}/{message_key}")
        
    except Exception as e:
        logger.error(f"Error storing message metadata: {str(e)}")
        # Don't fail the request if metadata storage fails


def route_to_document_processor(
    sender: str,
    message_id: str,
    media_url: str,
    media_type: str,
    request_id: str,
    language: str = 'hi-IN'
) -> Dict[str, Any]:
    """
    Route image message to DocumentProcessor Lambda.
    
    Implements: Requirement 6.1 - Route images to DocumentProcessor
    
    Args:
        sender: Phone number
        message_id: Message ID
        media_url: URL or ID of the image
        media_type: MIME type
        request_id: Request ID for logging
        language: Detected language code
        
    Returns:
        API Gateway response
    """
    try:
        logger.info(f"[{request_id}] Invoking DocumentProcessor for {sender}")
        
        # Prepare payload
        payload = {
            'sender': sender,
            'message_id': message_id,
            'image_id': media_url,  # WhatsApp image ID
            'media_type': media_type,
            'language': language
        }
        
        # Invoke DocumentProcessor asynchronously
        response_obj = lambda_client.invoke(
            FunctionName=PROCESSOR_FUNCTION_NAME,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )
        
        logger.info(f"[{request_id}] DocumentProcessor invoked successfully - StatusCode: {response_obj['StatusCode']}")
        
        # Update message status
        update_message_status(sender, message_id, 'processing_image')
        
        return response(200, {
            'status': 'processing',
            'message_type': 'image',
            'routed_to': 'DocumentProcessor',
            'request_id': request_id
        })
    
    except Exception as e:
        logger.error(f"[{request_id}] Error routing to DocumentProcessor: {str(e)}", exc_info=True)
        update_message_status(sender, message_id, 'error')
        return response(500, {'error': str(e), 'request_id': request_id})


def route_to_voice_agent(
    sender: str,
    message_id: str,
    audio_url: str,
    media_type: str,
    request_id: str
) -> Dict[str, Any]:
    """
    Route voice/audio message to VoiceAgent Lambda.
    
    Implements: Requirement 6.1 - Route voice to VoiceAgent
    
    Args:
        sender: Phone number
        message_id: Message ID
        audio_url: URL or ID of the audio
        media_type: MIME type
        request_id: Request ID for logging
        
    Returns:
        API Gateway response
    """
    try:
        logger.info(f"[{request_id}] Invoking VoiceAgent for {sender}")
        
        # Prepare payload
        # Detect language from user profile
        detected_lang = detect_user_language(sender)

        payload = {
            'action': 'transcribe',
            'sender_id': sender,
            'message_id': message_id,
            'audio_url': audio_url,
            'media_type': media_type,
            'language': detected_lang,
            'orchestrator_function': BEDROCK_ORCHESTRATOR_FUNCTION
        }
        
        # Invoke VoiceAgent asynchronously
        response_obj = lambda_client.invoke(
            FunctionName=VOICE_AGENT_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        
        logger.info(f"[{request_id}] VoiceAgent invoked successfully - StatusCode: {response_obj['StatusCode']}")
        
        # Update message status
        update_message_status(sender, message_id, 'processing_voice')
        
        return response(200, {
            'status': 'processing',
            'message_type': 'voice',
            'routed_to': 'VoiceAgent',
            'request_id': request_id
        })
    
    except Exception as e:
        logger.error(f"[{request_id}] Error routing to VoiceAgent: {str(e)}", exc_info=True)
        update_message_status(sender, message_id, 'error')
        return response(500, {'error': str(e), 'request_id': request_id})


def route_to_bedrock_orchestrator(
    sender: str,
    message_id: str,
    text: str,
    request_id: str
) -> Dict[str, Any]:
    """
    Route text message to BedrockOrchestrator Lambda.
    
    Applies input sanitization before forwarding:
    1. Max message length check (2000 chars)
    2. Prompt injection detection
    3. Special character sanitization
    
    Implements: Requirement 6.1, 7.1 - Route text to BedrockOrchestrator
    Implements: Requirement 2.8 - Input sanitization
    
    Args:
        sender: Phone number
        message_id: Message ID
        text: Message text
        request_id: Request ID for logging
        
    Returns:
        API Gateway response
    """
    try:
        # --- Input sanitization (Req 2.8) ---

        # 2.4.1: Max message length check
        is_valid, rejection_msg = validate_message_length(text)
        if not is_valid:
            logger.warning(f"[{request_id}] Message rejected: too long ({len(text)} chars) from {sender}")
            return response(200, {
                'status': 'rejected',
                'reason': 'message_too_long',
                'message': rejection_msg,
                'request_id': request_id
            })

        # 2.4.2: Prompt injection detection
        is_safe, rejection_msg = detect_prompt_injection(text)
        if not is_safe:
            logger.warning(f"[{request_id}] Message rejected: prompt injection detected from {sender}")
            return response(200, {
                'status': 'rejected',
                'reason': 'prompt_injection_detected',
                'message': rejection_msg,
                'request_id': request_id
            })

        # 2.4.3: Special character sanitization
        text = sanitize_text(text)

        logger.info(f"[{request_id}] Invoking BedrockOrchestrator for {sender}")
        
        # Prepare payload
        # Detect language: prefer user profile, then detect from text
        detected_lang = detect_user_language(sender)
        if detected_lang == 'en':
            # Profile not found or default, try detecting from text
            text_lang = detect_language_from_text(text)
            if text_lang != 'en':
                detected_lang = text_lang

        payload = {
            'sender_id': sender,
            'message_id': message_id,
            'message_text': text,
            'language': detected_lang
        }
        
        # Invoke BedrockOrchestrator asynchronously
        response_obj = lambda_client.invoke(
            FunctionName=BEDROCK_ORCHESTRATOR_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        
        logger.info(f"[{request_id}] BedrockOrchestrator invoked successfully - StatusCode: {response_obj['StatusCode']}")
        
        # Update message status
        update_message_status(sender, message_id, 'processing_text')
        
        return response(200, {
            'status': 'processing',
            'message_type': 'text',
            'routed_to': 'BedrockOrchestrator',
            'request_id': request_id
        })
    
    except Exception as e:
        logger.error(f"[{request_id}] Error routing to BedrockOrchestrator: {str(e)}", exc_info=True)
        update_message_status(sender, message_id, 'error')
        return response(500, {'error': str(e), 'request_id': request_id})


def update_message_status(sender: str, message_id: str, status: str):
    """
    Update message processing status in DynamoDB.
    
    Args:
        sender: Phone number
        message_id: Message ID
        status: New status
    """
    try:
        # NOTE: Direct boto3 DynamoDB calls — bypass DynamoDBAccess audit trails.
        # Consider migrating to DynamoDBAccess for audit compliance.
        # Query for the message
        response_obj = table.query(
            KeyConditionExpression='PK = :pk',
            ExpressionAttributeValues={
                ':pk': f"CONVERSATION#{sender}"
            },
            ScanIndexForward=False,
            Limit=1
        )
        
        if response_obj['Items']:
            item = response_obj['Items'][0]
            table.update_item(
                Key={
                    'PK': item['PK'],
                    'SK': item['SK']
                },
                UpdateExpression='SET #status = :status, updated_at = :updated',
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':status': status,
                    ':updated': datetime.utcnow().isoformat()
                }
            )
            logger.debug(f"Message status updated: {message_id} -> {status}")
    
    except Exception as e:
        logger.error(f"Error updating message status: {str(e)}")
        # Don't fail the request if status update fails


def detect_user_language(sender: str) -> str:
    """
    Detect user's preferred language from their DynamoDB profile.
    Falls back to 'hi-IN' (Hindi) as default for Indian farmers.

    Args:
        sender: Phone number

    Returns:
        Language code (hi-IN, mr-IN, ta-IN, en)
    """
    try:
        # NOTE: Direct boto3 DynamoDB call — bypasses DynamoDBAccess audit trails.
        # Consider migrating to DynamoDBAccess for audit compliance.
        result = table.get_item(
            Key={
                'PK': f"FARMER#{sender}",
                'SK': 'METADATA'
            },
            ProjectionExpression='preferredLanguage'
        )
        item = result.get('Item', {})
        lang = item.get('preferredLanguage', '')
        if lang:
            # Map short codes to full locale codes
            lang_map = {
                'hi': 'hi-IN', 'mr': 'mr-IN', 'ta': 'ta-IN', 'en': 'en',
                'hi-IN': 'hi-IN', 'mr-IN': 'mr-IN', 'ta-IN': 'ta-IN'
            }
            return lang_map.get(lang, 'hi-IN')
    except Exception as e:
        logger.debug(f"Could not detect language for {sender}: {e}")

    # Default to English
    return 'en'


def detect_language_from_text(text: str) -> str:
    """
    Detect language from message text using Unicode script analysis.

    Args:
        text: Message text

    Returns:
        Language code (hi-IN, ta-IN, mr-IN, en)
    """
    if not text or not text.strip():
        return 'en'

    # Count characters by script
    devanagari_count = sum(1 for c in text if '\u0900' <= c <= '\u097F')
    tamil_count = sum(1 for c in text if '\u0B80' <= c <= '\u0BFF')
    total = len(text.strip())

    if total == 0:
        return 'en'

    if tamil_count / total > 0.3:
        return 'ta-IN'
    if devanagari_count / total > 0.3:
        return 'hi-IN'

    return 'en'


def verify_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify WhatsApp webhook during initial setup.
    
    Meta WhatsApp uses webhook verification with challenge response.
    
    Args:
        event: API Gateway event with query parameters
        
    Returns:
        Response with challenge or error
    """
    try:
        params = event.get('queryStringParameters', {})
        mode = params.get('hub.mode')
        token = params.get('hub.verify_token')
        challenge = params.get('hub.challenge')
        
        logger.info(f"Webhook verification - mode: {mode}, token: {'***' if token else 'None'}")
        
        if mode == 'subscribe' and token == WEBHOOK_VERIFY_TOKEN:
            logger.info("Webhook verified successfully")
            return response(200, challenge, is_plain_text=True)
        else:
            logger.warning(f"Webhook verification failed")
            return response(403, {'error': 'Verification failed'})
    
    except Exception as e:
        logger.error(f"Error verifying webhook: {str(e)}", exc_info=True)
        return response(500, {'error': str(e)})


def response(status_code: int, body: Any, is_plain_text: bool = False) -> Dict[str, Any]:
    """
    Format API Gateway response.
    
    Args:
        status_code: HTTP status code
        body: Response body
        is_plain_text: If True, return plain text; otherwise JSON
        
    Returns:
        API Gateway response dictionary
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'text/plain' if is_plain_text else 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': str(body) if is_plain_text else json.dumps(body)
    }
