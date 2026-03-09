"""
Bedrock Orchestration Component with Tiered Model Routing

Uses a 3-tier model strategy for cost optimization and response quality:
- Primary (Nova Pro): Complex queries - credit analysis, detailed crop advice, multi-step reasoning
- Default (Nova Pro): Standard queries - general farming questions, moderate complexity
- Secondary (Nova Lite): Simple queries - greetings, FAQs, status checks, and cost threshold fallback

Actual inference uses LLMAdapter with 5-model fallback chain (see llm_adapter.py).
Current chain: Nova Pro → Nova Lite → Claude 3.7 Sonnet → Claude 3.5 Sonnet v2 → Claude 3 Haiku
(Claude APAC models require AWS Marketplace subscription to activate)

Implements Requirements 7.1, 7.2, 7.3, 7.4, 7.5
"""

import os
import json
import boto3
import sys
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date
from dataclasses import dataclass, asdict
from decimal import Decimal
import uuid

# Import WhatsApp interface from local copy
from meta_whatsapp_interface import MetaWhatsAppInterface
from common.llm_adapter import LLMAdapter, LLMAdapterError
from common.ledger_formatter import format_ledger_response, MARKET_PRICES, get_market_ref

# AWS clients
REGION = os.environ.get('REGION', 'ap-south-1')
bedrock_runtime = boto3.client('bedrock-runtime', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)
lambda_client = boto3.client('lambda', region_name=REGION)

# Environment variables
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'KisanSetuData')
DOCUMENT_PROCESSOR_FUNCTION = os.environ.get('DOCUMENT_PROCESSOR_FUNCTION', 'DocumentProcessor')
VOICE_AGENT_FUNCTION = os.environ.get('VOICE_AGENT_FUNCTION', 'VoiceAgent')
SATELLITE_ANALYZER_FUNCTION = os.environ.get('SATELLITE_ANALYZER_FUNCTION', 'SatelliteAnalyzer')
CREDIT_CALCULATOR_FUNCTION = os.environ.get('CREDIT_CALCULATOR_FUNCTION', 'CreditCalculator')
KNOWLEDGE_BASE_FUNCTION = os.environ.get('KNOWLEDGE_BASE_FUNCTION', 'KnowledgeBase')

table = dynamodb.Table(DYNAMODB_TABLE)

# ─── Model Tier Configuration ───
# Used for cost tracking and logging. Actual inference uses LLMAdapter fallback chain.
# LLMAdapter chain: Nova Pro → Nova Lite → Claude 3.7 Sonnet → Claude 3.5 Sonnet v2 → Claude 3 Haiku
MODEL_TIERS = {
    'primary': {
        'model_id': 'apac.amazon.nova-pro-v1:0',
        'name': 'Amazon Nova Pro',
        'max_tokens': 1024,
        'cost_per_1k_input': 0.0008,
        'cost_per_1k_output': 0.0032,
    },
    'default': {
        'model_id': 'apac.amazon.nova-pro-v1:0',
        'name': 'Amazon Nova Pro',
        'max_tokens': 1024,
        'cost_per_1k_input': 0.0008,
        'cost_per_1k_output': 0.0032,
    },
    'secondary': {
        'model_id': 'apac.amazon.nova-lite-v1:0',
        'name': 'Amazon Nova Lite',
        'max_tokens': 1024,
        'cost_per_1k_input': 0.00006,
        'cost_per_1k_output': 0.00024,
    }
}

# Daily cost threshold in USD - after this, downgrade to secondary for all queries
DAILY_COST_THRESHOLD = float(os.environ.get('DAILY_COST_THRESHOLD', '2.0'))

# MARKET_PRICES and get_market_ref are imported from common.ledger_formatter


# ─── Query Complexity Patterns ───
# Simple queries → Nova Lite (fast, cheap)
SIMPLE_PATTERNS = [
    r'^(hi|hello|hey|namaste|namaskar|vanakkam)\b',
    r'^(ok|okay|thanks|thank you|dhanyavaad|shukriya)\b',
    r'^(yes|no|haan|nahi|ha|nako)\b',
    r'^(bye|goodbye|alvida)\b',
    r'\b(status|check|kya hua|kab)\b',
    r'^.{1,15}$',  # Very short messages (under 15 chars)
]

# Complex queries → Opus 4.6 (deep reasoning)
COMPLEX_PATTERNS = [
    r'\b(credit\s*score|loan|rin|karj)\b',
    r'\b(analyze|analysis|vishleshan)\b',
    r'\b(compare|comparison|tulna)\b',
    r'\b(calculate|ganana|hisab)\b',
    r'\b(plan|planning|yojana|strategy)\b',
    r'\b(predict|forecast|bhavishya|anuman)\b',
    r'\b(satellite|upgraha|remote\s*sensing)\b',
    r'\b(soil\s*health|mitti|bhumi)\b.*\b(report|analysis)\b',
    r'\b(market|mandi|bazar)\b.*\b(trend|price|analysis)\b',
    r'\b(insurance|bima|fasal\s*bima)\b',
    r'\b(government\s*scheme|sarkari\s*yojana|subsidy)\b',
    r'\b(crop\s*rotation|fasal\s*chakra)\b',
    r'\b(pest|disease|rog|keeda)\b.*\b(identify|treatment|ilaj)\b',
]

SIMPLE_COMPILED = [re.compile(p, re.IGNORECASE) for p in SIMPLE_PATTERNS]
COMPLEX_COMPILED = [re.compile(p, re.IGNORECASE) for p in COMPLEX_PATTERNS]

# System prompt for the AI assistant
SYSTEM_PROMPT = """You are Kisan Setu (किसान सेतु), an AI assistant for Indian farmers and FPOs (Farmer Producer Organizations).

═══════════════════════════════════════════════════════════
ABSOLUTE RULE #1: LANGUAGE CONSISTENCY (MOST IMPORTANT!)
═══════════════════════════════════════════════════════════

⚠️ IF USER WRITES IN HINDI → RESPOND 100% IN HINDI
⚠️ IF USER WRITES IN ENGLISH → RESPOND 100% IN ENGLISH
⚠️ IF USER WRITES IN MARATHI → RESPOND 100% IN MARATHI
⚠️ IF USER WRITES IN TAMIL → RESPOND 100% IN TAMIL

❌ NEVER SWITCH LANGUAGES MID-RESPONSE
❌ NEVER USE ENGLISH WORDS IN HINDI RESPONSES (except technical terms)
❌ NEVER MIX "chemical pesticides", "IPM" etc. in Hindi responses

Example - CORRECT Hindi response:
User: "क्या यह कीटनाशक अच्छा है?"
Response: "यह इस बात पर निर्भर करता है कि आप किस कीट से लड़ रहे हैं। मेरा सुझाव है कि आप नीम-आधारित कीटनाशक का उपयोग करें क्योंकि यह सुरक्षित है। आप किस फसल में और किस कीट के लिए इसका उपयोग करना चाहते हैं?"

Example - WRONG (mixing languages):
❌ "कीटनाशकों के बारे में... générically, chemical pesticides can be effective..."

═══════════════════════════════════════════════════════════

Your role:
- Help farmers with agricultural queries in simple, practical language
- Provide crop advice, market prices, weather guidance, and credit information
- Support Hindi, English, Marathi, and Tamil
- Be concise and actionable — farmers need quick, clear answers
- Use local crop names and farming terminology they understand
- When discussing prices, use INR (₹)

⚠️ THIS SECTION IS REMOVED - SEE TOP OF PROMPT FOR LANGUAGE RULES ⚠️

HANDLING OFF-TOPIC QUESTIONS (RESPECTFULLY):
When farmers ask questions NOT related to agriculture, farming, crops, weather, markets, or credit:

1. Acknowledge their question politely
2. Explain that you're specialized for agricultural assistance
3. Gently redirect to how you can help with farming
4. Never refuse rudely or abruptly

Example (Hindi):
❌ BAD: "मैं यह नहीं जानता" (I don't know this)
✅ GOOD: "यह एक अच्छा सवाल है! हालांकि, मैं खेती और कृषि से संबंधित मामलों में विशेषज्ञता रखता हूं। क्या मैं फसल, मौसम, बाजार मूल्य या कृषि ऋण के बारे में आपकी मदद कर सकता हूं?"
(This is a good question! However, I specialize in farming and agricultural matters. Can I help you with crops, weather, market prices or agricultural loans?)

ACKNOWLEDGING UNCERTAINTY (TRANSPARENCY):
1. When you're SURE (based on agricultural knowledge):
   - State confidently: "यह सही है कि..." (It is correct that...)
   - Example: "प्याज की बुवाई अक्टूबर-नवंबर में सबसे अच्छी होती है"

2. When providing SUGGESTIONS (not definitive):
   - Use phrases: "मेरा सुझाव है..." (My suggestion is...)
   - Example: "मेरा सुझाव है कि आप मिट्टी परीक्षण करवाएं"

3. When you DON'T KNOW:
   - Be honest: "मुझे इसकी पूरी जानकारी नहीं है, लेकिन..." (I don't have complete information on this, but...)
   - Suggest alternatives: "कृपया अपने स्थानीय कृषि अधिकारी से परामर्श करें"

4. When providing GENERAL vs SPECIFIC information:
   - General: "आमतौर पर..." (Generally...)
   - Specific: "आपके क्षेत्र के लिए..." (For your region...)

RESPONSE QUALITY GUIDELINES:
- Keep responses under 300 words for WhatsApp readability
- Use bullet points (•) for lists
- Use emojis sparingly (🌾 ☀️ 💧 only for clarity)
- Be warm, respectful, and conversational
- Address farmers as "आप" (respectful you) in Hindi/Marathi

CRITICAL: Respond DIRECTLY in the farmer's language. Do NOT include:
- English meta-commentary like "Here is a response in Hindi"
- Translations or explanations of what you're doing
- Draft prefixes or formatting notes
- Any text that isn't part of your actual response to the farmer

Examples:

Farmer asks in Hindi: "Hello"
❌ BAD: "Here is a draft response in Hindi: नमस्ते!"
✅ GOOD: "नमस्ते! मैं किसान सेतु हूँ। मैं खेती, फसल, मौसम, बाजार और कृषि ऋण में आपकी मदद कर सकता हूं। आप किस बारे में जानना चाहते हैं?"

Farmer asks in English: "What is the price of onions?"
✅ GOOD: "Current onion prices vary by region. In Maharashtra, wholesale prices are around ₹30-40 per kg. For your local mandi prices, I suggest checking with your nearest APMC or FPO. Would you like guidance on onion storage or marketing?"

Farmer asks off-topic in Hindi: "IPL का स्कोर क्या है?" (What's the IPL score?)
✅ GOOD: "यह अच्छा सवाल है! हालांकि, मैं कृषि और खेती के मामलों में विशेषज्ञता रखता हूं। मैं आपकी फसल, मौसम की जानकारी, बाजार मूल्य, या कृषि ऋण में मदद कर सकता हूं। क्या इनमें से कुछ चाहिए?"

═══════════════════════════════════════════════════════════
CRITICAL EXAMPLE - PESTICIDE QUESTION (LANGUAGE CONSISTENCY)
═══════════════════════════════════════════════════════════

Farmer asks in Hindi: "क्या यह कीटनाशक अच्छा है?" (Is this pesticide good?)

❌ WRONG - Mixing languages:
"कीटनाशकों के बारे में बात कर रहे हैं! Generally, chemical pesticides can be effective in controlling pests, but they can also have negative impacts..."

✅ CORRECT - Pure Hindi:
"यह इस बात पर निर्भर करता है कि आप किस कीट से लड़ रहे हैं और कौन सी फसल है।

मेरा सुझाव है:
• नीम-आधारित कीटनाशक का उपयोग करें - यह अधिक सुरक्षित है
• फसल चक्र अपनाएं
• स्थानीय कृषि अधिकारी से सलाह लें

आप किस फसल में और किस कीट के लिए इसका उपयोग करना चाहते हैं? मैं अधिक विशिष्ट सुझाव दे सकता हूं।"

═══════════════════════════════════════════════════════════

REMEMBER: If farmer writes in Hindi, your ENTIRE response must be in Hindi. Never use English words like "chemical pesticides", "IPM", "generally" in Hindi responses. Use Hindi equivalents: रासायनिक कीटनाशक, एकीकृत कीट प्रबंधन, आमतौर पर

You are talking to a farmer via WhatsApp. Be their trusted agricultural advisor."""


@dataclass
class Message:
    """Message data structure"""
    message_id: str
    sender_id: str
    content: str
    timestamp: str
    language: str = 'en'
    message_type: str = 'text'


@dataclass
class SubTask:
    """Sub-task for decomposed complex requests"""
    task_id: str
    description: str
    tool_name: str
    parameters: Dict[str, Any]
    dependencies: List[str]
    status: str = 'pending'


@dataclass
class ToolResult:
    """Result from tool invocation"""
    tool_name: str
    status: str
    data: Any = None
    error: Optional[str] = None


@dataclass
class ConversationContext:
    """Conversation context for multi-turn interactions"""
    conversation_id: str
    farmer_id: str
    history: List[Dict[str, Any]]
    state: Dict[str, Any]
    last_updated: str


@dataclass
class Response:
    """Response structure"""
    text: str
    actions_taken: List[str]
    tool_calls: List[Dict[str, Any]]
    conversation_id: str
    timestamp: str
    model_used: str = ''
    tier_used: str = ''


class ModelRouter:
    """
    Intelligent model router that selects the optimal model tier based on:
    1. Query complexity analysis
    2. Daily cost tracking
    3. Conversation context
    """

    def __init__(self):
        self.daily_cost_key = f"MODEL_COST#{date.today().isoformat()}"

    def classify_query(self, message: str) -> str:
        """
        Classify query complexity → returns tier name.

        Returns:
            'secondary' for simple queries
            'primary' for complex queries
            'default' for everything else
        """
        msg = message.strip()

        # Check simple patterns first
        for pattern in SIMPLE_COMPILED:
            if pattern.search(msg):
                return 'secondary'

        # Check complex patterns
        for pattern in COMPLEX_COMPILED:
            if pattern.search(msg):
                return 'primary'

        # Default tier for moderate queries
        return 'default'

    def get_daily_cost(self) -> float:
        """Get today's accumulated model cost from DynamoDB."""
        try:
            resp = table.get_item(Key={'PK': 'SYSTEM#MODEL_COSTS', 'SK': self.daily_cost_key})
            item = resp.get('Item', {})
            return float(item.get('total_cost', 0.0))
        except Exception as e:
            print(f"Error reading daily cost: {e}")
            return 0.0

    def record_cost(self, tier: str, input_tokens: int, output_tokens: int):
        """Record model usage cost in DynamoDB."""
        try:
            config = MODEL_TIERS[tier]
            cost = (input_tokens / 1000 * config['cost_per_1k_input'] +
                    output_tokens / 1000 * config['cost_per_1k_output'])

            table.update_item(
                Key={'PK': 'SYSTEM#MODEL_COSTS', 'SK': self.daily_cost_key},
                UpdateExpression='SET total_cost = if_not_exists(total_cost, :zero) + :cost, '
                                 'model_name = :model, updated_at = :ts, '
                                 'calls = if_not_exists(calls, :zero_int) + :one',
                ExpressionAttributeValues={
                    ':cost': round(cost, 6),
                    ':zero': 0,
                    ':zero_int': 0,
                    ':one': 1,
                    ':model': config['name'],
                    ':ts': datetime.utcnow().isoformat()
                }
            )
            print(f"Recorded cost: ${cost:.6f} for {config['name']} "
                  f"({input_tokens} in / {output_tokens} out)")
        except Exception as e:
            print(f"Error recording cost: {e}")

    def select_model(self, message: str) -> Tuple[str, Dict]:
        """
        Select the best model tier for this query.

        Logic:
        1. If daily cost > threshold → force secondary (Haiku) for everything
        2. Otherwise, classify query and route to appropriate tier
        """
        daily_cost = self.get_daily_cost()

        if daily_cost >= DAILY_COST_THRESHOLD:
            print(f"Daily cost ${daily_cost:.4f} >= threshold ${DAILY_COST_THRESHOLD}. "
                  f"Forcing secondary (Haiku 4.5)")
            return 'secondary', MODEL_TIERS['secondary']

        tier = self.classify_query(message)
        config = MODEL_TIERS[tier]
        print(f"Query classified as '{tier}' → {config['name']} "
              f"(daily cost so far: ${daily_cost:.4f})")
        return tier, config


class BedrockOrchestrator:
    """
    Bedrock Orchestration with Tiered Model Routing.

    Tier strategy:
    - Primary (Opus 4.6): Complex analytical queries
    - Default (Sonnet 4): Standard farming queries
    - Secondary (Haiku 4.5): Simple greetings/FAQs + cost threshold fallback
    """

    # Tool name to Lambda function mapping
    TOOL_MAP = {
        'document_processor': DOCUMENT_PROCESSOR_FUNCTION,
        'textract': DOCUMENT_PROCESSOR_FUNCTION,
        'voice_agent': VOICE_AGENT_FUNCTION,
        'transcribe': VOICE_AGENT_FUNCTION,
        'satellite_analyzer': SATELLITE_ANALYZER_FUNCTION,
        'sagemaker': SATELLITE_ANALYZER_FUNCTION,
        'credit_calculator': CREDIT_CALCULATOR_FUNCTION,
        'knowledge_base': KNOWLEDGE_BASE_FUNCTION,
        'retrieve_and_generate': KNOWLEDGE_BASE_FUNCTION,
    }

    def __init__(self):
        self.router = ModelRouter()
        self.table = table
        self.llm_adapter = LLMAdapter(bedrock_runtime=bedrock_runtime)
        self.agent_id = os.environ.get('BEDROCK_AGENT_ID', '')
        self.agent_alias_id = os.environ.get('BEDROCK_AGENT_ALIAS_ID', '')

    def decompose_task(self, complex_request: str) -> List['SubTask']:
        """Break a complex request into ordered sub-tasks."""
        subtasks = []
        request_lower = complex_request.lower()

        if any(kw in request_lower for kw in ['ledger', 'photo', 'image', 'document', 'digitize']):
            subtasks.append(SubTask(
                task_id=str(uuid.uuid4()),
                description='Process ledger image with Document Processor',
                tool_name='document_processor',
                parameters={},
                dependencies=[]
            ))

        if any(kw in request_lower for kw in ['satellite', 'ndvi', 'field', 'imagery', 'crop health']):
            subtasks.append(SubTask(
                task_id=str(uuid.uuid4()),
                description='Retrieve satellite imagery and NDVI analysis',
                tool_name='satellite_analyzer',
                parameters={},
                dependencies=[]
            ))

        if any(kw in request_lower for kw in ['credit', 'score', 'reliability', 'loan']):
            subtasks.append(SubTask(
                task_id=str(uuid.uuid4()),
                description='Calculate credit / reliability score',
                tool_name='credit_calculator',
                parameters={},
                dependencies=[s.task_id for s in subtasks]
            ))

        if any(kw in request_lower for kw in ['voice', 'audio', 'transcribe']):
            subtasks.append(SubTask(
                task_id=str(uuid.uuid4()),
                description='Process voice audio with Voice Agent',
                tool_name='voice_agent',
                parameters={},
                dependencies=[]
            ))

        if not subtasks:
            subtasks.append(SubTask(
                task_id=str(uuid.uuid4()),
                description='General query processing',
                tool_name='knowledge_base',
                parameters={},
                dependencies=[]
            ))

        return subtasks

    def invoke_tool(self, tool_name: str, parameters: Dict[str, Any]) -> 'ToolResult':
        """Invoke a tool (Lambda function) by name."""
        function_name = self.TOOL_MAP.get(tool_name) or self.TOOL_MAP.get(tool_name.lower())
        if not function_name:
            return ToolResult(
                tool_name=tool_name,
                status='error',
                error=f'Unknown tool: {tool_name}'
            )

        try:
            payload = json.dumps(parameters).encode('utf-8')
            resp = lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=payload
            )
            result_payload = json.loads(resp['Payload'].read())
            return ToolResult(
                tool_name=tool_name,
                status='success',
                data=result_payload
            )
        except Exception as e:
            return ToolResult(
                tool_name=tool_name,
                status='error',
                error=str(e)
            )

    def maintain_context(
        self, conversation_id: str, message: 'Message'
    ) -> 'ConversationContext':
        """Store a message and return the conversation context."""
        farmer_id = message.sender_id
        try:
            # Fetch existing history
            resp = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                ExpressionAttributeValues={
                    ':pk': conversation_id,
                    ':sk': 'MSG#'
                },
                ScanIndexForward=True
            )
            history = resp.get('Items', [])

            # Store the new message
            ts = datetime.utcnow().isoformat()
            self.table.put_item(Item={
                'PK': conversation_id,
                'SK': f'MSG#{ts}',
                'message_id': message.message_id,
                'content': message.content,
                'sender_id': farmer_id,
                'language': message.language,
                'message_type': message.message_type,
                'timestamp': message.timestamp,
            })

            return ConversationContext(
                conversation_id=conversation_id,
                farmer_id=farmer_id,
                history=history,
                state={
                    'language': message.language,
                    'last_message_time': message.timestamp,
                },
                last_updated=ts
            )
        except Exception as e:
            print(f"Error maintaining context: {e}")
            return ConversationContext(
                conversation_id=conversation_id,
                farmer_id=farmer_id,
                history=[],
                state={
                    'language': message.language,
                    'last_message_time': message.timestamp,
                },
                last_updated=datetime.utcnow().isoformat()
            )

    def _detect_intent(self, message: str) -> Optional[str]:
        """Detect if the message requires a specific tool invocation."""
        msg_lower = message.lower()

        # Transaction / ledger creation intent — check BEFORE credit to avoid
        # matching "create ledger" as credit query
        transaction_keywords = [
            'create ledger', 'save ledger', 'add ledger', 'record ledger',
            'ledger banao', 'ledger bana do', 'khata banao', 'khata bana do',
            'save transaction', 'add transaction', 'record transaction',
            'convert it into ledger', 'convert to ledger', 'make ledger',
            'ledger mein daal', 'ledger me daal', 'khate mein likho',
        ]
        if any(kw in msg_lower for kw in transaction_keywords):
            return 'transaction'

        # Also detect transaction data patterns from voice transcription
        # e.g. "600 kg potato at 14 rupees per kg" or "100 kg onion 20 rupees"
        has_quantity = bool(re.search(r'\d+\s*(?:kg|kilo|quintal|ton|bags?|bori|bora)', msg_lower))
        has_crop = bool(re.search(
            r'\b(potato|onion|wheat|rice|cotton|soybean|grape|tomato|sugarcane|'
            r'jowar|bajra|tur|chilli|turmeric|aloo|pyaz|pyaaj|gehu|chawal|'
            r'kapas|angoor|tamatar|ganna|mirch|haldi)\b', msg_lower
        ))
        has_price = bool(re.search(r'(?:₹|rs\.?|rupee|rupay|price|rate)\s*\d+|\d+\s*(?:₹|rs\.?|rupee|rupay|per)', msg_lower))
        if has_quantity and has_crop and has_price:
            return 'transaction'

        # Credit score intent
        credit_keywords = ['credit score', 'credit', 'score', 'loan eligibility',
                           'rin', 'karj', 'krishi rin', 'mera score']
        if any(kw in msg_lower for kw in credit_keywords):
            return 'credit'

        # Satellite / crop health intent
        satellite_keywords = ['crop health', 'satellite', 'ndvi', 'field health',
                              'fasal swasthya', 'khet ki halat', 'remote sensing']
        if any(kw in msg_lower for kw in satellite_keywords):
            return 'satellite'

        return None

    @staticmethod
    def _score_rating(score: float) -> str:
        """Convert numeric score to rating."""
        if score >= 90:
            return "Excellent"
        elif score >= 75:
            return "Good"
        elif score >= 60:
            return "Fair"
        elif score >= 40:
            return "Poor"
        return "Very Poor"

    @staticmethod
    def _score_emoji(score: float) -> str:
        if score >= 75:
            return "🟢"
        elif score >= 50:
            return "🟡"
        return "🔴"

    @staticmethod
    def _loan_eligibility(score: float) -> str:
        if score >= 75:
            return "Eligible for standard agricultural loans"
        elif score >= 60:
            return "Eligible for microfinance loans"
        elif score >= 40:
            return "Limited eligibility — improve score for better loan options"
        return "Not yet eligible — build transaction history to qualify"

    def _format_credit_response(self, body: dict, language: str) -> str:
        """Format credit score as a structured WhatsApp message."""
        score = float(body.get('total_score', body.get('score', 0)))
        breakdown = body.get('breakdown', body.get('component_scores', {}))
        txn_count = body.get('transaction_count', body.get('total_transactions', 0))
        score_change = body.get('score_change', 0)
        rating = self._score_rating(score)
        emoji = self._score_emoji(score)

        # Component explanations
        component_labels = {
            'en': {
                'supply_consistency': ('Supply Consistency', '/30', 'Regular delivery to FPO'),
                'quality_metrics': ('Quality Metrics', '/25', 'Crop quality & moisture'),
                'transaction_history': ('Transaction History', '/20', 'Volume & relationship'),
                'financial_behavior': ('Financial Behavior', '/15', 'Payment timeliness'),
                'operational_transparency': ('Operational Transparency', '/10', 'Ledger digitization'),
            },
            'hi-IN': {
                'supply_consistency': ('आपूर्ति नियमितता', '/30', 'FPO को नियमित डिलीवरी'),
                'quality_metrics': ('गुणवत्ता मापदंड', '/25', 'फसल गुणवत्ता और नमी'),
                'transaction_history': ('लेनदेन इतिहास', '/20', 'मात्रा और संबंध'),
                'financial_behavior': ('वित्तीय व्यवहार', '/15', 'भुगतान समयबद्धता'),
                'operational_transparency': ('परिचालन पारदर्शिता', '/10', 'बही डिजिटाइज़ेशन'),
            }
        }

        labels = component_labels.get(language, component_labels['en'])

        if language in ('hi-IN', 'hi'):
            rating_map = {'Excellent': 'उत्कृष्ट', 'Good': 'अच्छा', 'Fair': 'ठीक',
                          'Poor': 'कमज़ोर', 'Very Poor': 'बहुत कमज़ोर'}
            rating_display = rating_map.get(rating, rating)

            msg = f"📊 *आपका किसान क्रेडिट स्कोर: {score:.1f}/100* {emoji}\n"
            msg += f"*रेटिंग:* {rating_display}\n\n"
            if txn_count:
                msg += f"📋 *आधारित:* {txn_count} लेनदेन\n\n"
            msg += "*स्कोर विवरण:*\n"
            for key, val in breakdown.items():
                label_info = labels.get(key, (key, '', ''))
                msg += f"  • {label_info[0]}: {val}{label_info[1]} — _{label_info[2]}_\n"
            if score_change:
                direction = "⬆️" if float(score_change) > 0 else "⬇️"
                msg += f"\n*बदलाव:* {direction} {abs(float(score_change)):.1f} अंक\n"
            msg += f"\n💰 *ऋण पात्रता:* {self._loan_eligibility(score)}\n"
            msg += "\n💡 *सुझाव:* नियमित बही अपलोड करें और गुणवत्ता बनाए रखें।"
        else:
            msg = f"📊 *Your Kisan Credit Score: {score:.1f}/100* {emoji}\n"
            msg += f"*Rating:* {rating}\n\n"
            if txn_count:
                msg += f"📋 *Based on:* {txn_count} transactions\n\n"
            msg += "*Score Breakdown:*\n"
            for key, val in breakdown.items():
                label_info = labels.get(key, (key, '', ''))
                msg += f"  • {label_info[0]}: {val}{label_info[1]} — _{label_info[2]}_\n"
            if score_change:
                direction = "⬆️" if float(score_change) > 0 else "⬇️"
                msg += f"\n*Change:* {direction} {abs(float(score_change)):.1f} points\n"
            msg += f"\n💰 *Loan Eligibility:* {self._loan_eligibility(score)}\n"
            msg += "\n💡 *Tip:* Upload ledger photos regularly and maintain quality to improve your score."

        return msg

    def _invoke_credit_calculator(self, sender_id: str, language: str) -> Optional[str]:
        """Invoke the CreditCalculator Lambda and return formatted result or status string."""
        try:
            print(f"Invoking CreditCalculator for farmer {sender_id}")
            result = self.invoke_tool('credit_calculator', {
                'farmer_id': sender_id,
                'action': 'calculate'
            })

            if result.status == 'error':
                print(f"CreditCalculator error: {result.error}")
                return None

            data = result.data
            if isinstance(data, dict) and data.get('statusCode') == 200:
                body = data.get('body', '{}')
                if isinstance(body, str):
                    body = json.loads(body)

                score = body.get('total_score', body.get('score'))
                if score is not None:
                    # Return pre-formatted structured message
                    return "FORMATTED:" + self._format_credit_response(body, language)

            # Check if it's a "no data" response
            if isinstance(data, dict):
                body = data.get('body', '{}')
                if isinstance(body, str):
                    body = json.loads(body)
                if body.get('error') or body.get('total_transactions', -1) == 0:
                    return "NO_CREDIT_DATA"

            print(f"Unexpected credit response format: {data}")
            return None

        except Exception as e:
            print(f"Error invoking CreditCalculator: {e}")
            return None

    def _invoke_satellite_analyzer(self, sender_id: str) -> Optional[str]:
        """Invoke the SatelliteAnalyzer Lambda and format the result."""
        try:
            # Look up farmer's GPS coordinates from DynamoDB
            farmer_resp = table.get_item(
                Key={'PK': f'FARMER#{sender_id}', 'SK': 'METADATA'}
            )
            farmer = farmer_resp.get('Item')
            if not farmer:
                return None

            lat = float(farmer.get('gps_latitude', 0))
            lon = float(farmer.get('gps_longitude', 0))
            if lat == 0 or lon == 0:
                return None

            print(f"Invoking SatelliteAnalyzer for ({lat}, {lon})")
            result = self.invoke_tool('satellite_analyzer', {
                'gps_coordinates': [lat, lon],
                'farmer_id': sender_id
            })

            if result.status == 'error':
                print(f"SatelliteAnalyzer error: {result.error}")
                return None

            data = result.data
            if isinstance(data, dict) and data.get('statusCode') == 200:
                body = data.get('body', '{}')
                if isinstance(body, str):
                    body = json.loads(body)

                report = "SATELLITE CROP HEALTH DATA:\n"
                report += f"NDVI Value: {body.get('ndvi_value', 'N/A')}\n"
                report += f"Health Status: {body.get('health_status', 'N/A')}\n"
                report += f"Crop Type: {body.get('crop_type', 'N/A')}\n"
                report += f"Maturity Stage: {body.get('maturity_stage', 'N/A')}\n"
                report += f"Estimated Yield: {body.get('estimated_yield', 'N/A')}\n"
                return report

            return None
        except Exception as e:
            print(f"Error invoking SatelliteAnalyzer: {e}")
            return None

    # Crop name mapping (English, Hindi, transliterated Hindi)
    CROP_MAP = {
        'potato': 'Potato', 'aloo': 'Potato', 'आलू': 'Potato',
        'onion': 'Onion', 'pyaz': 'Onion', 'pyaaj': 'Onion', 'प्याज': 'Onion',
        'wheat': 'Wheat', 'gehu': 'Wheat', 'गेहूं': 'Wheat',
        'rice': 'Rice', 'chawal': 'Rice', 'चावल': 'Rice',
        'cotton': 'Cotton', 'kapas': 'Cotton', 'कपास': 'Cotton',
        'soybean': 'Soybean', 'soya': 'Soybean', 'सोयाबीन': 'Soybean',
        'grape': 'Grape', 'angoor': 'Grape', 'अंगूर': 'Grape',
        'tomato': 'Tomato', 'tamatar': 'Tomato', 'टमाटर': 'Tomato',
        'sugarcane': 'Sugarcane', 'ganna': 'Sugarcane', 'गन्ना': 'Sugarcane',
        'jowar': 'Jowar', 'ज्वार': 'Jowar',
        'bajra': 'Bajra', 'बाजरा': 'Bajra',
        'tur': 'Tur', 'तूर': 'Tur', 'arhar': 'Tur',
        'chilli': 'Chilli', 'mirch': 'Chilli', 'मिर्च': 'Chilli',
        'turmeric': 'Turmeric', 'haldi': 'Turmeric', 'हल्दी': 'Turmeric',
    }

    def _parse_transaction_from_text(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """
        Parse one or more transaction items from voice-transcribed text.

        Supports multi-item messages like:
          "100 kg potato at ₹14 per kg and 500 kg onion at ₹17 per kg"

        Strategy: split text into segments around crop names, then extract
        quantity and price nearest to each crop mention.

        Returns list of dicts [{crop_type, quantity, quantity_unit, price}, ...]
        or None if nothing parseable.
        """
        msg = text.lower()

        # Find all crop mentions with their position in the string
        crop_mentions = []  # [(start_pos, end_pos, crop_name), ...]
        for keyword, crop_name in self.CROP_MAP.items():
            for m in re.finditer(r'\b' + re.escape(keyword) + r'\b', msg):
                crop_mentions.append((m.start(), m.end(), crop_name))

        # Deduplicate: keep only first occurrence of each crop name
        crop_mentions.sort(key=lambda x: x[0])
        seen_crops = set()
        deduped = []
        for start, end, crop_name in crop_mentions:
            if crop_name not in seen_crops:
                seen_crops.add(crop_name)
                deduped.append((start, end, crop_name))
        crop_mentions = deduped

        if not crop_mentions:
            # Fallback: try single-item parse (no crop name found)
            return self._parse_single_transaction(msg)

        # For each crop mention, carve out a "segment" of text around it
        # and extract quantity + price from that segment
        items = []
        for idx, (start, end, crop_name) in enumerate(crop_mentions):
            # Segment boundaries: halfway to previous crop / halfway to next crop
            seg_start = 0 if idx == 0 else (crop_mentions[idx - 1][1] + start) // 2
            seg_end = len(msg) if idx == len(crop_mentions) - 1 else (end + crop_mentions[idx + 1][0]) // 2
            segment = msg[seg_start:seg_end]

            quantity, quantity_unit = self._extract_quantity(segment)
            price = self._extract_price(segment)

            items.append({
                'crop_type': crop_name,
                'quantity': quantity,
                'quantity_unit': quantity_unit,
                'price': price,
            })

        # Filter out items where we got absolutely nothing useful
        items = [it for it in items if it['quantity'] > 0 or it['price'] > 0]
        return items if items else None

    def _parse_single_transaction(self, msg: str) -> Optional[List[Dict[str, Any]]]:
        """Fallback: parse a single transaction when no crop name found."""
        quantity, quantity_unit = self._extract_quantity(msg)
        price = self._extract_price(msg)
        if quantity == 0 and price == 0:
            return None
        return [{
            'crop_type': 'Unknown',
            'quantity': quantity,
            'quantity_unit': quantity_unit,
            'price': price,
        }]

    @staticmethod
    def _extract_quantity(text: str) -> Tuple[float, str]:
        """Extract quantity and unit from a text segment."""
        m = re.search(r'(\d+(?:\.\d+)?)\s*(?:kg|kilo(?:gram)?s?|केजी|किलो)', text)
        if m:
            return float(m.group(1)), 'kg'
        m = re.search(r'(\d+(?:\.\d+)?)\s*(?:quintal|क्विंटल)', text)
        if m:
            return float(m.group(1)) * 100, 'quintal'
        m = re.search(r'(\d+(?:\.\d+)?)\s*(?:ton|टन)', text)
        if m:
            return float(m.group(1)) * 1000, 'ton'
        m = re.search(r'(\d+(?:\.\d+)?)\s*(?:bags?|bori|बोरी)', text)
        if m:
            return float(m.group(1)) * 50, 'bags'
        return 0.0, 'kg'

    @staticmethod
    def _extract_price(text: str) -> float:
        """Extract price per unit from a text segment."""
        patterns = [
            r'(?:₹|rs\.?\s*|rupee[s]?\s*|rupay\s*)(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:₹|rs\.?|rupee|rupay)',
            r'(?:at|@|price|rate|per\s*kg)\s*(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*(?:per\s*kg|per\s*kilo|\/kg)',
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return float(m.group(1))
        return 0.0

    def _create_voice_ledger(self, sender_id: str, items: List[Dict[str, Any]],
                             language: str, original_text: str) -> str:
        """
        Save one or more voice/text-transcribed transactions to DynamoDB.
        Returns FORMATTED: prefixed WhatsApp message using shared formatter.
        """
        today = date.today().isoformat()
        farmer_pk = f"FARMER#{sender_id}"
        saved_items = []  # [(transaction_id, item_dict), ...]

        for item in items:
            import time as _time
            timestamp = datetime.utcnow().isoformat()
            transaction_id = f"TXN#{timestamp}"
            ledger_id = f"LEDGER#VOICE#{timestamp}"

            crop_type = item.get('crop_type', 'Unknown')
            quantity = item.get('quantity', 0)
            price = item.get('price', 0)

            # Build fields_needing_review based on what's missing
            review_fields = []
            if price == 0:
                review_fields.append('price')
            if not crop_type or crop_type == 'Unknown':
                review_fields.append('crop_type')
            if quantity == 0:
                review_fields.append('quantity')
            # Voice never has these
            review_fields.extend(['moisture', 'quality_grade', 'farmer_name'])

            try:
                db_item = {
                    'PK': farmer_pk,
                    'SK': transaction_id,
                    'entity_type': 'Transaction',
                    'transaction_id': transaction_id,
                    'ledger_id': ledger_id,
                    'farmer_id': farmer_pk,
                    'quantity': Decimal(str(quantity)),
                    'moisture': Decimal('0'),
                    'price': Decimal(str(price)),
                    'date': today,
                    'crop_type': crop_type,
                    'farmer_name': '',
                    'quality_grade': '',
                    'ledger_image_url': '',
                    'source': 'voice',
                    'original_text': original_text[:500],
                    'confidence_scores': {},
                    'validation_status': 'needs_review' if review_fields else 'valid',
                    'fields_needing_review': review_fields,
                    'sync_status': 'synced',
                    'timestamp': timestamp,
                    'created_at': timestamp,
                }
                self.table.put_item(Item=db_item)
                saved_items.append((transaction_id, item, review_fields))
                print(f"Stored voice ledger: {transaction_id} — {crop_type} {quantity}kg @₹{price}")
            except Exception as e:
                print(f"Error storing voice ledger item: {e}")

            # Small delay to ensure unique timestamps for SK
            _time.sleep(0.01)

        if not saved_items:
            if language in ('hi-IN', 'hi'):
                return "FORMATTED:❌ लेनदेन सहेजने में त्रुटि हुई। कृपया पुनः प्रयास करें।"
            return "FORMATTED:❌ Error saving transaction. Please try again."

        # Detect source: if original_text was from a voice transcription or text
        source = 'voice' if any(kw in original_text.lower() for kw in
                                ['voice', 'audio', '🎤']) else 'text'

        # Build formatter items
        formatter_items = []
        for txn_id, item, review_fields in saved_items:
            formatter_items.append({
                'transaction_id': txn_id,
                'crop_type': item.get('crop_type', 'Unknown'),
                'quantity': float(item.get('quantity', 0)),
                'price': float(item.get('price', 0)),
                'moisture': 0.0,
                'quality_grade': '',
                'date': today,
                'farmer_name': '',
                'fields_needing_review': review_fields,
            })

        msg = format_ledger_response(
            items=formatter_items,
            language=language,
            source=source,
        )
        return "FORMATTED:" + msg

    def process_request(
        self,
        user_message: str,
        sender_id: str,
        language: str = 'en',
        conversation_history: Optional[List] = None
    ) -> Response:
        """Process user request with LLM Adapter and automatic multi-model fallback."""
        conversation_id = ''
        try:
            print(f"Processing request from {sender_id}: {user_message}")
            conversation_id = f"CONV-{sender_id}-{datetime.utcnow().strftime('%Y%m%d')}"

            # Select model tier (for cost tracking / logging purposes)
            tier, model_config = self.router.select_model(user_message)

            # Detect intent and invoke relevant tools BEFORE LLM call
            intent = self._detect_intent(user_message)
            tool_context = ""
            actions_taken = [f'model_invocation:{tier}']

            if intent == 'transaction':
                # Voice-to-ledger: parse transaction data and save to DynamoDB
                # First try parsing from current message
                parsed = self._parse_transaction_from_text(user_message)

                if not parsed:
                    # If current message is "convert to ledger", check recent history
                    # for the actual transaction data
                    history = self._get_recent_history(sender_id, limit=4)
                    for msg in reversed(history):
                        if msg.get('role') == 'user':
                            parsed = self._parse_transaction_from_text(msg.get('content', ''))
                            if parsed:
                                break
                        elif msg.get('role') == 'assistant':
                            # Also try parsing from bot's previous response
                            # (e.g. "600 kg potato at ₹14/kg = ₹8,400")
                            parsed = self._parse_transaction_from_text(msg.get('content', ''))
                            if parsed:
                                break

                if parsed:
                    ledger_result = self._create_voice_ledger(
                        sender_id, parsed, language, user_message
                    )
                    if ledger_result.startswith("FORMATTED:"):
                        formatted_msg = ledger_result[len("FORMATTED:"):]
                        actions_taken.append('voice_ledger:success')
                        self._store_conversation(sender_id, conversation_id, user_message, formatted_msg)
                        return Response(
                            text=formatted_msg,
                            actions_taken=actions_taken,
                            tool_calls=[],
                            conversation_id=conversation_id,
                            timestamp=datetime.utcnow().isoformat(),
                            model_used='direct',
                            tier_used='none'
                        )
                else:
                    # Could not parse — ask LLM to help, with context
                    tool_context = (
                        "\n\n[SYSTEM DATA: The farmer wants to create a ledger entry but "
                        "the data could not be parsed. Ask them to provide: crop type, "
                        "quantity (in kg), and price (₹ per kg). Example: "
                        "'100 kg potato at ₹14 per kg']\n"
                    )
                    actions_taken.append('voice_ledger:need_more_data')

            elif intent == 'credit':
                credit_data = self._invoke_credit_calculator(sender_id, language)
                if credit_data and credit_data.startswith("FORMATTED:"):
                    # Return the structured credit score directly — skip LLM
                    formatted_msg = credit_data[len("FORMATTED:"):]
                    actions_taken.append('credit_calculator:success')
                    self._store_conversation(sender_id, conversation_id, user_message, formatted_msg)
                    return Response(
                        text=formatted_msg,
                        actions_taken=actions_taken,
                        tool_calls=[],
                        conversation_id=conversation_id,
                        timestamp=datetime.utcnow().isoformat(),
                        model_used='direct',
                        tier_used='none'
                    )
                elif credit_data == "NO_CREDIT_DATA":
                    tool_context = (
                        "\n\n[SYSTEM DATA: This farmer has no transaction records yet. "
                        "They need to upload ledger photos/data first. "
                        "Tell them: to generate your Kisan Credit Score, please upload photos of your "
                        "ledger/transaction records. You can also send a voice message describing your "
                        "recent sales (crop, quantity, price). Once we have enough data, "
                        "we will calculate your credit score.]\n"
                    )
                    actions_taken.append('credit_calculator:no_data')
                else:
                    tool_context = (
                        "\n\n[SYSTEM DATA: Could not retrieve credit score. "
                        "Ask the farmer to upload their ledger records first to build their credit profile.]\n"
                    )
                    actions_taken.append('credit_calculator:error')

            elif intent == 'satellite':
                satellite_data = self._invoke_satellite_analyzer(sender_id)
                if satellite_data:
                    tool_context = f"\n\n[SYSTEM DATA - Use this data to answer the farmer's query:\n{satellite_data}]\n"
                    actions_taken.append('satellite_analyzer:success')
                else:
                    tool_context = (
                        "\n\n[SYSTEM DATA: Could not retrieve satellite data for this farmer's location. "
                        "The farmer may need to update their GPS coordinates.]\n"
                    )
                    actions_taken.append('satellite_analyzer:error')

            # Build conversation context
            history = self._get_recent_history(sender_id, limit=6)
            history_text = ""
            for msg in history:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                history_text += f"{role}: {content}\n"

            prompt = history_text + f"user: {user_message}" if history_text else user_message

            # Append tool data to prompt so LLM can reference it
            if tool_context:
                prompt = prompt + tool_context

            # Add explicit language directive to prevent language switching
            # This overrides any language from conversation history
            lang_names = {
                'en': 'English', 'hi-IN': 'Hindi', 'hi': 'Hindi',
                'mr-IN': 'Marathi', 'mr': 'Marathi',
                'ta-IN': 'Tamil', 'ta': 'Tamil'
            }
            lang_name = lang_names.get(language, 'English')
            prompt += f"\n\n[CRITICAL INSTRUCTION: The user's current message is in {lang_name}. You MUST respond ENTIRELY in {lang_name}. Do NOT use any other language.]"

            # Use LLM Adapter with Converse API (automatic multi-model fallback)
            response_text, input_tokens, output_tokens = self.llm_adapter.converse(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT
            )

            # Log token usage for cost tracking
            print(f"Token usage: {input_tokens} in / {output_tokens} out")

            # Store this exchange in conversation history
            self._store_conversation(sender_id, conversation_id, user_message, response_text)

            return Response(
                text=response_text,
                actions_taken=actions_taken,
                tool_calls=[],
                conversation_id=conversation_id,
                timestamp=datetime.utcnow().isoformat(),
                model_used=model_config['name'],
                tier_used=tier
            )

        except LLMAdapterError as e:
            print(f"LLM Adapter failed (all models exhausted): {e}")
            # Return localized user-friendly error message
            error_messages = {
                'en': "I'm sorry, I'm having trouble processing your request. Please try again later.",
                'hi-IN': "क्षमा करें, आपके अनुरोध को संसाधित करने में समस्या हो रही है। कृपया बाद में पुनः प्रयास करें।",
                'hi': "क्षमा करें, आपके अनुरोध को संसाधित करने में समस्या हो रही है। कृपया बाद में पुनः प्रयास करें।",
                'mr-IN': "माफ करा, तुमची विनंती प्रक्रिया करण्यात अडचण येत आहे. कृपया नंतर पुन्हा प्रयत्न करा.",
                'mr': "माफ करा, तुमची विनंती प्रक्रिया करण्यात अडचण येत आहे. कृपया नंतर पुन्हा प्रयत्न करा.",
                'ta-IN': "மன்னிக்கவும், உங்கள் கோரிக்கையை செயலாக்குவதில் சிக்கல் உள்ளது. பின்னர் மீண்டும் முயற்சிக்கவும்.",
                'ta': "மன்னிக்கவும், உங்கள் கோரிக்கையை செயலாக்குவதில் சிக்கல் உள்ளது. பின்னர் மீண்டும் முயற்சிக்கவும்.",
            }
            error_text = error_messages.get(language, error_messages['en'])
            return Response(
                text=error_text,
                actions_taken=['llm_adapter_error'],
                tool_calls=[],
                conversation_id=conversation_id,
                timestamp=datetime.utcnow().isoformat(),
                model_used='none',
                tier_used='none'
            )

        except Exception as e:
            print(f"Error processing request: {e}")
            import traceback
            traceback.print_exc()

            # Static fallback when unexpected errors occur
            return Response(
                text=self._static_fallback(user_message, language),
                actions_taken=['static_fallback'],
                tool_calls=[],
                conversation_id=conversation_id,
                timestamp=datetime.utcnow().isoformat(),
                model_used='none',
                tier_used='none'
            )

    def _invoke_model(
        self,
        model_config: Dict,
        user_message: str,
        history: List[Dict],
        language: str
    ) -> Tuple[str, int, int]:
        """Invoke a Bedrock model using Converse API (works with all models)."""
        messages = []

        # Add conversation history
        for msg in history:
            messages.append({
                'role': msg['role'],
                'content': [{'text': msg['content']}]
            })

        # Add current user message
        messages.append({
            'role': 'user',
            'content': [{'text': user_message}]
        })

        print(f"Invoking {model_config['name']} ({model_config['model_id']})")

        # Use Converse API (unified API for all Bedrock models)
        resp = bedrock_runtime.converse(
            modelId=model_config['model_id'],
            messages=messages,
            system=[{'text': SYSTEM_PROMPT}],
            inferenceConfig={
                'maxTokens': model_config['max_tokens'],
                'temperature': 0.7
            }
        )

        # Extract response from Converse API format
        response_text = resp['output']['message']['content'][0]['text']
        input_tokens = resp.get('usage', {}).get('inputTokens', 0)
        output_tokens = resp.get('usage', {}).get('outputTokens', 0)

        print(f"Response from {model_config['name']}: {input_tokens} in / {output_tokens} out")
        return response_text, input_tokens, output_tokens

    def _invoke_fallback(self, user_message: str, language: str) -> str:
        """Fallback: try secondary model with minimal context."""
        resp = bedrock_runtime.converse(
            modelId=MODEL_TIERS['secondary']['model_id'],
            messages=[{
                'role': 'user',
                'content': [{'text': user_message}]
            }],
            system=[{'text': SYSTEM_PROMPT}],
            inferenceConfig={
                'maxTokens': 512,
                'temperature': 0.7
            }
        )
        return resp['output']['message']['content'][0]['text']

    def _static_fallback(self, user_message: str, language: str) -> str:
        """Static fallback when all models fail."""
        responses = {
            'en': "Hello! I received your message. I'm having trouble connecting right now, but please try again in a moment.",
            'hi-IN': "नमस्ते! मुझे आपका संदेश मिला। अभी कनेक्ट करने में समस्या हो रही है, कृपया कुछ देर बाद पुनः प्रयास करें।",
            'mr-IN': "नमस्कार! मला तुमचा संदेश मिळाला. सध्या कनेक्ट करण्यात अडचण येत आहे, कृपया थोड्या वेळाने पुन्हा प्रयत्न करा.",
            'ta-IN': "வணக்கம்! உங்கள் செய்தி கிடைத்தது. இப்போது இணைப்பதில் சிக்கல் உள்ளது, சிறிது நேரம் கழித்து மீண்டும் முயற்சிக்கவும்."
        }
        return responses.get(language, responses['en'])

    def _get_recent_history(self, sender_id: str, limit: int = 6) -> List[Dict]:
        """Get recent conversation history from DynamoDB."""
        try:
            resp = table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                ExpressionAttributeValues={
                    ':pk': f"CONVERSATION#{sender_id}",
                    ':sk': 'CHAT#'
                },
                ScanIndexForward=False,
                Limit=limit
            )
            items = resp.get('Items', [])
            # Reverse to chronological order
            items.reverse()
            history = []
            for item in items:
                history.append({'role': item.get('role', 'user'), 'content': item.get('content', '')})
            return history
        except Exception as e:
            print(f"Error fetching history: {e}")
            return []

    def _store_conversation(self, sender_id: str, conversation_id: str,
                            user_message: str, response_text: str):
        """Store conversation exchange in DynamoDB."""
        try:
            ts = datetime.utcnow().isoformat()
            # Store user message
            table.put_item(Item={
                'PK': f"CONVERSATION#{sender_id}",
                'SK': f"CHAT#{ts}#user",
                'role': 'user',
                'content': user_message,
                'conversation_id': conversation_id,
                'timestamp': ts
            })
            # Store assistant response
            ts2 = datetime.utcnow().isoformat()
            table.put_item(Item={
                'PK': f"CONVERSATION#{sender_id}",
                'SK': f"CHAT#{ts2}#assistant",
                'role': 'assistant',
                'content': response_text,
                'conversation_id': conversation_id,
                'timestamp': ts2
            })
        except Exception as e:
            print(f"Error storing conversation: {e}")


def handler(event, context):
    """
    Lambda handler for Bedrock Orchestrator with Tiered Model Routing.

    Receives text messages, selects optimal model, processes, and responds via WhatsApp.
    """
    try:
        print(f"Received event: {json.dumps(event)}")

        sender_id = event.get('sender_id', '')
        message_text = event.get('message_text', '')
        language = event.get('language', 'en')

        # Create orchestrator and process
        orchestrator = BedrockOrchestrator()
        response = orchestrator.process_request(
            user_message=message_text,
            sender_id=sender_id,
            language=language
        )

        # Send response back via WhatsApp
        whatsapp = MetaWhatsAppInterface()
        success = whatsapp.send_text_response(
            phone_number=sender_id,
            text=response.text,
            language=language
        )

        if not success:
            print(f"Failed to send WhatsApp response to {sender_id}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'response_text': response.text,
                'actions_taken': response.actions_taken,
                'model_used': response.model_used,
                'tier_used': response.tier_used,
                'conversation_id': response.conversation_id,
                'timestamp': response.timestamp,
                'whatsapp_sent': success
            })
        }

    except Exception as e:
        print(f"Error in handler: {e}")
        import traceback
        traceback.print_exc()

        # Try to send error message to user
        try:
            sender_id = event.get('sender_id', '')
            if sender_id:
                whatsapp = MetaWhatsAppInterface()
                error_messages = {
                    'en': 'Sorry, I encountered an error. Please try again.',
                    'hi-IN': 'क्षमा करें, त्रुटि हुई। कृपया पुनः प्रयास करें।',
                    'mr-IN': 'माफ करा, त्रुटी आली. कृपया पुन्हा प्रयत्न करा.',
                    'ta-IN': 'மன்னிக்கவும், பிழை ஏற்பட்டது. மீண்டும் முயற்சிக்கவும்.'
                }
                language = event.get('language', 'en')
                whatsapp.send_text_response(
                    sender_id,
                    error_messages.get(language, error_messages['en']),
                    language
                )
        except:
            pass

        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
