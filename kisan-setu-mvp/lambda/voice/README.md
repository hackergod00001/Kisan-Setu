# Voice Agent Component

## Overview

The Voice Agent provides multilingual voice processing for Kisan-Setu. It transcribes voice messages using Amazon Transcribe, sends a transcription confirmation to the user, then forwards the transcribed text to BedrockOrchestrator for AI processing. It also supports text-to-speech synthesis via Amazon Polly.

## Architecture

```mermaid
graph TB
    subgraph Input["Invocation"]
        ROUTER["MessageRouter<br/>(audio messages, async)"]
    end

    subgraph VoiceHandler["VoiceHandler (512 MB · 60s)"]
        HANDLER["handler()"]
        DOWNLOAD["Download audio<br/>(WhatsApp media API)"]
        UPLOAD["Upload to S3"]
        TRANSCRIBE_OP["Transcribe<br/>(VoiceAgent.transcribe_audio)"]
        NOTIFY["Send transcription<br/>confirmation to user"]
        FORWARD["Forward text to<br/>BedrockOrchestrator<br/>(async Lambda invoke)"]
    end

    subgraph External["AWS Services"]
        TRANSCRIBE["Amazon Transcribe<br/>(hi-IN, mr-IN, ta-IN)"]
        POLLY["Amazon Polly<br/>(Neural TTS)"]
        S3["S3 (raw bucket)"]
    end

    subgraph Output["Output"]
        WA["WhatsApp<br/>(transcription confirmation)"]
        ORCH["BedrockOrchestrator<br/>(processes text, sends AI response)"]
    end

    ROUTER --> HANDLER
    HANDLER --> DOWNLOAD
    DOWNLOAD --> UPLOAD
    UPLOAD --> S3
    UPLOAD --> TRANSCRIBE_OP
    TRANSCRIBE_OP --> TRANSCRIBE
    TRANSCRIBE --> TRANSCRIBE_OP
    TRANSCRIBE_OP --> NOTIFY
    NOTIFY --> WA
    TRANSCRIBE_OP --> FORWARD
    FORWARD --> ORCH
```

## Voice Message Processing Flow

```mermaid
sequenceDiagram
    participant Router as MessageRouter
    participant Voice as VoiceHandler
    participant WA_API as WhatsApp Media API
    participant S3 as S3 (raw)
    participant Transcribe as Amazon Transcribe
    participant WA as WhatsApp (user)
    participant Orch as BedrockOrchestrator

    Router->>Voice: Async invoke (audio_url, sender_id, language)
    Voice->>WA_API: Download audio (media ID)
    WA_API-->>Voice: Audio bytes
    Voice->>S3: Upload audio file
    Voice->>Transcribe: Start transcription job
    Transcribe-->>Voice: Transcribed text + confidence + language
    Voice->>WA: Send multilingual transcription confirmation
    Voice->>Orch: Async invoke (transcribed text, sender_id, language)
    Note over Orch: Orchestrator processes text<br/>and sends AI response via WhatsApp
```

## Lambda Configuration

| Property | Value |
|----------|-------|
| Runtime | Python 3.11 |
| Memory | 512 MB |
| Timeout | 60s |
| Handler | `voice.handler` |

## Supported Languages

| Language | Code | Transcribe | Polly Voice |
|----------|------|------------|-------------|
| Hindi | hi-IN | ✅ | Aditi (Neural) |
| Marathi | mr-IN | ✅ | — |
| Tamil | ta-IN | ✅ | — |

## Actions

| Action | Input | Output |
|--------|-------|--------|
| `transcribe` | `audio_url`, `language` (hint), `sender_id` | Transcribed text + confidence + detected language |
| `synthesize` | `text`, `language`, `voice_id` (optional) | S3 presigned URL to audio (1h validity) |
| `detect_language` | `audio_url` | Detected language code |

## Audio Format Support

OGG, MP3, WAV, M4A, FLAC, AMR, WebM (auto-detected from WhatsApp content type)

## Key Behavior

- On `transcribe` action: Downloads audio → uploads to S3 → transcribes → sends WhatsApp confirmation → forwards text to BedrockOrchestrator (async)
- The Orchestrator (not VoiceHandler) generates and sends the AI response
- Error messages are sent to user in their detected language (Hindi, Marathi, Tamil, English)

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `S3_BUCKET_RAW` | Raw audio storage bucket |
| `S3_BUCKET_PROCESSED` | Processed audio/transcripts bucket |
| `REGION` | AWS region (`ap-south-1`) |
| `WHATSAPP_SECRET_NAME` | Secrets Manager secret for WhatsApp |
| `SNS_ALERT_TOPIC_ARN` | Critical alerts topic |

## Testing

```bash
pytest tests/test_voice_agent.py -v
```
