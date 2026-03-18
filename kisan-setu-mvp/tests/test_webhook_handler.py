"""
Unit tests for the Message Router Lambda (router.py)

Tests the router's webhook verification, message routing, and response formatting.
This replaces the old webhook_handler tests — router.py is the deployed handler.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add lambda directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'router'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from router.router import (
    handler, verify_webhook, store_message_metadata,
    route_to_document_processor, route_to_voice_agent,
    route_to_bedrock_orchestrator, response
)


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables"""
    monkeypatch.setenv('DYNAMODB_TABLE', 'TestTable')
    monkeypatch.setenv('PROCESSOR_FUNCTION_NAME', 'DocumentProcessor')
    monkeypatch.setenv('VOICE_AGENT_FUNCTION', 'VoiceAgent')
    monkeypatch.setenv('BEDROCK_ORCHESTRATOR_FUNCTION', 'BedrockOrchestrator')
    monkeypatch.setenv('WEBHOOK_VERIFY_TOKEN', 'test-token')


@pytest.fixture
def mock_aws_clients():
    """Mock AWS clients used by router.py"""
    with patch('router.router.lambda_client') as mock_lambda, \
         patch('router.router.table') as mock_table, \
         patch('router.router.sns') as mock_sns:
        mock_table.get_item.return_value = {}
        mock_table.put_item.return_value = {}
        mock_table.query.return_value = {'Items': []}
        yield {
            'lambda': mock_lambda,
            'table': mock_table,
            'sns': mock_sns,
        }


class TestWebhookVerification:
    """Test webhook verification for initial setup"""

    @patch('router.router.WEBHOOK_VERIFY_TOKEN', 'test-token')
    def test_verify_webhook_success(self, mock_env):
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

    def test_route_image_to_document_processor(self, mock_env, mock_aws_clients):
        mock_aws_clients['lambda'].invoke.return_value = {'StatusCode': 202}

        result = route_to_document_processor(
            sender='+919876543210',
            message_id='SM123',
            media_url='https://example.com/image.jpg',
            media_type='image/jpeg',
            request_id='req-001',
            language='en'
        )

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['routed_to'] == 'DocumentProcessor'
        assert body['message_type'] == 'image'

        mock_aws_clients['lambda'].invoke.assert_called_once()
        call_kwargs = mock_aws_clients['lambda'].invoke.call_args[1]
        assert 'DocumentProcessor' in call_kwargs['FunctionName']
        assert call_kwargs['InvocationType'] == 'Event'

    def test_route_voice_to_voice_agent(self, mock_env, mock_aws_clients):
        mock_aws_clients['lambda'].invoke.return_value = {'StatusCode': 202}

        with patch('router.router.detect_user_language', return_value='hi-IN'), \
             patch('router.router.VOICE_AGENT_FUNCTION', 'VoiceAgent'):
            result = route_to_voice_agent(
                sender='+919876543210',
                message_id='SM456',
                audio_url='https://example.com/audio.ogg',
                media_type='audio/ogg',
                request_id='req-002'
            )

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['routed_to'] == 'VoiceAgent'
        assert body['message_type'] == 'voice'

        mock_aws_clients['lambda'].invoke.assert_called_once()
        call_kwargs = mock_aws_clients['lambda'].invoke.call_args[1]
        assert 'VoiceAgent' in call_kwargs['FunctionName']

    def test_route_text_to_bedrock_orchestrator(self, mock_env, mock_aws_clients):
        mock_aws_clients['lambda'].invoke.return_value = {'StatusCode': 202}

        with patch('router.router.detect_user_language', return_value='en'), \
             patch('router.router.detect_language_from_text', return_value='en'):
            result = route_to_bedrock_orchestrator(
                sender='+919876543210',
                message_id='SM789',
                text='What is my credit score?',
                request_id='req-003'
            )

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['routed_to'] == 'BedrockOrchestrator'
        assert body['message_type'] == 'text'

        mock_aws_clients['lambda'].invoke.assert_called_once()
        call_kwargs = mock_aws_clients['lambda'].invoke.call_args[1]
        assert 'BedrockOrchestrator' in call_kwargs['FunctionName']


class TestStoreMessageMetadata:
    """Test message metadata storage in DynamoDB"""

    @patch('router.router.table')
    def test_store_message_metadata(self, mock_table):
        store_message_metadata('+919876543210', 'SM123', '2024-01-15T10:00:00', 'meta')
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]['Item']
        assert item['PK'].startswith('CONVERSATION#')
        assert item['SK'].startswith('MSG#')
        assert item['message_id'] == 'SM123'


class TestHandlerIntegration:
    """Test main handler function with full integration"""

    @patch('router.router.WEBHOOK_VERIFY_TOKEN', 'test-token')
    def test_handler_get_request_verification(self, mock_env):
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

    def test_handler_invalid_content_type(self, mock_env):
        event = {
            'httpMethod': 'POST',
            'headers': {'Content-Type': 'text/xml'},
            'body': '<xml>not supported</xml>'
        }
        result = handler(event, None)
        assert result['statusCode'] == 400

    def test_handler_empty_entry(self, mock_env, mock_aws_clients):
        event = {
            'httpMethod': 'POST',
            'headers': {'Content-Type': 'application/json'},
            'body': '{"entry":[]}'
        }
        result = handler(event, None)
        assert result['statusCode'] == 400

    def test_handler_image_message_flow(self, mock_env, mock_aws_clients):
        mock_aws_clients['lambda'].invoke.return_value = {'StatusCode': 202}

        event = {
            'httpMethod': 'POST',
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'entry': [{
                    'changes': [{
                        'value': {
                            'messages': [{
                                'id': 'SM123',
                                'from': '919876543210',
                                'type': 'image',
                                'image': {'id': 'img1', 'mime_type': 'image/jpeg'},
                                'timestamp': '1234567890'
                            }]
                        }
                    }]
                }]
            })
        }

        with patch('router.router.detect_user_language', return_value='hi-IN'):
            result = handler(event, Mock(aws_request_id='test-req'))

        assert result['statusCode'] == 200


class TestResponseFormatter:
    """Test response formatting"""

    def test_response_json(self):
        result = response(200, {'status': 'success'})
        assert result['statusCode'] == 200
        assert result['headers']['Content-Type'] == 'application/json'
        assert json.loads(result['body'])['status'] == 'success'

    def test_response_plain_text(self):
        result = response(200, 'Hello', is_plain_text=True)
        assert result['statusCode'] == 200
        assert result['headers']['Content-Type'] == 'text/plain'
        assert result['body'] == 'Hello'

    def test_response_with_cors(self):
        result = response(200, {})
        assert result['headers']['Access-Control-Allow-Origin'] == '*'


class TestErrorHandling:
    """Test error handling in router"""

    def test_route_lambda_invocation_failure(self, mock_env, mock_aws_clients):
        mock_aws_clients['lambda'].invoke.side_effect = Exception("Lambda error")

        result = route_to_document_processor(
            sender='+919876543210',
            message_id='SM123',
            media_url='https://example.com/image.jpg',
            media_type='image/jpeg',
            request_id='req-err',
            language='en'
        )
        assert result['statusCode'] == 500

    def test_handler_exception_handling(self, mock_env, mock_aws_clients):
        event = {
            'httpMethod': 'POST',
            'headers': {'Content-Type': 'application/json'},
            'body': '{"entry":[{"changes":[{"value":{"messages":[{"id":"1","from":"123","type":"text","text":{"body":"hi"},"timestamp":"1234567890"}]}}]}]}'
        }

        mock_aws_clients['lambda'].invoke.side_effect = Exception("Test error")

        with patch('router.router.detect_user_language', return_value='en'), \
             patch('router.router.detect_language_from_text', return_value='en'):
            result = handler(event, Mock(aws_request_id='test-req'))

        assert result['statusCode'] == 500
        assert 'error' in json.loads(result['body'])
