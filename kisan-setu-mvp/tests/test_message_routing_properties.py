"""
Property-Based Tests for Message Type Routing

Tests Property 17: Message Type Routing
For any incoming WhatsApp message, the message should be routed to the correct
component based on its type: text messages to Bedrock Orchestrator, voice messages
to Voice_Agent, images to Document_Processor.

**Validates: Requirements 6.1, 6.4**

Tests target router.py — the actual deployed Lambda handler.
Uses Hypothesis framework with minimum 100 iterations.
"""

import pytest
import json
import sys
import os
from unittest.mock import Mock, patch
from hypothesis import given, settings, strategies as st
from datetime import datetime

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'router'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from router.router import (
    route_to_document_processor,
    route_to_voice_agent,
    route_to_bedrock_orchestrator,
)
from common.models import MessageType

# Import test data generators
from generators import indian_phone_number, s3_url, uuid_string


# ============================================================================
# Property 17: Message Type Routing
# ============================================================================

@given(
    phone=indian_phone_number(),
    msg_id=uuid_string(),
    msg_type=st.sampled_from([MessageType.TEXT, MessageType.IMAGE, MessageType.VOICE]),
    text_content=st.text(min_size=1, max_size=500),
    media_url=s3_url(),
    request_id=uuid_string(),
)
@settings(max_examples=100, deadline=None)
def test_property_17_message_type_routing(phone, msg_id, msg_type, text_content, media_url, request_id):
    """
    **Property 17: Message Type Routing**
    **Validates: Requirements 6.1, 6.4**

    For any incoming WhatsApp message, the router should invoke the correct
    Lambda function based on message type:
    - TEXT → BedrockOrchestrator
    - VOICE → VoiceAgent
    - IMAGE → DocumentProcessor

    All invocations must be asynchronous (InvocationType='Event').
    """
    with patch('router.router.lambda_client') as mock_lambda, \
         patch('router.router.table') as mock_table, \
         patch('router.router.detect_user_language', return_value='hi-IN'), \
         patch('router.router.detect_language_from_text', return_value='en'):

        mock_lambda.invoke.return_value = {'StatusCode': 202}
        mock_table.query.return_value = {'Items': []}

        if msg_type == MessageType.IMAGE:
            resp = route_to_document_processor(
                sender=phone, message_id=msg_id, media_url=media_url,
                media_type='image/jpeg', request_id=request_id, language='hi-IN'
            )
            expected_target = 'DocumentProcessor'
            expected_type = 'image'
        elif msg_type == MessageType.VOICE:
            resp = route_to_voice_agent(
                sender=phone, message_id=msg_id, audio_url=media_url,
                media_type='audio/ogg', request_id=request_id
            )
            expected_target = 'VoiceAgent'
            expected_type = 'voice'
        else:
            resp = route_to_bedrock_orchestrator(
                sender=phone, message_id=msg_id, text=text_content,
                request_id=request_id
            )
            expected_target = 'BedrockOrchestrator'
            expected_type = 'text'

        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['routed_to'] == expected_target
        assert body['message_type'] == expected_type

        # Verify async invocation
        assert mock_lambda.invoke.called
        call_kwargs = mock_lambda.invoke.call_args[1]
        assert call_kwargs['InvocationType'] == 'Event'


@given(
    phone=indian_phone_number(),
    text_content=st.text(min_size=1, max_size=500),
    image_url=s3_url(),
    audio_url=s3_url()
)
@settings(max_examples=100, deadline=None)
def test_property_17_routing_consistency(phone, text_content, image_url, audio_url):
    """
    **Property 17: Routing Consistency**
    **Validates: Requirements 6.1, 6.4**

    For any set of messages from the same sender with different types,
    each message should be routed to the correct component independently.
    Routing is stateless and consistent.
    """
    with patch('router.router.lambda_client') as mock_lambda, \
         patch('router.router.table') as mock_table, \
         patch('router.router.detect_user_language', return_value='en'), \
         patch('router.router.detect_language_from_text', return_value='en'):

        mock_lambda.invoke.return_value = {'StatusCode': 202}
        mock_table.query.return_value = {'Items': []}

        text_resp = route_to_bedrock_orchestrator(
            sender=phone, message_id='msg_text', text=text_content, request_id='req1'
        )
        image_resp = route_to_document_processor(
            sender=phone, message_id='msg_img', media_url=image_url,
            media_type='image/jpeg', request_id='req2', language='en'
        )
        voice_resp = route_to_voice_agent(
            sender=phone, message_id='msg_voice', audio_url=audio_url,
            media_type='audio/ogg', request_id='req3'
        )

        assert text_resp['statusCode'] == 200
        assert image_resp['statusCode'] == 200
        assert voice_resp['statusCode'] == 200

        assert json.loads(text_resp['body'])['routed_to'] == 'BedrockOrchestrator'
        assert json.loads(image_resp['body'])['routed_to'] == 'DocumentProcessor'
        assert json.loads(voice_resp['body'])['routed_to'] == 'VoiceAgent'

        assert mock_lambda.invoke.call_count == 3


@given(
    phone=indian_phone_number(),
    msg_id=uuid_string(),
    msg_type=st.sampled_from([MessageType.TEXT, MessageType.IMAGE, MessageType.VOICE]),
    content=st.text(min_size=1, max_size=200),
    media_url=s3_url(),
    request_id=uuid_string(),
)
@settings(max_examples=100, deadline=None)
def test_property_17_routing_preserves_metadata(phone, msg_id, msg_type, content, media_url, request_id):
    """
    **Property 17: Metadata Preservation**
    **Validates: Requirements 6.1, 6.4**

    For any incoming message, the routing should preserve sender and message
    metadata when forwarding to the target Lambda.
    """
    with patch('router.router.lambda_client') as mock_lambda, \
         patch('router.router.table') as mock_table, \
         patch('router.router.detect_user_language', return_value='hi-IN'), \
         patch('router.router.detect_language_from_text', return_value='en'):

        mock_lambda.invoke.return_value = {'StatusCode': 202}
        mock_table.query.return_value = {'Items': []}

        if msg_type == MessageType.IMAGE:
            route_to_document_processor(
                sender=phone, message_id=msg_id, media_url=media_url,
                media_type='image/jpeg', request_id=request_id, language='hi-IN'
            )
        elif msg_type == MessageType.VOICE:
            route_to_voice_agent(
                sender=phone, message_id=msg_id, audio_url=media_url,
                media_type='audio/ogg', request_id=request_id
            )
        else:
            route_to_bedrock_orchestrator(
                sender=phone, message_id=msg_id, text=content,
                request_id=request_id
            )

        assert mock_lambda.invoke.called
        call_kwargs = mock_lambda.invoke.call_args[1]
        payload = json.loads(call_kwargs['Payload'])

        # All routing functions include sender info in the payload
        assert payload.get('sender') or payload.get('sender_id'), \
            "Payload must include sender information"
        assert payload.get('message_id'), \
            "Payload must include message_id"


@given(msg_type=st.sampled_from([MessageType.TEXT, MessageType.IMAGE, MessageType.VOICE]))
@settings(max_examples=100, deadline=None)
def test_property_17_routing_invocation_type(msg_type):
    """
    **Property 17: Async Invocation**
    **Validates: Requirements 6.1, 6.4**

    For any message type, the routing should use asynchronous Lambda invocation
    (InvocationType='Event') to meet the 5-second webhook response requirement.
    """
    with patch('router.router.lambda_client') as mock_lambda, \
         patch('router.router.table') as mock_table, \
         patch('router.router.detect_user_language', return_value='en'), \
         patch('router.router.detect_language_from_text', return_value='en'):

        mock_lambda.invoke.return_value = {'StatusCode': 202}
        mock_table.query.return_value = {'Items': []}

        if msg_type == MessageType.IMAGE:
            route_to_document_processor(
                sender='+919876543210', message_id='msg_001',
                media_url='https://example.com/media', media_type='image/jpeg',
                request_id='req_001', language='en'
            )
        elif msg_type == MessageType.VOICE:
            route_to_voice_agent(
                sender='+919876543210', message_id='msg_001',
                audio_url='https://example.com/media', media_type='audio/ogg',
                request_id='req_001'
            )
        else:
            route_to_bedrock_orchestrator(
                sender='+919876543210', message_id='msg_001',
                text='test_content', request_id='req_001'
            )

        assert mock_lambda.invoke.called
        call_kwargs = mock_lambda.invoke.call_args[1]
        assert call_kwargs['InvocationType'] == 'Event', \
            f"Expected async invocation for {msg_type.value} messages"


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

def test_routing_with_lambda_failure():
    """Test that routing handles Lambda invocation failure gracefully."""
    with patch('router.router.lambda_client') as mock_lambda, \
         patch('router.router.table') as mock_table, \
         patch('router.router.detect_user_language', return_value='en'), \
         patch('router.router.detect_language_from_text', return_value='en'):

        mock_lambda.invoke.side_effect = Exception("Lambda client error")
        mock_table.query.return_value = {'Items': []}

        resp = route_to_bedrock_orchestrator(
            sender='+919876543210', message_id='msg_001',
            text='test message', request_id='req_001'
        )

        assert resp['statusCode'] == 500
        body = json.loads(resp['body'])
        assert 'error' in body
