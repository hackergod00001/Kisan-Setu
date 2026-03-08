"""
Mock services for testing AWS integrations.

This module provides mock implementations of AWS services (WhatsApp, Textract,
Transcribe, Polly, SageMaker) to enable testing without actual AWS API calls.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import base64


class MockWhatsAppService:
    """
    Mock WhatsApp Business API for testing.
    
    Simulates message sending/receiving without actual WhatsApp integration.
    """
    
    def __init__(self):
        self.sent_messages = []
        self.received_messages = []
    
    def send_message(self, phone_number: str, message: str, message_type: str = 'text') -> Dict[str, Any]:
        """
        Mock sending a WhatsApp message.
        
        Args:
            phone_number: Recipient phone number
            message: Message content or URL
            message_type: 'text', 'voice', 'image', or 'document'
        
        Returns: Dict with success status and message_id
        """
        message_data = {
            'message_id': f"mock_msg_{len(self.sent_messages)}",
            'phone_number': phone_number,
            'message': message,
            'message_type': message_type,
            'timestamp': datetime.now().isoformat(),
            'status': 'sent'
        }
        self.sent_messages.append(message_data)
        
        return {
            'success': True,
            'message_id': message_data['message_id']
        }
    
    def receive_message(self, phone_number: str, message: str, message_type: str = 'text') -> Dict[str, Any]:
        """
        Mock receiving a WhatsApp message.
        
        Args:
            phone_number: Sender phone number
            message: Message content or URL
            message_type: 'text', 'voice', or 'image'
        
        Returns: Dict representing webhook payload
        """
        message_data = {
            'message_id': f"mock_received_{len(self.received_messages)}",
            'from': phone_number,
            'message': message,
            'message_type': message_type,
            'timestamp': datetime.now().isoformat()
        }
        self.received_messages.append(message_data)
        
        return {
            'entry': [{
                'changes': [{
                    'value': {
                        'messages': [message_data]
                    }
                }]
            }]
        }
    
    def get_sent_messages(self) -> List[Dict[str, Any]]:
        """Get all sent messages."""
        return self.sent_messages
    
    def get_received_messages(self) -> List[Dict[str, Any]]:
        """Get all received messages."""
        return self.received_messages
    
    def clear_messages(self):
        """Clear all message history."""
        self.sent_messages = []
        self.received_messages = []


class MockTextractService:
    """
    Mock Amazon Textract for testing document processing.
    
    Simulates OCR and document analysis without actual Textract API calls.
    """
    
    def __init__(self):
        self.processed_documents = []
    
    def analyze_document(self, image_url: str, queries: List[str], language: str = 'hi-IN') -> Dict[str, Any]:
        """
        Mock Textract document analysis with queries.
        
        Args:
            image_url: S3 URL to image
            queries: List of query strings to extract
            language: Document language
        
        Returns: Dict with extracted data and confidence scores
        """
        # Generate mock extraction results
        extraction_results = {}
        confidence_scores = {}
        
        for query in queries:
            # Simulate extraction with varying confidence
            if 'quantity' in query.lower():
                extraction_results['quantity'] = '100.5'
                confidence_scores['quantity'] = 0.92
            elif 'moisture' in query.lower():
                extraction_results['moisture'] = '12.5'
                confidence_scores['moisture'] = 0.88
            elif 'price' in query.lower():
                extraction_results['price'] = '5000'
                confidence_scores['price'] = 0.95
            elif 'date' in query.lower():
                extraction_results['date'] = '2024-01-15'
                confidence_scores['date'] = 0.65  # Low confidence
            elif 'farmer' in query.lower() or 'name' in query.lower():
                extraction_results['farmer_name'] = 'Ram Kumar'
                confidence_scores['farmer_name'] = 0.90
            elif 'crop' in query.lower():
                extraction_results['crop_type'] = 'onion'
                confidence_scores['crop_type'] = 0.87
        
        result = {
            'image_url': image_url,
            'language': language,
            'extracted_data': extraction_results,
            'confidence_scores': confidence_scores,
            'timestamp': datetime.now().isoformat()
        }
        
        self.processed_documents.append(result)
        return result
    
    def get_processed_documents(self) -> List[Dict[str, Any]]:
        """Get all processed documents."""
        return self.processed_documents
    
    def clear_history(self):
        """Clear processing history."""
        self.processed_documents = []


class MockTranscribeService:
    """
    Mock Amazon Transcribe for testing speech-to-text.
    
    Simulates audio transcription without actual Transcribe API calls.
    """
    
    def __init__(self):
        self.transcriptions = []
    
    def transcribe_audio(self, audio_url: str, language_code: str = 'hi-IN') -> Dict[str, Any]:
        """
        Mock audio transcription.
        
        Args:
            audio_url: S3 URL to audio file
            language_code: Language code (hi-IN, mr-IN, ta-IN)
        
        Returns: Dict with transcription text and confidence
        """
        # Generate mock transcription based on language
        transcriptions_by_language = {
            'hi-IN': 'मेरे खेत में फसल की स्थिति कैसी है',
            'mr-IN': 'माझ्या शेतातील पिकाची स्थिती कशी आहे',
            'ta-IN': 'என் வயலில் பயிர் நிலை எப்படி உள்ளது'
        }
        
        transcription_text = transcriptions_by_language.get(
            language_code,
            'What is the status of my crop'
        )
        
        result = {
            'audio_url': audio_url,
            'language_code': language_code,
            'transcription': transcription_text,
            'confidence': 0.94,
            'timestamp': datetime.now().isoformat()
        }
        
        self.transcriptions.append(result)
        return result
    
    def detect_language(self, audio_url: str) -> str:
        """
        Mock language detection from audio.
        
        Args:
            audio_url: S3 URL to audio file
        
        Returns: Detected language code
        """
        # Simulate language detection
        return 'hi-IN'
    
    def get_transcriptions(self) -> List[Dict[str, Any]]:
        """Get all transcriptions."""
        return self.transcriptions
    
    def clear_history(self):
        """Clear transcription history."""
        self.transcriptions = []


class MockPollyService:
    """
    Mock Amazon Polly for testing text-to-speech.
    
    Simulates speech synthesis without actual Polly API calls.
    """
    
    def __init__(self):
        self.synthesized_speech = []
    
    def synthesize_speech(self, text: str, language_code: str = 'hi-IN', voice_id: str = None) -> Dict[str, Any]:
        """
        Mock speech synthesis.
        
        Args:
            text: Text to convert to speech
            language_code: Language code
            voice_id: Voice ID (optional)
        
        Returns: Dict with audio URL and metadata
        """
        # Select voice based on language if not provided
        if not voice_id:
            voice_map = {
                'hi-IN': 'Aditi',
                'mr-IN': 'Aditi',
                'ta-IN': 'Aditi'
            }
            voice_id = voice_map.get(language_code, 'Aditi')
        
        # Generate mock audio URL
        audio_url = f"s3://kisan-setu-audio/mock_audio_{len(self.synthesized_speech)}.mp3"
        
        result = {
            'text': text,
            'language_code': language_code,
            'voice_id': voice_id,
            'audio_url': audio_url,
            'duration_seconds': len(text) * 0.1,  # Rough estimate
            'timestamp': datetime.now().isoformat()
        }
        
        self.synthesized_speech.append(result)
        return result
    
    def get_synthesized_speech(self) -> List[Dict[str, Any]]:
        """Get all synthesized speech."""
        return self.synthesized_speech
    
    def clear_history(self):
        """Clear synthesis history."""
        self.synthesized_speech = []


class MockSageMakerGeospatialService:
    """
    Mock SageMaker Geospatial for testing satellite analysis.
    
    Simulates satellite imagery retrieval and NDVI calculation without actual API calls.
    """
    
    def __init__(self):
        self.imagery_requests = []
        self.ndvi_calculations = []
    
    def get_satellite_imagery(self, gps_coords: tuple, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Mock satellite imagery retrieval.
        
        Args:
            gps_coords: Tuple of (latitude, longitude)
            start_date: Start date in ISO format
            end_date: End date in ISO format
        
        Returns: Dict with imagery metadata
        """
        latitude, longitude = gps_coords
        
        # Simulate imagery availability (90% success rate)
        import random
        available = random.random() > 0.1
        
        if available:
            result = {
                'gps_coords': gps_coords,
                'start_date': start_date,
                'end_date': end_date,
                'image_url': f"s3://kisan-setu-satellite/sentinel2_{latitude}_{longitude}.tif",
                'cloud_cover': random.uniform(0, 30),
                'acquisition_date': end_date,
                'available': True
            }
        else:
            result = {
                'gps_coords': gps_coords,
                'start_date': start_date,
                'end_date': end_date,
                'available': False,
                'reason': 'Cloud cover too high'
            }
        
        self.imagery_requests.append(result)
        return result
    
    def calculate_ndvi(self, image_url: str) -> Dict[str, Any]:
        """
        Mock NDVI calculation.
        
        Args:
            image_url: S3 URL to satellite image
        
        Returns: Dict with NDVI value and metadata
        """
        import random
        
        # Generate realistic NDVI value (0.2 to 0.9 for healthy vegetation)
        ndvi_value = random.uniform(0.2, 0.9)
        
        # Determine maturity stage based on NDVI
        if ndvi_value < 0.3:
            maturity_stage = 'early'
        elif ndvi_value < 0.5:
            maturity_stage = 'mid'
        elif ndvi_value < 0.7:
            maturity_stage = 'late'
        else:
            maturity_stage = 'harvest_ready'
        
        result = {
            'image_url': image_url,
            'ndvi_value': ndvi_value,
            'maturity_stage': maturity_stage,
            'confidence': random.uniform(0.85, 0.98),
            'timestamp': datetime.now().isoformat()
        }
        
        self.ndvi_calculations.append(result)
        return result
    
    def predict_yield(self, ndvi_history: List[float], crop_type: str) -> Dict[str, Any]:
        """
        Mock yield prediction.
        
        Args:
            ndvi_history: List of historical NDVI values
            crop_type: Type of crop
        
        Returns: Dict with yield prediction
        """
        import random
        
        # Base yield by crop type (kg per hectare)
        base_yields = {
            'onion': 25000,
            'wheat': 3000,
            'rice': 4000,
            'cotton': 2000
        }
        
        base_yield = base_yields.get(crop_type, 3000)
        
        # Adjust based on average NDVI
        avg_ndvi = sum(ndvi_history) / len(ndvi_history) if ndvi_history else 0.5
        yield_factor = avg_ndvi / 0.7  # 0.7 is optimal NDVI
        
        estimated_volume = base_yield * yield_factor
        margin = estimated_volume * 0.15  # 15% margin
        
        result = {
            'crop_type': crop_type,
            'estimated_volume': estimated_volume,
            'confidence_interval': (estimated_volume - margin, estimated_volume + margin),
            'avg_ndvi': avg_ndvi,
            'timestamp': datetime.now().isoformat()
        }
        
        return result
    
    def get_imagery_requests(self) -> List[Dict[str, Any]]:
        """Get all imagery requests."""
        return self.imagery_requests
    
    def get_ndvi_calculations(self) -> List[Dict[str, Any]]:
        """Get all NDVI calculations."""
        return self.ndvi_calculations
    
    def clear_history(self):
        """Clear all history."""
        self.imagery_requests = []
        self.ndvi_calculations = []


class MockBedrockService:
    """
    Mock AWS Bedrock for testing orchestration.
    
    Simulates Bedrock Agent responses without actual API calls.
    """
    
    def __init__(self):
        self.invocations = []
    
    def invoke_agent(self, agent_id: str, session_id: str, input_text: str) -> Dict[str, Any]:
        """
        Mock Bedrock Agent invocation.
        
        Args:
            agent_id: Bedrock agent ID
            session_id: Session ID for conversation
            input_text: User input text
        
        Returns: Dict with agent response
        """
        # Generate mock response based on input
        response_text = f"Mock response to: {input_text}"
        
        # Simulate tool calls based on keywords
        tool_calls = []
        if 'ledger' in input_text.lower() or 'image' in input_text.lower():
            tool_calls.append({'tool': 'textract', 'action': 'analyze_document'})
        if 'voice' in input_text.lower() or 'audio' in input_text.lower():
            tool_calls.append({'tool': 'transcribe', 'action': 'transcribe_audio'})
        if 'satellite' in input_text.lower() or 'ndvi' in input_text.lower():
            tool_calls.append({'tool': 'sagemaker', 'action': 'get_satellite_imagery'})
        
        result = {
            'agent_id': agent_id,
            'session_id': session_id,
            'input_text': input_text,
            'response_text': response_text,
            'tool_calls': tool_calls,
            'timestamp': datetime.now().isoformat()
        }
        
        self.invocations.append(result)
        return result
    
    def get_invocations(self) -> List[Dict[str, Any]]:
        """Get all agent invocations."""
        return self.invocations
    
    def clear_history(self):
        """Clear invocation history."""
        self.invocations = []


# ============================================================================
# Mock Service Factory
# ============================================================================

class MockServiceFactory:
    """
    Factory for creating and managing mock services.
    
    Provides a centralized way to access all mock services for testing.
    """
    
    def __init__(self):
        self.whatsapp = MockWhatsAppService()
        self.textract = MockTextractService()
        self.transcribe = MockTranscribeService()
        self.polly = MockPollyService()
        self.sagemaker = MockSageMakerGeospatialService()
        self.bedrock = MockBedrockService()
    
    def clear_all(self):
        """Clear all mock service histories."""
        self.whatsapp.clear_messages()
        self.textract.clear_history()
        self.transcribe.clear_history()
        self.polly.clear_history()
        self.sagemaker.clear_history()
        self.bedrock.clear_history()
    
    def get_all_activity(self) -> Dict[str, Any]:
        """
        Get activity summary from all services.
        
        Returns: Dict with counts of operations per service
        """
        return {
            'whatsapp': {
                'sent': len(self.whatsapp.sent_messages),
                'received': len(self.whatsapp.received_messages)
            },
            'textract': {
                'documents_processed': len(self.textract.processed_documents)
            },
            'transcribe': {
                'transcriptions': len(self.transcribe.transcriptions)
            },
            'polly': {
                'synthesized': len(self.polly.synthesized_speech)
            },
            'sagemaker': {
                'imagery_requests': len(self.sagemaker.imagery_requests),
                'ndvi_calculations': len(self.sagemaker.ndvi_calculations)
            },
            'bedrock': {
                'invocations': len(self.bedrock.invocations)
            }
        }
