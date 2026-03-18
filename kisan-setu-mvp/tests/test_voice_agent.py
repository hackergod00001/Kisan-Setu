"""
Unit tests for VoiceAgent component.

Tests cover:
- Audio transcription with language detection
- Text-to-speech synthesis
- Language detection
- Audio quality validation
- Error handling
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import os
import sys

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../lambda/voice'))

from voice_agent import VoiceAgent, TranscriptionResult


@pytest.fixture
def voice_agent():
    """Create VoiceAgent instance for testing with mocked AWS clients."""
    with patch('voice_agent.boto3') as mock_boto3:
        # Mock AWS clients
        mock_transcribe = Mock()
        mock_polly = Mock()
        mock_s3 = Mock()
        
        mock_boto3.client.side_effect = lambda service, **kwargs: {
            'transcribe': mock_transcribe,
            'polly': mock_polly,
            's3': mock_s3
        }[service]
        
        agent = VoiceAgent(
            s3_bucket_raw='test-raw-bucket',
            s3_bucket_processed='test-processed-bucket',
            region='ap-south-1'
        )
        
        # Store mocks for test access
        agent._mock_transcribe = mock_transcribe
        agent._mock_polly = mock_polly
        agent._mock_s3 = mock_s3
        
        yield agent


class TestVoiceAgentInitialization:
    """Test VoiceAgent initialization."""
    
    def test_initialization_with_valid_params(self, voice_agent):
        """Test VoiceAgent initializes correctly with valid parameters."""
        assert voice_agent.s3_bucket_raw == 'test-raw-bucket'
        assert voice_agent.s3_bucket_processed == 'test-processed-bucket'
        assert voice_agent.region == 'ap-south-1'
        assert voice_agent.transcribe is not None
        assert voice_agent.polly is not None
        assert voice_agent.s3 is not None
    
    def test_supported_languages(self, voice_agent):
        """Test that all required languages are supported."""
        assert 'hi-IN' in voice_agent.SUPPORTED_LANGUAGES
        assert 'mr-IN' in voice_agent.SUPPORTED_LANGUAGES
        assert 'ta-IN' in voice_agent.SUPPORTED_LANGUAGES
    
    def test_voice_mapping_exists(self, voice_agent):
        """Test that voice mapping exists for all supported languages."""
        for lang in voice_agent.SUPPORTED_LANGUAGES:
            assert lang in voice_agent.VOICE_MAPPING


class TestAudioFormatDetection:
    """Test audio format detection."""
    
    def test_detect_mp3_format(self, voice_agent):
        """Test MP3 format detection."""
        assert voice_agent._detect_audio_format('audio.mp3') == 'mp3'
        assert voice_agent._detect_audio_format('s3://bucket/audio.MP3') == 'mp3'
    
    def test_detect_mp4_format(self, voice_agent):
        """Test MP4 format detection."""
        assert voice_agent._detect_audio_format('audio.mp4') == 'mp4'
        assert voice_agent._detect_audio_format('audio.m4a') == 'mp4'
    
    def test_detect_wav_format(self, voice_agent):
        """Test WAV format detection."""
        assert voice_agent._detect_audio_format('audio.wav') == 'wav'
    
    def test_detect_other_formats(self, voice_agent):
        """Test other audio format detection."""
        assert voice_agent._detect_audio_format('audio.flac') == 'flac'
        assert voice_agent._detect_audio_format('audio.ogg') == 'ogg'
        assert voice_agent._detect_audio_format('audio.amr') == 'amr'
        assert voice_agent._detect_audio_format('audio.webm') == 'webm'
    
    def test_default_format_for_unknown(self, voice_agent):
        """Test default format for unknown extensions."""
        assert voice_agent._detect_audio_format('audio.unknown') == 'mp3'
        assert voice_agent._detect_audio_format('audio') == 'mp3'


class TestTranscribeAudio:
    """Test audio transcription functionality."""
    
    @patch('voice_agent.VoiceAgent._wait_for_transcription')
    def test_transcribe_audio_with_language_hint(self, mock_wait, voice_agent):
        """Test transcription with language hint."""
        # Mock transcription result
        mock_wait.return_value = TranscriptionResult(
            text='नमस्ते',
            detected_language='hi-IN',
            confidence=0.95,
            transcript_url='s3://bucket/transcript.json'
        )
        
        # Mock Transcribe client
        voice_agent.transcribe.start_transcription_job = Mock()
        
        result = voice_agent.transcribe_audio(
            's3://test-raw-bucket/audio.mp3',
            language_hint='hi-IN'
        )
        
        assert result.text == 'नमस्ते'
        assert result.detected_language == 'hi-IN'
        assert result.confidence == 0.95
        
        # Verify start_transcription_job was called with correct params
        call_args = voice_agent.transcribe.start_transcription_job.call_args[1]
        assert call_args['LanguageCode'] == 'hi-IN'
        assert 'IdentifyLanguage' not in call_args
    
    @patch('voice_agent.VoiceAgent._wait_for_transcription')
    def test_transcribe_audio_without_language_hint(self, mock_wait, voice_agent):
        """Test transcription with automatic language detection."""
        # Mock transcription result
        mock_wait.return_value = TranscriptionResult(
            text='नमस्कार',
            detected_language='mr-IN',
            confidence=0.92,
            transcript_url='s3://bucket/transcript.json'
        )
        
        # Mock Transcribe client
        voice_agent.transcribe.start_transcription_job = Mock()
        
        result = voice_agent.transcribe_audio('s3://test-raw-bucket/audio.mp3')
        
        assert result.detected_language == 'mr-IN'
        
        # Verify start_transcription_job was called with language identification
        call_args = voice_agent.transcribe.start_transcription_job.call_args[1]
        assert call_args['IdentifyLanguage'] is True
        assert call_args['LanguageOptions'] == voice_agent.TRANSCRIBE_LANGUAGE_OPTIONS
    
    @patch('voice_agent.VoiceAgent._wait_for_transcription')
    def test_transcribe_audio_low_confidence(self, mock_wait, voice_agent):
        """Test transcription with low confidence raises error."""
        # Mock low confidence result
        mock_wait.return_value = TranscriptionResult(
            text='unclear audio',
            detected_language='hi-IN',
            confidence=0.3,  # Below MIN_CONFIDENCE (0.6)
            transcript_url='s3://bucket/transcript.json'
        )
        
        # Mock Transcribe client
        voice_agent.transcribe.start_transcription_job = Mock()
        
        with pytest.raises(ValueError, match='Audio quality is too poor'):
            voice_agent.transcribe_audio('s3://test-raw-bucket/audio.mp3')
    
    def test_transcribe_audio_service_failure(self, voice_agent):
        """Test transcription handles service failures."""
        # Mock Transcribe client to raise exception
        voice_agent.transcribe.start_transcription_job = Mock(
            side_effect=Exception('Service unavailable')
        )
        
        with pytest.raises(RuntimeError, match='Service temporarily unavailable'):
            voice_agent.transcribe_audio('s3://test-raw-bucket/audio.mp3')


class TestSynthesizeSpeech:
    """Test text-to-speech synthesis functionality."""
    
    def test_synthesize_speech_hindi(self, voice_agent):
        """Test speech synthesis for Hindi."""
        # Mock Polly response
        mock_audio_stream = MagicMock()
        mock_audio_stream.read.return_value = b'fake audio data'
        
        voice_agent.polly.synthesize_speech = Mock(
            return_value={'AudioStream': mock_audio_stream}
        )
        
        # Mock S3 operations
        voice_agent.s3.put_object = Mock()
        voice_agent.s3.generate_presigned_url = Mock(
            return_value='https://s3.amazonaws.com/bucket/audio.mp3'
        )
        
        audio_url = voice_agent.synthesize_speech(
            text='नमस्ते',
            language='hi-IN'
        )
        
        assert audio_url.startswith('https://')
        
        # Verify Polly was called with correct parameters
        call_args = voice_agent.polly.synthesize_speech.call_args[1]
        assert call_args['Text'] == 'नमस्ते'
        assert call_args['LanguageCode'] == 'hi-IN'
        assert call_args['VoiceId'] == 'Aditi'
        assert call_args['Engine'] == 'neural'
    
    def test_synthesize_speech_marathi(self, voice_agent):
        """Test speech synthesis for Marathi."""
        # Mock Polly response
        mock_audio_stream = MagicMock()
        mock_audio_stream.read.return_value = b'fake audio data'
        
        voice_agent.polly.synthesize_speech = Mock(
            return_value={'AudioStream': mock_audio_stream}
        )
        
        # Mock S3 operations
        voice_agent.s3.put_object = Mock()
        voice_agent.s3.generate_presigned_url = Mock(
            return_value='https://s3.amazonaws.com/bucket/audio.mp3'
        )
        
        audio_url = voice_agent.synthesize_speech(
            text='नमस्कार',
            language='mr-IN'
        )
        
        assert audio_url is not None
    
    def test_synthesize_speech_tamil(self, voice_agent):
        """Test speech synthesis for Tamil."""
        # Mock Polly response
        mock_audio_stream = MagicMock()
        mock_audio_stream.read.return_value = b'fake audio data'
        
        voice_agent.polly.synthesize_speech = Mock(
            return_value={'AudioStream': mock_audio_stream}
        )
        
        # Mock S3 operations
        voice_agent.s3.put_object = Mock()
        voice_agent.s3.generate_presigned_url = Mock(
            return_value='https://s3.amazonaws.com/bucket/audio.mp3'
        )
        
        audio_url = voice_agent.synthesize_speech(
            text='வணக்கம்',
            language='ta-IN'
        )
        
        assert audio_url is not None
    
    def test_synthesize_speech_unsupported_language(self, voice_agent):
        """Test synthesis with unsupported language raises error."""
        with pytest.raises(ValueError, match='Service temporarily unavailable'):
            voice_agent.synthesize_speech(
                text='Hello',
                language='en-US'
            )
    
    def test_synthesize_speech_custom_voice(self, voice_agent):
        """Test synthesis with custom voice ID."""
        # Mock Polly response
        mock_audio_stream = MagicMock()
        mock_audio_stream.read.return_value = b'fake audio data'
        
        voice_agent.polly.synthesize_speech = Mock(
            return_value={'AudioStream': mock_audio_stream}
        )
        
        # Mock S3 operations
        voice_agent.s3.put_object = Mock()
        voice_agent.s3.generate_presigned_url = Mock(
            return_value='https://s3.amazonaws.com/bucket/audio.mp3'
        )
        
        audio_url = voice_agent.synthesize_speech(
            text='नमस्ते',
            language='hi-IN',
            voice_id='Raveena'
        )
        
        # Verify custom voice was used
        call_args = voice_agent.polly.synthesize_speech.call_args[1]
        assert call_args['VoiceId'] == 'Raveena'
    
    def test_synthesize_speech_service_failure(self, voice_agent):
        """Test synthesis handles service failures."""
        voice_agent.polly.synthesize_speech = Mock(
            side_effect=Exception('Service unavailable')
        )
        
        with pytest.raises(RuntimeError):
            voice_agent.synthesize_speech(
                text='नमस्ते',
                language='hi-IN'
            )


class TestDetectLanguage:
    """Test language detection functionality."""
    
    @patch('voice_agent.VoiceAgent.transcribe_audio')
    def test_detect_language_hindi(self, mock_transcribe, voice_agent):
        """Test language detection for Hindi."""
        mock_transcribe.return_value = TranscriptionResult(
            text='नमस्ते',
            detected_language='hi-IN',
            confidence=0.95,
            transcript_url='s3://bucket/transcript.json'
        )
        
        language = voice_agent.detect_language('s3://test-raw-bucket/audio.mp3')
        
        assert language == 'hi-IN'
        mock_transcribe.assert_called_once_with(
            's3://test-raw-bucket/audio.mp3',
            language_hint=None
        )
    
    @patch('voice_agent.VoiceAgent.transcribe_audio')
    def test_detect_language_marathi(self, mock_transcribe, voice_agent):
        """Test language detection for Marathi."""
        mock_transcribe.return_value = TranscriptionResult(
            text='नमस्कार',
            detected_language='mr-IN',
            confidence=0.92,
            transcript_url='s3://bucket/transcript.json'
        )
        
        language = voice_agent.detect_language('s3://test-raw-bucket/audio.mp3')
        
        assert language == 'mr-IN'
    
    @patch('voice_agent.VoiceAgent.transcribe_audio')
    def test_detect_language_tamil(self, mock_transcribe, voice_agent):
        """Test language detection for Tamil."""
        mock_transcribe.return_value = TranscriptionResult(
            text='வணக்கம்',
            detected_language='ta-IN',
            confidence=0.90,
            transcript_url='s3://bucket/transcript.json'
        )
        
        language = voice_agent.detect_language('s3://test-raw-bucket/audio.mp3')
        
        assert language == 'ta-IN'
    
    @patch('voice_agent.VoiceAgent.transcribe_audio')
    def test_detect_language_failure(self, mock_transcribe, voice_agent):
        """Test language detection handles failures."""
        mock_transcribe.side_effect = Exception('Transcription failed')
        
        with pytest.raises(RuntimeError, match='Failed to detect language'):
            voice_agent.detect_language('s3://test-raw-bucket/audio.mp3')


class TestAudioQualityValidation:
    """Test audio quality validation."""
    
    def test_validate_audio_quality_valid_file(self, voice_agent):
        """Test validation with valid audio file."""
        # Mock S3 head_object response
        voice_agent._mock_s3.head_object.return_value = {
            'ContentLength': 10000  # 10KB file
        }
        
        is_valid = voice_agent.validate_audio_quality(
            's3://test-raw-bucket/audio.mp3'
        )
        
        assert is_valid is True
    
    def test_validate_audio_quality_file_too_small(self, voice_agent):
        """Test validation rejects files that are too small."""
        # Mock S3 head_object response
        voice_agent._mock_s3.head_object.return_value = {
            'ContentLength': 500  # 500 bytes (< 1KB)
        }
        
        is_valid = voice_agent.validate_audio_quality(
            's3://test-raw-bucket/audio.mp3'
        )
        
        assert is_valid is False
    
    def test_validate_audio_quality_file_too_large(self, voice_agent):
        """Test validation rejects files that are too large."""
        # Mock S3 head_object response
        voice_agent._mock_s3.head_object.return_value = {
            'ContentLength': 101 * 1024 * 1024  # 101MB (> 100MB)
        }
        
        is_valid = voice_agent.validate_audio_quality(
            's3://test-raw-bucket/audio.mp3'
        )
        
        assert is_valid is False
    
    def test_validate_audio_quality_nonexistent_file(self, voice_agent):
        """Test validation handles nonexistent files."""
        # Mock S3 to raise exception
        voice_agent._mock_s3.head_object.side_effect = Exception('Not found')
        
        is_valid = voice_agent.validate_audio_quality(
            's3://test-raw-bucket/nonexistent.mp3'
        )
        
        assert is_valid is False


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_text_synthesis(self, voice_agent):
        """Test synthesis with empty text."""
        # Mock Polly response
        mock_audio_stream = MagicMock()
        mock_audio_stream.read.return_value = b''
        
        voice_agent.polly.synthesize_speech = Mock(
            return_value={'AudioStream': mock_audio_stream}
        )
        
        # Mock S3 operations
        voice_agent.s3.put_object = Mock()
        voice_agent.s3.generate_presigned_url = Mock(
            return_value='https://s3.amazonaws.com/bucket/audio.mp3'
        )
        
        # Should not raise error, but produce empty audio
        audio_url = voice_agent.synthesize_speech(
            text='',
            language='hi-IN'
        )
        
        assert audio_url is not None
    
    def test_very_long_text_synthesis(self, voice_agent):
        """Test synthesis with very long text."""
        # Mock Polly response
        mock_audio_stream = MagicMock()
        mock_audio_stream.read.return_value = b'fake audio data'
        
        voice_agent.polly.synthesize_speech = Mock(
            return_value={'AudioStream': mock_audio_stream}
        )
        
        # Mock S3 operations
        voice_agent.s3.put_object = Mock()
        voice_agent.s3.generate_presigned_url = Mock(
            return_value='https://s3.amazonaws.com/bucket/audio.mp3'
        )
        
        # Very long text (3000 characters)
        long_text = 'नमस्ते ' * 500
        
        audio_url = voice_agent.synthesize_speech(
            text=long_text,
            language='hi-IN'
        )
        
        assert audio_url is not None
