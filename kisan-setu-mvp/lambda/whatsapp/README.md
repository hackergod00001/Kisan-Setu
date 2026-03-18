# WhatsApp Interface Component

## Overview

This directory contains the WhatsApp Interface Component for Kisan-Setu, using Meta WhatsApp Business Cloud API (v18.0). The primary class `MetaWhatsAppInterface` handles all WhatsApp communication. Webhook handling is done by the MessageRouter Lambda (`lambda/router/router.py`).

## Architecture

```mermaid
graph TB
    subgraph WhatsAppModule["WhatsApp Module"]
        META_IF["MetaWhatsAppInterface<br/>(meta_whatsapp_interface.py)"]
    end

    subgraph Consumers["Used By"]
        ROUTER["MessageRouter<br/>(webhook verification)"]
        DOC["DocumentProcessor<br/>(send ledger response)"]
        VOICE["VoiceHandler<br/>(send transcription confirmation)"]
        ORCH["BedrockOrchestrator<br/>(send AI response)"]
    end

    subgraph External["External"]
        SM["Secrets Manager<br/>kisan-setu/whatsapp/credentials"]
        META_API["Meta Graph API<br/>(v17.0)"]
        META_CDN["WhatsApp CDN<br/>(media download)"]
    end

    ROUTER --> META_IF
    DOC --> META_IF
    VOICE --> META_IF
    ORCH --> META_IF
    META_IF --> SM
    META_IF --> META_API
    META_IF --> META_CDN
```

## Components

### `meta_whatsapp_interface.py`

The main `MetaWhatsAppInterface` class that handles all WhatsApp communication.

**Capabilities:**
- **Credential loading**: From AWS Secrets Manager (`kisan-setu/whatsapp/credentials`) with env var fallback
- **Send text**: `send_text_response(phone, message, language)` via Meta Graph API (v18.0)
- **Send voice**: `send_voice_response(phone, audio_url)` for audio responses
- **Send image**: `send_image(phone, image_url, caption)` for image messages
- **Send document**: `send_document(phone, document_url, caption, filename)` for PDFs/Excel
- **Receive message**: `receive_message(webhook_payload)` — parse Meta webhook into `WhatsAppMessage` objects
- **Media download**: `download_media(media_id)` — fetch images/audio from WhatsApp CDN, upload to S3
- **Multilingual fallback**: Welcome messages and error messages in English, Hindi, Marathi, Tamil
- **Rate limit handling**: Detection of Meta API rate limit errors (codes 4, 80007)
- **Formatting**: Tables (`format_table`), numbered/bullet lists (`format_list`), structured data (`format_structured_data`)

> **Note**: `webhook_handler.py` was removed in Phase 5 cleanup. All webhook handling is done by MessageRouter (`lambda/router/router.py`).

## Message Flow

```mermaid
sequenceDiagram
    participant User as 📱 WhatsApp User
    participant Meta as Meta Cloud API
    participant APIGW as API Gateway
    participant Router as MessageRouter
    participant Lambda as Downstream Lambda
    participant WA_IF as MetaWhatsAppInterface
    participant Meta2 as Meta Graph API

    User->>Meta: Send message
    Meta->>APIGW: POST /webhook
    APIGW->>Router: Invoke
    Router->>Lambda: Async invoke (DocProc/Voice/Orch)
    Lambda->>WA_IF: Create interface instance
    WA_IF->>WA_IF: Load credentials from Secrets Manager
    WA_IF->>Meta2: POST /v18.0/{phone_id}/messages
    Meta2->>User: Deliver response
```

## WhatsApp Credentials

Stored in AWS Secrets Manager (`kisan-setu/whatsapp/credentials`):

```json
{
  "PHONE_NUMBER_ID": "1043444535519617",
  "ACCESS_TOKEN": "your_access_token",
  "VERIFY_TOKEN": "kisan-setu-verify-2026"
}
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `WHATSAPP_SECRET_NAME` | Secrets Manager secret name (`kisan-setu/whatsapp/credentials`) |
| `WEBHOOK_VERIFY_TOKEN` | Webhook verification token (`kisan-setu-verify-2026`) |

## Testing

```bash
pytest tests/test_webhook_handler.py -v
```

## Consumers

The `MetaWhatsAppInterface` class is used by multiple Lambda functions (each has its own copy in `common/`):
- **MessageRouter** — webhook verification, media download
- **DocumentProcessor** — send ledger extraction results directly to user
- **VoiceHandler** — send transcription confirmation
- **BedrockOrchestrator** — send AI responses
