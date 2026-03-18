# Kisan-Setu MVP — Architecture Document

> Comprehensive architecture reference derived from a line-by-line codebase audit.
> Last updated: March 15, 2026

---

## 1. Executive Summary

Kisan-Setu is a serverless, AI-powered WhatsApp assistant for Indian farmers and Farmer Producer Organizations (FPOs). It digitizes handwritten ledgers, provides agricultural advice, calculates credit scores, analyzes satellite imagery for crop health, and supports voice interactions in Hindi and regional languages — all through WhatsApp with zero UI.

The system is built entirely on AWS managed services (Lambda, DynamoDB, Bedrock, Textract, Transcribe, Polly, SageMaker Geospatial, AppSync, API Gateway) and deployed via AWS CDK (Python). It targets a cost of less than $50/month per FPO serving 500+ farmers.

---

## 2. High-Level System Architecture

```mermaid
graph TB
    subgraph UserLayer["👤 User Layer"]
        WA["📱 WhatsApp Users<br/>(Farmers, FPO Managers)<br/>Text / Voice / Image"]
        DASH["📊 FPO Admin Dashboard<br/>(S3-hosted static site)<br/>Leaflet map + Chart.js"]
    end

    subgraph APILayer["🌐 API Layer"]
        APIGW["Amazon API Gateway (REST)<br/>POST/GET /webhook<br/>POST /process, /credit, /knowledge<br/>Throttle: 100 req/s, burst 200"]
        APPSYNC["AWS AppSync (GraphQL)<br/>Offline sync mutations/queries<br/>DynamoDB + Lambda resolvers"]
    end

    subgraph ComputeLayer["⚡ Compute Layer (Lambda)"]
        ROUTER["MessageRouter<br/>512 MB · 30s"]
        DOC["DocumentProcessor<br/>1024 MB · 60s"]
        VOICE["VoiceHandler<br/>512 MB · 60s"]
        ORCH["BedrockOrchestrator<br/>1024 MB · 180s"]
        CREDIT["CreditCalculator<br/>512 MB · 30s"]
        SAT["SatelliteAnalyzer<br/>2048 MB · 120s"]
        KB["KnowledgeBase<br/>512 MB · 60s"]
        SYNC["SyncHandler<br/>512 MB · 60s"]
    end

    subgraph AILayer["🤖 AI Services Layer"]
        BEDROCK["AWS Bedrock (Converse API)<br/>5-Model APAC Fallback Chain"]
        BKBASE["Bedrock Knowledge Bases (RAG)"]
        TEXTRACT["Amazon Textract (Queries API)"]
        TRANSCRIBE["Amazon Transcribe"]
        POLLY["Amazon Polly"]
        SAGEMAKER["SageMaker Geospatial<br/>Sentinel-2 NDVI"]
    end

    subgraph DataLayer["💾 Data Layer"]
        DDB["DynamoDB: KisanSetuData<br/>(Single Table, on-demand, GSI1)"]
        S3["S3 Buckets: raw, processed,<br/>archive, dashboard"]
        SECRETS["Secrets Manager<br/>WhatsApp credentials"]
    end

    subgraph MonitorLayer["🔒 Monitoring & Security"]
        CW["CloudWatch Logs + 18 Alarms"]
        SNS["SNS: kisan-setu-critical-alerts<br/>(configurable email via CDK context)"]
        KMS["AWS KMS (field encryption)"]
        IAM["IAM (per-function least-privilege roles)"]
    end

    WA --> APIGW
    DASH --> S3
    APIGW --> ROUTER
    APPSYNC --> SYNC
    ROUTER -->|"image (async)"| DOC
    ROUTER -->|"audio (async)"| VOICE
    ROUTER -->|"text (async)"| ORCH
    VOICE -->|"transcribed text (async)"| ORCH
    ORCH -->|"Lambda invoke"| CREDIT
    ORCH -->|"Lambda invoke"| SAT
    ORCH -->|"Lambda invoke"| KB
    DOC --> BEDROCK
    DOC --> TEXTRACT
    VOICE --> TRANSCRIBE
    VOICE --> POLLY
    ORCH --> BEDROCK
    KB --> BKBASE
    SAT --> SAGEMAKER
    ROUTER --> DDB
    DOC --> DDB
    ORCH --> DDB
    CREDIT --> DDB
    SAT --> DDB
    SYNC --> DDB
    DOC --> S3
    VOICE --> S3
    SAT --> S3
    ComputeLayer --> CW
    ComputeLayer --> SNS
```

> **Key routing facts (verified from code):**
> - Router invokes only 3 Lambdas: DocumentProcessor (image), VoiceHandler (audio), BedrockOrchestrator (text). It does NOT directly invoke SatelliteAnalyzer or CreditCalculator.
> - VoiceHandler forwards transcribed text to BedrockOrchestrator via async Lambda invoke.
> - BedrockOrchestrator invokes CreditCalculator, SatelliteAnalyzer, and KnowledgeBase via synchronous Lambda invoke.
> - DocumentProcessor sends WhatsApp responses directly (not through Orchestrator).

---

## 3. Project Structure (Actual)

```
kisan-setu-mvp/
├── app.py                          # CDK app entry point
├── infrastructure_stack.py         # Single CDK stack (KisanSetuMVPStack)
├── cdk.json                        # CDK config (Python 3.11 runtime)
├── schema.graphql                  # AppSync GraphQL schema
├── requirements.txt                # Python deps (CDK, boto3, hypothesis, etc.)
├── seed_data.py                    # DynamoDB seed script (FPO, farmers, txns)
├── Dockerfile.lambda               # Lambda container build
├── deploy.sh / deploy_meta_whatsapp.sh / build_lambda_packages.sh
├── pytest.ini                      # Test config (markers: property, integration, e2e)
│
├── lambda/
│   ├── common/                     # Shared modules (copied into each Lambda)
│   │   ├── models.py               # Dataclasses: Message, LedgerData, NDVIResult, etc.
│   │   ├── dynamodb_access.py      # DynamoDBAccess class — CRUD for all entities
│   │   ├── validation.py           # GPS, phone, NDVI, crop, moisture validators
│   │   ├── error_handling.py       # CircuitBreaker, retry, CriticalErrorAlerter (SNS)
│   │   ├── llm_adapter.py          # LLMAdapter — 5-model fallback, circuit breakers
│   │   ├── cost_optimization.py    # CacheManager, TextractBatcher, ConcurrentProcessor
│   │   ├── encryption.py           # EncryptionService — KMS + Fernet field encryption
│   │   └── ledger_formatter.py     # Multilingual ledger response formatting
│   │
│   ├── router/router.py            # MessageRouter Lambda handler
│   ├── processor/processor.py      # DocumentProcessor Lambda handler
│   ├── orchestrator/orchestrator.py # BedrockOrchestrator Lambda handler
│   ├── voice/voice.py + voice_agent.py  # VoiceHandler Lambda
│   ├── credit/credit.py            # CreditEngine + handler
│   ├── satellite/satellite_analyzer.py + satellite_mock.py
│   ├── knowledge/knowledge_base.py # Bedrock Knowledge Base handler
│   ├── sync/sync_handler.py        # Offline sync handler
│   └── whatsapp/meta_whatsapp_interface.py # WhatsApp Business API interface
│
├── dashboard/                      # S3-hosted FPO admin dashboard
│   ├── index.html
│   └── app.js
│
├── tests/                          # 55+ test files
│   ├── conftest.py, generators.py, mock_services.py
│   └── ... (property-based, unit, integration tests)
│
├── docs/
│   ├── demo_video_script.md
│   └── presentation_outline.md
│
└── .github/workflows/test.yml      # CI/CD pipeline
```


---

## 4. Lambda Functions — Detailed Breakdown

### 4.1 MessageRouter (`lambda/router/router.py`)

| Property | Value |
|----------|-------|
| Runtime | Python 3.11 |
| Memory | 512 MB |
| Timeout | 30s |
| Handler | `router.handler` |

Entry point for all WhatsApp traffic. Responsibilities:

- **Webhook verification**: Handles Meta's `GET` challenge-response (`hub.verify_token` = `kisan-setu-verify-2026`)
- **Message parsing**: Extracts sender, message type, content from Meta webhook payload
- **Routing logic**: Inspects message type and invokes the appropriate downstream Lambda:
  - `image` → DocumentProcessor (async `lambda:InvokeFunction`, `InvocationType='Event'`)
  - `audio`/`voice` → VoiceHandler (async invoke)
  - `text` → BedrockOrchestrator (async invoke)
- **Language detection**: Unicode script analysis (Devanagari → Hindi, Tamil script → Tamil) + DynamoDB farmer preference lookup
- **Message metadata storage**: Writes to DynamoDB (`CONVERSATION#{sender}` / `MSG#{timestamp}`)
- **Duplicate detection**: Checks `MSGID#{message_id}` / `DEDUP` key with 24-hour TTL

> **Note**: Router does NOT directly invoke SatelliteAnalyzer or CreditCalculator. Those are invoked by BedrockOrchestrator.

### 4.2 DocumentProcessor (`lambda/processor/processor.py`)

| Property | Value |
|----------|-------|
| Runtime | Python 3.11 |
| Memory | 1024 MB |
| Timeout | 60s |
| Handler | `processor.handler` |

Processes handwritten ledger images. Key design decision: **multimodal LLM-first with Textract fallback**.

- **Image acquisition**: Downloads image from WhatsApp via media API, uploads to S3 (`kisan-setu-raw-{acct}`)
- **LLM extraction** (`_extract_with_multimodal_llm`): Sends image to Bedrock Converse API (multimodal chain) with structured extraction prompt for quantity, moisture, price, date, crop type, farmer name
- **Multi-entry support**: Parses multiple ledger entries from a single image (`_parse_llm_response_multi`)
- **Textract fallback**: If LLM extraction fails, falls back to Textract Queries API
- **Post-processing**: LLM-based field refinement and sanitization
- **Validation**: Confidence scoring per field, flags fields below threshold for review
- **Aggregation**: `aggregate_ledgers()` computes totals, averages, weighted prices across multiple entries
- **Batch processing**: `process_batch_ledgers()` handles multiple images with error isolation
- **Storage**: Writes structured `LedgerData` to DynamoDB, sends formatted response via WhatsApp directly (not through Orchestrator)

### 4.3 BedrockOrchestrator (`lambda/orchestrator/orchestrator.py`)

| Property | Value |
|----------|-------|
| Runtime | Python 3.11 |
| Memory | 1024 MB |
| Timeout | 180s |
| Handler | `orchestrator.handler` |

Central AI brain. Handles all text-based interactions.

- **ModelRouter**: Classifies queries into tiers (simple/default/complex) using regex patterns for cost-optimized model selection
- **Intent detection** (`_detect_intent`): Pattern-matching for:
  - `transaction` — ledger creation from text/voice transcription (checked first)
  - `credit` — credit score queries
  - `satellite` — crop health / NDVI queries (Hindi, Marathi, Tamil, English keywords)
- **Sub-Lambda invocation**: Calls CreditCalculator, SatelliteAnalyzer, KnowledgeBase via synchronous `lambda:InvokeFunction`
- **Voice ledger creation**: Parses transaction data from text messages (quantity + crop + price patterns), creates ledger entries
- **Conversation context**: Stores/retrieves conversation history from DynamoDB (`CONVERSATION#{sender_id}` / `CHAT#{timestamp}#role`) — last 6 messages
- **5-model fallback**: Uses `LLMAdapter` for Bedrock Converse API calls
- **Static fallback**: If all models fail, returns a hardcoded helpful response
- **Cost tracking**: Records token usage per tier for daily cost monitoring (`SYSTEM#MODEL_COSTS` / `MODEL_COST#{date}`)
- **Daily cost threshold**: When daily cost exceeds $2.00, forces all queries to secondary (Nova Lite) tier

### 4.4 VoiceHandler (`lambda/voice/voice.py` + `voice_agent.py`)

| Property | Value |
|----------|-------|
| Runtime | Python 3.11 |
| Memory | 512 MB |
| Timeout | 60s |
| Handler | `voice.handler` |

End-to-end voice pipeline:

1. Downloads audio from WhatsApp media API → uploads to S3
2. `VoiceAgent.transcribe_audio()`: Starts Amazon Transcribe async job, polls for completion
   - Supports: Hindi (`hi-IN`), Marathi (`mr-IN`), Tamil (`ta-IN`)
   - Audio formats: OGG, MP3, WAV, M4A (auto-detected)
   - Retry logic for job creation
3. Sends transcription confirmation to user via WhatsApp (multilingual)
4. **Forwards transcribed text to BedrockOrchestrator** via async Lambda invoke (`InvocationType='Event'`)
5. Orchestrator processes the text and sends AI response back to user via WhatsApp

> **Note**: VoiceHandler does NOT synthesize speech responses by default in the main transcribe flow. The TTS capability (`synthesize_speech` via Amazon Polly) exists in VoiceAgent but is invoked separately via the `synthesize` action.

### 4.5 CreditCalculator (`lambda/credit/credit.py`)

| Property | Value |
|----------|-------|
| Runtime | Python 3.11 |
| Memory | 512 MB |
| Timeout | 30s |
| Handler | `credit.handler` |

`CreditEngine` computes a 0-100 reliability score from 5 weighted components:

| Component | Max Points | Sub-metrics |
|-----------|-----------|-------------|
| Supply Consistency | 30 | Frequency (10), Adherence (10), Fulfillment (10) |
| Quality Metrics | 25 | Moisture (10), Grade Consistency (10), Rejection Rate (5) |
| Transaction History | 20 | Volume (10), Relationship Length (5), Success Rate (5) |
| Financial Behavior | 15 | Payment Timeliness (10), Outstanding Dues (5) |
| Operational Transparency | 10 | Digitization Rate (5), Data Completeness (5) |

- Queries farmer transactions from DynamoDB
- Stores score with timestamp (`FARMER#{farmer_id}` / `SCORE#{date}`)
- Detects significant changes (>10 points) and triggers notifications
- Maintains score history for trend analysis

### 4.6 SatelliteAnalyzer (`lambda/satellite/satellite_analyzer.py`)

| Property | Value |
|----------|-------|
| Runtime | Python 3.11 |
| Memory | **2048 MB** |
| Timeout | **120s** |
| Handler | `satellite_analyzer.handler` |
| Layers | GeospatialLayer (rasterio, pyproj, numpy) |

- **Live mode**: SageMaker Geospatial API for Sentinel-2 satellite imagery (region: `us-west-2`)
  - Generates bounding box from GPS coordinates
  - Retrieves Band 4 (Red) and Band 8 (NIR) for NDVI calculation
  - NDVI = (NIR - Red) / (NIR + Red), range [-1.0, 1.0]
- **Mock mode** (`SatelliteMock`): Deterministic NDVI generation for demo
  - Scoped to Maharashtra geographic bounds
  - 8 crop types with realistic yield ranges
  - Hash-based determinism (same coords + date = same result)
- **NDVI heatmap rendering**: PIL-based PNG generation of NDVI spatial data
- **Yield prediction**: Based on NDVI history trends
  - Maturity stages: Early, Mid, Late, Harvest Ready
  - Confidence intervals from cloud cover analysis
- **Caching**: DynamoDB-backed 24-hour cache for satellite imagery (`FIELD#{coords_hash}` / `NDVI#{timestamp}`)

### 4.7 KnowledgeBase (`lambda/knowledge/knowledge_base.py`)

| Property | Value |
|----------|-------|
| Runtime | Python 3.11 |
| Memory | 512 MB |
| Timeout | 60s |
| Handler | `knowledge_base.handler` |

RAG-based agricultural knowledge retrieval:

- `retrieve`: Vector search against Bedrock Knowledge Base
- `retrieve_and_generate`: Full RAG pipeline (retrieve + LLM generation)
- Domain-specific helpers: FPO guidelines, farming practices, quality standards, credit criteria
- Cost optimization: Reduces long-context prompting by ~40%

> **Note**: `KNOWLEDGE_BASE_ID` environment variable is empty string in CDK — requires manual configuration after running `setup_knowledge_base.py`.

### 4.8 SyncHandler (`lambda/sync/sync_handler.py`)

| Property | Value |
|----------|-------|
| Runtime | Python 3.11 |
| Memory | 512 MB |
| Timeout | 60s |
| Handler | `sync_handler.handler` |

AppSync Lambda resolver for offline sync:

- Handles `syncOfflineTransactions` GraphQL mutation
- Sorts transactions chronologically before processing
- **Conflict resolution**: Last-write-wins (higher version number wins)
- Reports: success count, failure count, conflict details with resolution


---

## 5. Shared Common Modules (`lambda/common/`)

### 5.1 Data Models (`models.py`)

Dataclasses matching the DynamoDB single-table design:

| Model | Key Fields |
|-------|-----------|
| `Message` | message_id, sender_id, message_type (TEXT/VOICE/IMAGE), content, language |
| `LedgerData` | ledger_id, farmer_id, quantity, moisture, price, crop_type, confidence_scores |
| `NDVIResult` | field_id, gps_coords, ndvi_value (-1.0 to 1.0), confidence |
| `YieldPrediction` | field_id, estimated_volume, confidence_interval, maturity_stage |
| `ReliabilityScore` | farmer_id, total_score (0-100), 5 component scores, score_change |
| `Transaction` | transaction_id, farmer_id, fpo_id, quantity, crop_type, quality_grade, sync_status |
| `Farmer` | farmer_id, name, phone, fpo_id, gps_coords, preferred_language |
| `FPO` | fpo_id, name, location, manager_contact, member_count |
| `AuditTrail` | audit_id, entity_type, entity_id, operation, changed_fields, previous_values |

### 5.2 LLM Adapter (`llm_adapter.py`)

The core AI resilience layer:

**Text Fallback Chain (APAC Inference Profiles):**

| Priority | Model | Inference Profile | Retries |
|----------|-------|--------------------|---------|
| 1 | Amazon Nova Pro | apac.amazon.nova-pro-v1:0 | 2 |
| 2 | Amazon Nova Lite | apac.amazon.nova-lite-v1:0 | 2 |
| 3 | Claude 3.7 Sonnet | apac.anthropic.claude-3-7-sonnet | 1 |
| 4 | Claude 3.5 Sonnet v2 | apac.anthropic.claude-3-5-sonnet-v2 | 1 |
| 5 | Claude 3 Haiku | apac.anthropic.claude-3-haiku | 1 |

**Multimodal Fallback Chain (Image Processing):**

| Priority | Model | Retries |
|----------|-------|---------|
| 1 | Claude 3.7 Sonnet | 2 |
| 2 | Claude 3.5 Sonnet v2 | 2 |
| 3 | Amazon Nova Pro | 2 |
| 4 | Claude 3 Haiku | 2 |
| 5 | Amazon Nova Lite | 2 |

**Resilience features:**

| Feature | Details |
|---------|---------|
| Circuit breaker | Per model: opens after 3 failures, 60s timeout, half-open probe |
| Exponential backoff | 1s, 2s, 4s for ThrottlingException, ModelTimeoutException, InternalServerException, ServiceUnavailableException |
| Token tracking | Input/output token counts per request |

### 5.3 DynamoDB Access (`dynamodb_access.py`)

Centralized data access layer with methods for all entities:

- CRUD for Farmer, FPO, Transaction, ReliabilityScore, NDVIResult, Message
- Date range queries for transactions
- Credit score history retrieval
- Audit trail creation (automatic on create/update operations)
- Pending sync management for offline devices

### 5.4 Error Handling (`error_handling.py`)

- `ErrorCategory` enum: VALIDATION, AUTHENTICATION, AUTHORIZATION, NOT_FOUND, RATE_LIMIT, SERVICE_ERROR, AI_ERROR, NETWORK_ERROR
- `ErrorSeverity` enum: LOW, MEDIUM, HIGH, CRITICAL
- `get_localized_message()`: Error messages in English, Hindi, Marathi, Tamil
- `CircuitBreaker`: Generic circuit breaker for any service
- `retry_with_exponential_backoff()`: Configurable retry decorator
- `CriticalErrorAlerter`: Publishes to SNS topic for critical errors
- `process_batch_with_resilience()`: Batch processing with per-item error isolation

### 5.5 Cost Optimization (`cost_optimization.py`)

- `CacheManager`: DynamoDB-backed cache with TTL (satellite imagery, Bedrock responses)
- `TextractBatcher`: Batches multiple document processing requests
- `ConcurrentProcessor`: Thread pool for parallel processing

### 5.6 Encryption (`encryption.py`)

- `EncryptionService`: AWS KMS data key generation + Fernet symmetric encryption
- Field-level encryption for sensitive data (price, phone, financial_behavior)
- Format: `base64(encrypted_key):base64(ciphertext)`
- Sensitive field definitions per entity type

### 5.7 Validation (`validation.py`)

- GPS coordinates: -90 to 90 lat, -180 to 180 lon
- Indian phone numbers: +91/91/10-digit, starting with 6-9
- Language codes: hi-IN, mr-IN, ta-IN
- NDVI: [-1.0, 1.0], Confidence: [0.0, 1.0], Reliability: [0, 100]
- Quality grades: A, B, C
- Crop types: onion, wheat, rice, cotton, soybean, maize
- Moisture: [0, 100]%

### 5.8 Ledger Formatter (`ledger_formatter.py`)

- Multilingual response formatting for extracted ledger data
- Market reference price comparison
- Suspicious price detection
- Localized labels (Hindi, Marathi, Tamil, English)


---

## 6. Data Architecture

### 6.1 DynamoDB Single Table Design

**Table**: `KisanSetuData` (on-demand billing, PK/SK key schema)

| Entity | PK | SK | Key Attributes |
|--------|----|----|----------------|
| Farmer | `FARMER#{farmer_id}` | `METADATA` | name, phone, fpo_id, gps_coords, preferred_language |
| Transaction | `FARMER#{farmer_id}` | `TXN#{timestamp}` | quantity, crop_type, quality_grade |
| Credit Score | `FARMER#{farmer_id}` | `SCORE#{date}` | total_score, component_scores |
| FPO | `FPO#{fpo_id}` | `METADATA` | name, location, member_count |
| NDVI Result | `FIELD#{coords_hash}` | `NDVI#{timestamp}` | ndvi_value, confidence |
| Conversation Message | `CONVERSATION#{sender_id}` | `MSG#{timestamp}` | message_type, content, status |
| Conversation Chat | `CONVERSATION#{sender_id}` | `CHAT#{timestamp}#role` | role (user/assistant), content |
| Message Dedup | `MSGID#{message_id}` | `DEDUP` | timestamp, ttl (24h) |
| Model Cost Tracking | `SYSTEM#MODEL_COSTS` | `MODEL_COST#{date}` | total_cost, calls, model_name |
| Audit Trail | `AUDIT#{entity_type}#{entity_id}` | `{timestamp}` | operation, changed_fields |
| Pending Sync | `SYNC#{device_id}` | `{timestamp}` | sync data |

```mermaid
graph TB
    subgraph DynamoDB["KisanSetuData — Single Table Design"]
        direction TB
        F["FARMER#id → METADATA<br/>FARMER#id → TXN#ts<br/>FARMER#id → SCORE#date"]
        FPO_E["FPO#id → METADATA"]
        FIELD["FIELD#hash → NDVI#ts"]
        CONV["CONVERSATION#sender → MSG#ts<br/>CONVERSATION#sender → CHAT#ts#role"]
        DEDUP["MSGID#id → DEDUP (24h TTL)"]
        COST["SYSTEM#MODEL_COSTS → MODEL_COST#date"]
        AUDIT["AUDIT#type#id → timestamp"]
        SYNC_E["SYNC#device → timestamp"]
    end

    GSI["GSI1: fpoId → list farmers by FPO"]
    DynamoDB --> GSI
```

**GSI1**: Partition key `fpoId` — enables "list farmers by FPO" queries

### 6.2 S3 Bucket Strategy

| Bucket | Purpose | Content |
|--------|---------|---------|
| `kisan-setu-raw-{acct}` | Raw uploads | Ledger images, voice recordings |
| `kisan-setu-processed-{acct}` | Processed data | Structured extractions |
| `kisan-setu-archive-{acct}` | Long-term storage | Archived data |
| `kisan-setu-dashboard-{acct}` | Static website (CDK-created) | Admin dashboard (HTML/JS) |

### 6.3 GraphQL Schema (AppSync)

Types: `Farmer`, `Transaction`, `CreditScore`, `SyncResult`, `ConflictInfo`

Queries:
- `getFarmer(farmerId)` — DynamoDB direct resolver
- `listTransactions(farmerId, limit, nextToken)` — Paginated query
- `getCreditScore(farmerId)` — Latest score
- `listFarmers(fpoId, limit, nextToken)` — GSI1 query

Mutations:
- `createTransaction(input)` — Conditional put (version check)
- `updateTransaction(input)` — Optimistic concurrency (version match)
- `syncOfflineTransactions(transactions)` — Lambda resolver (SyncHandler, batch sync)


---

## 7. Data Flow Diagrams

### 7.1 Image Message Flow (Ledger Digitization)

```mermaid
sequenceDiagram
    participant User as 📱 WhatsApp User
    participant Meta as Meta Cloud API
    participant APIGW as API Gateway
    participant Router as MessageRouter
    participant DocProc as DocumentProcessor
    participant Bedrock as Bedrock Converse API
    participant Textract as Amazon Textract
    participant S3 as S3 (raw)
    participant DB as DynamoDB
    participant WA as WhatsApp (Response)

    User->>Meta: Send ledger photo
    Meta->>APIGW: POST /webhook
    APIGW->>Router: Invoke
    Router->>Router: Dedup check (MSGID#id)
    Router->>DB: Store message metadata
    Router->>DocProc: Async invoke (InvocationType=Event)
    Router-->>APIGW: 200 OK (processing)

    DocProc->>Meta: Download image (media API)
    DocProc->>S3: Upload raw image
    DocProc->>Bedrock: Multimodal LLM extraction (image + prompt)
    alt LLM extraction succeeds
        Bedrock-->>DocProc: Structured ledger data (JSON)
    else LLM extraction fails
        DocProc->>Textract: Textract Queries API fallback
        Textract-->>DocProc: Extracted fields
        DocProc->>Bedrock: LLM post-processing (refine fields)
        Bedrock-->>DocProc: Refined data
    end
    DocProc->>DB: Store LedgerData (FARMER#id / TXN#ts)
    DocProc->>WA: Send formatted response directly
    WA->>Meta: Deliver to user
```

### 7.2 Voice Message Flow

```mermaid
sequenceDiagram
    participant User as 📱 WhatsApp User
    participant Meta as Meta Cloud API
    participant APIGW as API Gateway
    participant Router as MessageRouter
    participant Voice as VoiceHandler
    participant Transcribe as Amazon Transcribe
    participant S3 as S3 (raw)
    participant Orch as BedrockOrchestrator
    participant Bedrock as Bedrock Converse API
    participant DB as DynamoDB
    participant WA as WhatsApp (Response)

    User->>Meta: Send voice note
    Meta->>APIGW: POST /webhook
    APIGW->>Router: Invoke
    Router->>DB: Store message metadata
    Router->>Voice: Async invoke (InvocationType=Event)
    Router-->>APIGW: 200 OK (processing)

    Voice->>Meta: Download audio (media API)
    Voice->>S3: Upload audio file
    Voice->>Transcribe: Start transcription job (hi-IN/mr-IN/ta-IN)
    Transcribe-->>Voice: Transcribed text + confidence
    Voice->>WA: Send transcription confirmation to user
    Voice->>Orch: Async invoke with transcribed text
    Orch->>Bedrock: Converse API (text chain)
    Bedrock-->>Orch: AI response
    Orch->>DB: Store conversation (CHAT#ts)
    Orch->>WA: Send text response
    WA->>Meta: Deliver to user
```

### 7.3 Text Message Flow

```mermaid
sequenceDiagram
    participant User as 📱 WhatsApp User
    participant Meta as Meta Cloud API
    participant APIGW as API Gateway
    participant Router as MessageRouter
    participant Orch as BedrockOrchestrator
    participant Credit as CreditCalculator
    participant Sat as SatelliteAnalyzer
    participant KB as KnowledgeBase
    participant Bedrock as Bedrock Converse API
    participant DB as DynamoDB
    participant WA as WhatsApp (Response)

    User->>Meta: Send text message
    Meta->>APIGW: POST /webhook
    APIGW->>Router: Invoke
    Router->>DB: Store message metadata
    Router->>Orch: Async invoke (InvocationType=Event)
    Router-->>APIGW: 200 OK (processing)

    Orch->>Orch: Detect intent (credit/satellite/transaction/general)
    Orch->>DB: Load conversation history (last 6 msgs)

    alt Credit Score Intent
        Orch->>Credit: Sync Lambda invoke
        Credit->>DB: Query farmer transactions
        Credit->>DB: Store score (SCORE#date)
        Credit-->>Orch: Score + breakdown
        Orch->>Orch: Format credit response
    else Satellite/Crop Health Intent
        Orch->>Sat: Sync Lambda invoke
        Sat->>DB: Check cache / compute NDVI
        Sat-->>Orch: NDVI + yield prediction
    else General Knowledge Query
        Orch->>Bedrock: Converse API (text chain)
        Bedrock-->>Orch: AI response
    end

    Orch->>DB: Store conversation (CHAT#ts)
    Orch->>WA: Send response
    WA->>Meta: Deliver to user
```

### 7.4 Offline Sync Flow

```mermaid
sequenceDiagram
    participant Tablet as 📱 FPO Tablet (SQLite)
    participant AppSync as AWS AppSync (GraphQL)
    participant SyncHandler as SyncHandler Lambda
    participant DB as DynamoDB

    Tablet->>AppSync: syncOfflineTransactions(transactions[])
    AppSync->>SyncHandler: Lambda resolver invoke
    SyncHandler->>SyncHandler: Sort transactions chronologically
    loop For each transaction
        SyncHandler->>DB: Check existing version
        alt No conflict (new or higher version)
            SyncHandler->>DB: Write transaction (FARMER#id / TXN#ts)
        else Conflict (lower version)
            SyncHandler->>SyncHandler: Last-write-wins resolution
            SyncHandler->>DB: Keep higher version
        end
    end
    SyncHandler-->>AppSync: SyncResult (success, failures, conflicts)
    AppSync-->>Tablet: GraphQL response
```

---

## 8. WhatsApp Integration

### 8.1 Meta WhatsApp Business API

- **Phone Number ID**: `1043444535519617`
- **Business Account ID**: `1249840547247394`
- **Webhook URL**: `https://{api-id}.execute-api.ap-south-1.amazonaws.com/prod/webhook`
- **Verify Token**: `kisan-setu-verify-2026`

### 8.2 MetaWhatsAppInterface Class

Capabilities:
- Credential loading from AWS Secrets Manager (`kisan-setu/whatsapp/credentials`)
- Send: text, voice (audio URL), image, document
- Receive: Parse webhook payload into `WhatsAppMessage` objects
- Media download: Fetch image/audio from WhatsApp CDN
- Formatting: Tables, numbered lists, structured data (WhatsApp-compatible)
- Welcome message: Multilingual onboarding
- Rate limit handling: Exponential backoff on 429 responses

### 8.3 Complete Message Flow

```mermaid
sequenceDiagram
    participant User as 📱 WhatsApp User
    participant Meta as Meta Cloud API
    participant APIGW as API Gateway
    participant Router as MessageRouter
    participant DocProc as DocumentProcessor
    participant Voice as VoiceHandler
    participant Orch as BedrockOrchestrator
    participant AI as Bedrock / Textract / Transcribe
    participant DB as DynamoDB
    participant WA as WhatsApp (Response)

    User->>Meta: Send message (text/image/audio)
    Meta->>APIGW: POST /webhook
    APIGW->>Router: Invoke

    alt Image Message
        Router->>DocProc: Async invoke
        DocProc->>AI: LLM extraction (Bedrock Converse multimodal)
        AI-->>DocProc: Structured ledger data
        DocProc->>DB: Store LedgerData
        DocProc->>WA: Send formatted response directly
    else Audio Message
        Router->>Voice: Async invoke
        Voice->>AI: Transcribe audio (Amazon Transcribe)
        AI-->>Voice: Transcribed text
        Voice->>WA: Send transcription confirmation
        Voice->>Orch: Forward transcribed text (async invoke)
        Orch->>AI: Bedrock Converse API
        AI-->>Orch: AI response
        Orch->>DB: Store conversation
        Orch->>WA: Send text response
    else Text Message
        Router->>Orch: Async invoke
        Orch->>AI: Bedrock Converse API
        AI-->>Orch: AI response
        Orch->>DB: Store conversation
        Orch->>WA: Send text response
    end

    WA->>Meta: Send response
    Meta->>User: Deliver response
```


---

## 9. Security Architecture

```mermaid
graph TB
    subgraph ExternalBoundary["🌐 External Boundary"]
        WA["WhatsApp Users"]
        DASH["Admin Dashboard"]
    end

    subgraph APISecurityLayer["🔐 API Security Layer"]
        APIGW["API Gateway<br/>Throttle: 100/s, burst 200<br/>Webhook verify token"]
        APPSYNC["AppSync<br/>Cognito User Pool auth + X-Ray"]
    end

    subgraph CredentialMgmt["🔑 Credential Management"]
        SM["Secrets Manager<br/>kisan-setu/whatsapp/credentials<br/>(PHONE_NUMBER_ID, ACCESS_TOKEN, VERIFY_TOKEN)"]
    end

    subgraph EncryptionLayer["🔒 Encryption"]
        KMS["AWS KMS<br/>Data key generation"]
        FERNET["Fernet Symmetric Encryption<br/>Field-level: price, phone, financial_behavior<br/>Integrated into DynamoDBAccess"]
        FORMAT["Format: base64(encrypted_key):base64(ciphertext)"]
    end

    subgraph IAMLayer["👤 IAM"]
        ROLE["Per-Function Lambda Execution Roles (8 roles)"]
        MANAGED["Managed Policy:<br/>AWSLambdaBasicExecutionRole (all roles)"]
        CUSTOM["Scoped Inline Policies per function:<br/>DynamoDB (table ARN), S3 (bucket ARNs),<br/>Bedrock, Textract, Transcribe, Polly,<br/>SageMaker Geo, Lambda Invoke,<br/>Secrets Manager, SNS Publish, KMS"]
    end

    subgraph DataSecurity["💾 Data Security"]
        DDB_ENC["DynamoDB encryption at rest"]
        S3_ENC["S3 SSE encryption"]
        TLS["HTTPS/TLS for all API calls"]
    end

    subgraph Monitoring["📊 Monitoring & Alerting"]
        CW["CloudWatch Logs<br/>(all Lambda functions)"]
        SNS_ALERT["SNS: kisan-setu-critical-alerts<br/>CriticalErrorAlerter publishes on CRITICAL severity"]
        AUDIT["Audit Trail<br/>Via DynamoDBAccess class"]
    end

    WA --> APIGW
    DASH --> S3_ENC
    APIGW --> ROLE
    APPSYNC --> ROLE
    ROLE --> MANAGED
    ROLE --> CUSTOM
    ROLE --> SM
    ROLE --> KMS
    KMS --> FERNET
    FERNET --> FORMAT
    ROLE --> CW
    ROLE --> SNS_ALERT
```

### Security Controls Summary

| Layer | Mechanism | Details |
|-------|-----------|---------|
| API Security | API Gateway throttling | 100 req/s, burst 200 |
| API Security | Webhook verify token | `kisan-setu-verify-2026` |
| Credential Management | AWS Secrets Manager | WhatsApp tokens (PHONE_NUMBER_ID, ACCESS_TOKEN) |
| Field Encryption | KMS + Fernet | Sensitive fields: price, phone, financial_behavior — integrated into DynamoDBAccess |
| IAM | Per-function Lambda roles | 8 individual roles with least-privilege permissions scoped to specific table/bucket ARNs |
| Data at Rest | DynamoDB encryption | AWS-managed encryption |
| Data at Rest | S3 SSE | Server-side encryption |
| Data in Transit | HTTPS/TLS | All API calls encrypted |
| Audit Trail | DynamoDB audit records | Automatic on all data mutations via DynamoDBAccess class |
| AppSync Auth | Cognito User Pool authentication | X-Ray tracing enabled |
| Alerting | SNS critical alerts | Published on CRITICAL severity errors |


---

## 10. Infrastructure (CDK)

### 10.1 Stack: `KisanSetuMVPStack`

Single monolithic stack deployed to `ap-south-1` (Mumbai).

**Resources created by CDK:**
- 8 Lambda functions (per-function IAM roles with least-privilege permissions)
- 1 Lambda Layer (GeospatialLayer — rasterio, pyproj, numpy for SatelliteAnalyzer)
- 1 API Gateway (REST, `prod` stage, throttle 100/s burst 200)
- 1 AppSync GraphQL API (API key auth, X-Ray enabled)
- 1 SNS Topic (`kisan-setu-critical-alerts`, configurable email via `alert_email` CDK context)
- 18 CloudWatch Alarms (Errors + Throttles per Lambda, API Gateway 5xx + p99 latency)
- 1 S3 Bucket (dashboard, public read, static website)
- 1 S3 BucketDeployment (dashboard files)
- 1 AwsCustomResource (DynamoDB PITR enablement)
- 2 Lambda Aliases with provisioned concurrency (Router + Orchestrator, PC=2)

**Resources referenced (pre-existing):**
- DynamoDB table: `KisanSetuData`
- S3 buckets: raw, processed, archive

### 10.2 Lambda Configuration (from CDK)

| Function | Memory | Timeout | Layers | Key Env Vars |
|----------|--------|---------|--------|-------------|
| MessageRouter | 512 MB | 30s | — | PROCESSOR_FUNCTION_NAME, VOICE_AGENT_FUNCTION, BEDROCK_ORCHESTRATOR_FUNCTION |
| DocumentProcessor | 1024 MB | 60s | — | S3_BUCKET_RAW, WHATSAPP_SECRET_NAME |
| VoiceHandler | 512 MB | 60s | — | S3_BUCKET_RAW, WHATSAPP_SECRET_NAME |
| BedrockOrchestrator | 1024 MB | 180s | — | All sub-Lambda function names, BEDROCK_AGENT_ID |
| CreditCalculator | 512 MB | 30s | — | DYNAMODB_TABLE |
| SatelliteAnalyzer | **2048 MB** | **120s** | GeospatialLayer | SAGEMAKER_REGION=us-west-2, SENTINEL2_ARN |
| KnowledgeBase | 512 MB | 60s | — | KNOWLEDGE_BASE_ID (empty — needs config) |
| SyncHandler | 512 MB | 60s | — | DYNAMODB_TABLE |

### 10.3 IAM Roles (Per-Function Least Privilege)

Each Lambda function has its own IAM role with `AWSLambdaBasicExecutionRole` plus only the specific permissions it needs. DynamoDB permissions are scoped to the `KisanSetuData` table ARN; S3 permissions are scoped to specific bucket ARNs.

| Lambda | DynamoDB | S3 | Lambda:Invoke | Bedrock | Textract | Transcribe | Polly | SageMaker Geo | SecretsManager | SNS | KMS |
|--------|----------|-----|---------------|---------|----------|------------|-------|---------------|----------------|-----|-----|
| Router | R/W | R/W | ✓ | — | — | — | — | — | ✓ | ✓ | ✓ |
| Orchestrator | R/W | R | ✓ | Invoke/Converse | — | — | — | — | ✓ | ✓ | ✓ |
| DocumentProcessor | R/W | R/W | — | — | ✓ | — | — | — | ✓ | ✓ | ✓ |
| VoiceHandler | R/W | R/W | ✓ | — | — | ✓ | ✓ | — | ✓ | ✓ | ✓ |
| CreditCalculator | R/W | — | — | — | — | — | — | — | — | ✓ | ✓ |
| SatelliteAnalyzer | R/W | R/W | — | — | — | — | — | ✓ | — | ✓ | ✓ |
| KnowledgeBase | R/W | — | — | Retrieve/Invoke | — | — | — | — | — | ✓ | ✓ |
| SyncHandler | R/W | — | — | — | — | — | — | — | — | ✓ | ✓ |

### 10.4 CloudWatch Alarms (18 total)

| Alarm Type | Count | Threshold | Period | Action |
|------------|-------|-----------|--------|--------|
| Lambda Errors (per function) | 8 | > 0 | 5 min | SNS alert_topic |
| Lambda Throttles (per function) | 8 | > 0 | 5 min | SNS alert_topic |
| API Gateway 5xx | 1 | > 0 | 5 min | SNS alert_topic |
| API Gateway p99 Latency | 1 | > 10000ms | 5 min | SNS alert_topic |

### 10.5 Provisioned Concurrency

| Lambda | Provisioned Concurrency | Alias |
|--------|------------------------|-------|
| Router | 2 | `live` |
| Orchestrator | 2 | `live` |

API Gateway `/webhook` POST and GET integrations point to the Router alias (not `$LATEST`).

### 10.6 API Gateway Endpoints

| Method | Path | Target | Purpose |
|--------|------|--------|---------|
| GET | `/webhook` | MessageRouter | Meta webhook verification |
| POST | `/webhook` | MessageRouter | Incoming WhatsApp messages |
| POST | `/process` | DocumentProcessor | Direct document processing |
| POST | `/credit` | CreditCalculator | Direct credit score requests |
| POST | `/knowledge` | KnowledgeBase | Direct knowledge queries |

---

## 11. Testing Architecture

```mermaid
graph TB
    subgraph TestPyramid["🧪 Test Pyramid"]
        PBT["Property-Based Tests (Hypothesis)<br/>Core correctness properties"]
        UNIT["Unit Tests<br/>Individual function/class testing"]
        INT["Integration Tests<br/>LocalStack + DynamoDB Local"]
        E2E["E2E Tests<br/>Complete workflow verification"]
    end

    subgraph CICD["⚙️ CI/CD Pipeline (GitHub Actions)"]
        J1["Job 1: Unit Tests<br/>pytest -n auto + coverage"]
        J2["Job 2: Property Tests<br/>Hypothesis CI profile (100 examples)"]
        J3["Job 3: Integration Tests<br/>LocalStack (DynamoDB, S3, Lambda, APIGW)"]
        J4["Job 4: Code Quality<br/>black, isort, flake8, pylint"]
        J5["Job 5: Security Scan<br/>bandit (SAST) + safety (deps)"]
    end

    J1 --> SUMMARY["Test Summary<br/>PR Comment"]
    J2 --> SUMMARY
    J3 --> SUMMARY
    J4 --> SUMMARY
    J5 --> SUMMARY
```

### 11.1 Hypothesis Configuration

| Profile | Max Examples | Deadline | Use Case |
|---------|-------------|----------|----------|
| `ci` | 100 | None | CI pipeline |
| `dev` | 20 | None | Local development |
| `debug` | 10 | None (verbose) | Debugging |

### 11.2 Custom Generators (`generators.py`)

Hypothesis strategies for all domain types: GPS coordinates, phone numbers, transactions, NDVI results, yield predictions, reliability scores, ledger data, messages, audit trails, farmer-with-transactions, NDVI time series, ledger batches, conflicting transactions.


---

## 12. Resilience Patterns

```mermaid
graph LR
    subgraph CircuitBreaker["Circuit Breaker Pattern"]
        CLOSED["🟢 Closed<br/>(Normal)"] -->|"3 failures"| OPEN["🔴 Open<br/>(Reject all)"]
        OPEN -->|"60s timeout"| HALFOPEN["🟡 Half-Open<br/>(Probe)"]
        HALFOPEN -->|"Success"| CLOSED
        HALFOPEN -->|"Failure"| OPEN
    end
```

| Pattern | Implementation | Location |
|---------|---------------|----------|
| Circuit Breaker | Per-model failure tracking, open/half-open/closed states | `llm_adapter.py`, `error_handling.py` |
| Exponential Backoff | 2^attempt seconds (1s → 2s → 4s), configurable max retries | `llm_adapter.py`, `error_handling.py` |
| Multi-Model Fallback | 5-model chain with independent circuit breakers | `llm_adapter.py` |
| Batch Resilience | Per-item error isolation, partial success reporting | `error_handling.py` |
| Critical Alerting | SNS publish on CRITICAL severity errors | `error_handling.py` |
| Localized Errors | Error messages in 4 languages (en, hi, mr, ta) | `error_handling.py` |
| Conflict Resolution | Last-write-wins with version tracking | `sync_handler.py` |
| Optimistic Concurrency | Version-based conditional writes | AppSync resolvers |
| Caching | DynamoDB-backed TTL cache for satellite/LLM responses | `cost_optimization.py` |
| Duplicate Detection | Message ID tracking with 24h TTL in router | `router.py` |
| Daily Cost Threshold | Auto-downgrade to cheapest model when daily cost exceeds $2.00 | `orchestrator.py` |

---

## 13. Cost Optimization

| Strategy | Mechanism | Estimated Savings |
|----------|-----------|-------------------|
| Nova-first model selection | Cheaper AWS models before Claude | ~40% on LLM costs |
| Knowledge Base RAG | Reduces long-context prompting | ~40% on prompt costs |
| DynamoDB on-demand | Pay-per-request, no over-provisioning | Variable |
| Satellite caching | 24h DynamoDB cache for NDVI data | ~30% on SageMaker |
| Batch processing | TextractBatcher, ConcurrentProcessor | ~15% on Textract |
| Model routing | Query classification → appropriate tier | ~25% on LLM costs |
| Daily cost threshold | Auto-downgrade when daily cost > $2.00 | Prevents runaway costs |

---

## 14. Deployment

```mermaid
flowchart LR
    DEV["👨‍💻 Developer"] -->|"git push"| GH["GitHub Actions<br/>5 parallel jobs"]
    GH -->|"Tests pass"| CDK["AWS CDK<br/>(Python)"]
    CDK -->|"cdk deploy"| AWS["☁️ AWS ap-south-1"]

    subgraph Scripts["Deployment Scripts"]
        S1["deploy.sh<br/>Full automated"]
        S2["build_lambda_packages.sh<br/>Docker packaging"]
        S3["deploy_meta_whatsapp.sh<br/>WhatsApp setup"]
    end

    DEV --> Scripts
    Scripts --> CDK
```

- **Region**: ap-south-1 (Mumbai)
- **IaC**: AWS CDK (Python), single stack
- **Lambda packaging**: Each function directory includes `common/` symlink + vendored dependencies (requests, certifi, etc.)
- **Dashboard**: S3 static website with public read access
- **Scripts**: `deploy.sh`, `deploy_meta_whatsapp.sh`, `build_lambda_packages.sh`, `sync_common.sh`
- **Seed data**: `seed_data.py` creates 1 FPO, 3 farmers, 10-15 txns each, credit scores, NDVI data

---

## 15. Key Design Decisions

1. **Multimodal LLM-first for OCR**: Uses Bedrock Converse API with image input before falling back to Textract. Better accuracy for handwritten Hindi text.

2. **5-model APAC fallback chain**: Nova models prioritized (no Marketplace subscription needed), Claude models as fallback. Ensures availability across model outages.

3. **Single DynamoDB table**: All entities in one table with PK/SK patterns. Simplifies operations, reduces costs, enables atomic transactions.

4. **Per-function IAM roles**: Each Lambda function has its own IAM role with least-privilege permissions scoped to specific table/bucket ARNs. Replaced the shared role in Phase 6.

5. **WhatsApp as sole UI**: Zero-UI approach — farmers interact entirely through WhatsApp (text, voice, images). Dashboard is admin-only.

6. **Offline-first sync**: AppSync + GraphQL with last-write-wins conflict resolution. SQLite local storage on tablets.

7. **Mock satellite data**: `SatelliteMock` provides deterministic NDVI for demo when live SageMaker Geospatial is unavailable.

8. **Property-based testing**: Hypothesis-driven correctness properties for all domain logic, ensuring mathematical accuracy and data integrity.

9. **Async Lambda invocation**: Router uses `InvocationType='Event'` for all downstream calls, returning 200 immediately. Downstream Lambdas send WhatsApp responses directly.

10. **Voice → Orchestrator forwarding**: VoiceHandler transcribes audio then forwards the text to BedrockOrchestrator for AI processing, rather than generating responses itself.


