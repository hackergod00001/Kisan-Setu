"""
Document Processor Component
Extracts structured data from handwritten ledger images using Amazon Textract.

This component implements the DocumentProcessor class as specified in the design document,
with support for Hindi, Marathi, and Tamil scripts.
"""

import json
import boto3
import os
import sys
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from decimal import Decimal
from dataclasses import dataclass, asdict

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.error_handling import (
    retry_with_exponential_backoff,
    create_error_response,
    process_batch_with_resilience,
    ErrorCategory,
    ErrorSeverity
)
from common.cost_optimization import (
    textract_batcher,
    concurrent_processor
)
from common.llm_adapter import LLMAdapter, LLMAdapterError
# Import WhatsApp interface from local copy
from meta_whatsapp_interface import MetaWhatsAppInterface

# AWS clients
textract = boto3.client('textract')
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

# Environment variables
S3_BUCKET_RAW = os.environ.get('S3_BUCKET_RAW', 'kisan-setu-raw')
S3_BUCKET_PROCESSED = os.environ.get('S3_BUCKET_PROCESSED', 'kisan-setu-processed')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'KisanSetuData')
REGION = os.environ.get('REGION', 'ap-south-1')

table = dynamodb.Table(DYNAMODB_TABLE)

# Textract queries for ledger extraction (supports Hindi, Marathi, Tamil)
LEDGER_QUERIES = [
    {'Text': 'What is the quantity?', 'Alias': 'QUANTITY'},
    {'Text': 'What is the moisture level?', 'Alias': 'MOISTURE'},
    {'Text': 'What is the price?', 'Alias': 'PRICE'},
    {'Text': 'What is the date?', 'Alias': 'DATE'},
    {'Text': 'What is the farmer name?', 'Alias': 'FARMER_NAME'},
    {'Text': 'What is the crop type?', 'Alias': 'CROP_TYPE'},
    {'Text': 'What is the quality grade?', 'Alias': 'QUALITY_GRADE'}
]

# Confidence threshold for field validation
CONFIDENCE_THRESHOLD = 70.0


@dataclass
class LedgerData:
    """Structured data extracted from handwritten ledger images."""
    ledger_id: str
    farmer_id: str
    quantity: float
    moisture: float
    price: float
    date: str
    crop_type: str
    farmer_name: str
    quality_grade: str
    confidence_scores: Dict[str, float]
    image_url: str
    fields_needing_review: List[str]


@dataclass
class ValidationResult:
    """Result of ledger data validation."""
    is_valid: bool
    fields_needing_review: List[str]
    missing_fields: List[str]
    low_confidence_fields: List[str]


@dataclass
class AggregatedData:
    """Aggregated data from multiple ledger extractions."""
    farmer_id: str
    total_records: int
    ledger_ids: List[str]
    transactions: List[Dict[str, Any]]
    aggregation_date: str


class DocumentProcessor:
    """
    Document Processor Component for extracting structured data from handwritten ledgers.
    
    Supports Hindi, Marathi, and Tamil scripts using Amazon Textract Queries.
    Implements confidence score validation and low-confidence field flagging.
    """
    
    def __init__(
        self,
        textract_client=None,
        s3_client=None,
        dynamodb_table=None,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        use_multimodal_llm: bool = True
    ):
        """
        Initialize DocumentProcessor.

        Args:
            textract_client: Optional boto3 Textract client (for testing)
            s3_client: Optional boto3 S3 client (for testing)
            dynamodb_table: Optional DynamoDB table resource (for testing)
            confidence_threshold: Minimum confidence score for field validation
            use_multimodal_llm: Whether to use multimodal LLM for image understanding
        """
        self.textract = textract_client or textract
        self.s3 = s3_client or s3
        self.table = dynamodb_table or table
        self.confidence_threshold = confidence_threshold
        self.use_multimodal_llm = use_multimodal_llm
        self.llm_adapter = LLMAdapter() if use_multimodal_llm else None
    
    # Known Indian crops for validation and fuzzy matching
    KNOWN_CROPS = [
        'onion', 'wheat', 'rice', 'cotton', 'soybean', 'sugarcane', 'maize',
        'jowar', 'bajra', 'tur', 'gram', 'groundnut', 'sunflower', 'mustard',
        'potato', 'tomato', 'brinjal', 'chilli', 'turmeric', 'ginger',
        'garlic', 'coriander', 'cumin', 'fenugreek', 'mango', 'banana',
        'pomegranate', 'grapes', 'orange', 'lemon', 'papaya', 'guava',
        # Hindi names
        'प्याज', 'गेहूं', 'चावल', 'कपास', 'सोयाबीन', 'गन्ना', 'मक्का',
        'ज्वार', 'बाजरा', 'तूर', 'चना', 'मूंगफली', 'सूरजमुखी', 'सरसों',
        'आलू', 'टमाटर', 'बैंगन', 'मिर्च', 'हल्दी', 'अदरक', 'लहसुन',
        # Marathi names
        'कांदा', 'गहू', 'तांदूळ', 'कापूस', 'ऊस',
    ]

    def extract_ledger_data(self, image_url: str, language: str = 'en') -> LedgerData:
        """
        Extracts structured data from ledger image.

        Strategy: Always use multimodal LLM as primary (more accurate for handwritten
        Indian agricultural ledgers). Fall back to Textract if LLM fails.

        Args:
            image_url: S3 URL or key to the ledger image
            language: Language code (hi-IN, mr-IN, ta-IN, en)

        Returns:
            LedgerData with fields and confidence scores

        Raises:
            Exception: If all extraction methods fail
        """
        print(f"Extracting ledger data from: {image_url}, language: {language}")

        # Parse S3 URL to get bucket and key
        s3_bucket, s3_key = self._parse_s3_url(image_url)

        # Strategy: LLM first (better for handwritten Indian ledgers), Textract as fallback
        ledger_data = None

        # Try multimodal LLM first (primary path)
        if self.use_multimodal_llm and self.llm_adapter:
            try:
                print("Using multimodal LLM as primary extraction method...")
                ledger_data = self._extract_with_multimodal_llm(image_url, language, s3_bucket, s3_key)
                print(f"LLM extraction succeeded: {ledger_data.ledger_id}")
            except Exception as llm_error:
                print(f"LLM extraction failed: {str(llm_error)}, falling back to Textract...")

        # Fallback to Textract if LLM failed or not available
        if ledger_data is None:
            try:
                response = self._analyze_document_with_retry(s3_bucket, s3_key)
                extracted_data = self._parse_textract_response(response)

                ledger_id = f"LEDGER#{datetime.utcnow().isoformat()}"
                farmer_id = self._extract_farmer_id_from_url(image_url)

                ledger_data = LedgerData(
                    ledger_id=ledger_id,
                    farmer_id=farmer_id,
                    quantity=self._safe_float(extracted_data.get('QUANTITY', {}).get('value', '0')),
                    moisture=self._safe_float(extracted_data.get('MOISTURE', {}).get('value', '0')),
                    price=self._safe_float(extracted_data.get('PRICE', {}).get('value', '0')),
                    date=extracted_data.get('DATE', {}).get('value', ''),
                    crop_type=extracted_data.get('CROP_TYPE', {}).get('value', 'unknown'),
                    farmer_name=extracted_data.get('FARMER_NAME', {}).get('value', ''),
                    quality_grade=extracted_data.get('QUALITY_GRADE', {}).get('value', ''),
                    confidence_scores={
                        k: v['confidence'] for k, v in extracted_data.items()
                    },
                    image_url=image_url,
                    fields_needing_review=[]
                )

                # Post-process Textract results with LLM to fix common errors
                if self.use_multimodal_llm and self.llm_adapter:
                    ledger_data = self._post_process_with_llm(ledger_data, s3_bucket, s3_key)

            except Exception as e:
                print(f"Textract extraction also failed: {str(e)}")
                error = create_error_response(
                    error_code='EXTRACTION_FAILED',
                    technical_details=f"All extraction methods failed: {str(e)}",
                    language=language,
                    category=ErrorCategory.EXTERNAL_SERVICE,
                    severity=ErrorSeverity.HIGH
                )
                raise Exception(error.user_message)

        # Sanitize extracted fields
        ledger_data = self._sanitize_fields(ledger_data)

        print(f"Successfully extracted ledger data: {ledger_data.ledger_id}")
        return ledger_data
    
    @retry_with_exponential_backoff(max_retries=3, service_name='textract')
    def _analyze_document_with_retry(self, s3_bucket: str, s3_key: str) -> Dict:
        """Analyze document with Textract with retry logic."""
        return self.textract.analyze_document(
            Document={
                'S3Object': {
                    'Bucket': s3_bucket,
                    'Name': s3_key
                }
            },
            FeatureTypes=['QUERIES'],
            QueriesConfig={'Queries': LEDGER_QUERIES}
        )

    def _extract_with_multimodal_llm(
        self,
        image_url: str,
        language: str,
        s3_bucket: str,
        s3_key: str
    ) -> LedgerData:
        """
        Extract ledger data using multimodal LLM (Claude 3 vision).

        Args:
            image_url: S3 URL to the image
            language: Language code
            s3_bucket: S3 bucket name
            s3_key: S3 key

        Returns:
            LedgerData extracted by multimodal LLM
        """
        print(f"Using multimodal LLM for extraction: {image_url}")

        # Download image from S3
        response = self.s3.get_object(Bucket=s3_bucket, Key=s3_key)
        image_data = response['Body'].read()

        # Determine image format from key
        image_format = 'jpeg' if s3_key.lower().endswith(('.jpg', '.jpeg')) else 'png'

        # Prepare prompt — handles both formal ledger books and simple handwritten notes
        base_prompt = """You are analyzing a photo of a handwritten Indian agricultural record. It could be a formal ledger book OR a simple handwritten note/receipt.

CRITICAL RULES:
1. ONLY extract values you can actually SEE written in the image. Do NOT guess or infer.
2. If a field is not written in the image, return "0" for numbers or "" for text.
3. crop_type MUST be an actual crop name in English (e.g. "onion", "wheat", "rice", "cotton", "tomato"). The text may be in Hindi/Marathi — translate to English.
4. quantity: Extract the numeric weight value only (in kg). E.g. "6kg" → "6", "2 quintal" → "200".
5. price: The selling price in rupees. ONLY if explicitly written as a price/amount. Do NOT confuse quantity with price.
6. moisture: Percentage value (0-100). Only if explicitly mentioned.
7. quality_grade: Grade like A/B/C or descriptive quality. Only if explicitly mentioned.
8. date: In YYYY-MM-DD format. If only day-month visible, use current year.
9. farmer_name: Only if a person's name is written.

Respond ONLY with valid JSON, no other text:
{"crop_type": "...", "quantity": "...", "price": "...", "moisture": "...", "quality_grade": "...", "date": "...", "farmer_name": "..."}"""

        prompt = base_prompt

        # Call multimodal LLM
        response_text, input_tokens, output_tokens = self.llm_adapter.converse_with_image(
            prompt=prompt,
            image_data=image_data,
            image_format=image_format,
            temperature=0.1  # Very low temperature for deterministic extraction
        )

        print(f"LLM response: {response_text}")
        print(f"Token usage: {input_tokens} in / {output_tokens} out")

        # Parse JSON response
        extracted_data = self._parse_llm_response(response_text)

        # Generate ledger ID
        ledger_id = f"LEDGER#{datetime.utcnow().isoformat()}"

        # Extract farmer ID from image URL
        farmer_id = self._extract_farmer_id_from_url(image_url)

        # Build LedgerData object
        # LLM confidence is estimated based on successful parsing
        confidence = 85.0  # Assume high confidence if LLM parsed successfully

        ledger_data = LedgerData(
            ledger_id=ledger_id,
            farmer_id=farmer_id,
            quantity=self._safe_float(extracted_data.get('quantity', '0')),
            moisture=self._safe_float(extracted_data.get('moisture', '0')),
            price=self._safe_float(extracted_data.get('price', '0')),
            date=extracted_data.get('date', ''),
            crop_type=extracted_data.get('crop_type', 'unknown'),
            farmer_name=extracted_data.get('farmer_name', ''),
            quality_grade=extracted_data.get('quality_grade', ''),
            confidence_scores={
                'QUANTITY': confidence,
                'MOISTURE': confidence,
                'PRICE': confidence,
                'DATE': confidence,
                'CROP_TYPE': confidence,
                'FARMER_NAME': confidence,
                'QUALITY_GRADE': confidence
            },
            image_url=image_url,
            fields_needing_review=[]
        )

        print(f"Successfully extracted via LLM: {ledger_id}")
        return ledger_data

    def _parse_llm_response(self, response_text: str) -> Dict[str, str]:
        """Parse JSON from LLM response."""
        try:
            # Try to extract JSON from response (may have markdown code blocks)
            import re

            # Remove markdown code blocks if present
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)

            # Also try to find JSON object directly
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

            data = json.loads(response_text)
            return data
        except Exception as e:
            print(f"Failed to parse LLM response as JSON: {e}")
            print(f"Raw response: {response_text}")
            return {}

    def _post_process_with_llm(self, ledger_data: LedgerData, s3_bucket: str, s3_key: str) -> LedgerData:
        """
        Post-process Textract results using multimodal LLM to fix common extraction errors.
        Sends the image + Textract raw output to the LLM for intelligent correction.
        """
        try:
            print("Post-processing Textract results with multimodal LLM...")

            # Download image
            response = self.s3.get_object(Bucket=s3_bucket, Key=s3_key)
            image_data = response['Body'].read()
            image_format = 'jpeg' if s3_key.lower().endswith(('.jpg', '.jpeg')) else 'png'

            prompt = f"""You are analyzing a handwritten Indian agricultural ledger/receipt image.
Textract extracted these raw values (many may be wrong):
- Crop Type: {ledger_data.crop_type}
- Quantity: {ledger_data.quantity}
- Price: {ledger_data.price}
- Moisture: {ledger_data.moisture}
- Quality Grade: {ledger_data.quality_grade}
- Date: {ledger_data.date}
- Farmer Name: {ledger_data.farmer_name}

Look at the actual image and correct the extracted values. Rules:
1. crop_type MUST be an actual crop name (e.g. onion, wheat, rice, cotton). If Textract returned nonsense like "YES", "NO", a number, or gibberish, identify the crop from the image.
2. quantity should be in kg. Extract only the numeric weight value.
3. price should be in rupees (₹). If no price is visible in the image, return 0.
4. moisture should be a percentage (0-100). If not visible, return 0.
5. quality_grade should be A/B/C or a descriptive grade. If not visible, return empty string.
6. date should be in YYYY-MM-DD format. If only partial date visible, fill in what you can. If not visible, return empty string.
7. farmer_name: extract if visible, otherwise return empty string.

IMPORTANT: Only return values you can actually see in the image. Use 0 or empty string for fields not present.

Respond ONLY with JSON: {{"crop_type": "...", "quantity": "...", "price": "...", "moisture": "...", "quality_grade": "...", "date": "...", "farmer_name": "..."}}"""

            response_text, _, _ = self.llm_adapter.converse_with_image(
                prompt=prompt,
                image_data=image_data,
                image_format=image_format,
                temperature=0.1
            )

            corrected = self._parse_llm_response(response_text)
            if corrected:
                print(f"LLM corrections: {corrected}")
                # Apply corrections
                if corrected.get('crop_type') and corrected['crop_type'].lower() not in ('unknown', 'yes', 'no', ''):
                    ledger_data.crop_type = corrected['crop_type']
                    ledger_data.confidence_scores['CROP_TYPE'] = 90.0
                if corrected.get('quantity'):
                    val = self._safe_float(corrected['quantity'])
                    if val > 0:
                        ledger_data.quantity = val
                        ledger_data.confidence_scores['QUANTITY'] = 90.0
                if corrected.get('price'):
                    val = self._safe_float(corrected['price'])
                    ledger_data.price = val
                    ledger_data.confidence_scores['PRICE'] = 90.0 if val > 0 else 0.0
                if corrected.get('moisture'):
                    val = self._safe_float(corrected['moisture'])
                    ledger_data.moisture = val
                    ledger_data.confidence_scores['MOISTURE'] = 90.0 if val > 0 else 0.0
                if corrected.get('quality_grade'):
                    ledger_data.quality_grade = corrected['quality_grade']
                    ledger_data.confidence_scores['QUALITY_GRADE'] = 90.0 if corrected['quality_grade'] else 0.0
                if corrected.get('date'):
                    ledger_data.date = self._normalize_date(corrected['date'])
                    ledger_data.confidence_scores['DATE'] = 90.0 if ledger_data.date else 0.0
                if corrected.get('farmer_name'):
                    ledger_data.farmer_name = corrected['farmer_name']
                    ledger_data.confidence_scores['FARMER_NAME'] = 90.0 if corrected['farmer_name'] else 0.0

        except Exception as e:
            print(f"LLM post-processing failed (using raw Textract): {str(e)}")

        return ledger_data

    def _sanitize_fields(self, ledger_data: LedgerData) -> LedgerData:
        """Sanitize and validate extracted fields with domain-specific rules."""
        import re

        # Fix crop_type: must be an actual crop name
        crop = ledger_data.crop_type.strip()
        if crop.lower() in ('yes', 'no', 'unknown', '', 'none', 'n/a') or crop.replace('.', '').isdigit():
            ledger_data.crop_type = 'unknown'
            ledger_data.confidence_scores['CROP_TYPE'] = 0.0

        # Fix price: if price equals quantity AND both have low confidence, it's likely a misread
        # (Textract sometimes returns the same number for different fields)
        if (ledger_data.price > 0 and ledger_data.price == ledger_data.quantity
                and ledger_data.confidence_scores.get('PRICE', 0) < self.confidence_threshold
                and ledger_data.confidence_scores.get('QUANTITY', 0) < self.confidence_threshold):
            print(f"Price ({ledger_data.price}) equals quantity with both low confidence — likely misread, resetting price to 0")
            ledger_data.price = 0.0
            ledger_data.confidence_scores['PRICE'] = 0.0

        # Fix moisture: must be 0-100 range
        if ledger_data.moisture < 0 or ledger_data.moisture > 100:
            ledger_data.moisture = 0.0
            ledger_data.confidence_scores['MOISTURE'] = 0.0

        # Fix quality_grade: should be a grade, not a random number > 100
        grade = str(ledger_data.quality_grade).strip()
        try:
            grade_num = float(grade)
            if grade_num > 100:
                ledger_data.quality_grade = ''
                ledger_data.confidence_scores['QUALITY_GRADE'] = 0.0
        except ValueError:
            pass  # Non-numeric grade is fine (A, B, C, etc.)

        # Fix date: normalize to YYYY-MM-DD
        ledger_data.date = self._normalize_date(ledger_data.date)

        return ledger_data

    def _normalize_date(self, date_str: str) -> str:
        """Normalize date string to YYYY-MM-DD format."""
        import re
        if not date_str or not date_str.strip():
            return ''

        date_str = date_str.strip()

        # Already in YYYY-MM-DD format
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return date_str

        # Try common formats
        formats = [
            '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y',
            '%d-%m-%y', '%d/%m/%y', '%d.%m.%y',
            '%Y/%m/%d', '%m-%d-%Y', '%m/%d/%Y',
            '%d %b %Y', '%d %B %Y',
        ]
        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                return parsed.strftime('%Y-%m-%d')
            except ValueError:
                continue

        # Handle partial dates like "06-06" or "06- 06"
        clean = re.sub(r'\s+', '', date_str)
        match = re.match(r'^(\d{1,2})[/\-.](\d{1,2})$', clean)
        if match:
            day, month = match.group(1), match.group(2)
            year = datetime.utcnow().year
            try:
                parsed = datetime(year, int(month), int(day))
                return parsed.strftime('%Y-%m-%d')
            except ValueError:
                pass

        print(f"Could not normalize date: {date_str}")
        return date_str
    
    def validate_extraction(self, ledger_data: LedgerData) -> ValidationResult:
        """
        Validates extracted data and flags low-confidence fields.
        
        Args:
            ledger_data: LedgerData object to validate
            
        Returns:
            ValidationResult with valid fields and fields_needing_review
        """
        validation_result = ValidationResult(
            is_valid=True,
            fields_needing_review=[],
            missing_fields=[],
            low_confidence_fields=[]
        )
        
        # Required fields for a valid transaction
        required_fields = ['QUANTITY', 'PRICE', 'CROP_TYPE']
        
        # Check each required field
        for field in required_fields:
            if field not in ledger_data.confidence_scores:
                validation_result.missing_fields.append(field)
                validation_result.is_valid = False
                continue
            
            # Check if field value is empty or zero for numeric fields
            field_attr = field.lower()
            field_value = getattr(ledger_data, field_attr, None)
            if field_value is None or (isinstance(field_value, str) and not field_value.strip()):
                validation_result.missing_fields.append(field)
                validation_result.is_valid = False
                continue
            if isinstance(field_value, (int, float)) and field_value == 0:
                validation_result.missing_fields.append(field)
                validation_result.is_valid = False
                continue
            # Special check: crop_type must be a real crop name
            if field == 'CROP_TYPE' and str(field_value).lower() in ('unknown', 'yes', 'no', 'none', 'n/a'):
                validation_result.missing_fields.append(field)
                validation_result.is_valid = False
                continue
            
            # Check confidence score
            confidence = ledger_data.confidence_scores.get(field, 0)
            if confidence < self.confidence_threshold:
                validation_result.low_confidence_fields.append(field)
                validation_result.fields_needing_review.append(field)
        
        # Check optional fields for low confidence
        optional_fields = ['MOISTURE', 'DATE', 'FARMER_NAME', 'QUALITY_GRADE']
        for field in optional_fields:
            if field in ledger_data.confidence_scores:
                confidence = ledger_data.confidence_scores[field]
                if confidence < self.confidence_threshold:
                    validation_result.low_confidence_fields.append(field)
                    validation_result.fields_needing_review.append(field)
        
        # Also add missing required fields to fields_needing_review
        for field in validation_result.missing_fields:
            if field not in validation_result.fields_needing_review:
                validation_result.fields_needing_review.append(field)
        
        # Update ledger_data with fields needing review
        ledger_data.fields_needing_review = validation_result.fields_needing_review
        
        print(f"Validation result: valid={validation_result.is_valid}, "
              f"needs_review={validation_result.fields_needing_review}")
        
        return validation_result
    
    def aggregate_ledgers(self, ledger_list: List[LedgerData]) -> AggregatedData:
        """
        Combines multiple ledger extractions into single dataset.
        
        Args:
            ledger_list: List of LedgerData objects to aggregate
            
        Returns:
            AggregatedData with consolidated records
        """
        if not ledger_list:
            raise ValueError("Cannot aggregate empty ledger list")
        
        # All ledgers should be from the same farmer
        farmer_id = ledger_list[0].farmer_id
        
        # Build transaction list
        transactions = []
        ledger_ids = []
        
        for ledger in ledger_list:
            ledger_ids.append(ledger.ledger_id)
            
            # Convert ledger to transaction format
            transaction = {
                'ledger_id': ledger.ledger_id,
                'quantity': ledger.quantity,
                'moisture': ledger.moisture,
                'price': ledger.price,
                'date': ledger.date,
                'crop_type': ledger.crop_type,
                'farmer_name': ledger.farmer_name,
                'quality_grade': ledger.quality_grade,
                'confidence_scores': ledger.confidence_scores,
                'image_url': ledger.image_url,
                'fields_needing_review': ledger.fields_needing_review
            }
            transactions.append(transaction)
        
        aggregated = AggregatedData(
            farmer_id=farmer_id,
            total_records=len(ledger_list),
            ledger_ids=ledger_ids,
            transactions=transactions,
            aggregation_date=datetime.utcnow().isoformat()
        )
        
        print(f"Aggregated {len(ledger_list)} ledgers for farmer {farmer_id}")
        return aggregated
    
    def process_batch_ledgers(
        self,
        image_urls: List[str],
        language: str = 'en'
    ) -> Dict[str, Any]:
        """
        Process multiple ledger images with resilience (continue on individual failures).
        
        Uses TextractBatcher for efficient batch processing with concurrent execution.
        
        Args:
            image_urls: List of S3 URLs to ledger images
            language: Language code for error messages
            
        Returns:
            Dictionary with success_count, failure_count, results, and errors
        """
        print(f"Processing batch of {len(image_urls)} ledgers")
        
        # Parse S3 URLs to get bucket and key
        documents = []
        for url in image_urls:
            bucket, key = self._parse_s3_url(url)
            documents.append({
                'bucket': bucket,
                'key': key,
                'url': url
            })
        
        # Use TextractBatcher for efficient batch processing
        batch_result = textract_batcher.process_batch(documents, LEDGER_QUERIES)
        
        # Process Textract results and store in DynamoDB
        processed_results = []
        for result in batch_result.results:
            try:
                doc = result['document']
                textract_response = result['response']
                
                # Parse Textract response
                extracted_data = self._parse_textract_response(textract_response)
                
                # Build LedgerData
                ledger_id = f"LEDGER#{datetime.utcnow().isoformat()}"
                farmer_id = self._extract_farmer_id_from_url(doc['url'])
                
                ledger_data = LedgerData(
                    ledger_id=ledger_id,
                    farmer_id=farmer_id,
                    quantity=self._safe_float(extracted_data.get('QUANTITY', {}).get('value', '0')),
                    moisture=self._safe_float(extracted_data.get('MOISTURE', {}).get('value', '0')),
                    price=self._safe_float(extracted_data.get('PRICE', {}).get('value', '0')),
                    date=extracted_data.get('DATE', {}).get('value', ''),
                    crop_type=extracted_data.get('CROP_TYPE', {}).get('value', 'unknown'),
                    farmer_name=extracted_data.get('FARMER_NAME', {}).get('value', ''),
                    quality_grade=extracted_data.get('QUALITY_GRADE', {}).get('value', ''),
                    confidence_scores={k: v['confidence'] for k, v in extracted_data.items()},
                    image_url=doc['url'],
                    fields_needing_review=[]
                )
                
                # Validate and store
                validation_result = self.validate_extraction(ledger_data)
                transaction_id = self.store_ledger_data(ledger_data, validation_result)
                
                processed_results.append({
                    'transaction_id': transaction_id,
                    'ledger_id': ledger_id,
                    'status': 'success'
                })
                
            except Exception as e:
                print(f"Error processing result: {str(e)}")
                batch_result.errors.append({
                    'document': result.get('document', {}),
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        return {
            'success_count': len(processed_results),
            'failure_count': len(batch_result.errors),
            'results': processed_results,
            'errors': batch_result.errors,
            'processing_time': batch_result.processing_time
        }
    
    # ==================== Helper Methods ====================
    
    def _parse_s3_url(self, image_url: str) -> tuple:
        """Parse S3 URL to extract bucket and key."""
        if image_url.startswith('s3://'):
            # Format: s3://bucket/key
            parts = image_url[5:].split('/', 1)
            return parts[0], parts[1] if len(parts) > 1 else ''
        else:
            # Assume it's just a key in the default bucket
            return S3_BUCKET_RAW, image_url
    
    def _extract_farmer_id_from_url(self, image_url: str) -> str:
        """Extract farmer ID from image URL path."""
        # Expected format: ledger-images/{phone_number}/{timestamp}.jpg
        try:
            if 'ledger-images/' in image_url:
                parts = image_url.split('ledger-images/')[1].split('/')
                phone_number = parts[0]
                return f"FARMER#{phone_number}"
        except:
            pass
        return "FARMER#unknown"
    
    def _parse_textract_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Textract response to extract query results."""
        # Build a map of query IDs to aliases
        query_map = {}
        for block in response['Blocks']:
            if block['BlockType'] == 'QUERY':
                query_map[block['Id']] = block['Query']['Alias']
        
        # Extract answers
        extracted_data = {}
        for block in response['Blocks']:
            if block['BlockType'] == 'QUERY_RESULT':
                # Find parent query by checking relationships
                query_id = None
                for parent_block in response['Blocks']:
                    if parent_block['BlockType'] == 'QUERY':
                        if 'Relationships' in parent_block:
                            for rel in parent_block['Relationships']:
                                if rel['Type'] == 'ANSWER' and block['Id'] in rel['Ids']:
                                    query_id = parent_block['Id']
                                    break
                
                if query_id and query_id in query_map:
                    alias = query_map[query_id]
                    text = block.get('Text', '')
                    confidence = block.get('Confidence', 0)
                    
                    extracted_data[alias] = {
                        'value': text,
                        'confidence': float(confidence)
                    }
        
        return extracted_data
    
    def _safe_float(self, value: str, default: float = 0.0) -> float:
        """Safely convert string to float, handling scientific notation and removing non-numeric characters."""
        try:
            value_str = str(value).strip()
            
            # First, try direct conversion (handles scientific notation like '5e-324', '1.5e10')
            try:
                result = float(value_str)
                # Validate the result is reasonable for our use case
                # Scientific notation values like 5e-324 are essentially 0 for our purposes
                if abs(result) < 1e-100:
                    return 0.0
                return result
            except ValueError:
                pass
            
            # If direct conversion fails, extract numeric characters
            # This handles cases like "Rs. 2500" where the period after Rs shouldn't be treated as decimal
            result = ''
            decimal_found = False
            
            for i, c in enumerate(value_str):
                if c.isdigit():
                    result += c
                elif c == '.' and not decimal_found:
                    # Only treat as decimal if there are digits before and after
                    # or if there are digits before and we're not at the end
                    if result and (i + 1 < len(value_str) and value_str[i + 1].isdigit()):
                        result += c
                        decimal_found = True
            
            return float(result) if result and result != '.' else default
        except:
            return default
    
    def store_ledger_data(self, ledger_data: LedgerData, validation_result: ValidationResult) -> str:
        """
        Store extracted ledger data in DynamoDB and return transaction ID.
        
        Args:
            ledger_data: LedgerData object to store
            validation_result: ValidationResult from validation
            
        Returns:
            Transaction ID
        """
        timestamp = datetime.utcnow().isoformat()
        transaction_id = f"TXN#{timestamp}"
        
        try:
            item = {
                'PK': ledger_data.farmer_id,
                'SK': transaction_id,
                'entity_type': 'Transaction',
                'transaction_id': transaction_id,
                'ledger_id': ledger_data.ledger_id,
                'farmer_id': ledger_data.farmer_id,
                'quantity': Decimal(str(ledger_data.quantity)),
                'moisture': Decimal(str(ledger_data.moisture)),
                'price': Decimal(str(ledger_data.price)),
                'date': ledger_data.date,
                'crop_type': ledger_data.crop_type,
                'farmer_name': ledger_data.farmer_name,
                'quality_grade': ledger_data.quality_grade,
                'ledger_image_url': ledger_data.image_url,
                'confidence_scores': {
                    k: Decimal(str(v)) for k, v in ledger_data.confidence_scores.items()
                },
                'validation_status': 'valid' if validation_result.is_valid else 'needs_review',
                'fields_needing_review': validation_result.fields_needing_review,
                'sync_status': 'synced',
                'timestamp': timestamp,
                'created_at': timestamp
            }
            
            self.table.put_item(Item=item)
            print(f"Stored transaction: {transaction_id}")
            return transaction_id
            
        except Exception as e:
            print(f"Error storing ledger data: {str(e)}")
            raise


# ==================== Lambda Handler ====================

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for document processing.
    
    Input:
        - sender: Phone number
        - message_id: WhatsApp message ID
        - image_id: WhatsApp image ID (optional)
        - s3_key: S3 key if image already uploaded (optional)
        - language: Language code (hi-IN, mr-IN, ta-IN, en)
    
    Output:
        - Structured ledger data stored in DynamoDB
        - Response with transaction details sent to WhatsApp
    """
    
    try:
        print(f"Processing document: {json.dumps(event)}")
        
        sender = event.get('sender')
        message_id = event.get('message_id')
        image_id = event.get('image_id')
        s3_key = event.get('s3_key')
        language = event.get('language', 'en')
        
        if not sender:
            raise ValueError("Missing required field: sender")
        
        # If s3_key not provided, download from WhatsApp and upload to S3
        if not s3_key:
            if image_id:
                s3_key = download_and_upload_image(image_id, sender)
            else:
                raise ValueError("Either s3_key or image_id must be provided")
        
        # Build S3 URL
        image_url = f"s3://{S3_BUCKET_RAW}/{s3_key}"
        
        # Initialize DocumentProcessor
        processor = DocumentProcessor()
        
        # Extract data using Textract
        ledger_data = processor.extract_ledger_data(image_url, language)
        
        # Validate extraction
        validation_result = processor.validate_extraction(ledger_data)
        
        # Store in DynamoDB
        transaction_id = processor.store_ledger_data(ledger_data, validation_result)
        
        # Format response for WhatsApp — show "Not detected" for missing values
        def fmt(val, unit='', is_currency=False):
            """Format a field value, showing 'Not detected' for empty/zero."""
            if val is None:
                return 'Not detected'
            if isinstance(val, (int, float)) and val == 0:
                return 'Not detected'
            if isinstance(val, str) and not val.strip():
                return 'Not detected'
            if isinstance(val, str) and val.lower() in ('unknown', 'none', 'n/a'):
                return 'Not detected'
            if is_currency:
                return f"₹{val}"
            return f"{val}{unit}"

        crop_display = fmt(ledger_data.crop_type)
        qty_display = fmt(ledger_data.quantity, ' kg')
        price_display = fmt(ledger_data.price, is_currency=True)
        moisture_display = fmt(ledger_data.moisture, '%')
        grade_display = fmt(ledger_data.quality_grade)
        date_display = fmt(ledger_data.date)

        response_messages = {
            'en': f"""✅ *Ledger Processed Successfully*

📋 *Transaction ID:* {transaction_id}

*Extracted Data:*
• Crop Type: {crop_display}
• Quantity: {qty_display}
• Price: {price_display}
• Moisture: {moisture_display}
• Quality Grade: {grade_display}
• Date: {date_display}

{f"⚠️ *Fields needing review:* {', '.join(validation_result.fields_needing_review)}" if validation_result.fields_needing_review else "✓ All fields validated"}

Your data has been saved to the system.""",
            
            'hi-IN': f"""✅ *खाता सफलतापूर्वक संसाधित*

📋 *लेनदेन ID:* {transaction_id}

*निकाला गया डेटा:*
• फसल प्रकार: {crop_display}
• मात्रा: {qty_display}
• मूल्य: {price_display}
• नमी: {moisture_display}
• गुणवत्ता ग्रेड: {grade_display}
• तारीख: {date_display}

{f"⚠️ *समीक्षा की आवश्यकता:* {', '.join(validation_result.fields_needing_review)}" if validation_result.fields_needing_review else "✓ सभी फ़ील्ड सत्यापित"}

आपका डेटा सिस्टम में सहेजा गया है।""",
            
            'mr-IN': f"""✅ *खाते यशस्वीरित्या प्रक्रिया केली*

📋 *व्यवहार ID:* {transaction_id}

*काढलेला डेटा:*
• पीक प्रकार: {crop_display}
• प्रमाण: {qty_display}
• किंमत: {price_display}
• ओलावा: {moisture_display}
• गुणवत्ता ग्रेड: {grade_display}
• तारीख: {date_display}

{f"⚠️ *पुनरावलोकन आवश्यक:* {', '.join(validation_result.fields_needing_review)}" if validation_result.fields_needing_review else "✓ सर्व फील्ड सत्यापित"}

तुमचा डेटा सिस्टममध्ये जतन केला आहे।""",
            
            'ta-IN': f"""✅ *கணக்கு வெற்றிகரமாக செயலாக்கப்பட்டது*

📋 *பரிவர்த்தனை ID:* {transaction_id}

*பிரித்தெடுக்கப்பட்ட தரவு:*
• பயிர் வகை: {crop_display}
• அளவு: {qty_display}
• விலை: {price_display}
• ஈரப்பதம்: {moisture_display}
• தர தரம்: {grade_display}
• தேதி: {date_display}

{f"⚠️ *மதிப்பாய்வு தேவை:* {', '.join(validation_result.fields_needing_review)}" if validation_result.fields_needing_review else "✓ அனைத்து புலங்களும் சரிபார்க்கப்பட்டன"}

உங்கள் தரவு அமைப்பில் சேமிக்கப்பட்டது."""
        }
        
        response_text = response_messages.get(language, response_messages['en'])
        
        # Send response to WhatsApp
        whatsapp = MetaWhatsAppInterface()
        success = whatsapp.send_text_response(
            phone_number=sender,
            text=response_text,
            language=language
        )
        
        if not success:
            print(f"Failed to send WhatsApp response to {sender}")
        
        # Build response
        response_data = {
            'status': 'success',
            'transaction_id': transaction_id,
            'ledger_id': ledger_data.ledger_id,
            'quantity': float(ledger_data.quantity),
            'moisture': float(ledger_data.moisture),
            'price': float(ledger_data.price),
            'crop_type': ledger_data.crop_type,
            'quality_grade': ledger_data.quality_grade,
            'farmer_name': ledger_data.farmer_name,
            'date': ledger_data.date,
            'validation_status': 'valid' if validation_result.is_valid else 'needs_review',
            'fields_needing_review': validation_result.fields_needing_review,
            'confidence_scores': ledger_data.confidence_scores,
            'whatsapp_sent': success
        }
        
        print(f"Successfully processed document: {transaction_id}")
        
        return {
            'statusCode': 200,
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        print(f"Error processing document: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Try to send error message to user
        try:
            sender = event.get('sender')
            if sender:
                whatsapp = MetaWhatsAppInterface()
                error_messages = {
                    'en': 'Sorry, I could not process your image. Please make sure the image is clear and try again.',
                    'hi-IN': 'क्षमा करें, मैं आपकी छवि संसाधित नहीं कर सका। कृपया सुनिश्चित करें कि छवि स्पष्ट है और पुनः प्रयास करें।',
                    'mr-IN': 'माफ करा, मी तुमची प्रतिमा प्रक्रिया करू शकलो नाही. कृपया प्रतिमा स्पष्ट आहे याची खात्री करा आणि पुन्हा प्रयत्न करा.',
                    'ta-IN': 'மன்னிக்கவும், உங்கள் படத்தை செயலாக்க முடியவில்லை. படம் தெளிவாக உள்ளதா என்பதை உறுதிப்படுத்தி மீண்டும் முயற்சிக்கவும்.'
                }
                language = event.get('language', 'en')
                error_msg = error_messages.get(language, error_messages['en'])
                whatsapp.send_text_response(sender, error_msg, language)
        except:
            pass
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'error': str(e)
            })
        }


def download_and_upload_image(image_id: str, sender: str) -> str:
    """
    Download image from WhatsApp and upload to S3.

    Args:
        image_id: WhatsApp image ID
        sender: Phone number

    Returns:
        S3 key where image was uploaded
    """
    try:
        # Initialize WhatsApp interface
        whatsapp = MetaWhatsAppInterface()

        # Download media from WhatsApp (returns S3 URL if already uploaded)
        print(f"Downloading image {image_id} from WhatsApp...")
        media_url = whatsapp.download_media(image_id)

        if not media_url:
            raise Exception(f"Failed to download image {image_id} from WhatsApp")

        # Check if media is already uploaded to S3
        if media_url.startswith('s3://'):
            # Extract S3 key from S3 URL (format: s3://bucket/key)
            s3_key = media_url.replace(f's3://{S3_BUCKET_RAW}/', '')
            print(f"Media already uploaded to S3: {s3_key}")
            return s3_key

        # Download the actual image content from HTTP URL
        import requests
        response = requests.get(media_url, headers={
            'Authorization': f'Bearer {whatsapp.access_token}'
        }, timeout=30)

        if response.status_code != 200:
            raise Exception(f"Failed to download image content: {response.status_code}")

        # Generate S3 key
        timestamp = datetime.utcnow().isoformat().replace(':', '-')
        s3_key = f"ledger-images/{sender}/{timestamp}.jpg"

        # Upload to S3
        print(f"Uploading image to S3: {s3_key}")
        s3.put_object(
            Bucket=S3_BUCKET_RAW,
            Key=s3_key,
            Body=response.content,
            ContentType='image/jpeg'
        )

        print(f"Image uploaded successfully to s3://{S3_BUCKET_RAW}/{s3_key}")
        return s3_key

    except Exception as e:
        print(f"Error downloading and uploading image: {str(e)}")
        raise
