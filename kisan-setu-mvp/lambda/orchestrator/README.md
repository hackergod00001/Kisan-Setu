# Bedrock Orchestration Component

## Overview

The Bedrock Orchestration Component uses AWS Bedrock Agents with Claude 3.5 Sonnet v2 to orchestrate complex multi-step requests, decompose tasks, invoke appropriate tools, and maintain conversation context.

## Features

- **Intelligent Request Processing**: Uses Bedrock Agent to understand and process complex farmer queries
- **Task Decomposition**: Automatically breaks down multi-step requests into sub-tasks
- **Tool Invocation**: Invokes appropriate AWS services (Textract, SageMaker, Transcribe) based on request type
- **Conversation Context**: Maintains conversation history in DynamoDB for contextual responses
- **Error Handling**: Gracefully handles errors and provides user-friendly messages
- **Multilingual Support**: Supports Hindi, Marathi, and Tamil through language context

## Requirements Implemented

- **Requirement 7.1**: Decompose complex multi-step requests into sub-tasks
- **Requirement 7.2**: Invoke appropriate tools and combine results
- **Requirement 7.3**: Perform mathematical calculations accurately
- **Requirement 7.4**: Maintain conversation history and reference prior interactions
- **Requirement 7.5**: Handle errors gracefully and inform user of partial results

## Architecture

```
User Message → BedrockOrchestrator.process_request()
                ↓
            Maintain Context (DynamoDB)
                ↓
            Invoke Bedrock Agent
                ↓
            Agent Reasoning & Tool Selection
                ↓
            Invoke Tools (Lambda Functions)
                ↓
            Combine Results
                ↓
            Generate Response
                ↓
            Store in Context
                ↓
            Return to User
```

## Class: BedrockOrchestrator

### Methods

#### `process_request(user_message, conversation_history, sender_id, language)`

Processes user request using Bedrock Agent.

**Parameters:**
- `user_message` (str): User's text message
- `conversation_history` (List[Message]): List of previous messages
- `sender_id` (str): User's phone number or ID
- `language` (str): User's preferred language (default: 'en')

**Returns:**
- `Response`: Response object with text, actions taken, and tool calls

**Example:**
```python
orchestrator = BedrockOrchestrator()
response = orchestrator.process_request(
    user_message="What is my credit score?",
    conversation_history=[],
    sender_id="919876543210",
    language="en"
)
print(response.text)  # "Your credit score is 85/100..."
```

#### `decompose_task(complex_request)`

Decomposes complex request into ordered sub-tasks.

**Parameters:**
- `complex_request` (str): Complex multi-step request

**Returns:**
- `List[SubTask]`: List of SubTask objects with dependencies

**Example:**
```python
subtasks = orchestrator.decompose_task(
    "Process this ledger and calculate my credit score"
)
# Returns: [SubTask(tool_name='document_processor'), SubTask(tool_name='credit_calculator')]
```

#### `invoke_tool(tool_name, parameters)`

Invokes external tool (Textract, SageMaker, Transcribe, etc.).

**Parameters:**
- `tool_name` (str): Name of the tool to invoke
- `parameters` (Dict[str, Any]): Tool parameters

**Returns:**
- `ToolResult`: Result with data and status

**Supported Tools:**
- `document_processor` / `textract`: Document processing
- `voice_agent` / `transcribe`: Voice transcription
- `satellite_analyzer` / `sagemaker`: Satellite analysis
- `credit_calculator`: Credit score calculation

**Example:**
```python
result = orchestrator.invoke_tool(
    'document_processor',
    {'image_url': 's3://bucket/ledger.jpg'}
)
print(result.data)  # {'quantity': 100, 'moisture': 12.5, ...}
```

#### `maintain_context(conversation_id, new_message)`

Updates and retrieves conversation context.

**Parameters:**
- `conversation_id` (str): Conversation ID
- `new_message` (Message): New message to add

**Returns:**
- `ConversationContext`: Context with history and state

**Example:**
```python
message = Message(
    message_id='msg-123',
    sender_id='919876543210',
    content='Hello',
    timestamp=datetime.utcnow().isoformat(),
    language='en'
)
context = orchestrator.maintain_context('CONV#919876543210#20260302', message)
print(len(context.history))  # Number of previous messages
```

## Data Structures

### Message
```python
@dataclass
class Message:
    message_id: str
    sender_id: str
    content: str
    timestamp: str
    language: str = 'en'
    message_type: str = 'text'
```

### SubTask
```python
@dataclass
class SubTask:
    task_id: str
    description: str
    tool_name: str
    parameters: Dict[str, Any]
    dependencies: List[str]
    status: str = 'pending'
```

### ToolResult
```python
@dataclass
class ToolResult:
    tool_name: str
    status: str
    data: Any
    error: Optional[str] = None
```

### Response
```python
@dataclass
class Response:
    text: str
    actions_taken: List[str]
    tool_calls: List[Dict[str, Any]]
    conversation_id: str
    timestamp: str
```

### ConversationContext
```python
@dataclass
class ConversationContext:
    conversation_id: str
    farmer_id: str
    history: List[Dict[str, Any]]
    state: Dict[str, Any]
    last_updated: str
```

## Lambda Handler

The `handler` function is the entry point for AWS Lambda.

**Event Structure:**
```json
{
  "sender_id": "919876543210",
  "message_text": "What is my credit score?",
  "language": "en",
  "conversation_history": []
}
```

**Response Structure:**
```json
{
  "statusCode": 200,
  "body": {
    "response_text": "Your credit score is 85/100...",
    "actions_taken": ["reasoning", "tool_invocation"],
    "tool_calls": [...],
    "conversation_id": "CONV#919876543210#20260302",
    "timestamp": "2026-03-02T10:00:00"
  }
}
```

## Environment Variables

- `DYNAMODB_TABLE`: DynamoDB table name (default: 'KisanSetuData')
- `REGION`: AWS region (default: 'ap-south-1')
- `BEDROCK_AGENT_ID`: Bedrock Agent ID
- `BEDROCK_AGENT_ALIAS_ID`: Bedrock Agent Alias ID
- `DOCUMENT_PROCESSOR_FUNCTION`: Document processor Lambda function name
- `VOICE_AGENT_FUNCTION`: Voice agent Lambda function name
- `SATELLITE_ANALYZER_FUNCTION`: Satellite analyzer Lambda function name
- `CREDIT_CALCULATOR_FUNCTION`: Credit calculator Lambda function name

## DynamoDB Schema

### Conversation Messages
```
PK: CONV#{sender_id}#{date}
SK: MSG#{timestamp}
Attributes:
  - message_id
  - sender_id
  - content
  - timestamp
  - language
  - message_type
```

### Conversation Responses
```
PK: CONV#{sender_id}#{date}
SK: RESPONSE#{timestamp}
Attributes:
  - response_text
  - actions_taken
  - tool_calls
  - timestamp
```

## Integration with Bedrock Agent

The orchestrator integrates with AWS Bedrock Agent configured with:

- **Foundation Model**: Claude 3.5 Sonnet v2 (anthropic.claude-3-5-sonnet-20241022-v2:0)
- **Agent ID**: UUQPVM0ULJ
- **Alias ID**: A2TGFPMFXZ
- **Action Groups**: Document processing, satellite analysis, voice processing

### Agent Instruction

The agent is configured with instructions for:
- FPO operations support
- Multilingual responses (Hindi, Marathi, Tamil)
- Ledger digitization guidance
- Credit score calculation
- Farming best practices

## Error Handling

The orchestrator implements comprehensive error handling:

1. **Bedrock Agent Errors**: Catches and logs agent invocation errors
2. **Tool Invocation Errors**: Returns ToolResult with error status
3. **DynamoDB Errors**: Returns minimal context on database errors
4. **Unknown Tools**: Returns error message for unsupported tools

All errors are logged and user-friendly messages are returned.

## Testing

Run tests with:
```bash
pytest tests/test_orchestrator.py -v
```

Test coverage includes:
- Request processing (success and error cases)
- Task decomposition
- Tool invocation (all tool types)
- Context maintenance
- Lambda handler
- Data structures
- Tool mapping

## Usage Example

```python
from orchestrator import BedrockOrchestrator, Message

# Create orchestrator
orchestrator = BedrockOrchestrator()

# Process a simple query
response = orchestrator.process_request(
    user_message="What is my credit score?",
    conversation_history=[],
    sender_id="919876543210",
    language="en"
)
print(response.text)

# Process a complex multi-step query
response = orchestrator.process_request(
    user_message="Process this ledger photo and calculate my credit score",
    conversation_history=[],
    sender_id="919876543210",
    language="hi"
)
print(response.text)
print(response.actions_taken)  # ['reasoning', 'tool_invocation', ...]
print(response.tool_calls)  # [{'type': 'action_group', ...}]
```

## Performance Considerations

- **Timeout**: Lambda timeout set to 60 seconds for complex requests
- **Memory**: 1024 MB allocated for Bedrock Agent invocations
- **Conversation History**: Limited to last 10 messages for context
- **Session Attributes**: Includes last 5 messages for agent context

## Future Enhancements

- [ ] Add support for more languages (Punjabi, Bengali, etc.)
- [ ] Implement conversation summarization for long histories
- [ ] Add caching for frequently asked questions
- [ ] Implement streaming responses for real-time feedback
- [ ] Add metrics and monitoring for agent performance
- [ ] Implement A/B testing for different agent prompts
