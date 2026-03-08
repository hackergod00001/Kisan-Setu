"""
Integration tests for Voice Handler Lambda.

Tests the Lambda handler function that orchestrates VoiceAgent operations.
"""

import pytest
import json
import os
import sys
import importlib
import importlib.util
from unittest.mock import Mock, patch, MagicMock

# Add lambda directory to path
_voice_dir = os.path.join(os.path.dirname(__file__), '../lambda/voice')
sys.path.insert(0, _voice_dir)


def _load_voice_module():
    """Load voice.py as a fresh module, avoiding name conflicts with the voice package."""
    voice_path = os.path.join(_voice_dir, 'voice.py')
    spec = importlib.util.spec_from_file_location('_voice_handler', voice_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestVoiceHandlerLambda:
    """Test Voice Handler Lambda function."""

    @patch.dict(os.environ, {
        'S3_BUCKET_RAW': 'test-raw-bucket',
        'S3_BUCKET_PROCESSED': 'test-processed-bucket',
        'REGION': 'ap-south-1'
    })
    def test_transcribe_action(self):
        """Test transcribe action."""
        with patch('voice_agent.boto3'):
            voice = _load_voice_module()
            from voice_agent import TranscriptionResult

            mock_result = TranscriptionResult(
                text='नमस्ते',
                detected_language='hi-IN',
                confidence=0.95,
                transcript_url='s3://bucket/transcript.json'
            )

            with patch.object(voice.voice_agent, 'transcribe_audio', return_value=mock_result):
                event = {
                    'action': 'transcribe',
                    'audio_url': 's3://test-raw-bucket/audio.mp3',
                    'language': 'hi-IN'
                }
                response = voice.handler(event, None)

            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['action'] == 'transcribe'
            assert body['text'] == 'नमस्ते'
            assert body['detected_language'] == 'hi-IN'
            assert body['confidence'] == 0.95

    @patch.dict(os.environ, {
        'S3_BUCKET_RAW': 'test-raw-bucket',
        'S3_BUCKET_PROCESSED': 'test-processed-bucket',
        'REGION': 'ap-south-1'
    })
    def test_synthesize_action(self):
        """Test synthesize action."""
        with patch('voice_agent.boto3'):
            voice = _load_voice_module()

            with patch.object(voice.voice_agent, 'synthesize_speech', return_value='https://s3.amazonaws.com/bucket/audio.mp3'):
                event = {
                    'action': 'synthesize',
                    'text': 'नमस्ते',
                    'language': 'hi-IN'
                }
                response = voice.handler(event, None)

            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['action'] == 'synthesize'
            assert body['audio_url'] == 'https://s3.amazonaws.com/bucket/audio.mp3'
            assert body['language'] == 'hi-IN'

    @patch.dict(os.environ, {
        'S3_BUCKET_RAW': 'test-raw-bucket',
        'S3_BUCKET_PROCESSED': 'test-processed-bucket',
        'REGION': 'ap-south-1'
    })
    def test_detect_language_action(self):
        """Test detect_language action."""
        with patch('voice_agent.boto3'):
            voice = _load_voice_module()

            with patch.object(voice.voice_agent, 'detect_language', return_value='mr-IN'):
                event = {
                    'action': 'detect_language',
                    'audio_url': 's3://test-raw-bucket/audio.mp3'
                }
                response = voice.handler(event, None)

            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['action'] == 'detect_language'
            assert body['detected_language'] == 'mr-IN'

    @patch.dict(os.environ, {
        'S3_BUCKET_RAW': 'test-raw-bucket',
        'S3_BUCKET_PROCESSED': 'test-processed-bucket',
        'REGION': 'ap-south-1'
    })
    def test_unknown_action(self):
        """Test unknown action returns error."""
        with patch('voice_agent.boto3'):
            voice = _load_voice_module()

            event = {'action': 'unknown_action'}
            response = voice.handler(event, None)

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Unknown action' in body['error']
        assert 'supported_actions' in body

    @patch.dict(os.environ, {
        'S3_BUCKET_RAW': 'test-raw-bucket',
        'S3_BUCKET_PROCESSED': 'test-processed-bucket',
        'REGION': 'ap-south-1'
    })
    def test_validation_error_handling(self):
        """Test validation error handling."""
        with patch('voice_agent.boto3'):
            voice = _load_voice_module()

            with patch.object(voice.voice_agent, 'transcribe_audio', side_effect=ValueError('Audio quality too poor')):
                event = {
                    'action': 'transcribe',
                    'audio_url': 's3://test-raw-bucket/audio.mp3'
                }
                response = voice.handler(event, None)

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] == 'Audio quality too poor'
        assert body['error_type'] == 'validation_error'

    @patch.dict(os.environ, {
        'S3_BUCKET_RAW': 'test-raw-bucket',
        'S3_BUCKET_PROCESSED': 'test-processed-bucket',
        'REGION': 'ap-south-1'
    })
    def test_runtime_error_handling(self):
        """Test runtime error handling."""
        with patch('voice_agent.boto3'):
            voice = _load_voice_module()

            with patch.object(voice.voice_agent, 'synthesize_speech', side_effect=RuntimeError('Service unavailable')):
                event = {
                    'action': 'synthesize',
                    'text': 'नमस्ते',
                    'language': 'hi-IN'
                }
                response = voice.handler(event, None)

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['error'] == 'Service unavailable'
        assert body['error_type'] == 'service_error'

    @patch.dict(os.environ, {
        'S3_BUCKET_RAW': 'test-raw-bucket',
        'S3_BUCKET_PROCESSED': 'test-processed-bucket',
        'REGION': 'ap-south-1'
    })
    def test_unexpected_error_handling(self):
        """Test unexpected error handling."""
        with patch('voice_agent.boto3'):
            voice = _load_voice_module()

            with patch.object(voice.voice_agent, 'transcribe_audio', side_effect=Exception('Unexpected error')):
                event = {
                    'action': 'transcribe',
                    'audio_url': 's3://test-raw-bucket/audio.mp3'
                }
                response = voice.handler(event, None)

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['error'] == 'An unexpected error occurred'
        assert body['error_type'] == 'internal_error'

    @patch.dict(os.environ, {
        'S3_BUCKET_RAW': 'test-raw-bucket',
        'S3_BUCKET_PROCESSED': 'test-processed-bucket',
        'REGION': 'ap-south-1'
    })
    def test_synthesize_with_custom_voice(self):
        """Test synthesize with custom voice ID."""
        with patch('voice_agent.boto3'):
            voice = _load_voice_module()

            with patch.object(voice.voice_agent, 'synthesize_speech', return_value='https://s3.amazonaws.com/bucket/audio.mp3') as mock_synth:
                event = {
                    'action': 'synthesize',
                    'text': 'नमस्ते',
                    'language': 'hi-IN',
                    'voice_id': 'Raveena'
                }
                response = voice.handler(event, None)

            assert response['statusCode'] == 200
            mock_synth.assert_called_once_with(
                'नमस्ते',
                'hi-IN',
                'Raveena'
            )
