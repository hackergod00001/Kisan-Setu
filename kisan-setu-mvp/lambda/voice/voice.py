"""
Voice Handler Lambda
Transcribes voice messages and processes them using VoiceAgent
"""

import json
import os
import sys
import logging
from datetime import datetime
from voice_agent import VoiceAgent

# Import WhatsApp interface from local copy
from meta_whatsapp_interface import MetaWhatsAppInterface

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
S3_BUCKET_RAW = os.environ.get('S3_BUCKET_RAW', '')
S3_BUCKET_PROCESSED = os.environ.get('S3_BUCKET_PROCESSED', '')
REGION = os.environ.get('REGION', 'ap-south-1')

# Initialize VoiceAgent at module level (tests patch this attribute)
try:
    voice_agent = VoiceAgent(
        s3_bucket_raw=S3_BUCKET_RAW,
        s3_bucket_processed=S3_BUCKET_PROCESSED,
        region=REGION
    )
except Exception:
    voice_agent = None


def handler(event, context):
    """
    Process voice message with VoiceAgent.
    
    Expected event format:
    {
        'action': 'transcribe' | 'synthesize' | 'detect_language',
        'audio_url': 's3://bucket/key',  # For transcribe/detect_language
        'text': 'text to synthesize',    # For synthesize
        'language': 'hi-IN',              # For synthesize or as hint for transcribe
        'sender_id': 'phone_number'       # Optional
    }
    """
    
    try:
        logger.info(f"Processing voice request: {json.dumps(event)}")
        
        action = event.get('action', 'transcribe')
        sender_id = event.get('sender_id')
        language = event.get('language', 'en')
        
        if action == 'transcribe':
            audio_input = event['audio_url']
            language_hint = event.get('language', 'hi-IN')

            # Download and save audio to S3 for archival
            try:
                if not (audio_input.startswith('s3://') or audio_input.startswith('http')):
                    logger.info(f"Downloading audio from WhatsApp media ID: {audio_input}")
                    audio_url = download_and_upload_audio(audio_input, sender_id)
                else:
                    audio_url = audio_input
                logger.info(f"Audio saved successfully: {audio_url}")
            except Exception as e:
                logger.warning(f"Could not save audio: {e}")
                audio_url = audio_input

            # Transcribe audio using VoiceAgent
            result = voice_agent.transcribe_audio(audio_url, language_hint=language_hint)
            
            # Send transcription result to WhatsApp
            if sender_id:
                whatsapp = MetaWhatsAppInterface()
                
                # Format response based on language
                response_messages = {
                    'en': f"""🎤 *Voice Message Transcribed*

*Text:* {result.text}

*Detected Language:* {result.detected_language}
*Confidence:* {result.confidence:.1%}

Processing your request...""",
                    
                    'hi-IN': f"""🎤 *वॉयस मैसेज ट्रांसक्राइब किया गया*

*टेक्स्ट:* {result.text}

*पहचानी गई भाषा:* {result.detected_language}
*विश्वास:* {result.confidence:.1%}

आपके अनुरोध को संसाधित किया जा रहा है...""",
                    
                    'mr-IN': f"""🎤 *व्हॉइस मेसेज ट्रान्सक्राइब केला*

*मजकूर:* {result.text}

*ओळखली गेलेली भाषा:* {result.detected_language}
*विश्वास:* {result.confidence:.1%}

तुमची विनंती प्रक्रिया केली जात आहे...""",
                    
                    'ta-IN': f"""🎤 *குரல் செய்தி படியெடுக்கப்பட்டது*

*உரை:* {result.text}

*கண்டறியப்பட்ட மொழி:* {result.detected_language}
*நம்பிக்கை:* {result.confidence:.1%}

உங்கள் கோரிக்கை செயலாக்கப்படுகிறது..."""
                }
                
                response_text = response_messages.get(language, response_messages['en'])
                success = whatsapp.send_text_response(sender_id, response_text, language)

                if not success:
                    logger.warning(f"Failed to send WhatsApp response to {sender_id}")

            # Forward transcribed text to orchestrator for processing
            orchestrator_function = event.get('orchestrator_function') or os.environ.get('BEDROCK_ORCHESTRATOR_FUNCTION')
            if orchestrator_function and sender_id and result.text.strip():
                try:
                    import boto3 as _boto3
                    _lambda_client = _boto3.client('lambda', region_name=REGION)
                    # Use detected language for the orchestrator response
                    detected_lang = result.detected_language if result.detected_language else language
                    # Map Transcribe locale codes back to our app codes
                    lang_map = {'en-IN': 'en', 'en-US': 'en', 'en-GB': 'en',
                                'hi-IN': 'hi-IN', 'mr-IN': 'mr-IN', 'ta-IN': 'ta-IN'}
                    app_lang = lang_map.get(detected_lang, 'en')

                    logger.info(f"Forwarding transcribed text to orchestrator: '{result.text}' (lang={app_lang})")
                    _lambda_client.invoke(
                        FunctionName=orchestrator_function,
                        InvocationType='Event',  # Async so we don't block
                        Payload=json.dumps({
                            'sender_id': sender_id,
                            'message_text': result.text,
                            'message_id': event.get('message_id', ''),
                            'language': app_lang
                        }).encode('utf-8')
                    )
                    logger.info("Orchestrator invoked successfully for voice transcription")
                except Exception as fwd_err:
                    logger.error(f"Failed to forward to orchestrator: {fwd_err}")

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'action': 'transcribe',
                    'text': result.text,
                    'detected_language': result.detected_language,
                    'confidence': result.confidence,
                    'transcript_url': result.transcript_url,
                    'whatsapp_sent': success if sender_id else False
                })
            }
        
        elif action == 'synthesize':
            # Synthesize text to speech
            text = event['text']
            language = event['language']
            voice_id = event.get('voice_id')
            
            audio_url = voice_agent.synthesize_speech(text, language, voice_id)
            
            # Send audio to WhatsApp
            if sender_id:
                whatsapp = MetaWhatsAppInterface()
                success = whatsapp.send_voice_response(sender_id, audio_url)
                
                if not success:
                    logger.warning(f"Failed to send voice response to {sender_id}")
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'action': 'synthesize',
                    'audio_url': audio_url,
                    'language': language,
                    'whatsapp_sent': success if sender_id else False
                })
            }
        
        elif action == 'detect_language':
            # Detect language from audio
            audio_url = event['audio_url']
            
            detected_language = voice_agent.detect_language(audio_url)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'action': 'detect_language',
                    'detected_language': detected_language
                })
            }
        
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': f"Unknown action: {action}",
                    'supported_actions': ['transcribe', 'synthesize', 'detect_language']
                })
            }
    
    except ValueError as e:
        # User input errors (bad audio quality, unsupported language, etc.)
        logger.warning(f"Validation error: {str(e)}")
        
        # Try to send error message to user
        try:
            sender_id = event.get('sender_id')
            if sender_id:
                whatsapp = MetaWhatsAppInterface()
                error_messages = {
                    'en': 'Sorry, I could not process your voice message. Please try recording again with clear audio.',
                    'hi-IN': 'क्षमा करें, मैं आपका वॉयस मैसेज संसाधित नहीं कर सका। कृपया स्पष्ट ऑडियो के साथ फिर से रिकॉर्ड करें।',
                    'mr-IN': 'माफ करा, मी तुमचा व्हॉइस मेसेज प्रक्रिया करू शकलो नाही. कृपया स्पष्ट ऑडिओसह पुन्हा रेकॉर्ड करा.',
                    'ta-IN': 'மன்னிக்கவும், உங்கள் குரல் செய்தியை செயலாக்க முடியவில்லை. தெளிவான ஆடியோவுடன் மீண்டும் பதிவு செய்யவும்.'
                }
                language = event.get('language', 'en')
                error_msg = error_messages.get(language, error_messages['en'])
                whatsapp.send_text_response(sender_id, error_msg, language)
        except Exception as notify_err:
            logger.error(f"Failed to send validation error notification: {notify_err}")

        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': str(e),
                'error_type': 'validation_error'
            })
        }
    
    except RuntimeError as e:
        # Service errors (transcription failed, synthesis failed, etc.)
        logger.error(f"Runtime error: {str(e)}")
        
        # Try to send error message to user
        try:
            sender_id = event.get('sender_id')
            if sender_id:
                whatsapp = MetaWhatsAppInterface()
                error_messages = {
                    'en': 'Sorry, there was a problem processing your voice message. Please try again later.',
                    'hi-IN': 'क्षमा करें, आपके वॉयस मैसेज को संसाधित करने में समस्या थी। कृपया बाद में पुनः प्रयास करें।',
                    'mr-IN': 'माफ करा, तुमचा व्हॉइस मेसेज प्रक्रिया करताना समस्या आली. कृपया नंतर पुन्हा प्रयत्न करा.',
                    'ta-IN': 'மன்னிக்கவும், உங்கள் குரல் செய்தியை செயலாக்குவதில் சிக்கல் ஏற்பட்டது. பிறகு மீண்டும் முயற்சிக்கவும்.'
                }
                language = event.get('language', 'en')
                error_msg = error_messages.get(language, error_messages['en'])
                whatsapp.send_text_response(sender_id, error_msg, language)
        except Exception as notify_err:
            logger.error(f"Failed to send service error notification: {notify_err}")

        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'error_type': 'service_error'
            })
        }
    
    except Exception as e:
        # Unexpected errors
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        
        # Try to send error message to user
        try:
            sender_id = event.get('sender_id')
            if sender_id:
                whatsapp = MetaWhatsAppInterface()
                error_messages = {
                    'en': 'Sorry, an unexpected error occurred. Please try again.',
                    'hi-IN': 'क्षमा करें, एक अप्रत्याशित त्रुटि हुई। कृपया पुनः प्रयास करें।',
                    'mr-IN': 'माफ करा, अनपेक्षित त्रुटी आली. कृपया पुन्हा प्रयत्न करा.',
                    'ta-IN': 'மன்னிக்கவும், எதிர்பாராத பிழை ஏற்பட்டது. மீண்டும் முயற்சிக்கவும்.'
                }
                language = event.get('language', 'en')
                error_msg = error_messages.get(language, error_messages['en'])
                whatsapp.send_text_response(sender_id, error_msg, language)
        except Exception as notify_err:
            logger.error(f"Failed to send unexpected error notification: {notify_err}")

        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'An unexpected error occurred',
                'error_type': 'internal_error'
            })
        }


def download_and_upload_audio(media_id: str, sender_id: str) -> str:
    """
    Download audio from WhatsApp and upload to S3.

    Args:
        media_id: WhatsApp media ID
        sender_id: Phone number

    Returns:
        S3 URL where audio was uploaded
    """
    import boto3

    s3_client = boto3.client('s3')

    try:
        # Initialize WhatsApp interface
        whatsapp = MetaWhatsAppInterface()

        # Download media from WhatsApp (returns S3 URL if already uploaded)
        logger.info(f"Downloading audio {media_id} from WhatsApp...")
        media_url = whatsapp.download_media(media_id)

        if not media_url:
            raise Exception(f"Failed to download audio {media_id} from WhatsApp")

        # Check if media is already uploaded to S3
        if media_url.startswith('s3://'):
            logger.info(f"Audio already uploaded to S3: {media_url}")
            return media_url

        # If it's an HTTP URL, download and upload to S3
        import requests

        response = requests.get(media_url, headers={
            'Authorization': f'Bearer {whatsapp.access_token}'
        }, timeout=30)

        if response.status_code != 200:
            raise Exception(f"Failed to download audio content: {response.status_code}")

        # Generate S3 key
        from datetime import datetime
        timestamp = datetime.utcnow().isoformat().replace(':', '-')

        # Detect audio format (WhatsApp usually sends .ogg or .opus)
        content_type = response.headers.get('Content-Type', 'audio/ogg')
        extension = '.ogg' if 'ogg' in content_type else '.opus' if 'opus' in content_type else '.mp3'
        s3_key = f"voice-messages/{sender_id}/{timestamp}{extension}"

        # Upload to S3
        logger.info(f"Uploading audio to S3: {s3_key}")
        s3_client.put_object(
            Bucket=S3_BUCKET_RAW,
            Key=s3_key,
            Body=response.content,
            ContentType=content_type
        )

        s3_url = f"s3://{S3_BUCKET_RAW}/{s3_key}"
        logger.info(f"Audio uploaded successfully: {s3_url}")
        return s3_url

    except Exception as e:
        logger.error(f"Error downloading and uploading audio: {str(e)}")
        raise
