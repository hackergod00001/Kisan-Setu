# WhatsApp Interface Component

This directory contains the WhatsApp Interface Component for the Kisan-Setu system, using Meta WhatsApp Business API.

## Components

### 1. `meta_whatsapp_interface.py`
The main MetaWhatsAppInterface class that handles all WhatsApp communication via Meta WhatsApp Business Cloud API.

**Key Features:**
- **Message Sending**: Send text responses via Meta Graph API
- **Media Download**: Download images and voice messages from WhatsApp
- **Multilingual Support**: Error messages in English, Hindi, Marathi, and Tamil
- **Credentials Management**: Load credentials from AWS Secrets Manager

**Methods:**
- `send_message(phone_number, message)`: Send text message via Meta API
- `download_media(media_id)`: Download media (images/voice) from WhatsApp
- `get_fallback_response(language)`: Get localized fallback error message

### 2. `webhook_handler.py`
Lambda function that receives WhatsApp webhooks and routes messages to appropriate components.

**Routing Logic:**
- **Image messages** → DocumentProcessor Lambda (for ledger digitization)
- **Voice/Audio messages** → VoiceAgent Lambda (for transcription and processing)
- **Text messages** → BedrockOrchestrator Lambda (for AI-powered responses)

## Environment Variables

- `DYNAMODB_TABLE`: DynamoDB table name for storing messages
- `DOCUMENT_PROCESSOR_FUNCTION`: Lambda function name for document processing
- `VOICE_AGENT_FUNCTION`: Lambda function name for voice processing
- `BEDROCK_ORCHESTRATOR_FUNCTION`: Lambda function name for text processing
- `WEBHOOK_VERIFY_TOKEN`: Token for webhook verification (kisan-setu-verify-2026)
- `WHATSAPP_SECRET_NAME`: AWS Secrets Manager secret name for WhatsApp credentials

## WhatsApp Credentials

Credentials are stored in AWS Secrets Manager (`kisan-setu/whatsapp/credentials`):

```json
{
  "PHONE_NUMBER_ID": "your_phone_number_id",
  "ACCESS_TOKEN": "your_access_token",
  "VERIFY_TOKEN": "kisan-setu-verify-2026"
}
```

## Usage

```python
from meta_whatsapp_interface import MetaWhatsAppInterface

whatsapp = MetaWhatsAppInterface()
whatsapp.send_message("919876543210", "Your ledger has been processed!")
```

## Testing

```bash
pytest tests/test_webhook_handler.py -v
```
