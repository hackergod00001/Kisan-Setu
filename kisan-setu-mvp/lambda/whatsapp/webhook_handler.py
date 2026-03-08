"""
WhatsApp Webhook Handler Lambda Function

This Lambda function receives WhatsApp messages via webhook from Meta WhatsApp Business API,
detects message types, and routes them to appropriate components.

Implements Requirements 6.1, 6.2, 6.3, 6.4
"""

import json
import os
import boto3
from typing import Dict, Any

from meta_whatsapp_interface import MetaWhatsAppInterface, MessageType
WhatsAppInterface = MetaWhatsAppInterface  # Alias for test compatibility

# AWS clients
lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')

# Environment variables
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'KisanSetuData')
DOCUMENT_PROCESSOR_FUNCTION = os.environ.get('DOCUMENT_PROCESSOR_FUNCTION', 'DocumentProcessor')
VOICE_AGENT_FUNCTION = os.environ.get('VOICE_AGENT_FUNCTION', 'VoiceAgent')
BEDROCK_ORCHESTRATOR_FUNCTION = os.environ.get('BEDROCK_ORCHESTRATOR_FUNCTION', 'BedrockOrchestrator')
WEBHOOK_VERIFY_TOKEN = os.environ.get('WEBHOOK_VERIFY_TOKEN', 'kisan-setu-verify-token')

table = dynamodb.Table(DYNAMODB_TABLE)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main webhook handler for WhatsApp messages from Meta WhatsApp Business API
    
    Routes messages based on type:
    - Image messages → DocumentProcessor
    - Voice/Audio messages → VoiceAgent
    - Text messages → BedrockOrchestrator
    
    Implements: Requirements 6.1, 6.2, 6.3, 6.4
    """
    try:
        print(f"Received webhook event: {json.dumps(event)}")
        
        # Handle webhook verification (GET request)
        if event.get('httpMethod') == 'GET':
            return verify_webhook(event)
        
        # Parse incoming message (Meta JSON format)
        body_str = event.get('body', '')
        content_type = event.get('headers', {}).get('Content-Type', '').lower()
        
        # Meta WhatsApp sends JSON
        if 'application/json' in content_type or body_str.startswith('{'):
            body = json.loads(body_str)
        else:
            return response(400, {'error': 'Unsupported content type'})
        
        # Initialize Meta WhatsApp interface
        whatsapp = MetaWhatsAppInterface()
        
        # Parse message using MetaWhatsAppInterface
        message = whatsapp.receive_message(body)
        
        if not message:
            return response(400, {'error': 'Failed to parse message'})
        
        # Store message in DynamoDB
        store_message(message)
        
        # Route message based on type
        if message.message_type == MessageType.IMAGE:
            return route_to_document_processor(message)
        
        elif message.message_type in [MessageType.VOICE, MessageType.AUDIO]:
            return route_to_voice_agent(message)
        
        elif message.message_type == MessageType.TEXT:
            return route_to_bedrock_orchestrator(message)
        
        else:
            # Unsupported message type
            whatsapp.send_text_response(
                message.sender_id,
                "Sorry, this message type is not supported yet. Please send text, voice, or image messages.",
                message.language or 'en'
            )
            return response(200, {'status': 'unsupported_type'})
    
    except Exception as e:
        print(f"Error in webhook handler: {e}")
        import traceback
        traceback.print_exc()
        return response(500, {'error': str(e)})


def verify_webhook(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify WhatsApp webhook during initial setup
    
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
        
        if mode == 'subscribe' and token == WEBHOOK_VERIFY_TOKEN:
            print("Webhook verified successfully")
            return response(200, int(challenge), is_plain_text=True)
        else:
            print(f"Webhook verification failed: mode={mode}, token={token}")
            return response(403, {'error': 'Verification failed'})
    
    except Exception as e:
        print(f"Error verifying webhook: {e}")
        return response(500, {'error': str(e)})


def store_message(message) -> bool:
    """
    Store message in DynamoDB for conversation history
    
    Args:
        message: WhatsAppMessage object
        
    Returns:
        True if stored successfully
    """
    try:
        timestamp_str = message.timestamp.isoformat()
        
        item = {
            'PK': f'CONVERSATION#{message.sender_id}',
            'SK': f'MSG#{timestamp_str}',
            'entity_type': 'Message',
            'message_id': message.message_id,
            'sender_id': message.sender_id,
            'message_type': message.message_type.value,
            'content': message.content,
            'timestamp': timestamp_str,
            'language': message.language or 'en',
            'status': 'received',
            'created_at': timestamp_str
        }
        
        if message.metadata:
            item['metadata'] = message.metadata
        
        table.put_item(Item=item)
        print(f"Message stored: {message.message_id}")
        return True
    
    except Exception as e:
        print(f"Error storing message: {e}")
        return False


def route_to_document_processor(message) -> Dict[str, Any]:
    """
    Route image message to DocumentProcessor Lambda
    
    Args:
        message: WhatsAppMessage with image
        
    Returns:
        API Gateway response
        
    Implements: Requirement 6.1 - Route to appropriate component
    """
    try:
        print(f"Routing image message to DocumentProcessor: {message.message_id}")
        
        # Prepare payload for DocumentProcessor
        payload = {
            'sender_id': message.sender_id,
            'message_id': message.message_id,
            'image_url': message.content,
            'media_type': message.metadata.get('media_type', 'image/jpeg'),
            'language': message.language or 'en'
        }
        
        # Invoke DocumentProcessor asynchronously
        lambda_client.invoke(
            FunctionName=DOCUMENT_PROCESSOR_FUNCTION,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )
        
        # Send acknowledgment to user
        whatsapp = MetaWhatsAppInterface()
        whatsapp.send_text_response(
            message.sender_id,
            "📸 Image received! Processing your ledger... I'll send you the results shortly.",
            message.language or 'en'
        )
        
        return response(200, {
            'status': 'processing',
            'message_type': 'image',
            'routed_to': 'DocumentProcessor'
        })
    
    except Exception as e:
        print(f"Error routing to DocumentProcessor: {e}")
        return response(500, {'error': str(e)})


def route_to_voice_agent(message) -> Dict[str, Any]:
    """
    Route voice/audio message to VoiceAgent Lambda
    
    Args:
        message: WhatsAppMessage with audio
        
    Returns:
        API Gateway response
        
    Implements: Requirement 6.1 - Route to appropriate component
    """
    try:
        print(f"Routing voice message to VoiceAgent: {message.message_id}")
        
        # Prepare payload for VoiceAgent
        payload = {
            'sender_id': message.sender_id,
            'message_id': message.message_id,
            'audio_url': message.content,
            'media_type': message.metadata.get('media_type', 'audio/ogg'),
            'language': message.language or 'hi-IN'  # Default to Hindi
        }
        
        # Invoke VoiceAgent asynchronously
        lambda_client.invoke(
            FunctionName=VOICE_AGENT_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        
        # Send acknowledgment to user
        whatsapp = MetaWhatsAppInterface()
        whatsapp.send_text_response(
            message.sender_id,
            "🎤 Voice message received! Processing your request...",
            message.language or 'en'
        )
        
        return response(200, {
            'status': 'processing',
            'message_type': 'voice',
            'routed_to': 'VoiceAgent'
        })
    
    except Exception as e:
        print(f"Error routing to VoiceAgent: {e}")
        return response(500, {'error': str(e)})


def route_to_bedrock_orchestrator(message) -> Dict[str, Any]:
    """
    Route text message to BedrockOrchestrator Lambda
    
    Args:
        message: WhatsAppMessage with text
        
    Returns:
        API Gateway response
        
    Implements: Requirement 6.1 - Route to appropriate component
    """
    try:
        print(f"Routing text message to BedrockOrchestrator: {message.message_id}")
        
        # Prepare payload for BedrockOrchestrator
        payload = {
            'sender_id': message.sender_id,
            'message_id': message.message_id,
            'text': message.content,
            'language': message.language or 'en'
        }
        
        # Invoke BedrockOrchestrator asynchronously
        lambda_client.invoke(
            FunctionName=BEDROCK_ORCHESTRATOR_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        
        # For text messages, we don't send immediate acknowledgment
        # The orchestrator will respond directly
        
        return response(200, {
            'status': 'processing',
            'message_type': 'text',
            'routed_to': 'BedrockOrchestrator'
        })
    
    except Exception as e:
        print(f"Error routing to BedrockOrchestrator: {e}")
        return response(500, {'error': str(e)})


def response(status_code: int, body: Any, is_plain_text: bool = False) -> Dict[str, Any]:
    """
    Format API Gateway response
    
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
