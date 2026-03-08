"""
Knowledge Base Query Handler
Provides retrieve_and_generate functionality for cost-optimized information retrieval
"""

import json
import os
import boto3
from typing import Dict, List, Any, Optional

# Initialize clients
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name=os.environ.get('REGION', 'us-east-1'))

# Configuration
KB_ID = os.environ.get('KNOWLEDGE_BASE_ID', '')
MODEL_ARN = 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0'

def retrieve_from_kb(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieve relevant documents from Knowledge Base
    
    Args:
        query: Search query
        max_results: Maximum number of results to return
        
    Returns:
        List of retrieved documents with content and metadata
    """
    try:
        response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=KB_ID,
            retrievalQuery={
                'text': query
            },
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': max_results
                }
            }
        )
        
        results = []
        for result in response.get('retrievalResults', []):
            results.append({
                'content': result['content']['text'],
                'score': result.get('score', 0),
                'location': result.get('location', {}),
                'metadata': result.get('metadata', {})
            })
        
        return results
        
    except Exception as e:
        print(f"Error retrieving from KB: {e}")
        return []

def retrieve_and_generate(query: str, context: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve relevant information and generate response using Bedrock
    This is the cost-optimized alternative to long-context prompting
    
    Args:
        query: User query
        context: Optional additional context
        
    Returns:
        Dict with generated response and retrieved sources
    """
    try:
        # Build retrieval configuration
        retrieval_config = {
            'knowledgeBaseId': KB_ID,
            'modelArn': MODEL_ARN,
            'input': {
                'text': query
            }
        }
        
        # Add session configuration if context provided
        if context:
            retrieval_config['sessionConfiguration'] = {
                'kmsKeyArn': None
            }
        
        # Call retrieve_and_generate
        response = bedrock_agent_runtime.retrieve_and_generate(
            input={
                'text': query
            },
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': KB_ID,
                    'modelArn': MODEL_ARN
                }
            }
        )
        
        # Extract response
        output = response.get('output', {}).get('text', '')
        citations = response.get('citations', [])
        
        # Format citations
        sources = []
        for citation in citations:
            for reference in citation.get('retrievedReferences', []):
                sources.append({
                    'content': reference.get('content', {}).get('text', ''),
                    'location': reference.get('location', {}),
                    'metadata': reference.get('metadata', {})
                })
        
        return {
            'response': output,
            'sources': sources,
            'session_id': response.get('sessionId', '')
        }
        
    except Exception as e:
        print(f"Error in retrieve_and_generate: {e}")
        return {
            'response': f"Error querying knowledge base: {str(e)}",
            'sources': [],
            'session_id': ''
        }

def get_fpo_guidelines(topic: str) -> Dict[str, Any]:
    """
    Get FPO guidelines for a specific topic
    
    Args:
        topic: Topic to query (e.g., "credit scoring", "quality grades")
        
    Returns:
        Dict with guidelines and sources
    """
    query = f"What are the FPO guidelines for {topic}?"
    return retrieve_and_generate(query)

def get_farming_practices(crop: str, practice: str) -> Dict[str, Any]:
    """
    Get farming best practices for a specific crop and practice
    
    Args:
        crop: Crop name (e.g., "onion", "wheat", "rice")
        practice: Practice type (e.g., "irrigation", "fertilizer", "pest management")
        
    Returns:
        Dict with best practices and sources
    """
    query = f"What are the best practices for {practice} in {crop} farming?"
    return retrieve_and_generate(query)

def get_quality_standards(crop: str) -> Dict[str, Any]:
    """
    Get quality standards and grading criteria for a crop
    
    Args:
        crop: Crop name
        
    Returns:
        Dict with quality standards and sources
    """
    query = f"What are the quality standards and grading criteria for {crop}?"
    return retrieve_and_generate(query)

def get_credit_criteria() -> Dict[str, Any]:
    """
    Get credit scoring criteria and requirements
    
    Returns:
        Dict with credit criteria and sources
    """
    query = "What are the credit scoring criteria for farmers? Explain all components and their weightage."
    return retrieve_and_generate(query)

def handler(event, context):
    """
    Lambda handler for knowledge base queries
    
    Event format:
    {
        "action": "retrieve" | "retrieve_and_generate" | "get_guidelines" | "get_practices" | "get_quality" | "get_credit",
        "query": "user query",
        "topic": "topic for guidelines",
        "crop": "crop name",
        "practice": "practice type",
        "max_results": 5
    }
    """
    try:
        action = event.get('action', 'retrieve_and_generate')
        
        if action == 'retrieve':
            # Simple retrieval without generation
            query = event.get('query', '')
            max_results = event.get('max_results', 5)
            results = retrieve_from_kb(query, max_results)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'results': results,
                    'count': len(results)
                })
            }
            
        elif action == 'retrieve_and_generate':
            # Retrieve and generate response
            query = event.get('query', '')
            context = event.get('context')
            result = retrieve_and_generate(query, context)
            
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }
            
        elif action == 'get_guidelines':
            # Get FPO guidelines
            topic = event.get('topic', '')
            result = get_fpo_guidelines(topic)
            
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }
            
        elif action == 'get_practices':
            # Get farming practices
            crop = event.get('crop', '')
            practice = event.get('practice', '')
            result = get_farming_practices(crop, practice)
            
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }
            
        elif action == 'get_quality':
            # Get quality standards
            crop = event.get('crop', '')
            result = get_quality_standards(crop)
            
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }
            
        elif action == 'get_credit':
            # Get credit criteria
            result = get_credit_criteria()
            
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }
            
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': f'Unknown action: {action}'
                })
            }
            
    except Exception as e:
        print(f"Error in handler: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
