"""
Unit tests for WhatsApp Webhook Handler Lambda

Tests the webhook handler's routing logic and message processing.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
import sys
import os
import importlib
import importlib.util

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'whatsapp'))

# Ensure the real meta_whatsapp_interface is loaded (not the conftest mock)
_real_path = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'whatsapp', 'meta_whatsapp_interface.py')
_spec = importlib.util.spec_from_file_location('meta_whatsapp_interface', _real_path)
_real_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_real_mod)
sys.modules['meta_whatsapp_interface'] = _real_mod

# Now import (or reload) webhook_handler with the real meta_whatsapp_interface
if 'webhook_handler' in sys.modules:
    importlib.reload(sys.modules['webhook_handler'])

from webhook_handler import (
    handler, verify_webhook, store_message,
    route_to_document_processor, route_to_voice_agent,
    route_to_bedrock_orchestrator, response
)


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables"""
    monkeypatch.setenv('DYNAMODB_TABLE', 'TestTable')
    monkeypatch.setenv('DOCUMENT_PROCESSOR_FUNCTION', 'DocumentProcessor')
    monkeypatch.setenv('VOICE_AGENT_FUNCTION', 'VoiceAgent')
    monkeypatch.setenv('BEDROCK_ORCHESTRATOR_FUNCTION', 'BedrockOrchestrator')
    monkeypatch.setenv('WEBHOOK_VERIFY_TOKEN', 'test-token')


@pytest.fixture
def mock_aws_clients():
    """Mock AWS clients"""
    with patch('webhook_handler.lambda_client') as mock_lambda, \
         patch('webhook_handler.dynamodb') as mock_dynamodb, \
         patch('webhook_handler.table') as mock_table:
        yield {
            'lambda': mock_lambda,
            'dynamodb': mock_dynamodb,
            'table': mock_table
        }


class TestWebhookVerification:
    """Test webhook verification for initial setup"""
    
    @patch('webhook_handler.WEBHOOK_VERIFY_TOKEN', 'test-token')
    def test_verify_webhook_success(self, mock_env):
        """Test successful webhook verification"""
        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'hub.mode': 'subscribe',
                'hub.verify_token': 'test-token',
                'hub.challenge': '12345'
            }
        }
        
        result = verify_webhook(event)
        
        assert result['statusCode'] == 200
        assert result['body'] == '12345'
    
    def test_verify_webhook_wrong_token(self, mock_env):
        """Test webhook verification with wrong token"""
        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'hub.mode': 'subscribe',
                'hub.verify_token': 'wrong-token',
                'hub.challenge': '12345'
            }
        }
        
        result = verify_webhook(event)
        
        assert result['statusCode'] == 403
    
    def test_verify_webhook_wrong_mode(self, mock_env):
        """Test webhook verification with wrong mode"""
        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'hub.mode': 'unsubscribe',
                'hub.verify_token': 'test-token',
                'hub.challenge': '12345'
            }
        }
        
        result = verify_webhook(event)
        
        assert result['statusCode'] == 403


class TestMessageRouting:
    """Test message routing to appropriate components"""
    
    @patch('webhook_handler.WhatsAppInterface')
    def test_route_image_to_document_processor(self, mock_interface_class, mock_env, mock_aws_clients):
        """Test routing image message to DocumentProcessor"""
        # Setup mock
        mock_interface = Mock()
        mock_interface_class.return_value = mock_interface
        
        mock_message = Mock()
        mock_message.message_id = 'SM123'
        mock_message.sender_id = '+919876543210'
        mock_message.message_type = Mock(value='image')
        mock_message.content = 'https://example.com/image.jpg'
        mock_message.language = 'en'
        mock_message.metadata = {'media_type': 'image/jpeg'}
        
        mock_interface.receive_message.return_value = mock_message
        
        # Create event
        event = {
            'httpMethod': 'POST',
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'},
            'body': 'MessageSid=SM123&From=whatsapp:+919876543210&NumMedia=1&MediaUrl0=https://example.com/image.jpg&MediaContentType0=image/jpeg'
        }
        
        result = route_to_document_processor(mock_message)
        
        assert result['statusCode'] == 200
        assert 'DocumentProcessor' in json.loads(result['body'])['routed_to']
        
        # Verify Lambda was invoked
        mock_aws_clients['lambda'].invoke.assert_called_once()
        call_args = mock_aws_clients['lambda'].invoke.call_args
        assert call_args[1]['FunctionName'] == 'DocumentProcessor'
        assert call_args[1]['InvocationType'] == 'Event'  # Async
    
    @patch('webhook_handler.WhatsAppInterface')
    def test_route_voice_to_voice_agent(self, mock_interface_class, mock_env, mock_aws_clients):
        """Test routing voice message to VoiceAgent"""
        mock_interface = Mock()
        mock_interface_class.return_value = mock_interface
        
        mock_message = Mock()
        mock_message.message_id = 'SM456'
        mock_message.sender_id = '+919876543210'
        mock_message.message_type = Mock(value='voice')
        mock_message.content = 'https://example.com/audio.ogg'
        mock_message.language = 'hi-IN'
        mock_message.metadata = {'media_type': 'audio/ogg'}
        
        result = route_to_voice_agent(mock_message)
        
        assert result['statusCode'] == 200
        assert 'VoiceAgent' in json.loads(result['body'])['routed_to']
        
        # Verify Lambda was invoked
        mock_aws_clients['lambda'].invoke.assert_called_once()
        call_args = mock_aws_clients['lambda'].invoke.call_args
        assert call_args[1]['FunctionName'] == 'VoiceAgent'
    
    @patch('webhook_handler.WhatsAppInterface')
    def test_route_text_to_bedrock_orchestrator(self, mock_interface_class, mock_env, mock_aws_clients):
        """Test routing text message to BedrockOrchestrator"""
        mock_interface = Mock()
        mock_interface_class.return_value = mock_interface
        
        mock_message = Mock()
        mock_message.message_id = 'SM789'
        mock_message.sender_id = '+919876543210'
        mock_message.message_type = Mock(value='text')
        mock_message.content = 'What is my credit score?'
        mock_message.language = 'en'
        mock_message.metadata = {}
        
        result = route_to_bedrock_orchestrator(mock_message)
        
        assert result['statusCode'] == 200
        assert 'BedrockOrchestrator' in json.loads(result['body'])['routed_to']
        
        # Verify Lambda was invoked
        mock_aws_clients['lambda'].invoke.assert_called_once()
        call_args = mock_aws_clients['lambda'].invoke.call_args
        assert call_args[1]['FunctionName'] == 'BedrockOrchestrator'


class TestStoreMessage:
    """Test message storage in DynamoDB"""
    
    @patch('webhook_handler.table')
    def test_store_text_message(self, mock_table):
        """Test storing text message in DynamoDB"""
        from datetime import datetime
        from meta_whatsapp_interface import MessageType
        
        mock_message = Mock()
        mock_message.message_id = 'SM123'
        mock_message.sender_id = '+919876543210'
        mock_message.message_type = MessageType.TEXT
        mock_message.content = 'Hello'
        mock_message.timestamp = datetime.utcnow()
        mock_message.language = 'en'
        mock_message.metadata = None
        
        result = store_message(mock_message)
        
        assert result is True
        mock_table.put_item.assert_called_once()
        
        # Verify item structure
        call_args = mock_table.put_item.call_args
        item = call_args[1]['Item']
        assert item['PK'].startswith('CONVERSATION#')
        assert item['SK'].startswith('MSG#')
        assert item['message_type'] == 'text'
    
    @patch('webhook_handler.table')
    def test_store_image_message_with_metadata(self, mock_table):
        """Test storing image message with metadata"""
        from datetime import datetime
        from meta_whatsapp_interface import MessageType
        
        mock_message = Mock()
        mock_message.message_id = 'SM456'
        mock_message.sender_id = '+919876543210'
        mock_message.message_type = MessageType.IMAGE
        mock_message.content = 'https://example.com/image.jpg'
        mock_message.timestamp = datetime.utcnow()
        mock_message.language = 'en'
        mock_message.metadata = {'media_type': 'image/jpeg', 'size': 1024}
        
        result = store_message(mock_message)
        
        assert result is True
        call_args = mock_table.put_item.call_args
        item = call_args[1]['Item']
        assert 'metadata' in item
        assert item['metadata']['media_type'] == 'image/jpeg'


class TestHandlerIntegration:
    """Test main handler function with full integration"""
    
    @patch('webhook_handler.WhatsAppInterface')
    @patch('webhook_handler.store_message')
    @patch('webhook_handler.route_to_document_processor')
    def test_handler_image_message_flow(self, mock_route, mock_store, mock_interface_class, mock_env, mock_aws_clients):
        """Test complete flow for image message"""
        from meta_whatsapp_interface import MessageType
        
        # Setup mocks
        mock_interface = Mock()
        mock_interface_class.return_value = mock_interface
        
        mock_message = Mock()
        mock_message.message_type = MessageType.IMAGE
        mock_interface.receive_message.return_value = mock_message
        
        mock_store.return_value = True
        mock_route.return_value = {'statusCode': 200, 'body': '{}'}
        
        # Create event
        event = {
            'httpMethod': 'POST',
            'headers': {'Content-Type': 'application/json'},
            'body': '{"entry":[{"changes":[{"value":{"messages":[{"id":"SM123","from":"919876543210","type":"image","image":{"id":"img1"},"timestamp":"1234567890"}]}}]}]}'
        }
        
        result = handler(event, None)
        
        assert result['statusCode'] == 200
        mock_store.assert_called_once()
        mock_route.assert_called_once()
    
    @patch('webhook_handler.WEBHOOK_VERIFY_TOKEN', 'test-token')
    def test_handler_get_request_verification(self, mock_env):
        """Test handler with GET request for verification"""
        event = {
            'httpMethod': 'GET',
            'queryStringParameters': {
                'hub.mode': 'subscribe',
                'hub.verify_token': 'test-token',
                'hub.challenge': '54321'
            }
        }
        
        result = handler(event, None)
        
        assert result['statusCode'] == 200
        assert result['body'] == '54321'
    
    @patch('webhook_handler.WhatsAppInterface')
    def test_handler_invalid_content_type(self, mock_interface_class, mock_env):
        """Test handler with unsupported content type"""
        event = {
            'httpMethod': 'POST',
            'headers': {'Content-Type': 'text/xml'},
            'body': '<xml>not supported</xml>'
        }
        
        result = handler(event, None)
        
        assert result['statusCode'] == 400
    
    @patch('webhook_handler.WhatsAppInterface')
    def test_handler_parse_failure(self, mock_interface_class, mock_env):
        """Test handler when message parsing fails"""
        mock_interface = Mock()
        mock_interface_class.return_value = mock_interface
        mock_interface.receive_message.return_value = None
        
        event = {
            'httpMethod': 'POST',
            'headers': {'Content-Type': 'application/json'},
            'body': '{"entry":[]}'
        }
        
        result = handler(event, None)
        
        assert result['statusCode'] == 400


class TestResponseFormatter:
    """Test response formatting"""
    
    def test_response_json(self):
        """Test JSON response formatting"""
        result = response(200, {'status': 'success'})
        
        assert result['statusCode'] == 200
        assert result['headers']['Content-Type'] == 'application/json'
        assert json.loads(result['body'])['status'] == 'success'
    
    def test_response_plain_text(self):
        """Test plain text response formatting"""
        result = response(200, 'Hello', is_plain_text=True)
        
        assert result['statusCode'] == 200
        assert result['headers']['Content-Type'] == 'text/plain'
        assert result['body'] == 'Hello'
    
    def test_response_with_cors(self):
        """Test that response includes CORS headers"""
        result = response(200, {})
        
        assert 'Access-Control-Allow-Origin' in result['headers']
        assert result['headers']['Access-Control-Allow-Origin'] == '*'


class TestErrorHandling:
    """Test error handling in webhook handler"""
    
    @patch('webhook_handler.WhatsAppInterface')
    def test_handler_exception_handling(self, mock_interface_class, mock_env):
        """Test that handler catches and returns errors gracefully"""
        mock_interface_class.side_effect = Exception("Test error")
        
        event = {
            'httpMethod': 'POST',
            'headers': {'Content-Type': 'application/json'},
            'body': '{"entry":[{"changes":[{"value":{"messages":[{"id":"1","from":"123","type":"text","text":{"body":"hi"},"timestamp":"1234567890"}]}}]}]}'
        }
        
        result = handler(event, None)
        
        assert result['statusCode'] == 500
        assert 'error' in json.loads(result['body'])
    
    @patch('webhook_handler.lambda_client')
    @patch('webhook_handler.WhatsAppInterface')
    def test_route_lambda_invocation_failure(self, mock_interface_class, mock_lambda, mock_env):
        """Test handling of Lambda invocation failure"""
        mock_lambda.invoke.side_effect = Exception("Lambda error")
        
        mock_message = Mock()
        mock_message.sender_id = '+919876543210'
        mock_message.message_id = 'SM123'
        mock_message.content = 'https://example.com/image.jpg'
        mock_message.language = 'en'
        mock_message.metadata = {'media_type': 'image/jpeg'}
        
        result = route_to_document_processor(mock_message)
        
        assert result['statusCode'] == 500
