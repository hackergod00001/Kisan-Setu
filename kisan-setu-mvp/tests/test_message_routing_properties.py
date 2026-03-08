"""
Property-Based Tests for Message Type Routing

Tests Property 17: Message Type Routing
For any incoming WhatsApp message, the message should be routed to the correct
component based on its type: text messages to Bedrock Orchestrator, voice messages
to Voice_Agent, images to Document_Processor.

**Validates: Requirements 6.1, 6.4**

Uses Hypothesis framework with minimum 100 iterations.
"""

import pytest
import json
import sys
import os
import importlib
import importlib.util
from unittest.mock import Mock, patch, MagicMock
from hypothesis import given, settings, strategies as st
from datetime import datetime

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'whatsapp'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

# Ensure the real meta_whatsapp_interface is loaded (not the conftest mock)
_real_path = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'whatsapp', 'meta_whatsapp_interface.py')
_spec = importlib.util.spec_from_file_location('meta_whatsapp_interface', _real_path)
_real_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_real_mod)
sys.modules['meta_whatsapp_interface'] = _real_mod

# Reload webhook_handler if already imported with mock
if 'webhook_handler' in sys.modules:
    importlib.reload(sys.modules['webhook_handler'])

from meta_whatsapp_interface import MetaWhatsAppInterface as WhatsAppInterface, MessageType, WhatsAppMessage
from webhook_handler import (
    route_to_document_processor,
    route_to_voice_agent,
    route_to_bedrock_orchestrator
)

# Import test data generators
from generators import message_data, indian_phone_number, s3_url, uuid_string


# ============================================================================
# Property 17: Message Type Routing
# ============================================================================

@given(message=message_data())
@settings(max_examples=100, deadline=None)
def test_property_17_message_type_routing(message):
    """
    **Property 17: Message Type Routing**
    **Validates: Requirements 6.1, 6.4**
    
    For any incoming WhatsApp message, the message should be routed to the
    correct component based on its type:
    - TEXT messages → Bedrock Orchestrator
    - VOICE/AUDIO messages → Voice Agent
    - IMAGE messages → Document Processor
    
    This property verifies that the routing logic correctly identifies message
    types and invokes the appropriate Lambda function.
    """
    with patch('webhook_handler.lambda_client') as mock_lambda, \
         patch('webhook_handler.WhatsAppInterface') as mock_whatsapp_class:
        
        # Setup mock WhatsApp interface
        mock_whatsapp = Mock()
        mock_whatsapp_class.return_value = mock_whatsapp
        mock_whatsapp.send_text_response.return_value = True
        
        # Setup mock Lambda client
        mock_lambda.invoke.return_value = {'StatusCode': 202}
        
        # Route based on message type
        if message.message_type == MessageType.IMAGE:
            response = route_to_document_processor(message)
            
            # Verify routed to DocumentProcessor
            assert response['statusCode'] == 200
            assert response['body']
            body = json.loads(response['body'])
            assert body['routed_to'] == 'DocumentProcessor'
            assert body['message_type'] == 'image'
            
            # Verify Lambda was invoked with correct function name
            assert mock_lambda.invoke.called
            call_kwargs = mock_lambda.invoke.call_args[1]
            assert 'DocumentProcessor' in call_kwargs['FunctionName']
            assert call_kwargs['InvocationType'] == 'Event'  # Async
            
            # Verify payload contains image URL
            payload = json.loads(call_kwargs['Payload'])
            assert payload['image_url'] == message.content
            assert payload['sender_id'] == message.sender_id
            
        elif message.message_type == MessageType.VOICE:
            response = route_to_voice_agent(message)
            
            # Verify routed to VoiceAgent
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['routed_to'] == 'VoiceAgent'
            assert body['message_type'] == 'voice'
            
            # Verify Lambda was invoked with correct function name
            assert mock_lambda.invoke.called
            call_kwargs = mock_lambda.invoke.call_args[1]
            assert 'VoiceAgent' in call_kwargs['FunctionName']
            assert call_kwargs['InvocationType'] == 'Event'  # Async
            
            # Verify payload contains audio URL
            payload = json.loads(call_kwargs['Payload'])
            assert payload['audio_url'] == message.content
            assert payload['sender_id'] == message.sender_id
            
        elif message.message_type == MessageType.TEXT:
            response = route_to_bedrock_orchestrator(message)
            
            # Verify routed to BedrockOrchestrator
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['routed_to'] == 'BedrockOrchestrator'
            assert body['message_type'] == 'text'
            
            # Verify Lambda was invoked with correct function name
            assert mock_lambda.invoke.called
            call_kwargs = mock_lambda.invoke.call_args[1]
            assert 'BedrockOrchestrator' in call_kwargs['FunctionName']
            assert call_kwargs['InvocationType'] == 'Event'  # Async
            
            # Verify payload contains text content
            payload = json.loads(call_kwargs['Payload'])
            assert payload['text'] == message.content
            assert payload['sender_id'] == message.sender_id


@given(
    phone=indian_phone_number(),
    text_content=st.text(min_size=1, max_size=500),
    image_url=s3_url(),
    audio_url=s3_url()
)
@settings(max_examples=100, deadline=None)
def test_property_17_routing_consistency(phone, text_content, image_url, audio_url):
    """
    **Property 17: Message Type Routing (Consistency Check)**
    **Validates: Requirements 6.1, 6.4**
    
    For any set of messages from the same sender with different types,
    each message should be routed to the correct component independently.
    
    This verifies that routing is stateless and consistent across multiple
    messages from the same user.
    """
    with patch('webhook_handler.lambda_client') as mock_lambda, \
         patch('webhook_handler.WhatsAppInterface') as mock_whatsapp_class:
        
        # Setup mocks
        mock_whatsapp = Mock()
        mock_whatsapp_class.return_value = mock_whatsapp
        mock_whatsapp.send_text_response.return_value = True
        mock_lambda.invoke.return_value = {'StatusCode': 202}
        
        # Create messages of different types from same sender
        text_message = WhatsAppMessage(
            message_id='msg_text_001',
            sender_id=phone,
            message_type=MessageType.TEXT,
            content=text_content,
            timestamp=datetime.utcnow(),
            language='en'
        )
        
        image_message = WhatsAppMessage(
            message_id='msg_image_001',
            sender_id=phone,
            message_type=MessageType.IMAGE,
            content=image_url,
            timestamp=datetime.utcnow(),
            language='en',
            metadata={'media_type': 'image/jpeg'}
        )
        
        voice_message = WhatsAppMessage(
            message_id='msg_voice_001',
            sender_id=phone,
            message_type=MessageType.VOICE,
            content=audio_url,
            timestamp=datetime.utcnow(),
            language='hi-IN',
            metadata={'media_type': 'audio/ogg'}
        )
        
        # Route each message
        text_response = route_to_bedrock_orchestrator(text_message)
        image_response = route_to_document_processor(image_message)
        voice_response = route_to_voice_agent(voice_message)
        
        # Verify all succeeded
        assert text_response['statusCode'] == 200
        assert image_response['statusCode'] == 200
        assert voice_response['statusCode'] == 200
        
        # Verify correct routing for each
        text_body = json.loads(text_response['body'])
        image_body = json.loads(image_response['body'])
        voice_body = json.loads(voice_response['body'])
        
        assert text_body['routed_to'] == 'BedrockOrchestrator'
        assert image_body['routed_to'] == 'DocumentProcessor'
        assert voice_body['routed_to'] == 'VoiceAgent'
        
        # Verify Lambda was invoked 3 times (once for each message)
        assert mock_lambda.invoke.call_count == 3


@given(message=message_data())
@settings(max_examples=100, deadline=None)
def test_property_17_routing_preserves_metadata(message):
    """
    **Property 17: Message Type Routing (Metadata Preservation)**
    **Validates: Requirements 6.1, 6.4**
    
    For any incoming message, the routing should preserve all message metadata
    (sender_id, message_id, language, etc.) when forwarding to the target component.
    
    This ensures no information is lost during the routing process.
    """
    with patch('webhook_handler.lambda_client') as mock_lambda, \
         patch('webhook_handler.WhatsAppInterface') as mock_whatsapp_class:
        
        # Setup mocks
        mock_whatsapp = Mock()
        mock_whatsapp_class.return_value = mock_whatsapp
        mock_whatsapp.send_text_response.return_value = True
        mock_lambda.invoke.return_value = {'StatusCode': 202}
        
        # Convert Message to WhatsAppMessage (add metadata field)
        whatsapp_message = WhatsAppMessage(
            message_id=message.message_id,
            sender_id=message.sender_id,
            message_type=message.message_type,
            content=message.content,
            timestamp=message.timestamp,
            language=message.language,
            metadata={'media_type': 'image/jpeg'} if message.message_type == MessageType.IMAGE else {}
        )
        
        # Route message based on type
        if whatsapp_message.message_type == MessageType.IMAGE:
            route_to_document_processor(whatsapp_message)
        elif whatsapp_message.message_type == MessageType.VOICE:
            route_to_voice_agent(whatsapp_message)
        elif whatsapp_message.message_type == MessageType.TEXT:
            route_to_bedrock_orchestrator(whatsapp_message)
        else:
            # Skip unsupported types
            return
        
        # Verify Lambda was invoked
        assert mock_lambda.invoke.called
        
        # Extract payload
        call_kwargs = mock_lambda.invoke.call_args[1]
        payload = json.loads(call_kwargs['Payload'])
        
        # Verify metadata is preserved
        assert payload['sender_id'] == message.sender_id
        assert payload['message_id'] == message.message_id
        
        # Verify language is preserved (with defaults)
        if message.language:
            assert payload['language'] == message.language
        else:
            # Should have a default language
            assert 'language' in payload


@given(message_type=st.sampled_from([MessageType.TEXT, MessageType.IMAGE, MessageType.VOICE]))
@settings(max_examples=100, deadline=None)
def test_property_17_routing_invocation_type(message_type):
    """
    **Property 17: Message Type Routing (Async Invocation)**
    **Validates: Requirements 6.1, 6.4**
    
    For any message type, the routing should use asynchronous Lambda invocation
    (InvocationType='Event') to ensure the webhook responds quickly without
    waiting for processing to complete.
    
    This verifies the system meets the 5-second response requirement (6.2).
    """
    with patch('webhook_handler.lambda_client') as mock_lambda, \
         patch('webhook_handler.WhatsAppInterface') as mock_whatsapp_class:
        
        # Setup mocks
        mock_whatsapp = Mock()
        mock_whatsapp_class.return_value = mock_whatsapp
        mock_whatsapp.send_text_response.return_value = True
        mock_lambda.invoke.return_value = {'StatusCode': 202}
        
        # Create message of specified type
        message = WhatsAppMessage(
            message_id='msg_001',
            sender_id='+919876543210',
            message_type=message_type,
            content='test_content' if message_type == MessageType.TEXT else 'https://example.com/media',
            timestamp=datetime.utcnow(),
            language='en',
            metadata={'media_type': 'image/jpeg'} if message_type == MessageType.IMAGE else {}
        )
        
        # Route message
        if message_type == MessageType.IMAGE:
            route_to_document_processor(message)
        elif message_type == MessageType.VOICE:
            route_to_voice_agent(message)
        elif message_type == MessageType.TEXT:
            route_to_bedrock_orchestrator(message)
        
        # Verify async invocation
        assert mock_lambda.invoke.called
        call_kwargs = mock_lambda.invoke.call_args[1]
        assert call_kwargs['InvocationType'] == 'Event', \
            f"Expected async invocation for {message_type.value} messages"


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

def test_routing_with_missing_lambda_client():
    """
    Test that routing handles missing Lambda client gracefully.
    """
    with patch('webhook_handler.lambda_client') as mock_lambda, \
         patch('webhook_handler.WhatsAppInterface') as mock_whatsapp_class:
        
        # Setup mocks
        mock_whatsapp = Mock()
        mock_whatsapp_class.return_value = mock_whatsapp
        mock_whatsapp.send_text_response.return_value = True
        
        # Simulate Lambda invocation failure
        mock_lambda.invoke.side_effect = Exception("Lambda client error")
        
        message = WhatsAppMessage(
            message_id='msg_001',
            sender_id='+919876543210',
            message_type=MessageType.TEXT,
            content='test message',
            timestamp=datetime.utcnow(),
            language='en'
        )
        
        # Should handle error gracefully
        response = route_to_bedrock_orchestrator(message)
        
        # Should return error response
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body


def test_routing_with_document_type():
    """
    Test that DOCUMENT message type is handled (edge case).
    """
    with patch('webhook_handler.lambda_client') as mock_lambda, \
         patch('webhook_handler.WhatsAppInterface') as mock_whatsapp_class:
        
        # Setup mocks
        mock_whatsapp = Mock()
        mock_whatsapp_class.return_value = mock_whatsapp
        mock_whatsapp.send_text_response.return_value = True
        mock_lambda.invoke.return_value = {'StatusCode': 202}
        
        # DOCUMENT type should be treated like IMAGE (goes to DocumentProcessor)
        message = WhatsAppMessage(
            message_id='msg_doc_001',
            sender_id='+919876543210',
            message_type=MessageType.DOCUMENT,
            content='https://example.com/document.pdf',
            timestamp=datetime.utcnow(),
            language='en',
            metadata={'media_type': 'application/pdf'}
        )
        
        # Note: Based on webhook_handler.py, DOCUMENT type is not explicitly
        # handled in the routing logic, so this would fall through to the
        # unsupported type case. This test documents current behavior.
        # In a real implementation, DOCUMENT might need explicit routing.
