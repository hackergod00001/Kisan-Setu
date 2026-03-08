# Voice Agent Component

The Voice Agent component provides multilingual voice processing capabilities for the Kisan-Setu system, supporting Hindi, Marathi, and Tamil languages.

## Features

- **Speech-to-Text Transcription**: Convert voice messages to text using Amazon Transcribe
- **Text-to-Speech Synthesis**: Generate voice responses using Amazon Polly
- **Language Detection**: Automatically identify the language from audio
- **Audio Quality Validation**: Ensure audio quality meets minimum standards
- **Error Handling**: Comprehensive error handling with user-friendly messages

## Supported Languages

- Hindi (hi-IN)
- Marathi (mr-IN)
- Tamil (ta-IN)

## Components

### VoiceAgent Class

The main class that handles all voice processing operations.

#### Initialization

```python
from voice_agent import VoiceAgent

voice_agent = VoiceAgent(
    s3_bucket_raw='kisan-setu-raw',
    s3_bucket_processed='kisan-setu-processed',
    region='ap-south-1'
)
```

#### Methods

##### transcribe_audio(audio_url, language_hint=None)

Transcribe audio to text with automatic language detection.

**Parameters:**
- `audio_url` (str): S3 URL to audio file
- `language_hint` (str, optional): Language hint (hi-IN, mr-IN, ta-IN)

**Returns:**
- `TranscriptionResult`: Object containing text, detected_language, confidence, and transcript_url

**Raises:**
- `ValueError`: If audio quality is too poor (confidence < 0.6)
- `RuntimeError`: If transcription service fails

**Example:**
```python
result = voice_agent.transcribe_audio(
    's3://bucket/audio.mp3',
    language_hint='hi-IN'
)
print(f"Text: {result.text}")
print(f"Language: {result.detected_language}")
print(f"Confidence: {result.confidence}")
```

##### synthesize_speech(text, language, voice_id=None)

Convert text to speech in the specified language.

**Parameters:**
- `text` (str): Text to convert to speech
- `language` (str): Language code (hi-IN, mr-IN, ta-IN)
- `voice_id` (str, optional): Specific Polly voice ID

**Returns:**
- `str`: S3 presigned URL to generated audio file (valid for 1 hour)

**Raises:**
- `ValueError`: If language is unsupported
- `RuntimeError`: If synthesis service fails

**Example:**
```python
audio_url = voice_agent.synthesize_speech(
    text='नमस्ते, आपका स्वागत है',
    language='hi-IN'
)
print(f"Audio URL: {audio_url}")
```

##### detect_language(audio_url)

Identify the language from an audio file.

**Parameters:**
- `audio_url` (str): S3 URL to audio file

**Returns:**
- `str`: Detected language code (hi-IN, mr-IN, ta-IN)

**Raises:**
- `RuntimeError`: If language detection fails

**Example:**
```python
language = voice_agent.detect_language('s3://bucket/audio.mp3')
print(f"Detected language: {language}")
```

##### validate_audio_quality(audio_url)

Validate audio file quality before processing.

**Parameters:**
- `audio_url` (str): S3 URL to audio file

**Returns:**
- `bool`: True if audio quality is acceptable, False otherwise

**Example:**
```python
is_valid = voice_agent.validate_audio_quality('s3://bucket/audio.mp3')
if is_valid:
    result = voice_agent.transcribe_audio('s3://bucket/audio.mp3')
```

### Voice Handler Lambda

The Lambda function that exposes the VoiceAgent functionality via API.

#### Event Format

```json
{
  "action": "transcribe|synthesize|detect_language",
  "audio_url": "s3://bucket/audio.mp3",
  "text": "Text to synthesize",
  "language": "hi-IN",
  "sender_id": "+919876543210"
}
```

#### Actions

**transcribe**: Transcribe audio to text
```json
{
  "action": "transcribe",
  "audio_url": "s3://bucket/audio.mp3",
  "language": "hi-IN"
}
```

**synthesize**: Convert text to speech
```json
{
  "action": "synthesize",
  "text": "नमस्ते",
  "language": "hi-IN"
}
```

**detect_language**: Detect language from audio
```json
{
  "action": "detect_language",
  "audio_url": "s3://bucket/audio.mp3"
}
```

#### Response Format

**Success Response:**
```json
{
  "statusCode": 200,
  "body": {
    "action": "transcribe",
    "text": "नमस्ते",
    "detected_language": "hi-IN",
    "confidence": 0.95,
    "transcript_url": "s3://bucket/transcript.json"
  }
}
```

**Error Response:**
```json
{
  "statusCode": 400,
  "body": {
    "error": "Audio quality too poor",
    "error_type": "validation_error"
  }
}
```

## Audio Format Support

The Voice Agent supports the following audio formats:
- MP3
- MP4/M4A
- WAV
- FLAC
- OGG
- AMR
- WebM

## Quality Requirements

- **Minimum file size**: 1 KB
- **Maximum file size**: 100 MB
- **Minimum confidence**: 0.6 (60%)

## Error Handling

The Voice Agent implements comprehensive error handling:

### User Input Errors (ValueError)
- Audio quality too poor
- Unsupported language
- Invalid audio format

### Service Errors (RuntimeError)
- Transcription service failure
- Synthesis service failure
- S3 access errors

## Integration with WhatsApp

The Voice Agent integrates with the WhatsApp interface to process voice messages:

1. User sends voice message via WhatsApp
2. WhatsApp webhook handler uploads audio to S3
3. Voice Agent transcribes audio to text
4. Bedrock Agent processes the text
5. Voice Agent synthesizes response to audio
6. WhatsApp interface sends audio response to user

## AWS Services Used

- **Amazon Transcribe**: Speech-to-text transcription with language identification
- **Amazon Polly**: Text-to-speech synthesis with neural voices
- **Amazon S3**: Storage for audio files and transcripts

## Configuration

### Environment Variables

- `S3_BUCKET_RAW`: S3 bucket for raw audio files
- `S3_BUCKET_PROCESSED`: S3 bucket for processed audio and transcripts
- `REGION`: AWS region (default: ap-south-1)

### IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "transcribe:StartTranscriptionJob",
        "transcribe:GetTranscriptionJob"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "polly:SynthesizeSpeech"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:HeadObject"
      ],
      "Resource": [
        "arn:aws:s3:::kisan-setu-raw/*",
        "arn:aws:s3:::kisan-setu-processed/*"
      ]
    }
  ]
}
```

## Testing

Run the unit tests:

```bash
pytest tests/test_voice_agent.py -v
```

## Performance Considerations

- **Transcription**: Typically takes 30-60 seconds for a 1-minute audio file
- **Synthesis**: Typically takes 1-2 seconds for short text
- **S3 Presigned URLs**: Valid for 1 hour
- **Caching**: Consider caching frequently used voice responses

## Cost Optimization

- Use S3 lifecycle policies to delete old audio files after 30 days
- Batch multiple synthesis requests when possible
- Cache common responses to reduce Polly API calls

## Limitations

- Maximum audio file size: 100 MB
- Transcription timeout: 5 minutes
- Supported languages: Hindi, Marathi, Tamil only
- Polly neural voices may not be available in all regions

## Future Enhancements

- Support for additional Indian languages (Punjabi, Bengali, Telugu)
- Real-time streaming transcription
- Custom vocabulary for agricultural terms
- Dialect-specific voice models
- Voice activity detection to filter silence
