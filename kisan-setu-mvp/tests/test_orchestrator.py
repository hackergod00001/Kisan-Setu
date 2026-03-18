"""
Unit tests for Bedrock Orchestrator Component

Tests Requirements 7.1, 7.2, 7.3, 7.4, 7.5
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'orchestrator'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'common'))

from orchestrator import (
    BedrockOrchestrator, Message, SubTask, ToolResult, Response,
    ConversationContext, handler, get_orchestrator
)
import orchestrator as orchestrator_module


@pytest.fixture
def mock_aws_clients(monkeypatch):
    """Mock AWS clients"""
    mock_bedrock = Mock()
    mock_dynamodb = Mock()
    mock_lambda = Mock()
    mock_table = Mock()

    monkeypatch.setattr('orchestrator.bedrock_runtime', mock_bedrock)
    monkeypatch.setattr('orchestrator.dynamodb', mock_dynamodb)
    monkeypatch.setattr('orchestrator.lambda_client', mock_lambda)
    monkeypatch.setattr('orchestrator.table', mock_table)

    # Setup table mock
    mock_dynamodb.Table.return_value = mock_table

    return {
        'bedrock': mock_bedrock,
        'dynamodb': mock_dynamodb,
        'lambda': mock_lambda,
        'table': mock_table
    }


@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables"""
    monkeypatch.setenv('DYNAMODB_TABLE', 'TestTable')
    monkeypatch.setenv('REGION', 'ap-south-1')
    monkeypatch.setenv('DOCUMENT_PROCESSOR_FUNCTION', 'TestDocProcessor')
    monkeypatch.setenv('VOICE_AGENT_FUNCTION', 'TestVoiceAgent')
    monkeypatch.setenv('SATELLITE_ANALYZER_FUNCTION', 'TestSatellite')
    monkeypatch.setenv('CREDIT_CALCULATOR_FUNCTION', 'TestCredit')


class TestBedrockOrchestrator:
    """Test BedrockOrchestrator class"""

    def test_init(self, mock_env, mock_aws_clients):
        """Test orchestrator initialization"""
        import importlib
        import orchestrator as orch_module
        importlib.reload(orch_module)

        orchestrator = orch_module.BedrockOrchestrator()

        assert orchestrator.table is not None

    def test_process_request_success(self, mock_env, mock_aws_clients):
        """Test successful request processing"""
        orchestrator = BedrockOrchestrator()

        # Mock LLM adapter converse method
        orchestrator.llm_adapter = Mock()
        orchestrator.llm_adapter.converse.return_value = (
            'Hello! I can help you with that.',
            100,  # input_tokens
            50    # output_tokens
        )

        # Mock DynamoDB query
        mock_aws_clients['table'].query.return_value = {
            'Items': []
        }

        # Mock DynamoDB put_item
        mock_aws_clients['table'].put_item.return_value = {}

        response = orchestrator.process_request(
            user_message='What is my credit score?',
            sender_id='919876543210',
            language='en'
        )

        assert hasattr(response, 'text') and hasattr(response, 'conversation_id')
        assert response.text == 'Hello! I can help you with that.'
        assert '919876543210' in response.conversation_id
        assert len(response.timestamp) > 0

    def test_process_request_with_error(self, mock_env, mock_aws_clients):
        """Test request processing with error"""
        orchestrator = BedrockOrchestrator()

        # Mock LLM adapter to raise error
        orchestrator.llm_adapter = Mock()
        orchestrator.llm_adapter.converse.side_effect = Exception('Bedrock error')

        # Mock DynamoDB query
        mock_aws_clients['table'].query.return_value = {
            'Items': []
        }

        response = orchestrator.process_request(
            user_message='Test message',
            sender_id='919876543210',
            language='en'
        )

        assert hasattr(response, 'text') and hasattr(response, 'conversation_id')
        # Should return a fallback response (not crash)
        assert len(response.text) > 0
        assert 'static_fallback' in response.actions_taken or 'llm_adapter_error' in response.actions_taken

    def test_decompose_task_ledger(self, mock_env, mock_aws_clients):
        """Test task decomposition for ledger request"""
        orchestrator = BedrockOrchestrator()

        subtasks = orchestrator.decompose_task(
            'Please process this ledger photo and calculate credit score'
        )

        assert len(subtasks) >= 1
        assert any('ledger' in task.description.lower() for task in subtasks)
        assert any('credit' in task.description.lower() for task in subtasks)

    def test_decompose_task_satellite(self, mock_env, mock_aws_clients):
        """Test task decomposition for satellite request"""
        orchestrator = BedrockOrchestrator()

        subtasks = orchestrator.decompose_task(
            'Show me satellite imagery for my field'
        )

        assert len(subtasks) >= 1
        assert any('satellite' in task.description.lower() for task in subtasks)

    def test_invoke_tool_document_processor(self, mock_env, mock_aws_clients):
        """Test tool invocation for document processor"""
        orchestrator = BedrockOrchestrator()

        mock_payload = Mock()
        mock_payload.read.return_value = json.dumps({
            'statusCode': 200,
            'body': json.dumps({
                'quantity': 100,
                'moisture': 12.5
            })
        }).encode('utf-8')

        mock_response = {'Payload': mock_payload}
        mock_aws_clients['lambda'].invoke.return_value = mock_response

        result = orchestrator.invoke_tool(
            'document_processor',
            {'image_url': 's3://bucket/image.jpg'}
        )

        assert hasattr(result, 'tool_name') and hasattr(result, 'status')
        assert result.status == 'success'
        assert result.tool_name == 'document_processor'
        assert result.data is not None

    def test_invoke_tool_unknown(self, mock_env, mock_aws_clients):
        """Test tool invocation with unknown tool"""
        orchestrator = BedrockOrchestrator()

        result = orchestrator.invoke_tool(
            'unknown_tool',
            {}
        )

        assert hasattr(result, 'tool_name') and hasattr(result, 'status')
        assert result.status == 'error'
        assert 'Unknown tool' in result.error

    def test_invoke_tool_error(self, mock_env, mock_aws_clients):
        """Test tool invocation with Lambda error"""
        orchestrator = BedrockOrchestrator()

        mock_aws_clients['lambda'].invoke.side_effect = Exception('Lambda error')

        result = orchestrator.invoke_tool(
            'document_processor',
            {}
        )

        assert hasattr(result, 'tool_name') and hasattr(result, 'status')
        assert result.status == 'error'
        assert result.error is not None

    def test_maintain_context_new_conversation(self, mock_env, mock_aws_clients):
        """Test context maintenance for new conversation"""
        orchestrator = BedrockOrchestrator()

        mock_aws_clients['table'].query.return_value = {
            'Items': []
        }
        mock_aws_clients['table'].put_item.return_value = {}

        message = Message(
            message_id='msg-123',
            sender_id='919876543210',
            content='Hello',
            timestamp=datetime.utcnow().isoformat(),
            language='en'
        )

        context = orchestrator.maintain_context(
            'CONV#919876543210#20260302',
            message
        )

        assert hasattr(context, 'conversation_id') and hasattr(context, 'farmer_id')
        assert context.conversation_id == 'CONV#919876543210#20260302'
        assert context.farmer_id == '919876543210'
        assert context.state['language'] == 'en'

        # Verify TTL attribute is set on the stored conversation item
        put_call = mock_aws_clients['table'].put_item.call_args
        item = put_call[1]['Item'] if 'Item' in put_call[1] else put_call[0][0]
        assert 'ttl' in item
        import time as _time
        expected_ttl_approx = int(_time.time()) + (30 * 24 * 60 * 60)
        # Allow 5 seconds tolerance
        assert abs(item['ttl'] - expected_ttl_approx) < 5

    def test_maintain_context_existing_conversation(self, mock_env, mock_aws_clients):
        """Test context maintenance for existing conversation"""
        orchestrator = BedrockOrchestrator()

        mock_aws_clients['table'].query.return_value = {
            'Items': [
                {
                    'PK': 'CONV#919876543210#20260302',
                    'SK': 'MSG#2026-03-02T10:00:00',
                    'content': 'Previous message',
                    'sender_id': '919876543210'
                }
            ]
        }
        mock_aws_clients['table'].put_item.return_value = {}

        message = Message(
            message_id='msg-124',
            sender_id='919876543210',
            content='Follow-up message',
            timestamp=datetime.utcnow().isoformat(),
            language='en'
        )

        context = orchestrator.maintain_context(
            'CONV#919876543210#20260302',
            message
        )

        assert hasattr(context, 'conversation_id') and hasattr(context, 'farmer_id')
        assert len(context.history) == 1
        assert context.history[0]['content'] == 'Previous message'

    def test_maintain_context_error_handling(self, mock_env, mock_aws_clients):
        """Test context maintenance with DynamoDB error"""
        orchestrator = BedrockOrchestrator()

        mock_aws_clients['table'].query.side_effect = Exception('DynamoDB error')

        message = Message(
            message_id='msg-125',
            sender_id='919876543210',
            content='Test message',
            timestamp=datetime.utcnow().isoformat(),
            language='en'
        )

        context = orchestrator.maintain_context(
            'CONV#919876543210#20260302',
            message
        )

        assert hasattr(context, 'conversation_id') and hasattr(context, 'farmer_id')
        assert context.farmer_id == '919876543210'
        assert len(context.history) == 0

    def test_store_conversation_includes_ttl(self, mock_env, mock_aws_clients):
        """Test that _store_conversation adds TTL to both user and assistant items"""
        orchestrator = BedrockOrchestrator()
        mock_aws_clients['table'].put_item.return_value = {}

        orchestrator._store_conversation(
            sender_id='919876543210',
            conversation_id='CONV-919876543210-20260302',
            user_message='Hello',
            response_text='Namaste!'
        )

        # Two put_item calls: user message + assistant response
        assert mock_aws_clients['table'].put_item.call_count == 2

        import time as _time
        expected_ttl_approx = int(_time.time()) + (30 * 24 * 60 * 60)

        for call in mock_aws_clients['table'].put_item.call_args_list:
            item = call[1]['Item'] if 'Item' in call[1] else call[0][0]
            assert 'ttl' in item, f"TTL missing from conversation item with role={item.get('role')}"
            assert abs(item['ttl'] - expected_ttl_approx) < 5


class TestGetOrchestrator:
    """Test module-level lazy-init helper for BedrockOrchestrator"""

    def setup_method(self):
        """Reset module-level _orchestrator before each test."""
        orchestrator_module._orchestrator = None

    def test_lazy_init_creates_instance(self, mock_env, mock_aws_clients):
        """get_orchestrator() creates a BedrockOrchestrator on first call."""
        result = get_orchestrator()
        assert result is not None
        assert type(result).__name__ == 'BedrockOrchestrator'

    def test_lazy_init_returns_same_instance(self, mock_env, mock_aws_clients):
        """get_orchestrator() returns the same instance on subsequent calls."""
        first = get_orchestrator()
        second = get_orchestrator()
        assert first is second

    def test_module_level_variable_starts_none(self, mock_env, mock_aws_clients):
        """_orchestrator is None before first call."""
        assert orchestrator_module._orchestrator is None
        get_orchestrator()
        assert orchestrator_module._orchestrator is not None


class TestLambdaHandler:
    """Test Lambda handler function"""

    def setup_method(self):
        """Reset module-level _orchestrator before each test."""
        orchestrator_module._orchestrator = None

    def test_handler_success(self, mock_env, mock_aws_clients):
        """Test successful handler execution"""
        with patch('orchestrator.LLMAdapter') as MockLLMAdapter, \
             patch('orchestrator.MetaWhatsAppInterface') as MockWhatsApp:
            mock_adapter = Mock()
            mock_adapter.converse.return_value = ('Response text', 50, 20)
            MockLLMAdapter.return_value = mock_adapter
            MockWhatsApp.return_value.send_text_response.return_value = True

            mock_aws_clients['table'].query.return_value = {'Items': []}
            mock_aws_clients['table'].put_item.return_value = {}

            event = {
                'sender_id': '919876543210',
                'message_text': 'What is my credit score?',
                'language': 'en'
            }

            response = handler(event, None)

            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert 'response_text' in body
            assert 'conversation_id' in body

    def test_handler_missing_parameters(self, mock_env, mock_aws_clients):
        """Test handler with missing parameters"""
        with patch('orchestrator.LLMAdapter') as MockLLMAdapter, \
             patch('orchestrator.MetaWhatsAppInterface') as MockWhatsApp:
            mock_adapter = Mock()
            mock_adapter.converse.return_value = ('Response text', 50, 20)
            MockLLMAdapter.return_value = mock_adapter
            MockWhatsApp.return_value.send_text_response.return_value = True

            mock_aws_clients['table'].query.return_value = {'Items': []}
            mock_aws_clients['table'].put_item.return_value = {}

            event = {}

            response = handler(event, None)

            assert response['statusCode'] in [200, 500]

    def test_handler_error(self, mock_env, mock_aws_clients):
        """Test handler with processing error"""
        with patch('orchestrator.LLMAdapter') as MockLLMAdapter, \
             patch('orchestrator.MetaWhatsAppInterface') as MockWhatsApp:
            mock_adapter = Mock()
            mock_adapter.converse.side_effect = Exception('Processing error')
            MockLLMAdapter.return_value = mock_adapter
            MockWhatsApp.return_value.send_text_response.return_value = True

            mock_aws_clients['table'].query.return_value = {'Items': []}

            event = {
                'sender_id': '919876543210',
                'message_text': 'Test message',
                'language': 'en'
            }

            response = handler(event, None)

            assert response['statusCode'] == 200  # Returns 200 with fallback message
            body = json.loads(response['body'])
            assert 'response_text' in body


class TestDataStructures:
    """Test data structure classes"""

    def test_message_creation(self):
        """Test Message dataclass"""
        message = Message(
            message_id='msg-123',
            sender_id='919876543210',
            content='Test message',
            timestamp='2026-03-02T10:00:00',
            language='en'
        )

        assert message.message_id == 'msg-123'
        assert message.sender_id == '919876543210'
        assert message.language == 'en'

    def test_subtask_creation(self):
        """Test SubTask dataclass"""
        subtask = SubTask(
            task_id='task-123',
            description='Process ledger',
            tool_name='document_processor',
            parameters={'image_url': 's3://bucket/image.jpg'},
            dependencies=[]
        )

        assert subtask.task_id == 'task-123'
        assert subtask.status == 'pending'
        assert subtask.tool_name == 'document_processor'

    def test_tool_result_creation(self):
        """Test ToolResult dataclass"""
        result = ToolResult(
            tool_name='document_processor',
            status='success',
            data={'quantity': 100}
        )

        assert result.tool_name == 'document_processor'
        assert result.status == 'success'
        assert result.error is None

    def test_response_creation(self):
        """Test Response dataclass"""
        response = Response(
            text='Response text',
            actions_taken=['reasoning', 'tool_invocation'],
            tool_calls=[],
            conversation_id='CONV#123',
            timestamp='2026-03-02T10:00:00'
        )

        assert response.text == 'Response text'
        assert len(response.actions_taken) == 2
        assert response.conversation_id == 'CONV#123'

    def test_conversation_context_creation(self):
        """Test ConversationContext dataclass"""
        context = ConversationContext(
            conversation_id='CONV#123',
            farmer_id='919876543210',
            history=[],
            state={'language': 'en'},
            last_updated='2026-03-02T10:00:00'
        )

        assert context.conversation_id == 'CONV#123'
        assert context.farmer_id == '919876543210'
        assert context.state['language'] == 'en'


class TestToolMapping:
    """Test tool name to Lambda function mapping"""

    def test_document_processor_mapping(self, mock_env, mock_aws_clients):
        """Test document processor tool mapping"""
        orchestrator = BedrockOrchestrator()

        mock_payload = Mock()
        mock_payload.read.return_value = json.dumps({}).encode('utf-8')
        mock_response = {'Payload': mock_payload}
        mock_aws_clients['lambda'].invoke.return_value = mock_response

        result1 = orchestrator.invoke_tool('document_processor', {})
        result2 = orchestrator.invoke_tool('textract', {})

        assert result1.status == 'success'
        assert result2.status == 'success'

    def test_voice_agent_mapping(self, mock_env, mock_aws_clients):
        """Test voice agent tool mapping"""
        orchestrator = BedrockOrchestrator()

        mock_payload = Mock()
        mock_payload.read.return_value = json.dumps({}).encode('utf-8')
        mock_response = {'Payload': mock_payload}
        mock_aws_clients['lambda'].invoke.return_value = mock_response

        result1 = orchestrator.invoke_tool('voice_agent', {})
        result2 = orchestrator.invoke_tool('transcribe', {})

        assert result1.status == 'success'
        assert result2.status == 'success'

    def test_satellite_analyzer_mapping(self, mock_env, mock_aws_clients):
        """Test satellite analyzer tool mapping"""
        orchestrator = BedrockOrchestrator()

        mock_payload = Mock()
        mock_payload.read.return_value = json.dumps({}).encode('utf-8')
        mock_response = {'Payload': mock_payload}
        mock_aws_clients['lambda'].invoke.return_value = mock_response

        result1 = orchestrator.invoke_tool('satellite_analyzer', {})
        result2 = orchestrator.invoke_tool('sagemaker', {})

        assert result1.status == 'success'
        assert result2.status == 'success'

    def test_credit_calculator_mapping(self, mock_env, mock_aws_clients):
        """Test credit calculator tool mapping"""
        orchestrator = BedrockOrchestrator()

        mock_payload = Mock()
        mock_payload.read.return_value = json.dumps({}).encode('utf-8')
        mock_response = {'Payload': mock_payload}
        mock_aws_clients['lambda'].invoke.return_value = mock_response

        result = orchestrator.invoke_tool('credit_calculator', {})

        assert result.status == 'success'
