"""
Voice Agent Component for Kisan-Setu.

This module provides voice processing capabilities including:
- Speech-to-text transcription using Amazon Transcribe
- Text-to-speech synthesis using Amazon Polly
- Language detection for Hindi, Marathi, and Tamil
- Audio quality validation and error handling
"""

import boto3
import os
import time
import uuid
from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime
import logging
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.error_handling import (
    retry_with_exponential_backoff,
    create_error_response,
    ErrorCategory,
    ErrorSeverity
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class TranscriptionResult:
    """Result from audio transcription."""
    text: str
    detected_language: str
    confidence: float
    transcript_url: Optional[str] = None


class VoiceAgent:
    """
    Voice Agent for processing audio messages.
    
    Handles transcription, synthesis, and language detection for
    Hindi (hi-IN), Marathi (mr-IN), and Tamil (ta-IN).
    """
    
    # Supported languages
    SUPPORTED_LANGUAGES = ['hi-IN', 'mr-IN', 'ta-IN']
    
    # Language to Polly voice mapping
    VOICE_MAPPING = {
        'hi-IN': 'Aditi',  # Hindi female voice
        'mr-IN': 'Aditi',  # Use Hindi voice for Marathi (closest available)
        'ta-IN': 'Aditi',  # Use Hindi voice for Tamil (closest available)
    }
    
    # Minimum confidence threshold for transcription
    MIN_CONFIDENCE = 0.6
    
    def __init__(
        self,
        s3_bucket_raw: str,
        s3_bucket_processed: str,
        region: str = 'ap-south-1'
    ):
        """
        Initialize Voice Agent.
        
        Args:
            s3_bucket_raw: S3 bucket for raw audio files
            s3_bucket_processed: S3 bucket for processed audio files
            region: AWS region
        """
        self.s3_bucket_raw = s3_bucket_raw
        self.s3_bucket_processed = s3_bucket_processed
        self.region = region
        
        # Initialize AWS clients
        self.transcribe = boto3.client('transcribe', region_name=region)
        self.polly = boto3.client('polly', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
    
    def transcribe_audio(
        self,
        audio_url: str,
        language_hint: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio to text using Amazon Transcribe.
        
        Args:
            audio_url: S3 URL or path to audio file
            language_hint: Optional language hint (hi-IN, mr-IN, ta-IN)
            
        Returns:
            TranscriptionResult with text, detected_language, and confidence
            
        Raises:
            ValueError: If audio quality is too poor or language unsupported
            RuntimeError: If transcription fails
        """
        try:
            logger.info(f"Starting transcription for audio: {audio_url}")
            
            # Generate unique job name
            job_name = f"transcribe-{uuid.uuid4()}"
            
            # Prepare transcription job parameters
            job_params = {
                'TranscriptionJobName': job_name,
                'Media': {'MediaFileUri': audio_url},
                'MediaFormat': self._detect_audio_format(audio_url),
                'OutputBucketName': self.s3_bucket_processed,
            }
            
            # Add language identification or specific language
            if language_hint and language_hint in self.SUPPORTED_LANGUAGES:
                job_params['LanguageCode'] = language_hint
            else:
                # Use automatic language identification
                job_params['IdentifyLanguage'] = True
                job_params['LanguageOptions'] = self.SUPPORTED_LANGUAGES
            
            # Start transcription job with retry logic
            self._start_transcription_with_retry(job_params)
            
            # Wait for job completion
            result = self._wait_for_transcription(job_name)
            
            # Validate audio quality
            if result.confidence < self.MIN_CONFIDENCE:
                error = create_error_response(
                    error_code='AUDIO_QUALITY_POOR',
                    technical_details=f"Audio confidence {result.confidence:.2f} below threshold {self.MIN_CONFIDENCE}",
                    language=language_hint or 'en',
                    category=ErrorCategory.USER_INPUT,
                    severity=ErrorSeverity.LOW
                )
                raise ValueError(error.user_message)
            
            logger.info(
                f"Transcription completed: language={result.detected_language}, "
                f"confidence={result.confidence:.2f}"
            )
            
            return result
            
        except ValueError:
            # Re-raise ValueError as-is (user input errors)
            raise
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            error = create_error_response(
                error_code='SERVICE_UNAVAILABLE',
                technical_details=f"Transcription error: {str(e)}",
                language=language_hint or 'en',
                category=ErrorCategory.EXTERNAL_SERVICE,
                severity=ErrorSeverity.HIGH
            )
            raise RuntimeError(error.user_message)
    
    @retry_with_exponential_backoff(max_retries=3, service_name='transcribe')
    def _start_transcription_with_retry(self, job_params: Dict):
        """Start transcription job with retry logic."""
        self.transcribe.start_transcription_job(**job_params)
    
    def synthesize_speech(
        self,
        text: str,
        language: str,
        voice_id: Optional[str] = None
    ) -> str:
        """
        Convert text to speech using Amazon Polly.
        
        Args:
            text: Text to convert to speech
            language: Language code (hi-IN, mr-IN, ta-IN)
            voice_id: Optional specific voice ID (uses default if not provided)
            
        Returns:
            S3 URL to generated audio file
            
        Raises:
            ValueError: If language is unsupported
            RuntimeError: If synthesis fails
        """
        if language not in self.SUPPORTED_LANGUAGES:
            error = create_error_response(
                error_code='SERVICE_UNAVAILABLE',
                technical_details=f"Unsupported language: {language}",
                language='en',
                category=ErrorCategory.USER_INPUT,
                severity=ErrorSeverity.LOW
            )
            raise ValueError(error.user_message)
        
        try:
            logger.info(f"Synthesizing speech for language: {language}")
            
            # Select voice
            if not voice_id:
                voice_id = self.VOICE_MAPPING.get(language, 'Aditi')
            
            # Synthesize speech with retry logic
            response = self._synthesize_with_retry(text, language, voice_id)
            
            # Generate S3 key for audio file
            audio_key = f"voice-responses/{uuid.uuid4()}.mp3"
            
            # Upload to S3
            self.s3.put_object(
                Bucket=self.s3_bucket_processed,
                Key=audio_key,
                Body=response['AudioStream'].read(),
                ContentType='audio/mpeg',
                Metadata={
                    'language': language,
                    'voice_id': voice_id,
                    'generated_at': datetime.utcnow().isoformat()
                }
            )
            
            # Generate presigned URL (valid for 1 hour)
            audio_url = self.s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.s3_bucket_processed,
                    'Key': audio_key
                },
                ExpiresIn=3600
            )
            
            logger.info(f"Speech synthesis completed: {audio_url}")
            
            return audio_url
            
        except Exception as e:
            logger.error(f"Speech synthesis failed: {str(e)}")
            error = create_error_response(
                error_code='SERVICE_UNAVAILABLE',
                technical_details=f"Polly synthesis error: {str(e)}",
                language=language,
                category=ErrorCategory.EXTERNAL_SERVICE,
                severity=ErrorSeverity.HIGH
            )
            raise RuntimeError(error.user_message)
    
    @retry_with_exponential_backoff(max_retries=3, service_name='polly')
    def _synthesize_with_retry(self, text: str, language: str, voice_id: str) -> Dict:
        """Synthesize speech with retry logic."""
        return self.polly.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId=voice_id,
            LanguageCode=language,
            Engine='neural'  # Use neural engine for better quality
        )
    
    def detect_language(self, audio_url: str) -> str:
        """
        Identify language from audio.
        
        Args:
            audio_url: S3 URL or path to audio file
            
        Returns:
            Language code (hi-IN, mr-IN, ta-IN)
            
        Raises:
            RuntimeError: If language detection fails
        """
        try:
            logger.info(f"Detecting language for audio: {audio_url}")
            
            # Use transcribe_audio with language identification
            result = self.transcribe_audio(audio_url, language_hint=None)
            
            return result.detected_language
            
        except Exception as e:
            logger.error(f"Language detection failed: {str(e)}")
            raise RuntimeError(f"Failed to detect language: {str(e)}")
    
    def _detect_audio_format(self, audio_url: str) -> str:
        """
        Detect audio format from URL/filename.
        
        Args:
            audio_url: Audio file URL or path
            
        Returns:
            Audio format (mp3, mp4, wav, flac, ogg, amr, webm)
        """
        url_lower = audio_url.lower()
        
        if url_lower.endswith('.mp3'):
            return 'mp3'
        elif url_lower.endswith('.mp4') or url_lower.endswith('.m4a'):
            return 'mp4'
        elif url_lower.endswith('.wav'):
            return 'wav'
        elif url_lower.endswith('.flac'):
            return 'flac'
        elif url_lower.endswith('.ogg'):
            return 'ogg'
        elif url_lower.endswith('.amr'):
            return 'amr'
        elif url_lower.endswith('.webm'):
            return 'webm'
        else:
            # Default to mp3 for WhatsApp audio
            return 'mp3'
    
    def _wait_for_transcription(
        self,
        job_name: str,
        max_wait_seconds: int = 300
    ) -> TranscriptionResult:
        """
        Wait for transcription job to complete.
        
        Args:
            job_name: Transcription job name
            max_wait_seconds: Maximum time to wait (default: 5 minutes)
            
        Returns:
            TranscriptionResult
            
        Raises:
            RuntimeError: If job fails or times out
        """
        start_time = time.time()
        
        while True:
            # Check if timeout exceeded
            if time.time() - start_time > max_wait_seconds:
                raise RuntimeError(
                    f"Transcription job timed out after {max_wait_seconds} seconds"
                )
            
            # Get job status
            response = self.transcribe.get_transcription_job(
                TranscriptionJobName=job_name
            )
            
            status = response['TranscriptionJob']['TranscriptionJobStatus']
            
            if status == 'COMPLETED':
                # Extract results
                transcript_uri = response['TranscriptionJob']['Transcript']['TranscriptFileUri']
                
                # Download transcript
                transcript_data = self._download_transcript(transcript_uri)
                
                # Extract text and confidence
                text = transcript_data['results']['transcripts'][0]['transcript']
                
                # Calculate average confidence
                items = transcript_data['results']['items']
                confidences = [
                    float(item.get('alternatives', [{}])[0].get('confidence', 0))
                    for item in items
                    if 'alternatives' in item
                ]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                
                # Get detected language
                detected_language = response['TranscriptionJob'].get(
                    'LanguageCode',
                    'hi-IN'  # Default to Hindi
                )
                
                return TranscriptionResult(
                    text=text,
                    detected_language=detected_language,
                    confidence=avg_confidence,
                    transcript_url=transcript_uri
                )
            
            elif status == 'FAILED':
                failure_reason = response['TranscriptionJob'].get('FailureReason', 'Unknown')
                raise RuntimeError(f"Transcription job failed: {failure_reason}")
            
            # Wait before checking again
            time.sleep(2)
    
    def _download_transcript(self, transcript_uri: str) -> Dict:
        """
        Download transcript JSON from S3.
        
        Args:
            transcript_uri: S3 URI to transcript file
            
        Returns:
            Transcript data as dictionary
        """
        import json
        import urllib.request
        
        # Download transcript
        with urllib.request.urlopen(transcript_uri) as response:
            transcript_data = json.loads(response.read().decode('utf-8'))
        
        return transcript_data
    
    def validate_audio_quality(self, audio_url: str) -> bool:
        """
        Validate audio quality before processing.
        
        Args:
            audio_url: S3 URL or path to audio file
            
        Returns:
            True if audio quality is acceptable, False otherwise
        """
        try:
            # Get audio file metadata
            if audio_url.startswith('s3://'):
                # Parse S3 URL
                parts = audio_url.replace('s3://', '').split('/', 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ''
                
                # Get object metadata
                response = self.s3.head_object(Bucket=bucket, Key=key)
                
                # Check file size (minimum 1KB, maximum 100MB)
                file_size = response['ContentLength']
                if file_size < 1024 or file_size > 100 * 1024 * 1024:
                    logger.warning(f"Audio file size out of range: {file_size} bytes")
                    return False
                
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"Audio quality validation failed: {str(e)}")
            return False
