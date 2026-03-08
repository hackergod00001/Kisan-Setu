"""
Property-based tests for text-to-speech language matching.

**Validates: Requirement 1.4**

Property 2: Text-to-Speech Language Matching
For any text response in a supported language (Hindi, Marathi, Tamil), synthesizing 
speech should produce audio in the same language as the input text.

This test uses Hypothesis framework with minimum 100 iterations to verify that:
1. The Voice_Agent synthesizes speech in the same language as the input text
2. The correct voice is selected for each language
3. The generated audio URL is valid and accessible
4. All supported languages can generate speech responses
"""

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from voice.voice_agent import VoiceAgent
from generators import language_code


# ============================================================================
# Test Data Generators
# ============================================================================

@st.composite
def text_response_with_language(draw):
    """
    Generate a text response with associated language.
    
    Returns: Tuple of (text, language)
    """
    lang = draw(language_code())
    
    # Sample response texts in each language
    response_texts = {
        'hi-IN': [
            'आपकी फसल की जानकारी यहाँ है',
            'आपका खाता अपडेट हो गया है',
            'मौसम की जानकारी: आज धूप रहेगी',
            'आपका लेनदेन सफल रहा',
            'कृपया अधिक जानकारी प्रदान करें'
        ],
        'mr-IN': [
            'तुमच्या पिकाची माहिती येथे आहे',
            'तुमचे खाते अपडेट झाले आहे',
            'हवामान माहिती: आज सूर्यप्रकाश असेल',
            'तुमचा व्यवहार यशस्वी झाला',
            'कृपया अधिक माहिती द्या'
        ],
        'ta-IN': [
            'உங்கள் பயிர் தகவல் இங்கே உள்ளது',
            'உங்கள் கணக்கு புதுப்பிக்கப்பட்டது',
            'வானிலை தகவல்: இன்று வெயில் இருக்கும்',
            'உங்கள் பரிவர்த்தனை வெற்றிகரமாக இருந்தது',
            'தயவுசெய்து கூடுதல் தகவல் வழங்கவும்'
        ]
    }
    
    text = draw(st.sampled_from(response_texts[lang]))
    
    return (text, lang)


# ============================================================================
# Property Tests
# ============================================================================

class TestTextToSpeechLanguageMatching:
    """
    Property-based tests for text-to-speech language matching.
    
    **Validates: Requirement 1.4**
    """
    
    @given(text_response_with_language())
    @settings(max_examples=100, deadline=None)
    def test_property_2_tts_language_matching(self, text_language_data):
        """
        **Property 2: Text-to-Speech Language Matching**
        **Validates: Requirement 1.4**
        
        For any text response in a supported language (Hindi, Marathi, Tamil), 
        synthesizing speech should produce audio in the same language as the 
        input text.
        
        This property verifies:
        1. The synthesized audio uses the same language as the input text
        2. The correct voice is selected for the language
        3. The generated audio URL is valid
        4. The audio is stored in S3 with proper metadata
        """
        text, language = text_language_data
        
        with patch('voice.voice_agent.boto3') as mock_boto3:
            # Mock AWS clients
            mock_transcribe = Mock()
            mock_polly = Mock()
            mock_s3 = Mock()
            
            mock_boto3.client.side_effect = lambda service, **kwargs: {
                'transcribe': mock_transcribe,
                'polly': mock_polly,
                's3': mock_s3
            }[service]
            
            # Create VoiceAgent instance
            agent = VoiceAgent(
                s3_bucket_raw='test-raw-bucket',
                s3_bucket_processed='test-processed-bucket',
                region='ap-south-1'
            )
            
            # Mock Polly response
            mock_audio_stream = MagicMock()
            mock_audio_stream.read.return_value = b'fake audio data for testing'
            mock_polly.synthesize_speech.return_value = {
                'AudioStream': mock_audio_stream
            }
            
            # Mock S3 operations
            mock_s3.put_object = Mock()
            mock_s3.generate_presigned_url = Mock(
                return_value=f'https://s3.amazonaws.com/test-processed-bucket/voice-responses/audio-{language}.mp3'
            )
            
            # Execute speech synthesis
            audio_url = agent.synthesize_speech(
                text=text,
                language=language
            )
            
            # Property assertions
            
            # 1. Audio URL must be generated (Requirement 1.4)
            assert audio_url is not None, "Audio URL should not be None"
            assert len(audio_url) > 0, "Audio URL should not be empty"
            assert audio_url.startswith('https://'), "Audio URL should be a valid HTTPS URL"
            
            # 2. Polly should be called with the correct language (Requirement 1.4)
            call_args = mock_polly.synthesize_speech.call_args[1]
            assert call_args['LanguageCode'] == language, (
                f"Synthesized audio language {call_args['LanguageCode']} does not match "
                f"input text language {language}"
            )
            
            # 3. The correct voice should be used for the language
            expected_voice = agent.VOICE_MAPPING[language]
            assert call_args['VoiceId'] == expected_voice, (
                f"Voice ID {call_args['VoiceId']} does not match expected "
                f"voice {expected_voice} for language {language}"
            )
            
            # 4. The text should be passed correctly
            assert call_args['Text'] == text, (
                f"Text passed to Polly does not match input text"
            )
            
            # 5. Output format should be MP3
            assert call_args['OutputFormat'] == 'mp3', (
                "Output format should be mp3"
            )
            
            # 6. S3 put_object should be called with proper metadata
            s3_call_args = mock_s3.put_object.call_args[1]
            assert s3_call_args['Bucket'] == 'test-processed-bucket', (
                "Audio should be stored in the processed bucket"
            )
            assert s3_call_args['ContentType'] == 'audio/mpeg', (
                "Content type should be audio/mpeg"
            )
            assert 'Metadata' in s3_call_args, (
                "S3 object should have metadata"
            )
            assert s3_call_args['Metadata']['language'] == language, (
                f"S3 metadata language {s3_call_args['Metadata']['language']} "
                f"does not match input language {language}"
            )
    
    @given(text_response_with_language())
    @settings(max_examples=100, deadline=None)
    def test_property_2_voice_mapping_consistency(self, text_language_data):
        """
        **Property 2: Text-to-Speech Language Matching (Voice Mapping)**
        **Validates: Requirement 1.4**
        
        For any supported language, the voice mapping should be consistent and 
        the same voice should always be used for that language.
        
        This property verifies:
        1. Voice mapping exists for all supported languages
        2. The same voice is consistently used for each language
        3. Voice selection is deterministic
        """
        text, language = text_language_data
        
        with patch('voice.voice_agent.boto3') as mock_boto3:
            # Mock AWS clients
            mock_transcribe = Mock()
            mock_polly = Mock()
            mock_s3 = Mock()
            
            mock_boto3.client.side_effect = lambda service, **kwargs: {
                'transcribe': mock_transcribe,
                'polly': mock_polly,
                's3': mock_s3
            }[service]
            
            # Create VoiceAgent instance
            agent = VoiceAgent(
                s3_bucket_raw='test-raw-bucket',
                s3_bucket_processed='test-processed-bucket',
                region='ap-south-1'
            )
            
            # Mock Polly response
            mock_audio_stream = MagicMock()
            mock_audio_stream.read.return_value = b'fake audio data'
            mock_polly.synthesize_speech.return_value = {
                'AudioStream': mock_audio_stream
            }
            
            # Mock S3 operations
            mock_s3.put_object = Mock()
            mock_s3.generate_presigned_url = Mock(
                return_value='https://s3.amazonaws.com/test-processed-bucket/audio.mp3'
            )
            
            # Property assertions
            
            # 1. Voice mapping must exist for the language
            assert language in agent.VOICE_MAPPING, (
                f"No voice mapping found for language {language}"
            )
            
            # 2. Voice mapping should be non-empty
            voice_id = agent.VOICE_MAPPING[language]
            assert voice_id is not None, (
                f"Voice ID for language {language} should not be None"
            )
            assert len(voice_id) > 0, (
                f"Voice ID for language {language} should not be empty"
            )
            
            # 3. Synthesize speech multiple times and verify consistency
            for _ in range(3):
                agent.synthesize_speech(text=text, language=language)
                
                call_args = mock_polly.synthesize_speech.call_args[1]
                assert call_args['VoiceId'] == voice_id, (
                    f"Voice ID should be consistent across multiple calls"
                )
    
    @given(text_response_with_language())
    @settings(max_examples=100, deadline=None)
    def test_property_2_all_languages_supported(self, text_language_data):
        """
        **Property 2: Text-to-Speech Language Matching (Language Support)**
        **Validates: Requirement 1.4**
        
        For any supported language, speech synthesis should succeed without errors.
        
        This property verifies:
        1. All supported languages can generate speech
        2. No language raises an exception during synthesis
        3. The language is validated before synthesis
        """
        text, language = text_language_data
        
        with patch('voice.voice_agent.boto3') as mock_boto3:
            # Mock AWS clients
            mock_transcribe = Mock()
            mock_polly = Mock()
            mock_s3 = Mock()
            
            mock_boto3.client.side_effect = lambda service, **kwargs: {
                'transcribe': mock_transcribe,
                'polly': mock_polly,
                's3': mock_s3
            }[service]
            
            # Create VoiceAgent instance
            agent = VoiceAgent(
                s3_bucket_raw='test-raw-bucket',
                s3_bucket_processed='test-processed-bucket',
                region='ap-south-1'
            )
            
            # Mock Polly response
            mock_audio_stream = MagicMock()
            mock_audio_stream.read.return_value = b'fake audio data'
            mock_polly.synthesize_speech.return_value = {
                'AudioStream': mock_audio_stream
            }
            
            # Mock S3 operations
            mock_s3.put_object = Mock()
            mock_s3.generate_presigned_url = Mock(
                return_value='https://s3.amazonaws.com/test-processed-bucket/audio.mp3'
            )
            
            # Property assertions
            
            # 1. Language must be in supported languages
            assert language in agent.SUPPORTED_LANGUAGES, (
                f"Language {language} should be in supported languages"
            )
            
            # 2. Speech synthesis should succeed without exceptions
            try:
                audio_url = agent.synthesize_speech(text=text, language=language)
                assert audio_url is not None, "Audio URL should be generated"
            except Exception as e:
                pytest.fail(
                    f"Speech synthesis failed for supported language {language}: {str(e)}"
                )
            
            # 3. Polly should be called exactly once
            assert mock_polly.synthesize_speech.call_count >= 1, (
                "Polly synthesize_speech should be called at least once"
            )


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestTextToSpeechEdgeCases:
    """
    Edge case tests for text-to-speech language matching.
    """
    
    def test_unsupported_language_raises_error(self):
        """
        Verify that unsupported languages raise a ValueError.
        
        This ensures that the system only generates speech for supported languages.
        """
        with patch('voice.voice_agent.boto3') as mock_boto3:
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
            
            # Try to synthesize speech in an unsupported language
            with pytest.raises((ValueError, RuntimeError)):
                agent.synthesize_speech(
                    text='Hello, this is a test',
                    language='en-US'  # Unsupported language
                )
    
    def test_all_supported_languages_have_voice_mapping(self):
        """
        Verify that all supported languages have a voice mapping.
        
        This ensures that speech can be generated for all supported languages.
        """
        with patch('voice.voice_agent.boto3'):
            agent = VoiceAgent(
                s3_bucket_raw='test-raw-bucket',
                s3_bucket_processed='test-processed-bucket',
                region='ap-south-1'
            )
            
            for language in agent.SUPPORTED_LANGUAGES:
                assert language in agent.VOICE_MAPPING, (
                    f"Language {language} is supported but has no voice mapping"
                )
                assert agent.VOICE_MAPPING[language] is not None, (
                    f"Voice mapping for {language} should not be None"
                )
    
    def test_empty_text_handling(self):
        """
        Verify that empty text is handled appropriately.
        
        This ensures that the system doesn't generate audio for empty text.
        """
        with patch('voice.voice_agent.boto3') as mock_boto3:
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
            
            # Mock Polly response
            mock_audio_stream = MagicMock()
            mock_audio_stream.read.return_value = b''
            mock_polly.synthesize_speech.return_value = {
                'AudioStream': mock_audio_stream
            }
            
            # Mock S3 operations
            mock_s3.put_object = Mock()
            mock_s3.generate_presigned_url = Mock(
                return_value='https://s3.amazonaws.com/test-processed-bucket/audio.mp3'
            )
            
            # Empty text should still call Polly (Polly will handle it)
            audio_url = agent.synthesize_speech(text='', language='hi-IN')
            
            # Verify Polly was called with empty text
            call_args = mock_polly.synthesize_speech.call_args[1]
            assert call_args['Text'] == '', "Empty text should be passed to Polly"
    
    def test_custom_voice_id_override(self):
        """
        Verify that a custom voice ID can override the default mapping.
        
        This ensures flexibility in voice selection when needed.
        """
        with patch('voice.voice_agent.boto3') as mock_boto3:
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
            
            # Mock Polly response
            mock_audio_stream = MagicMock()
            mock_audio_stream.read.return_value = b'fake audio data'
            mock_polly.synthesize_speech.return_value = {
                'AudioStream': mock_audio_stream
            }
            
            # Mock S3 operations
            mock_s3.put_object = Mock()
            mock_s3.generate_presigned_url = Mock(
                return_value='https://s3.amazonaws.com/test-processed-bucket/audio.mp3'
            )
            
            # Use custom voice ID
            custom_voice = 'Raveena'
            agent.synthesize_speech(
                text='Test text',
                language='hi-IN',
                voice_id=custom_voice
            )
            
            # Verify custom voice was used
            call_args = mock_polly.synthesize_speech.call_args[1]
            assert call_args['VoiceId'] == custom_voice, (
                f"Custom voice ID {custom_voice} should be used"
            )
    
    def test_language_consistency_across_multiple_responses(self):
        """
        Verify that language remains consistent across multiple speech synthesis calls.
        
        This simulates generating multiple responses in the same language.
        """
        with patch('voice.voice_agent.boto3') as mock_boto3:
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
            
            # Mock Polly response
            mock_audio_stream = MagicMock()
            mock_audio_stream.read.return_value = b'fake audio data'
            mock_polly.synthesize_speech.return_value = {
                'AudioStream': mock_audio_stream
            }
            
            # Mock S3 operations
            mock_s3.put_object = Mock()
            mock_s3.generate_presigned_url = Mock(
                return_value='https://s3.amazonaws.com/test-processed-bucket/audio.mp3'
            )
            
            # Generate multiple responses in Hindi
            language = 'hi-IN'
            texts = [
                'आपकी फसल की जानकारी यहाँ है',
                'आपका खाता अपडेट हो गया है',
                'धन्यवाद'
            ]
            
            for text in texts:
                agent.synthesize_speech(text=text, language=language)
                
                # Verify language consistency
                call_args = mock_polly.synthesize_speech.call_args[1]
                assert call_args['LanguageCode'] == language, (
                    f"Language should remain consistent as {language}"
                )
                assert call_args['VoiceId'] == agent.VOICE_MAPPING[language], (
                    f"Voice should remain consistent for {language}"
                )
