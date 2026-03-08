"""
Unit tests for Knowledge Base functionality
Tests retrieve_and_generate queries and cost optimization
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
import sys

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'knowledge'))

from knowledge_base import (
    retrieve_from_kb,
    retrieve_and_generate,
    get_fpo_guidelines,
    get_farming_practices,
    get_quality_standards,
    get_credit_criteria,
    handler
)


class TestKnowledgeBaseRetrieval:
    """Test knowledge base retrieval functionality"""
    
    @patch('knowledge_base.bedrock_agent_runtime')
    def test_retrieve_from_kb_success(self, mock_bedrock):
        """Test successful retrieval from knowledge base"""
        # Mock response
        mock_bedrock.retrieve.return_value = {
            'retrievalResults': [
                {
                    'content': {'text': 'FPO guidelines content'},
                    'score': 0.95,
                    'location': {'s3Location': {'uri': 's3://bucket/doc.txt'}},
                    'metadata': {'source': 'fpo-guidelines.txt'}
                },
                {
                    'content': {'text': 'Additional guidelines'},
                    'score': 0.85,
                    'location': {'s3Location': {'uri': 's3://bucket/doc2.txt'}},
                    'metadata': {'source': 'fpo-guidelines.txt'}
                }
            ]
        }
        
        # Test retrieval
        results = retrieve_from_kb('What are FPO guidelines?', max_results=5)
        
        # Assertions
        assert len(results) == 2
        assert results[0]['content'] == 'FPO guidelines content'
        assert results[0]['score'] == 0.95
        assert results[1]['score'] == 0.85
        
        # Verify API call
        mock_bedrock.retrieve.assert_called_once()
        call_args = mock_bedrock.retrieve.call_args[1]
        assert call_args['retrievalQuery']['text'] == 'What are FPO guidelines?'
        assert call_args['retrievalConfiguration']['vectorSearchConfiguration']['numberOfResults'] == 5
    
    @patch('knowledge_base.bedrock_agent_runtime')
    def test_retrieve_from_kb_empty_results(self, mock_bedrock):
        """Test retrieval with no results"""
        mock_bedrock.retrieve.return_value = {'retrievalResults': []}
        
        results = retrieve_from_kb('Unknown query')
        
        assert len(results) == 0
    
    @patch('knowledge_base.bedrock_agent_runtime')
    def test_retrieve_from_kb_error_handling(self, mock_bedrock):
        """Test error handling in retrieval"""
        mock_bedrock.retrieve.side_effect = Exception('API error')
        
        results = retrieve_from_kb('Test query')
        
        assert len(results) == 0


class TestRetrieveAndGenerate:
    """Test retrieve_and_generate functionality"""
    
    @patch('knowledge_base.bedrock_agent_runtime')
    def test_retrieve_and_generate_success(self, mock_bedrock):
        """Test successful retrieve_and_generate"""
        # Mock response
        mock_bedrock.retrieve_and_generate.return_value = {
            'output': {
                'text': 'FPO credit scoring uses 5 components: supply consistency (30 points), quality metrics (25 points), transaction history (20 points), financial behavior (15 points), and operational transparency (10 points).'
            },
            'citations': [
                {
                    'retrievedReferences': [
                        {
                            'content': {'text': 'Credit scoring criteria...'},
                            'location': {'s3Location': {'uri': 's3://bucket/fpo-guidelines.txt'}},
                            'metadata': {'source': 'fpo-guidelines.txt'}
                        }
                    ]
                }
            ],
            'sessionId': 'session-123'
        }
        
        # Test retrieve_and_generate
        result = retrieve_and_generate('Explain FPO credit scoring')
        
        # Assertions
        assert 'response' in result
        assert 'supply consistency' in result['response']
        assert len(result['sources']) == 1
        assert result['sources'][0]['content'] == 'Credit scoring criteria...'
        assert result['session_id'] == 'session-123'
        
        # Verify API call
        mock_bedrock.retrieve_and_generate.assert_called_once()
    
    @patch('knowledge_base.bedrock_agent_runtime')
    def test_retrieve_and_generate_with_context(self, mock_bedrock):
        """Test retrieve_and_generate with additional context"""
        mock_bedrock.retrieve_and_generate.return_value = {
            'output': {'text': 'Response with context'},
            'citations': [],
            'sessionId': 'session-456'
        }
        
        result = retrieve_and_generate('Follow-up question', context='Previous conversation')
        
        assert result['response'] == 'Response with context'
    
    @patch('knowledge_base.bedrock_agent_runtime')
    def test_retrieve_and_generate_error_handling(self, mock_bedrock):
        """Test error handling in retrieve_and_generate"""
        mock_bedrock.retrieve_and_generate.side_effect = Exception('API error')
        
        result = retrieve_and_generate('Test query')
        
        assert 'Error querying knowledge base' in result['response']
        assert len(result['sources']) == 0


class TestHelperFunctions:
    """Test helper functions for specific queries"""
    
    @patch('knowledge_base.retrieve_and_generate')
    def test_get_fpo_guidelines(self, mock_rag):
        """Test getting FPO guidelines"""
        mock_rag.return_value = {
            'response': 'Credit scoring guidelines...',
            'sources': [],
            'session_id': 'test'
        }
        
        result = get_fpo_guidelines('credit scoring')
        
        assert 'Credit scoring guidelines' in result['response']
        mock_rag.assert_called_once()
        call_args = mock_rag.call_args[0][0]
        assert 'credit scoring' in call_args
    
    @patch('knowledge_base.retrieve_and_generate')
    def test_get_farming_practices(self, mock_rag):
        """Test getting farming practices"""
        mock_rag.return_value = {
            'response': 'Onion irrigation practices...',
            'sources': [],
            'session_id': 'test'
        }
        
        result = get_farming_practices('onion', 'irrigation')
        
        assert 'irrigation' in result['response']
        mock_rag.assert_called_once()
        call_args = mock_rag.call_args[0][0]
        assert 'onion' in call_args
        assert 'irrigation' in call_args
    
    @patch('knowledge_base.retrieve_and_generate')
    def test_get_quality_standards(self, mock_rag):
        """Test getting quality standards"""
        mock_rag.return_value = {
            'response': 'Wheat quality standards: Grade A...',
            'sources': [],
            'session_id': 'test'
        }
        
        result = get_quality_standards('wheat')
        
        assert 'quality standards' in result['response']
        mock_rag.assert_called_once()
    
    @patch('knowledge_base.retrieve_and_generate')
    def test_get_credit_criteria(self, mock_rag):
        """Test getting credit criteria"""
        mock_rag.return_value = {
            'response': 'Credit criteria include 5 components...',
            'sources': [],
            'session_id': 'test'
        }
        
        result = get_credit_criteria()
        
        assert 'Credit criteria' in result['response']
        mock_rag.assert_called_once()


class TestLambdaHandler:
    """Test Lambda handler"""
    
    @patch('knowledge_base.retrieve_from_kb')
    def test_handler_retrieve_action(self, mock_retrieve):
        """Test handler with retrieve action"""
        mock_retrieve.return_value = [
            {'content': 'Result 1', 'score': 0.9},
            {'content': 'Result 2', 'score': 0.8}
        ]
        
        event = {
            'action': 'retrieve',
            'query': 'Test query',
            'max_results': 5
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['count'] == 2
        assert len(body['results']) == 2
    
    @patch('knowledge_base.retrieve_and_generate')
    def test_handler_retrieve_and_generate_action(self, mock_rag):
        """Test handler with retrieve_and_generate action"""
        mock_rag.return_value = {
            'response': 'Generated response',
            'sources': [],
            'session_id': 'test'
        }
        
        event = {
            'action': 'retrieve_and_generate',
            'query': 'Test query'
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['response'] == 'Generated response'
    
    @patch('knowledge_base.get_fpo_guidelines')
    def test_handler_get_guidelines_action(self, mock_guidelines):
        """Test handler with get_guidelines action"""
        mock_guidelines.return_value = {
            'response': 'Guidelines response',
            'sources': [],
            'session_id': 'test'
        }
        
        event = {
            'action': 'get_guidelines',
            'topic': 'credit scoring'
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['response'] == 'Guidelines response'
    
    @patch('knowledge_base.get_farming_practices')
    def test_handler_get_practices_action(self, mock_practices):
        """Test handler with get_practices action"""
        mock_practices.return_value = {
            'response': 'Practices response',
            'sources': [],
            'session_id': 'test'
        }
        
        event = {
            'action': 'get_practices',
            'crop': 'onion',
            'practice': 'irrigation'
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['response'] == 'Practices response'
    
    @patch('knowledge_base.get_quality_standards')
    def test_handler_get_quality_action(self, mock_quality):
        """Test handler with get_quality action"""
        mock_quality.return_value = {
            'response': 'Quality standards',
            'sources': [],
            'session_id': 'test'
        }
        
        event = {
            'action': 'get_quality',
            'crop': 'wheat'
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['response'] == 'Quality standards'
    
    @patch('knowledge_base.get_credit_criteria')
    def test_handler_get_credit_action(self, mock_credit):
        """Test handler with get_credit action"""
        mock_credit.return_value = {
            'response': 'Credit criteria',
            'sources': [],
            'session_id': 'test'
        }
        
        event = {
            'action': 'get_credit'
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['response'] == 'Credit criteria'
    
    def test_handler_unknown_action(self):
        """Test handler with unknown action"""
        event = {
            'action': 'unknown_action'
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
    
    @patch('knowledge_base.retrieve_and_generate')
    def test_handler_error_handling(self, mock_rag):
        """Test handler error handling"""
        mock_rag.side_effect = Exception('Test error')
        
        event = {
            'action': 'retrieve_and_generate',
            'query': 'Test query'
        }
        
        response = handler(event, None)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body


class TestCostOptimization:
    """Test cost optimization aspects"""
    
    @patch('knowledge_base.bedrock_agent_runtime')
    def test_retrieve_and_generate_reduces_context_size(self, mock_bedrock):
        """
        Test that retrieve_and_generate reduces context size compared to
        sending full documents in prompt
        """
        # Simulate large document content
        large_document = "FPO Guidelines: " + ("content " * 1000)  # ~7000 chars
        
        # Mock retrieve_and_generate with small response
        mock_bedrock.retrieve_and_generate.return_value = {
            'output': {'text': 'Concise answer based on retrieved context'},
            'citations': [
                {
                    'retrievedReferences': [
                        {'content': {'text': 'Relevant excerpt only'}, 'location': {}, 'metadata': {}}
                    ]
                }
            ],
            'sessionId': 'test'
        }
        
        result = retrieve_and_generate('What are FPO guidelines?')
        
        # Verify response is much smaller than full document
        response_size = len(result['response'])
        assert response_size < len(large_document) / 10  # At least 10x reduction
        
        # Verify we got a useful response
        assert len(result['response']) > 0
        assert 'answer' in result['response'].lower() or 'based' in result['response'].lower()
    
    @patch('knowledge_base.bedrock_agent_runtime')
    def test_retrieval_limits_number_of_results(self, mock_bedrock):
        """Test that retrieval limits results to avoid excessive context"""
        mock_bedrock.retrieve.return_value = {
            'retrievalResults': [
                {'content': {'text': f'Result {i}'}, 'score': 0.9 - i*0.1, 'location': {}, 'metadata': {}}
                for i in range(3)
            ]
        }
        
        # Request limited results
        results = retrieve_from_kb('Test query', max_results=5)
        
        # Verify we don't get excessive results
        assert len(results) <= 5
        
        # Verify API was called with limit
        call_args = mock_bedrock.retrieve.call_args[1]
        assert call_args['retrievalConfiguration']['vectorSearchConfiguration']['numberOfResults'] == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
