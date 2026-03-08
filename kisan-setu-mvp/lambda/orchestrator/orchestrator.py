"""
Bedrock Orchestration Component with Tiered Model Routing

Uses a 3-tier model strategy for cost optimization and response quality:
- Primary (Opus 4.6): Complex queries - credit analysis, detailed crop advice, multi-step reasoning
- Default (Sonnet 4): Standard queries - general farming questions, moderate complexity
- Secondary (Haiku 4.5): Simple queries - greetings, FAQs, status checks, and cost threshold fallback

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
import uuid

# Import WhatsApp interface from local copy
from meta_whatsapp_interface import MetaWhatsAppInterface
from common.llm_adapter import LLMAdapter, LLMAdapterError

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
# TEMPORARY: Using Amazon Nova models (no marketplace subscription required)
# Switch back to Claude models once Bedrock access is enabled
MODEL_TIERS = {
    'primary': {
        'model_id': 'meta.llama3-70b-instruct-v1:0',  # Nova Pro for complex queries
        'name': 'Meta Llama 3 70B',
        'max_tokens': 1024,
        'cost_per_1k_input': 0.0008,
        'cost_per_1k_output': 0.0032,
    },
    'default': {
        'model_id': 'meta.llama3-8b-instruct-v1:0',  # Nova Lite for standard queries
        'name': 'Meta Llama 3 8B',
        'max_tokens': 1024,
        'cost_per_1k_input': 0.00006,
        'cost_per_1k_output': 0.00024,
    },
    'secondary': {
        'model_id': 'meta.llama3-8b-instruct-v1:0',  # Nova Micro for simple queries
        'name': 'Meta Llama 3 8B',
        'max_tokens': 1024,
        'cost_per_1k_input': 0.000035,
        'cost_per_1k_output': 0.00014,
    }
}

# ORIGINAL CLAUDE MODELS (restore these once Bedrock access is enabled):
# 'primary': 'global.anthropic.claude-opus-4-6-v1' (Claude Opus 4.6)
# 'default': 'apac.anthropic.claude-sonnet-4-20250514-v1:0' (Claude Sonnet 4)
# 'secondary': 'global.anthropic.claude-haiku-4-5-20251001-v1:0' (Claude Haiku 4.5)

# Daily cost threshold in USD - after this, downgrade to secondary for all queries
DAILY_COST_THRESHOLD = float(os.environ.get('DAILY_COST_THRESHOLD', '2.0'))


# ─── Query Complexity Patterns ───
# Simple queries → Haiku 4.5 (fast, cheap)
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

            # Build conversation context
            history = self._get_recent_history(sender_id, limit=6)
            history_text = ""
            for msg in history:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                history_text += f"{role}: {content}\n"

            prompt = history_text + f"user: {user_message}" if history_text else user_message

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
                actions_taken=[f'model_invocation:{tier}'],
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
