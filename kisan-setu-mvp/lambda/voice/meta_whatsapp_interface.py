"""
Meta WhatsApp Business API Interface for Kisan-Setu

This module provides the MetaWhatsAppInterface class that handles all WhatsApp
communication using Meta's WhatsApp Business Platform (Cloud API).

Implements Requirements 6.1, 6.2, 6.3, 6.4, 6.5
"""

import os
import json
import boto3
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

# AWS clients
secrets_client = boto3.client('secretsmanager')
s3_client = boto3.client('s3')

# S3 bucket for media storage
S3_BUCKET_RAW = os.environ.get('S3_BUCKET_RAW', 'kisan-setu-raw')


class MessageType(Enum):
    """Types of messages supported by WhatsApp"""
    TEXT = "text"
    VOICE = "voice"
    AUDIO = "audio"
    IMAGE = "image"
    DOCUMENT = "document"
    VIDEO = "video"


@dataclass
class WhatsAppMessage:
    """Represents a WhatsApp message"""
    message_id: str
    sender_id: str
    message_type: MessageType
    content: str  # text content or URL to media
    timestamp: datetime
    language: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MetaWhatsAppInterface:
    """
    Meta WhatsApp Business API Interface
    
    Handles all WhatsApp communication via Meta's Cloud API.
    Provides methods for receiving messages, sending responses, and formatting
    structured data for WhatsApp display.
    """
    
    def __init__(self):
        """Initialize WhatsApp interface with Meta credentials"""
        self.credentials = self._load_credentials()
        self.access_token = self.credentials.get('access_token')
        self.phone_number_id = self.credentials.get('phone_number_id')
        self.business_account_id = self.credentials.get('business_account_id')
        self.api_version = os.environ.get('WHATSAPP_API_VERSION', 'v18.0')
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
    
    def _load_credentials(self) -> Dict[str, str]:
        """
        Load Meta WhatsApp credentials from environment or Secrets Manager
        
        Returns:
            Dictionary with access_token, phone_number_id, business_account_id
        """
        try:
            # Try environment variables first (for test mode)
            if os.environ.get('WHATSAPP_API_TOKEN'):
                return {
                    'access_token': os.environ.get('WHATSAPP_API_TOKEN'),
                    'phone_number_id': os.environ.get('WHATSAPP_PHONE_NUMBER_ID'),
                    'business_account_id': os.environ.get('WHATSAPP_BUSINESS_ACCOUNT_ID')
                }
            
            # Otherwise load from Secrets Manager
            secret_name = os.environ.get('WHATSAPP_SECRET_NAME', 'kisan-setu/whatsapp/credentials')
            response = secrets_client.get_secret_value(SecretId=secret_name)
            credentials = json.loads(response['SecretString'])
            
            # Handle both uppercase and lowercase keys
            return {
                'access_token': (
                    credentials.get('WHATSAPP_ACCESS_TOKEN') or 
                    credentials.get('access_token') or 
                    credentials.get('api_token')
                ),
                'phone_number_id': (
                    credentials.get('PHONE_NUMBER_ID') or 
                    credentials.get('phone_number_id')
                ),
                'business_account_id': (
                    credentials.get('BUSINESS_ACCOUNT_ID') or 
                    credentials.get('business_account_id')
                )
            }
        except Exception as e:
            print(f"Error loading Meta WhatsApp credentials: {e}")
            return {}
    
    def receive_message(self, webhook_payload: Dict[str, Any]) -> Optional[WhatsAppMessage]:
        """
        Receive and parse WhatsApp webhook payload from Meta
        
        Args:
            webhook_payload: Webhook payload from Meta (JSON format)
            
        Returns:
            WhatsAppMessage object or None if parsing fails
            
        Implements: Requirement 6.1 - Receive and route messages
        """
        try:
            # Meta webhook structure
            entry = webhook_payload.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            value = changes.get('value', {})
            messages = value.get('messages', [])
            
            if not messages:
                print("No messages in webhook payload")
                return None
            
            # Get first message
            msg = messages[0]
            
            message_id = msg.get('id')
            from_number = msg.get('from')
            timestamp_str = msg.get('timestamp')
            msg_type_str = msg.get('type', 'text')
            
            # Parse timestamp
            timestamp = datetime.fromtimestamp(int(timestamp_str)) if timestamp_str else datetime.utcnow()
            
            # Extract content based on message type
            content = ""
            metadata = {}
            
            if msg_type_str == 'text':
                msg_type = MessageType.TEXT
                content = msg.get('text', {}).get('body', '')
            
            elif msg_type_str == 'image':
                msg_type = MessageType.IMAGE
                image_data = msg.get('image', {})
                content = image_data.get('id')  # Media ID
                metadata = {
                    'media_id': image_data.get('id'),
                    'mime_type': image_data.get('mime_type'),
                    'sha256': image_data.get('sha256'),
                    'caption': image_data.get('caption', '')
                }
            
            elif msg_type_str == 'audio' or msg_type_str == 'voice':
                msg_type = MessageType.VOICE
                audio_data = msg.get('audio', msg.get('voice', {}))
                content = audio_data.get('id')
                metadata = {
                    'media_id': audio_data.get('id'),
                    'mime_type': audio_data.get('mime_type'),
                    'sha256': audio_data.get('sha256')
                }
            
            elif msg_type_str == 'document':
                msg_type = MessageType.DOCUMENT
                doc_data = msg.get('document', {})
                content = doc_data.get('id')
                metadata = {
                    'media_id': doc_data.get('id'),
                    'mime_type': doc_data.get('mime_type'),
                    'sha256': doc_data.get('sha256'),
                    'filename': doc_data.get('filename', ''),
                    'caption': doc_data.get('caption', '')
                }
            
            elif msg_type_str == 'video':
                msg_type = MessageType.VIDEO
                video_data = msg.get('video', {})
                content = video_data.get('id')
                metadata = {
                    'media_id': video_data.get('id'),
                    'mime_type': video_data.get('mime_type'),
                    'sha256': video_data.get('sha256'),
                    'caption': video_data.get('caption', '')
                }
            
            else:
                print(f"Unsupported message type: {msg_type_str}")
                return None
            
            # Create WhatsAppMessage object
            message = WhatsAppMessage(
                message_id=message_id,
                sender_id=from_number,
                message_type=msg_type,
                content=content,
                timestamp=timestamp,
                metadata=metadata
            )
            
            print(f"Received message: type={msg_type.value}, sender={from_number}")
            return message
            
        except Exception as e:
            print(f"Error parsing WhatsApp message: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def send_text_response(self, phone_number: str, text: str, language: str = 'en') -> bool:
        """
        Send text message to WhatsApp user
        
        Args:
            phone_number: Recipient phone number (format: 919876543210, no + or spaces)
            text: Message text to send
            language: Language code (hi-IN, mr-IN, ta-IN, en)
            
        Returns:
            True if sent successfully, False otherwise
            
        Implements: Requirement 6.2 - Deliver responses within 5 seconds
        """
        try:
            if not self.access_token or not self.phone_number_id:
                print("Missing Meta WhatsApp credentials")
                return False
            
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Clean phone number (remove + and spaces)
            clean_number = phone_number.replace('+', '').replace(' ', '').replace('-', '')
            
            payload = {
                'messaging_product': 'whatsapp',
                'recipient_type': 'individual',
                'to': clean_number,
                'type': 'text',
                'text': {
                    'preview_url': False,
                    'body': text
                }
            }
            
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=5  # 5 second timeout for requirement 6.2
            )
            
            if response.status_code == 200:
                print(f"Text message sent successfully to {phone_number}")
                return True
            else:
                print(f"Failed to send text message: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Error sending text message: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def download_media(self, media_id: str) -> Optional[str]:
        """
        Download media file from Meta and return URL
        
        Args:
            media_id: Media ID from webhook
            
        Returns:
            Public URL to downloaded media or None
        """
        try:
            # Get media URL
            url = f"{self.base_url}/{media_id}"
            headers = {
                'Authorization': f'Bearer {self.access_token}'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                media_data = response.json()
                media_url = media_data.get('url')
                
                # Download the actual file
                media_response = requests.get(
                    media_url,
                    headers=headers,
                    timeout=30
                )
                
                if media_response.status_code == 200:
                    # Upload to S3 for permanent storage
                    mime_type = media_data.get('mime_type', 'application/octet-stream')
                    file_ext = self._get_file_extension(mime_type)
                    timestamp = datetime.utcnow().isoformat().replace(':', '-')
                    s3_key = f"media/{media_id}/{timestamp}{file_ext}"

                    try:
                        s3_client.put_object(
                            Bucket=S3_BUCKET_RAW,
                            Key=s3_key,
                            Body=media_response.content,
                            ContentType=mime_type
                        )

                        s3_url = f"s3://{S3_BUCKET_RAW}/{s3_key}"
                        print(f"Media uploaded to S3: {s3_url}")
                        return s3_url
                    except Exception as s3_error:
                        print(f"S3 upload failed: {s3_error}, falling back to WhatsApp URL")
                        return media_url  # Fallback to temporary URL if S3 fails
            
            return None
            
        except Exception as e:
            print(f"Error downloading media: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_file_extension(self, mime_type: str) -> str:
        """Get file extension from MIME type."""
        extensions = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/webp': '.webp',
            'image/gif': '.gif',
            'audio/ogg': '.ogg',
            'audio/mpeg': '.mp3',
            'audio/mp4': '.m4a',
            'video/mp4': '.mp4',
            'video/3gpp': '.3gp',
            'application/pdf': '.pdf',
            'application/vnd.ms-excel': '.xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        }
        return extensions.get(mime_type, '.bin')

    def send_voice_response(self, phone_number: str, audio_url: str) -> bool:
        """
        Send voice message to WhatsApp user
        
        Args:
            phone_number: Recipient phone number
            audio_url: Public URL to audio file (must be accessible)
            
        Returns:
            True if sent successfully, False otherwise
            
        Implements: Requirement 6.4 - Accept and forward audio files
        """
        try:
            if not self.access_token or not self.phone_number_id:
                print("Missing Meta WhatsApp credentials")
                return False
            
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            clean_number = phone_number.replace('+', '').replace(' ', '').replace('-', '')
            
            payload = {
                'messaging_product': 'whatsapp',
                'recipient_type': 'individual',
                'to': clean_number,
                'type': 'audio',
                'audio': {
                    'link': audio_url
                }
            }
            
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"Voice message sent successfully to {phone_number}")
                return True
            else:
                print(f"Failed to send voice message: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Error sending voice message: {e}")
            return False
    
    def send_document(self, phone_number: str, document_url: str, caption: str = "", filename: str = "document.pdf") -> bool:
        """
        Send document (PDF, Excel) to WhatsApp user
        
        Args:
            phone_number: Recipient phone number
            document_url: Public URL to document file
            caption: Optional caption for the document
            filename: Document filename
            
        Returns:
            True if sent successfully, False otherwise
            
        Implements: Requirement 6.3 - Accept images up to 16MB
        """
        try:
            if not self.access_token or not self.phone_number_id:
                print("Missing Meta WhatsApp credentials")
                return False
            
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            clean_number = phone_number.replace('+', '').replace(' ', '').replace('-', '')
            
            payload = {
                'messaging_product': 'whatsapp',
                'recipient_type': 'individual',
                'to': clean_number,
                'type': 'document',
                'document': {
                    'link': document_url,
                    'filename': filename
                }
            }
            
            if caption:
                payload['document']['caption'] = caption
            
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"Document sent successfully to {phone_number}")
                return True
            else:
                print(f"Failed to send document: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Error sending document: {e}")
            return False
    
    def send_image(self, phone_number: str, image_url: str, caption: str = "") -> bool:
        """
        Send image to WhatsApp user
        
        Args:
            phone_number: Recipient phone number
            image_url: Public URL to image file
            caption: Optional caption for the image
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if not self.access_token or not self.phone_number_id:
                print("Missing Meta WhatsApp credentials")
                return False
            
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            clean_number = phone_number.replace('+', '').replace(' ', '').replace('-', '')
            
            payload = {
                'messaging_product': 'whatsapp',
                'recipient_type': 'individual',
                'to': clean_number,
                'type': 'image',
                'image': {
                    'link': image_url
                }
            }
            
            if caption:
                payload['image']['caption'] = caption
            
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"Image sent successfully to {phone_number}")
                return True
            else:
                print(f"Failed to send image: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Error sending image: {e}")
            return False
    
    def format_table(self, headers: List[str], rows: List[List[str]]) -> str:
        """
        Format table data for WhatsApp display
        
        Args:
            headers: List of column headers
            rows: List of rows, each row is a list of values
            
        Returns:
            Formatted string suitable for WhatsApp
            
        Implements: Requirement 6.5 - Format tables and lists
        """
        if not headers or not rows:
            return ""
        
        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Build formatted table
        lines = []
        
        # Header row
        header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
        lines.append(header_line)
        
        # Separator
        separator = "-+-".join("-" * w for w in col_widths)
        lines.append(separator)
        
        # Data rows
        for row in rows:
            row_line = " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
            lines.append(row_line)
        
        return "\n".join(lines)
    
    def format_list(self, items: List[str], numbered: bool = True) -> str:
        """
        Format list data for WhatsApp display
        
        Args:
            items: List of items to format
            numbered: If True, use numbered list; otherwise use bullet points
            
        Returns:
            Formatted string suitable for WhatsApp
            
        Implements: Requirement 6.5 - Format tables and lists
        """
        if not items:
            return ""
        
        lines = []
        for i, item in enumerate(items, 1):
            if numbered:
                lines.append(f"{i}. {item}")
            else:
                lines.append(f"• {item}")
        
        return "\n".join(lines)
    
    def format_structured_data(self, data: Dict[str, Any]) -> str:
        """
        Format structured data (JSON-like) for WhatsApp display
        
        Args:
            data: Dictionary of key-value pairs
            
        Returns:
            Formatted string suitable for WhatsApp
            
        Implements: Requirement 6.5 - Format structured data
        """
        if not data:
            return ""
        
        lines = []
        for key, value in data.items():
            # Format key (capitalize and replace underscores)
            formatted_key = key.replace('_', ' ').title()
            
            # Format value
            if isinstance(value, (list, tuple)):
                formatted_value = ", ".join(str(v) for v in value)
            elif isinstance(value, dict):
                formatted_value = json.dumps(value, indent=2)
            else:
                formatted_value = str(value)
            
            lines.append(f"*{formatted_key}:* {formatted_value}")
        
        return "\n".join(lines)
    
    def send_welcome_message(self, phone_number: str, language: str = 'en') -> bool:
        """
        Send welcome message with available commands
        
        Args:
            phone_number: Recipient phone number
            language: Preferred language code
            
        Returns:
            True if sent successfully
            
        Implements: Requirement 6.6 - Welcome message with commands
        """
        # Welcome messages in different languages
        welcome_messages = {
            'en': """🌾 *Welcome to Kisan-Setu!*

I'm your AI-powered FPO assistant. I can help you with:

📸 *Send a photo* of your ledger to digitize records
🎤 *Send a voice message* to ask questions
💬 *Send a text message* for quick queries
📊 *Check credit score* - Type "credit score"
🛰️ *Get yield prediction* - Share your field location

How can I help you today?""",
            
            'hi-IN': """🌾 *किसान-सेतु में आपका स्वागत है!*

मैं आपका AI-संचालित FPO सहायक हूं। मैं आपकी मदद कर सकता हूं:

📸 *फोटो भेजें* अपने खाते की डिजिटाइज़ करने के लिए
🎤 *वॉयस मैसेज भेजें* सवाल पूछने के लिए
💬 *टेक्स्ट मैसेज भेजें* त्वरित प्रश्नों के लिए
📊 *क्रेडिट स्कोर देखें* - "credit score" टाइप करें
🛰️ *उपज पूर्वानुमान प्राप्त करें* - अपने खेत का स्थान साझा करें

आज मैं आपकी कैसे मदद कर सकता हूं?""",
            
            'mr-IN': """🌾 *किसान-सेतु मध्ये आपले स्वागत आहे!*

मी तुमचा AI-चालित FPO सहाय्यक आहे. मी तुम्हाला मदत करू शकतो:

📸 *फोटो पाठवा* तुमच्या खात्याचे डिजिटायझेशन करण्यासाठी
🎤 *व्हॉइस मेसेज पाठवा* प्रश्न विचारण्यासाठी
💬 *टेक्स्ट मेसेज पाठवा* जलद प्रश्नांसाठी
📊 *क्रेडिट स्कोअर पहा* - "credit score" टाइप करा
🛰️ *उत्पन्न अंदाज मिळवा* - तुमच्या शेताचे स्थान शेअर करा

आज मी तुम्हाला कशी मदत करू शकतो?""",
            
            'ta-IN': """🌾 *கிசான்-சேது-வில் உங்களை வரவேற்கிறோம்!*

நான் உங்கள் AI-இயக்கப்படும் FPO உதவியாளர். நான் உங்களுக்கு உதவ முடியும்:

📸 *புகைப்படம் அனுப்பவும்* உங்கள் கணக்கை டிஜிட்டல் மயமாக்க
🎤 *குரல் செய்தி அனுப்பவும்* கேள்விகள் கேட்க
💬 *உரை செய்தி அனுப்பவும்* விரைவான கேள்விகளுக்கு
📊 *கடன் மதிப்பெண் சரிபார்க்கவும்* - "credit score" என தட்டச்சு செய்யவும்
🛰️ *விளைச்சல் முன்னறிவிப்பு பெறவும்* - உங்கள் வயல் இடத்தை பகிரவும்

இன்று நான் உங்களுக்கு எப்படி உதவ முடியும்?"""
        }
        
        message = welcome_messages.get(language, welcome_messages['en'])
        return self.send_text_response(phone_number, message, language)
    
    def handle_rate_limit_error(self, error_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle WhatsApp API rate limit errors
        
        Args:
            error_response: Error response from Meta API
            
        Returns:
            Dictionary with retry_after seconds and error details
        """
        try:
            # Meta rate limit error code
            error_data = error_response.get('error', {})
            error_code = error_data.get('code')
            
            if error_code == 4 or error_code == 80007:  # Rate limit errors
                return {
                    'error': 'rate_limit_exceeded',
                    'retry_after': 60,  # Default 60 seconds
                    'message': 'Too many requests. Please try again later.'
                }
            
            return {
                'error': 'unknown_error',
                'message': str(error_response)
            }
            
        except Exception as e:
            print(f"Error handling rate limit: {e}")
            return {
                'error': 'error_handling_failed',
                'message': str(e)
            }


# Alias for backward compatibility
WhatsAppInterface = MetaWhatsAppInterface
