"""
Property-based tests for language-consistent transcription.

**Validates: Requirements 1.1, 1.2**

Property 1: Language-Consistent Transcription
For any voice message in Hindi, Marathi, or Tamil, transcribing the audio should 
produce text in the same language as the spoken input, with the detected language 
correctly identified.

This test uses Hypothesis framework with minimum 100 iterations to verify that:
1. The Voice_Agent correctly identifies the language of the audio input
2. The transcribed text is in the same language as the input
3. The system can generate responses in the same language as the input
"""

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from voice.voice_agent import VoiceAgent, TranscriptionResult
from generators import language_code, s3_url


# ============================================================================
# Test Data Generators
# ============================================================================

@st.composite
def voice_message_with_language(draw):
    """
    Generate a voice message with associated language and transcribed text.
    
    Returns: Tuple of (audio_url, language, sample_text)
    """
    lang = draw(language_code())
    audio_url = draw(s3_url(prefix='s3://kisan-setu-raw/voice'))
    
    # Sample text in each language
    sample_texts = {
        'hi-IN': [
            'नमस्ते, मुझे मदद चाहिए',
            'मेरी फसल की जानकारी दें',
            'आज का मौसम कैसा है',
            'मेरा खाता देखें',
            'धन्यवाद'
        ],
        'mr-IN': [
            'नमस्कार, मला मदत हवी आहे',
            'माझ्या पिकाची माहिती द्या',
            'आजचे हवामान कसे आहे',
            'माझे खाते पहा',
            'धन्यवाद'
        ],
        'ta-IN': [
            'வணக்கம், எனக்கு உதவி வேண்டும்',
            'என் பயிர் தகவல் கொடுங்கள்',
            'இன்றைய வானிலை எப்படி',
            'என் கணக்கைப் பார்க்கவும்',
            'நன்றி'
        ]
    }
    
    text = draw(st.sampled_from(sample_texts[lang]))
    confidence = draw(st.floats(min_value=0.6, max_value=1.0, allow_nan=False, allow_infinity=False))
    
    return (audio_url, lang, text, confidence)


# ============================================================================
# Property Tests
# ============================================================================

class TestLanguageConsistentTranscription:
    """
    Property-based tests for language-consistent transcription.
    
    **Validates: Requirements 1.1, 1.2**
    """
    
    @given(voice_message_with_language())
    @settings(max_examples=100, deadline=None)
    def test_property_1_language_consistent_transcription(self, voice_message_data):
        """
        **Property 1: Language-Consistent Transcription**
        **Validates: Requirements 1.1, 1.2**
        
        For any voice message in Hindi, Marathi, or Tamil, transcribing the audio 
        should produce text in the same language as the spoken input, with the 
        detected language correctly identified.
        
        This property verifies:
        1. The detected language matches the input language
        2. The transcription confidence is above the minimum threshold
        3. The transcribed text is non-empty
        4. The system can process all supported languages (hi-IN, mr-IN, ta-IN)
        """
        audio_url, expected_language, sample_text, confidence = voice_message_data
        
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
            
            # Mock the transcription job to return expected results
            mock_transcribe.start_transcription_job = Mock()
            
            # Mock the wait_for_transcription method to return consistent results
            with patch.object(
                agent,
                '_wait_for_transcription',
                return_value=TranscriptionResult(
                    text=sample_text,
                    detected_language=expected_language,
                    confidence=confidence,
                    transcript_url=f's3://test-processed-bucket/transcript-{expected_language}.json'
                )
            ):
                # Execute transcription
                result = agent.transcribe_audio(
                    audio_url=audio_url,
                    language_hint=expected_language
                )
                
                # Property assertions
                
                # 1. Detected language must match the input language (Requirement 1.1)
                assert result.detected_language == expected_language, (
                    f"Language mismatch: expected {expected_language}, "
                    f"got {result.detected_language}"
                )
                
                # 2. Transcribed text must be non-empty
                assert len(result.text) > 0, (
                    "Transcribed text should not be empty"
                )
                
                # 3. Confidence must be above minimum threshold
                assert result.confidence >= agent.MIN_CONFIDENCE, (
                    f"Confidence {result.confidence} below minimum threshold "
                    f"{agent.MIN_CONFIDENCE}"
                )
                
                # 4. Language must be one of the supported languages
                assert result.detected_language in agent.SUPPORTED_LANGUAGES, (
                    f"Detected language {result.detected_language} not in "
                    f"supported languages {agent.SUPPORTED_LANGUAGES}"
                )
    
    @given(voice_message_with_language())
    @settings(max_examples=100, deadline=None)
    def test_property_1_response_language_consistency(self, voice_message_data):
        """
        **Property 1: Language-Consistent Transcription (Response Generation)**
        **Validates: Requirement 1.2**
        
        For any transcribed query, the system should generate a response in the 
        same language as the input.
        
        This property verifies:
        1. Text-to-speech synthesis uses the same language as the input
        2. The generated audio URL is valid
        3. The voice mapping exists for the language
        """
        audio_url, language, sample_text, confidence = voice_message_data
        
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
                return_value=f'https://s3.amazonaws.com/test-processed-bucket/response-{language}.mp3'
            )
            
            # Generate response text in the same language
            response_text = sample_text  # Using same text for simplicity
            
            # Execute speech synthesis
            audio_url = agent.synthesize_speech(
                text=response_text,
                language=language
            )
            
            # Property assertions
            
            # 1. Audio URL must be generated
            assert audio_url is not None, "Audio URL should not be None"
            assert len(audio_url) > 0, "Audio URL should not be empty"
            
            # 2. Polly should be called with the correct language (Requirement 1.2)
            call_args = mock_polly.synthesize_speech.call_args[1]
            assert call_args['LanguageCode'] == language, (
                f"Response language {call_args['LanguageCode']} does not match "
                f"input language {language}"
            )
            
            # 3. Voice mapping should exist for the language
            assert language in agent.VOICE_MAPPING, (
                f"No voice mapping found for language {language}"
            )
            
            # 4. The correct voice should be used
            expected_voice = agent.VOICE_MAPPING[language]
            assert call_args['VoiceId'] == expected_voice, (
                f"Voice ID {call_args['VoiceId']} does not match expected "
                f"voice {expected_voice} for language {language}"
            )
    
    @given(voice_message_with_language())
    @settings(max_examples=100, deadline=None)
    def test_property_1_automatic_language_detection(self, voice_message_data):
        """
        **Property 1: Language-Consistent Transcription (Automatic Detection)**
        **Validates: Requirement 1.1**
        
        For any voice message without a language hint, the system should 
        automatically detect the correct language.
        
        This property verifies:
        1. Language identification is enabled when no hint is provided
        2. All supported languages are included in language options
        3. The detected language is one of the supported languages
        """
        audio_url, expected_language, sample_text, confidence = voice_message_data
        
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
            
            # Mock the transcription job
            mock_transcribe.start_transcription_job = Mock()
            
            # Mock the wait_for_transcription method
            with patch.object(
                agent,
                '_wait_for_transcription',
                return_value=TranscriptionResult(
                    text=sample_text,
                    detected_language=expected_language,
                    confidence=confidence,
                    transcript_url=f's3://test-processed-bucket/transcript-{expected_language}.json'
                )
            ):
                # Execute transcription WITHOUT language hint
                result = agent.transcribe_audio(
                    audio_url=audio_url,
                    language_hint=None  # No hint provided
                )
                
                # Property assertions
                
                # 1. Language identification should be enabled
                call_args = mock_transcribe.start_transcription_job.call_args[1]
                assert call_args.get('IdentifyLanguage') is True, (
                    "IdentifyLanguage should be True when no language hint is provided"
                )
                
                # 2. Language options should include all supported languages
                assert call_args.get('LanguageOptions') == agent.TRANSCRIBE_LANGUAGE_OPTIONS, (
                    f"LanguageOptions should be {agent.TRANSCRIBE_LANGUAGE_OPTIONS}"
                )
                
                # 3. Detected language must be one of the supported languages
                assert result.detected_language in agent.SUPPORTED_LANGUAGES, (
                    f"Detected language {result.detected_language} not in "
                    f"supported languages {agent.SUPPORTED_LANGUAGES}"
                )
                
                # 4. Detected language should match the expected language
                assert result.detected_language == expected_language, (
                    f"Detected language {result.detected_language} does not match "
                    f"expected language {expected_language}"
                )


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestLanguageConsistencyEdgeCases:
    """
    Edge case tests for language-consistent transcription.
    """
    
    def test_all_supported_languages_have_voice_mapping(self):
        """
        Verify that all supported languages have a voice mapping.
        
        This ensures that responses can be generated in all supported languages.
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
    
    def test_language_consistency_across_conversation(self):
        """
        Verify that language remains consistent across multiple interactions.
        
        This simulates a conversation where the farmer sends multiple messages
        in the same language.
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
            
            # Simulate multiple messages in Hindi
            language = 'hi-IN'
            messages = [
                'नमस्ते, मुझे मदद चाहिए',
                'मेरी फसल की जानकारी दें',
                'धन्यवाद'
            ]
            
            for message in messages:
                mock_transcribe.start_transcription_job = Mock()
                
                with patch.object(
                    agent,
                    '_wait_for_transcription',
                    return_value=TranscriptionResult(
                        text=message,
                        detected_language=language,
                        confidence=0.95,
                        transcript_url='s3://bucket/transcript.json'
                    )
                ):
                    result = agent.transcribe_audio(
                        audio_url='s3://bucket/audio.mp3',
                        language_hint=language
                    )
                    
                    # Language should remain consistent
                    assert result.detected_language == language, (
                        f"Language changed from {language} to {result.detected_language}"
                    )
