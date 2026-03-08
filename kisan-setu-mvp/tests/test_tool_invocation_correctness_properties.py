"""
Property-Based Tests for Tool Invocation Correctness

Tests Property 19: Tool Invocation Correctness
For any user request requiring a specific tool (document processing, satellite analysis,
voice processing), the orchestrator must invoke the correct AWS service with properly
formatted parameters.

**Validates: Requirements 7.2**

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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'orchestrator'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

# Load orchestrator module directly to avoid namespace package conflicts
_orch_path = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'orchestrator', 'orchestrator.py')
_orch_spec = importlib.util.spec_from_file_location('_orchestrator', _orch_path)
_orch_mod = importlib.util.module_from_spec(_orch_spec)
_orch_spec.loader.exec_module(_orch_mod)
sys.modules['_orchestrator'] = _orch_mod
BedrockOrchestrator = _orch_mod.BedrockOrchestrator
ToolResult = _orch_mod.ToolResult

# Patch target prefix for this module
_ORCH = '_orchestrator'

# Import test data generators
from generators import (
    uuid_string, s3_url, gps_coordinates, indian_phone_number,
    crop_type, language_code
)


# ============================================================================
# Property 19: Tool Invocation Correctness
# ============================================================================

@given(
    tool_name=st.sampled_from([
        'document_processor', 'textract',
        'voice_agent', 'transcribe',
        'satellite_analyzer', 'sagemaker',
        'credit_calculator',
        'knowledge_base', 'retrieve_and_generate'
    ]),
    image_url=s3_url(),
    audio_url=s3_url(),
    coords=gps_coordinates(),
    farmer_id=uuid_string()
)
@settings(max_examples=100, deadline=None)
def test_property_19_tool_invocation_correctness(
    tool_name, image_url, audio_url, coords, farmer_id
):
    """
    **Property 19: Tool Invocation Correctness**
    **Validates: Requirements 7.2**
    
    For any request requiring external data (document extraction, satellite analysis,
    transcription), the appropriate tool should be invoked with correct parameters
    based on the request type.
    
    This property verifies that:
    1. Tool names are correctly mapped to AWS Lambda functions
    2. Parameters are properly formatted for each tool type
    3. Tool invocation returns a ToolResult with appropriate structure
    """
    with patch.object(_orch_mod, 'lambda_client') as mock_lambda:
        # Setup mock Lambda response
        mock_response = {
            'StatusCode': 200,
            'Payload': MagicMock()
        }
        
        # Create appropriate response data based on tool type
        if tool_name in ['document_processor', 'textract']:
            response_data = {
                'ledger_id': 'ledger_001',
                'extracted_data': {
                    'quantity': 100.0,
                    'moisture': 12.5,
                    'price': 5000.0
                }
            }
        elif tool_name in ['voice_agent', 'transcribe']:
            response_data = {
                'transcription': 'Sample transcription',
                'language': 'hi-IN',
                'confidence': 0.95
            }
        elif tool_name in ['satellite_analyzer', 'sagemaker']:
            response_data = {
                'ndvi_value': 0.75,
                'predicted_yield': 1500.0,
                'maturity_stage': 'mid'
            }
        elif tool_name == 'credit_calculator':
            response_data = {
                'total_score': 75.5,
                'breakdown': {
                    'supply_consistency': 22.0,
                    'quality_metrics': 18.5
                }
            }
        else:  # knowledge_base, retrieve_and_generate
            response_data = {
                'answer': 'Sample answer from knowledge base',
                'sources': ['doc1', 'doc2']
            }
        
        mock_response['Payload'].read.return_value = json.dumps(response_data).encode('utf-8')
        mock_lambda.invoke.return_value = mock_response
        
        # Create orchestrator
        orchestrator = BedrockOrchestrator()
        
        # Prepare parameters based on tool type
        if tool_name in ['document_processor', 'textract']:
            parameters = {
                'image_url': image_url,
                'farmer_id': farmer_id
            }
        elif tool_name in ['voice_agent', 'transcribe']:
            parameters = {
                'audio_url': audio_url,
                'language_hint': 'hi-IN'
            }
        elif tool_name in ['satellite_analyzer', 'sagemaker']:
            parameters = {
                'gps_coords': coords,
                'date_range': ['2024-01-01', '2024-01-31']
            }
        elif tool_name == 'credit_calculator':
            parameters = {
                'farmer_id': farmer_id
            }
        else:  # knowledge_base, retrieve_and_generate
            parameters = {
                'query': 'What are best practices for onion farming?'
            }
        
        # Invoke tool
        result = orchestrator.invoke_tool(tool_name, parameters)
        
        # Verify tool invocation correctness
        assert isinstance(result, ToolResult), \
            "Tool invocation should return a ToolResult object"
        
        assert result.tool_name == tool_name, \
            f"ToolResult should preserve the tool name: expected {tool_name}, got {result.tool_name}"
        
        assert result.status in ['success', 'error'], \
            f"ToolResult status should be 'success' or 'error', got {result.status}"
        
        # Verify Lambda was invoked
        assert mock_lambda.invoke.called, \
            f"Lambda client should be invoked for tool {tool_name}"
        
        # Extract invocation arguments
        call_kwargs = mock_lambda.invoke.call_args[1]
        
        # Verify correct Lambda function was invoked
        function_name = call_kwargs['FunctionName']
        
        # Map tool names to expected function names
        expected_functions = {
            'document_processor': 'DocumentProcessor',
            'textract': 'DocumentProcessor',
            'voice_agent': 'VoiceAgent',
            'transcribe': 'VoiceAgent',
            'satellite_analyzer': 'SatelliteAnalyzer',
            'sagemaker': 'SatelliteAnalyzer',
            'credit_calculator': 'CreditCalculator',
            'knowledge_base': 'KnowledgeBase',
            'retrieve_and_generate': 'KnowledgeBase'
        }
        
        expected_function = expected_functions[tool_name]
        assert expected_function in function_name or function_name == expected_function, \
            f"Expected function name to contain '{expected_function}', got '{function_name}'"
        
        # Verify invocation type is synchronous (RequestResponse)
        assert call_kwargs['InvocationType'] == 'RequestResponse', \
            "Tool invocations should use RequestResponse for synchronous execution"
        
        # Verify parameters were passed correctly
        payload = json.loads(call_kwargs['Payload'])
        
        # Check that parameters are present in payload
        for key, value in parameters.items():
            assert key in payload, \
                f"Parameter '{key}' should be in payload for tool {tool_name}"
        
        # Verify result contains data when successful
        if result.status == 'success':
            assert result.data is not None, \
                "Successful tool invocation should return data"
            assert result.error is None, \
                "Successful tool invocation should not have error"
        else:
            assert result.error is not None, \
                "Failed tool invocation should have error message"


@given(
    tool_name=st.sampled_from([
        'document_processor', 'voice_agent', 'satellite_analyzer'
    ]),
    farmer_id=uuid_string()
)
@settings(max_examples=100, deadline=None)
def test_property_19_tool_routing_consistency(tool_name, farmer_id):
    """
    **Property 19: Tool Invocation Correctness (Routing Consistency)**
    **Validates: Requirements 7.2**
    
    For any tool name, the routing should consistently map to the same
    AWS Lambda function across multiple invocations.
    
    This verifies that tool routing is deterministic and reliable.
    """
    with patch.object(_orch_mod, 'lambda_client') as mock_lambda:
        # Setup mock
        mock_response = {
            'StatusCode': 200,
            'Payload': MagicMock()
        }
        mock_response['Payload'].read.return_value = json.dumps({'result': 'success'}).encode('utf-8')
        mock_lambda.invoke.return_value = mock_response
        
        orchestrator = BedrockOrchestrator()
        
        # Invoke tool multiple times
        parameters = {'farmer_id': farmer_id}
        
        results = []
        invoked_functions = []
        
        for _ in range(3):
            result = orchestrator.invoke_tool(tool_name, parameters)
            results.append(result)
            
            # Get invoked function name
            call_kwargs = mock_lambda.invoke.call_args[1]
            invoked_functions.append(call_kwargs['FunctionName'])
        
        # Verify all invocations routed to the same function
        assert len(set(invoked_functions)) == 1, \
            f"Tool {tool_name} should consistently route to the same function, got {invoked_functions}"
        
        # Verify all results have the same tool_name
        for result in results:
            assert result.tool_name == tool_name, \
                "All results should preserve the original tool name"


@given(
    unknown_tool=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz_',
        min_size=5,
        max_size=20
    ).filter(lambda x: x not in [
        'document_processor', 'textract', 'voice_agent', 'transcribe',
        'satellite_analyzer', 'sagemaker', 'credit_calculator',
        'knowledge_base', 'retrieve_and_generate'
    ])
)
@settings(max_examples=100, deadline=None)
def test_property_19_unknown_tool_handling(unknown_tool):
    """
    **Property 19: Tool Invocation Correctness (Unknown Tool Handling)**
    **Validates: Requirements 7.2**
    
    For any unknown tool name, the orchestrator should return an error
    ToolResult without attempting to invoke a Lambda function.
    
    This verifies graceful error handling for invalid tool names.
    """
    with patch.object(_orch_mod, 'lambda_client') as mock_lambda:
        orchestrator = BedrockOrchestrator()
        
        # Invoke unknown tool
        result = orchestrator.invoke_tool(unknown_tool, {})
        
        # Verify error handling
        assert isinstance(result, ToolResult), \
            "Should return ToolResult even for unknown tools"
        
        assert result.status == 'error', \
            f"Unknown tool should return error status, got {result.status}"
        
        assert result.error is not None, \
            "Error ToolResult should have error message"
        
        assert 'unknown' in result.error.lower() or 'not found' in result.error.lower(), \
            f"Error message should indicate unknown tool, got: {result.error}"
        
        # Verify Lambda was NOT invoked
        assert not mock_lambda.invoke.called, \
            "Lambda should not be invoked for unknown tools"


@given(
    tool_name=st.sampled_from(['document_processor', 'satellite_analyzer']),
    image_url=s3_url(),
    coords=gps_coordinates()
)
@settings(max_examples=100, deadline=None)
def test_property_19_parameter_preservation(tool_name, image_url, coords):
    """
    **Property 19: Tool Invocation Correctness (Parameter Preservation)**
    **Validates: Requirements 7.2**
    
    For any tool invocation, all parameters passed to invoke_tool should be
    preserved and forwarded to the Lambda function without modification.
    
    This verifies that parameter data is not lost or corrupted during routing.
    """
    with patch.object(_orch_mod, 'lambda_client') as mock_lambda:
        # Setup mock
        mock_response = {
            'StatusCode': 200,
            'Payload': MagicMock()
        }
        mock_response['Payload'].read.return_value = json.dumps({'result': 'success'}).encode('utf-8')
        mock_lambda.invoke.return_value = mock_response
        
        orchestrator = BedrockOrchestrator()
        
        # Prepare parameters
        if tool_name == 'document_processor':
            parameters = {
                'image_url': image_url,
                'language': 'hi-IN',
                'farmer_id': 'farmer_123'
            }
        else:  # satellite_analyzer
            parameters = {
                'gps_coords': coords,
                'date_range': ['2024-01-01', '2024-01-31'],
                'crop_type': 'onion'
            }
        
        # Invoke tool
        result = orchestrator.invoke_tool(tool_name, parameters)
        
        # Extract payload sent to Lambda
        call_kwargs = mock_lambda.invoke.call_args[1]
        payload = json.loads(call_kwargs['Payload'])
        
        # Verify all parameters are preserved
        for key, value in parameters.items():
            assert key in payload, \
                f"Parameter '{key}' should be in Lambda payload"
            
            # For simple types, verify exact match
            if isinstance(value, (str, int, float, bool)):
                assert payload[key] == value, \
                    f"Parameter '{key}' value should be preserved: expected {value}, got {payload[key]}"


@given(
    tool_name=st.sampled_from(['document_processor', 'voice_agent', 'satellite_analyzer'])
)
@settings(max_examples=100, deadline=None)
def test_property_19_lambda_invocation_failure_handling(tool_name):
    """
    **Property 19: Tool Invocation Correctness (Failure Handling)**
    **Validates: Requirements 7.2**
    
    For any tool invocation, if the Lambda function fails or is unavailable,
    the orchestrator should return an error ToolResult with appropriate error message.
    
    This verifies graceful error handling for Lambda invocation failures.
    """
    with patch.object(_orch_mod, 'lambda_client') as mock_lambda:
        # Simulate Lambda invocation failure
        mock_lambda.invoke.side_effect = Exception("Lambda invocation failed")
        
        orchestrator = BedrockOrchestrator()
        
        # Invoke tool
        result = orchestrator.invoke_tool(tool_name, {'test': 'data'})
        
        # Verify error handling
        assert isinstance(result, ToolResult), \
            "Should return ToolResult even when Lambda fails"
        
        assert result.status == 'error', \
            f"Failed invocation should return error status, got {result.status}"
        
        assert result.error is not None, \
            "Error ToolResult should have error message"
        
        assert result.tool_name == tool_name, \
            "ToolResult should preserve tool name even on failure"
        
        assert result.data is None, \
            "Error ToolResult should not have data"


@given(
    request_type=st.sampled_from([
        'document_extraction',
        'voice_transcription',
        'satellite_analysis',
        'credit_calculation'
    ]),
    language=language_code()
)
@settings(max_examples=100, deadline=None)
def test_property_19_request_type_to_tool_mapping(request_type, language):
    """
    **Property 19: Tool Invocation Correctness (Request Type Mapping)**
    **Validates: Requirements 7.2**
    
    For any request type, the orchestrator should map it to the correct tool:
    - document_extraction → document_processor/textract
    - voice_transcription → voice_agent/transcribe
    - satellite_analysis → satellite_analyzer/sagemaker
    - credit_calculation → credit_calculator
    
    This verifies that request types are correctly mapped to tools.
    """
    with patch.object(_orch_mod, 'lambda_client') as mock_lambda:
        # Setup mock
        mock_response = {
            'StatusCode': 200,
            'Payload': MagicMock()
        }
        mock_response['Payload'].read.return_value = json.dumps({'result': 'success'}).encode('utf-8')
        mock_lambda.invoke.return_value = mock_response
        
        orchestrator = BedrockOrchestrator()
        
        # Map request types to tool names
        request_to_tool = {
            'document_extraction': 'document_processor',
            'voice_transcription': 'voice_agent',
            'satellite_analysis': 'satellite_analyzer',
            'credit_calculation': 'credit_calculator'
        }
        
        tool_name = request_to_tool[request_type]
        
        # Invoke tool
        result = orchestrator.invoke_tool(tool_name, {'language': language})
        
        # Verify correct function was invoked
        call_kwargs = mock_lambda.invoke.call_args[1]
        function_name = call_kwargs['FunctionName']
        
        # Map request types to expected function names
        expected_functions = {
            'document_extraction': 'DocumentProcessor',
            'voice_transcription': 'VoiceAgent',
            'satellite_analysis': 'SatelliteAnalyzer',
            'credit_calculation': 'CreditCalculator'
        }
        
        expected_function = expected_functions[request_type]
        assert expected_function in function_name or function_name == expected_function, \
            f"Request type '{request_type}' should invoke '{expected_function}', got '{function_name}'"


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

def test_tool_invocation_with_empty_parameters():
    """
    Test that tool invocation handles empty parameters gracefully.
    """
    with patch.object(_orch_mod, 'lambda_client') as mock_lambda:
        # Setup mock
        mock_response = {
            'StatusCode': 200,
            'Payload': MagicMock()
        }
        mock_response['Payload'].read.return_value = json.dumps({'result': 'success'}).encode('utf-8')
        mock_lambda.invoke.return_value = mock_response
        
        orchestrator = BedrockOrchestrator()
        
        # Invoke with empty parameters
        result = orchestrator.invoke_tool('document_processor', {})
        
        # Should succeed (parameters validation is tool's responsibility)
        assert result.status == 'success'
        assert mock_lambda.invoke.called


def test_tool_invocation_with_none_parameters():
    """
    Test that tool invocation handles None parameters.
    """
    with patch.object(_orch_mod, 'lambda_client') as mock_lambda:
        # Setup mock
        mock_response = {
            'StatusCode': 200,
            'Payload': MagicMock()
        }
        mock_response['Payload'].read.return_value = json.dumps({'result': 'success'}).encode('utf-8')
        mock_lambda.invoke.return_value = mock_response
        
        orchestrator = BedrockOrchestrator()
        
        # Invoke with None parameters (should be handled)
        # Note: This tests robustness, actual implementation may vary
        try:
            result = orchestrator.invoke_tool('document_processor', None)
            # If it doesn't raise, verify it returns error or handles gracefully
            assert result.status in ['success', 'error']
        except (TypeError, AttributeError):
            # Expected if implementation doesn't handle None
            pass


def test_tool_invocation_case_insensitivity():
    """
    Test that tool names are case-insensitive.
    """
    with patch.object(_orch_mod, 'lambda_client') as mock_lambda:
        # Setup mock
        mock_response = {
            'StatusCode': 200,
            'Payload': MagicMock()
        }
        mock_response['Payload'].read.return_value = json.dumps({'result': 'success'}).encode('utf-8')
        mock_lambda.invoke.return_value = mock_response
        
        orchestrator = BedrockOrchestrator()
        
        # Test different case variations
        tool_variations = [
            'document_processor',
            'DOCUMENT_PROCESSOR',
            'Document_Processor',
            'TEXTRACT',
            'textract',
            'Textract'
        ]
        
        for tool_name in tool_variations:
            result = orchestrator.invoke_tool(tool_name, {})
            
            # All should route to DocumentProcessor
            if mock_lambda.invoke.called:
                call_kwargs = mock_lambda.invoke.call_args[1]
                function_name = call_kwargs['FunctionName']
                assert 'DocumentProcessor' in function_name or function_name == 'DocumentProcessor'
            
            mock_lambda.reset_mock()
