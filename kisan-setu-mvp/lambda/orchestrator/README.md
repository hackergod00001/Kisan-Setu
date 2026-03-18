# Bedrock Orchestration Component

## Overview

The Bedrock Orchestration Component is the central AI brain of Kisan-Setu. It handles all text-based interactions, performs intent detection, invokes sub-Lambdas (CreditCalculator, SatelliteAnalyzer, KnowledgeBase), and maintains conversation context.

It uses the LLM Adapter with a 5-model APAC inference profile fallback chain via the Bedrock Converse API. The text model fallback chain is: Nova Pro → Nova Lite → Claude 3.7 Sonnet → Claude 3.5 Sonnet v2 → Claude 3 Haiku. Each model has a circuit breaker (3 failures → 60s cooldown) and exponential backoff retries.

## Architecture

```mermaid
graph TB
    subgraph Input["Input Sources"]
        ROUTER["MessageRouter<br/>(text messages, async)"]
        VOICE["VoiceHandler<br/>(transcribed text, async)"]
    end

    subgraph Orchestrator["BedrockOrchestrator (1024 MB · 180s)"]
        INTENT["Intent Detection<br/>(_detect_intent)"]
        MODEL_ROUTER["ModelRouter<br/>(simple/default/complex tier)"]
        CONTEXT["Conversation Context<br/>(DynamoDB: last 6 messages)"]
        COST["Cost Tracking<br/>(daily threshold: $2.00)"]
    end

    subgraph SubLambdas["Sub-Lambda Invocations (sync)"]
        CREDIT["CreditCalculator"]
        SAT["SatelliteAnalyzer"]
        KB["KnowledgeBase"]
    end

    subgraph AI["AI Layer"]
        BEDROCK["Bedrock Converse API<br/>(5-model fallback chain)"]
        STATIC["Static Fallback Response<br/>(if all models fail)"]
    end

    subgraph Output["Output"]
        WA["WhatsApp Response<br/>(via MetaWhatsAppInterface)"]
        DB["DynamoDB<br/>(CONVERSATION#sender / CHAT#ts)"]
    end

    ROUTER --> INTENT
    VOICE --> INTENT
    INTENT -->|"credit"| CREDIT
    INTENT -->|"satellite"| SAT
    INTENT -->|"transaction"| CONTEXT
    INTENT -->|"general"| MODEL_ROUTER
    MODEL_ROUTER --> BEDROCK
    BEDROCK --> WA
    BEDROCK --> DB
    CREDIT --> WA
    SAT --> WA
    COST --> MODEL_ROUTER
```

## Intent Detection Flow

```mermaid
flowchart TD
    MSG["Incoming Text Message"] --> DETECT["_detect_intent()"]
    DETECT -->|"transaction keywords<br/>(create ledger, save ledger, khata banao)<br/>OR quantity+crop+price pattern"| TXN["Transaction Intent<br/>→ Create ledger entry from text"]
    DETECT -->|"credit keywords<br/>(credit score, loan, rin, karj)"| CREDIT["Credit Intent<br/>→ Invoke CreditCalculator Lambda"]
    DETECT -->|"satellite keywords<br/>(crop health, ndvi, fasal swasthya)<br/>Hindi/Marathi/Tamil/English"| SAT["Satellite Intent<br/>→ Invoke SatelliteAnalyzer Lambda"]
    DETECT -->|"No match"| GENERAL["General Query<br/>→ Bedrock Converse API"]

    TXN --> PARSE["Parse quantity, crop, price<br/>from message text"]
    PARSE --> STORE["Store as LedgerData in DynamoDB"]

    CREDIT --> FORMAT["Format credit response<br/>(score, breakdown, loan eligibility)"]

    GENERAL --> TIER["ModelRouter.classify_query()"]
    TIER -->|"simple patterns"| NOVA_LITE["Nova Lite (secondary)"]
    TIER -->|"complex patterns"| NOVA_PRO["Nova Pro (primary)"]
    TIER -->|"default"| NOVA_PRO_D["Nova Pro (default)"]
```

## Features

- **Intent Detection**: Pattern-matching for credit, satellite, transaction, and general queries (supports Hindi, Marathi, Tamil, English)
- **Task Decomposition**: Breaks complex requests into ordered sub-tasks with dependencies
- **Sub-Lambda Invocation**: Calls CreditCalculator, SatelliteAnalyzer, KnowledgeBase via synchronous `lambda:InvokeFunction`
- **Voice Ledger Creation**: Parses transaction data from voice transcriptions (quantity + crop + price patterns)
- **Conversation Context**: Stores/retrieves last 6 messages from DynamoDB (`CONVERSATION#{sender}` / `CHAT#{ts}#role`)
- **Tiered Model Routing**: Classifies queries as simple/default/complex for cost optimization
- **Daily Cost Threshold**: Auto-downgrades to Nova Lite when daily cost exceeds $2.00
- **Static Fallback**: Returns hardcoded helpful response if all 5 models fail
- **Multilingual Support**: System prompt enforces language consistency (Hindi, Marathi, Tamil, English)

## Requirements Implemented

- **Requirement 7.1**: Decompose complex multi-step requests into sub-tasks
- **Requirement 7.2**: Invoke appropriate tools and combine results
- **Requirement 7.3**: Perform mathematical calculations accurately
- **Requirement 7.4**: Maintain conversation history and reference prior interactions
- **Requirement 7.5**: Handle errors gracefully and inform user of partial results

## Lambda Configuration

| Property | Value |
|----------|-------|
| Runtime | Python 3.11 |
| Memory | 1024 MB |
| Timeout | 180s |
| Handler | `orchestrator.handler` |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `DYNAMODB_TABLE` | DynamoDB table name (default: `KisanSetuData`) |
| `REGION` | AWS region (default: `ap-south-1`) |
| `DOCUMENT_PROCESSOR_FUNCTION` | DocumentProcessor Lambda function name |
| `VOICE_AGENT_FUNCTION` | VoiceHandler Lambda function name |
| `SATELLITE_ANALYZER_FUNCTION` | SatelliteAnalyzer Lambda function name |
| `CREDIT_CALCULATOR_FUNCTION` | CreditCalculator Lambda function name |
| `KNOWLEDGE_BASE_FUNCTION` | KnowledgeBase Lambda function name |
| `WHATSAPP_SECRET_NAME` | Secrets Manager secret for WhatsApp credentials |
| `DAILY_COST_THRESHOLD` | Daily cost limit in USD (default: `2.0`) |

## Tool Mapping

| Tool Name | Lambda Function |
|-----------|----------------|
| `document_processor` / `textract` | DocumentProcessor |
| `voice_agent` / `transcribe` | VoiceHandler |
| `satellite_analyzer` / `sagemaker` | SatelliteAnalyzer |
| `credit_calculator` | CreditCalculator |
| `knowledge_base` / `retrieve_and_generate` | KnowledgeBase |

## DynamoDB Key Patterns

| Entity | PK | SK |
|--------|----|----|
| Conversation Chat | `CONVERSATION#{sender_id}` | `CHAT#{timestamp}#user` or `CHAT#{timestamp}#assistant` |
| Model Cost Tracking | `SYSTEM#MODEL_COSTS` | `MODEL_COST#{date}` |

## Testing

```bash
pytest tests/test_orchestrator.py -v
```
