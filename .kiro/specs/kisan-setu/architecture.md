> **Note:** This is a historical spec document representing the original design intent. The implementation evolved beyond this spec — notably using a 5-model APAC inference profile fallback chain (Nova Pro → Nova Lite → Claude 3.7 Sonnet → Claude 3.5 Sonnet v2 → Claude 3 Haiku), multimodal LLM-first document processing with Textract fallback, and a live S3-hosted FPO admin dashboard. See `kisan-setu-mvp/README.md` for current architecture.

# Kisan-Setu Architecture Document

## Executive Summary

Kisan-Setu is a serverless, AI-powered FPO Operating System built on AWS that transforms rural agricultural operations through voice-first, zero-UI interactions. The architecture prioritizes offline-first capabilities, cost optimization (<$50/month per FPO), and deep integration with AWS AI services.

## System Architecture Overview

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER LAYER                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────────┐              ┌──────────────────────┐         │
│  │  WhatsApp Business   │              │   Tablet Offline     │         │
│  │       API            │              │       Mode           │         │
│  │  (Voice, Text, Img)  │              │   (Field Managers)   │         │
│  └──────────┬───────────┘              └──────────┬───────────┘         │
│             │                                      │                     │
└─────────────┼──────────────────────────────────────┼─────────────────────┘
              │                                      │
              │                                      │
┌─────────────┼──────────────────────────────────────┼─────────────────────┐
│             │         API GATEWAY LAYER            │                     │
├─────────────┼──────────────────────────────────────┼─────────────────────┤
│             │                                      │                     │
│  ┌──────────▼───────────┐              ┌──────────▼───────────┐         │
│  │  Amazon API Gateway  │              │    AWS AppSync       │         │
│  │   (REST/WebSocket)   │              │  (GraphQL + Sync)    │         │
│  └──────────┬───────────┘              └──────────┬───────────┘         │
│             │                                      │                     │
└─────────────┼──────────────────────────────────────┼─────────────────────┘
              │                                      │
              │                                      │
┌─────────────┼──────────────────────────────────────┼─────────────────────┐
│             │      ORCHESTRATION LAYER             │                     │
├─────────────┼──────────────────────────────────────┼─────────────────────┤
│             │                                      │                     │
│  ┌──────────▼───────────┐              ┌──────────▼───────────┐         │
│  │   AWS Lambda         │◄─────────────┤  AWS Bedrock Agent   │         │
│  │   Functions          │              │  (Claude 3.5 Sonnet) │         │
│  │  - Message Router    │              │  - Intent Analysis   │         │
│  │  - Voice Handler     │              │  - Tool Orchestration│         │
│  │  - Doc Processor     │              │  - Context Memory    │         │
│  │  - Credit Calculator │              └──────────────────────┘         │
│  └──────────┬───────────┘                                                │
│             │                                                            │
└─────────────┼────────────────────────────────────────────────────────────┘
              │
              │
┌─────────────┼────────────────────────────────────────────────────────────┐
│             │           AI SERVICES LAYER                                │
├─────────────┼────────────────────────────────────────────────────────────┤
│             │                                                            │
│  ┌──────────▼───────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Amazon Textract     │  │  Amazon Transcribe│  │  Amazon Polly    │  │
│  │  - Queries API       │  │  - Multilingual   │  │  - Voice Synth   │  │
│  │  - Forms Extraction  │  │  - Hindi/Marathi  │  │  - Indian Voices │  │
│  │  - Handwriting OCR   │  │  - Tamil Support  │  │                  │  │
│  └──────────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │           Amazon SageMaker Geospatial                            │  │
│  │           - Sentinel-2 Satellite Data                            │  │
│  │           - NDVI Calculation                                     │  │
│  │           - Crop Monitoring                                      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                                       │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Amazon DynamoDB     │  │   Amazon S3      │  │  Bedrock KB      │  │
│  │  - Single Table      │  │  - Images        │  │  - FPO Guidelines│  │
│  │  - Farmer Data       │  │  - Audio Files   │  │  - Crop Data     │  │
│  │  - Transactions      │  │  - Satellite Img │  │  - Best Practices│  │
│  │  - Credit Scores     │  │                  │  │                  │  │
│  └──────────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                    MONITORING & SECURITY                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  CloudWatch          │  │   AWS IAM        │  │  AWS KMS         │  │
│  │  - Logs              │  │  - Role-Based    │  │  - Encryption    │  │
│  │  - Metrics           │  │  - Least Privilege│  │  - Key Rotation  │  │
│  │  - Alarms            │  │                  │  │                  │  │
│  └──────────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagrams

### Flow 1: Voice Query Processing

```
Farmer (WhatsApp)
    │
    │ 1. Send voice message
    ▼
WhatsApp Business API
    │
    │ 2. Webhook POST
    ▼
API Gateway
    │
    │ 3. Invoke Lambda
    ▼
Message Router Lambda
    │
    │ 4. Detect message type = voice
    ▼
Voice Handler Lambda
    │
    │ 5. Call Transcribe API
    ▼
Amazon Transcribe
    │
    │ 6. Return text + language
    ▼
Voice Handler Lambda
    │
    │ 7. Send to Bedrock Agent
    ▼
AWS Bedrock Agent (Claude 3.5)
    │
    │ 8. Analyze intent, generate response
    ▼
Voice Handler Lambda
    │
    │ 9. Call Polly for TTS
    ▼
Amazon Polly
    │
    │ 10. Return audio URL
    ▼
Voice Handler Lambda
    │
    │ 11. Send via WhatsApp API
    ▼
WhatsApp Business API
    │
    │ 12. Deliver audio message
    ▼
Farmer (WhatsApp)
```

### Flow 2: Handwritten Ledger Digitization

```
FPO Manager (WhatsApp)
    │
    │ 1. Send photo of handwritten ledger
    ▼
WhatsApp Business API
    │
    │ 2. Upload image, send webhook
    ▼
API Gateway
    │
    │ 3. Invoke Lambda
    ▼
Message Router Lambda
    │
    │ 4. Detect message type = image
    │ 5. Store image in S3
    ▼
Document Processor Lambda
    │
    │ 6. Call Textract Queries API
    │    Questions: "What is quantity?", "What is moisture?", etc.
    ▼
Amazon Textract
    │
    │ 7. Extract fields with confidence scores
    ▼
Document Processor Lambda
    │
    │ 8. Send to Bedrock Agent for structuring
    ▼
AWS Bedrock Agent
    │
    │ 9. Structure as JSON, validate fields
    ▼
Document Processor Lambda
    │
    │ 10. Store in DynamoDB
    ▼
DynamoDB
    │
    │ 11. Return success
    ▼
Document Processor Lambda
    │
    │ 12. Send formatted response via WhatsApp
    ▼
FPO Manager (WhatsApp)
```

### Flow 3: Satellite Yield Prediction

```
Farmer (WhatsApp)
    │
    │ 1. Send GPS coordinates or location
    ▼
WhatsApp Business API
    │
    │ 2. Webhook POST
    ▼
API Gateway → Message Router Lambda
    │
    │ 3. Parse GPS coordinates
    ▼
Bedrock Agent
    │
    │ 4. Invoke SageMaker Geospatial tool
    ▼
SageMaker Geospatial Lambda
    │
    │ 5. Query Sentinel-2 satellite data
    ▼
Amazon SageMaker Geospatial
    │
    │ 6. Retrieve imagery, calculate NDVI
    ▼
SageMaker Geospatial Lambda
    │
    │ 7. Predict yield based on NDVI trends
    │ 8. Store results in DynamoDB
    ▼
Bedrock Agent
    │
    │ 9. Format prediction with confidence interval
    ▼
Message Router Lambda
    │
    │ 10. Send via WhatsApp
    ▼
Farmer (WhatsApp)
```

### Flow 4: Offline Sync (Tablet Mode)

```
FPO Manager (Tablet - Offline)
    │
    │ 1. Enter transaction data
    ▼
Tablet App (Local Storage)
    │
    │ 2. Store with timestamp
    │ 3. Queue for sync
    ▼
[Internet connectivity restored]
    │
    │ 4. Detect connectivity
    ▼
Tablet App
    │
    │ 5. GraphQL mutation via AppSync
    ▼
AWS AppSync
    │
    │ 6. Batch upload transactions
    ▼
AppSync Resolver Lambda
    │
    │ 7. Check for conflicts (same transaction_id)
    ▼
DynamoDB
    │
    │ 8. Apply last-write-wins resolution
    │ 9. Log conflicts
    ▼
AppSync Resolver Lambda
    │
    │ 10. Return sync status
    ▼
AWS AppSync
    │
    │ 11. Send confirmation
    ▼
Tablet App
    │
    │ 12. Clear local queue, notify user
    ▼
FPO Manager (Tablet)
```

### Flow 5: Credit Score Calculation

```
Bank Loan Officer (Request)
    │
    │ 1. Request farmer credit score
    ▼
API Gateway
    │
    │ 2. Invoke Lambda
    ▼
Credit Calculator Lambda
    │
    │ 3. Query farmer transaction history
    ▼
DynamoDB
    │
    │ 4. Return transactions, quality data
    ▼
Credit Calculator Lambda
    │
    │ 5. Calculate components:
    │    - Supply Consistency (30 pts)
    │    - Quality Metrics (25 pts)
    │    - Transaction History (20 pts)
    │    - Financial Behavior (15 pts)
    │    - Operational Transparency (10 pts)
    │
    │ 6. Sum to total score (0-100)
    │ 7. Generate breakdown
    ▼
DynamoDB
    │
    │ 8. Store score with timestamp
    ▼
Credit Calculator Lambda
    │
    │ 9. Check if score changed >10 points
    │ 10. If yes, notify FPO manager
    ▼
WhatsApp Business API
    │
    │ 11. Send notification
    ▼
FPO Manager (WhatsApp)
```

## Technology Stack

### Core Infrastructure
- **Compute:** AWS Lambda (Python 3.11)
- **API Gateway:** Amazon API Gateway (REST + WebSocket)
- **Orchestration:** AWS Step Functions (for complex workflows)

### AI/ML Services
- **LLM:** AWS Bedrock (Claude 3.5 Sonnet)
- **OCR:** Amazon Textract (Queries + Forms)
- **Speech:** Amazon Transcribe + Amazon Polly
- **Geospatial:** Amazon SageMaker Geospatial
- **Knowledge Base:** Bedrock Knowledge Bases (RAG)

### Data Storage
- **Database:** Amazon DynamoDB (Single Table Design)
- **Object Storage:** Amazon S3 (Standard + Intelligent-Tiering)
- **Sync:** AWS AppSync (GraphQL + Offline)

### Integration
- **Messaging:** WhatsApp Business API (via Meta WhatsApp Cloud API)
- **Authentication:** Amazon Cognito
- **Secrets:** AWS Secrets Manager

### Monitoring & Security
- **Logging:** Amazon CloudWatch Logs
- **Metrics:** Amazon CloudWatch Metrics
- **Tracing:** AWS X-Ray
- **Encryption:** AWS KMS
- **IAM:** AWS IAM (Role-based access)

## Data Strategy

### Data Sources

1. **Primary Sources:**
   - WhatsApp messages (text, voice, images)
   - Handwritten ledger photographs
   - GPS coordinates from farmers
   - Voice recordings in Hindi/Marathi/Tamil

2. **External Sources:**
   - Sentinel-2 satellite imagery (via SageMaker Geospatial)
   - Weather data (optional integration)
   - Market prices (optional integration)

3. **Derived Data:**
   - Structured ledger data (from Textract)
   - NDVI values (from satellite imagery)
   - Credit scores (from transaction history)
   - Conversation context (from Bedrock Agent)

### Data Storage Strategy

#### DynamoDB Single Table Design

**Table Name:** `KisanSetuData`

**Key Structure:**
- **PK (Partition Key):** Entity type + ID (e.g., `FARMER#123`, `FPO#456`)
- **SK (Sort Key):** Related entity or timestamp (e.g., `METADATA`, `TXN#2024-01-15`)

**Access Patterns:**

| Pattern | PK | SK | GSI |
|---------|----|----|-----|
| Get farmer details | `FARMER#{id}` | `METADATA` | - |
| Get farmer transactions | `FARMER#{id}` | `TXN#{timestamp}` | - |
| Get farmer credit score | `FARMER#{id}` | `SCORE#{date}` | - |
| List farmers by FPO | - | - | GSI-1: `fpo_id` |
| Query transactions by date | - | - | GSI-2: `fpo_id` + `timestamp` |
| Get pending sync items | - | - | GSI-3: `sync_status` + `timestamp` |

**Data Retention:**
- Transaction data: 7 years (compliance)
- Satellite imagery: 90 days (cached)
- Voice recordings: 30 days (privacy)
- Conversation history: 180 days

#### S3 Storage Strategy

**Bucket Structure:**
```
kisan-setu-data/
├── ledger-images/
│   ├── {fpo_id}/{farmer_id}/{timestamp}.jpg
├── voice-recordings/
│   ├── {fpo_id}/{farmer_id}/{timestamp}.mp3
├── satellite-imagery/
│   ├── {gps_hash}/{date}.tif
└── exports/
    ├── {fpo_id}/credit-reports/{date}.pdf
```

**Lifecycle Policies:**
- Ledger images: Standard → Glacier after 90 days
- Voice recordings: Delete after 30 days
- Satellite imagery: Delete after 90 days
- Exports: Standard → IA after 30 days

### Data Processing Pipeline

```
Raw Data (WhatsApp/Tablet)
    │
    ▼
Ingestion Layer (API Gateway + Lambda)
    │
    ▼
Validation & Enrichment (Bedrock Agent)
    │
    ▼
AI Processing (Textract/Transcribe/SageMaker)
    │
    ▼
Structuring & Storage (DynamoDB + S3)
    │
    ▼
Analytics & Reporting (QuickSight - optional)
```

### Data Security

1. **Encryption at Rest:**
   - DynamoDB: AWS KMS encryption
   - S3: SSE-KMS encryption
   - Sensitive fields: Application-level encryption

2. **Encryption in Transit:**
   - TLS 1.3 for all API calls
   - HTTPS for WhatsApp webhooks

3. **Access Control:**
   - IAM roles with least privilege
   - Cognito for user authentication
   - Row-level security in DynamoDB (via IAM conditions)

4. **Data Privacy:**
   - PII masking in logs
   - Anonymization for analytics
   - GDPR-compliant data deletion

## Cost Optimization Strategy

### Target: <$50/month per FPO (500+ farmers)

#### Cost Breakdown (Estimated)

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| DynamoDB | 10M reads, 1M writes | $3 |
| S3 | 50GB storage, 100K requests | $2 |
| Lambda | 1M invocations, 512MB | $5 |
| Bedrock | 10K requests, Claude 3.5 | $15 |
| Textract | 1K documents | $10 |
| Transcribe | 500 minutes | $8 |
| SageMaker Geospatial | 100 queries | $5 |
| AppSync | 1M operations | $2 |
| **Total** | | **$50** |

#### Optimization Techniques

1. **Bedrock Knowledge Bases:**
   - Store FPO guidelines, crop data in KB
   - Reduce long-context prompting by 40%
   - Cost savings: ~$6/month

2. **SageMaker Spot Instances:**
   - Use Spot for model training (if needed)
   - Cost savings: up to 90% on compute

3. **DynamoDB On-Demand:**
   - Pay only for actual usage
   - No over-provisioning
   - Auto-scaling for spikes

4. **Request Batching:**
   - Batch similar AI requests
   - Reduce per-request overhead
   - Cost savings: ~15%

5. **Caching Strategy:**
   - Cache satellite imagery (24 hours)
   - Cache Bedrock responses (1 hour)
   - Reduce redundant API calls by 30%

6. **S3 Intelligent-Tiering:**
   - Automatic cost optimization
   - Move infrequently accessed data to cheaper tiers
   - Cost savings: ~20% on storage

## Deployment Architecture

### Multi-Region Strategy

**Primary Region:** ap-south-1 (Mumbai) - Closest to target users in India

**Backup Region:** ap-southeast-1 (Singapore) - Disaster recovery

**Services:**
- Lambda: Deployed in both regions
- DynamoDB: Global Tables for cross-region replication
- S3: Cross-region replication for critical data

### Environment Strategy

```
Development → Staging → Production
    │            │            │
    ▼            ▼            ▼
  Dev AWS    Staging AWS   Prod AWS
  Account      Account      Account
```

**Environments:**
1. **Development:** Single region, minimal resources
2. **Staging:** Production-like, single region
3. **Production:** Multi-region, full monitoring

### CI/CD Pipeline

```
GitHub Repository
    │
    │ 1. Push code
    ▼
GitHub Actions
    │
    │ 2. Run tests (unit + property)
    ▼
Build & Package
    │
    │ 3. Create Lambda deployment packages
    ▼
AWS CodePipeline
    │
    │ 4. Deploy to Dev
    ▼
Automated Tests
    │
    │ 5. Integration tests pass?
    ▼
Manual Approval
    │
    │ 6. Deploy to Staging
    ▼
Smoke Tests
    │
    │ 7. All checks pass?
    ▼
Manual Approval
    │
    │ 8. Deploy to Production
    ▼
Production Monitoring
```

### Infrastructure as Code

**Tool:** AWS CDK (Python)

**Stack Structure:**
```
kisan-setu-cdk/
├── stacks/
│   ├── networking_stack.py      # VPC, subnets
│   ├── data_stack.py             # DynamoDB, S3
│   ├── compute_stack.py          # Lambda functions
│   ├── ai_stack.py               # Bedrock, Textract configs
│   ├── api_stack.py              # API Gateway, AppSync
│   └── monitoring_stack.py       # CloudWatch, X-Ray
├── app.py                        # CDK app entry point
└── cdk.json                      # CDK configuration
```

## Scalability & Performance

### Scalability Targets

| Metric | Target | Strategy |
|--------|--------|----------|
| Concurrent users | 10,000 | Lambda auto-scaling |
| Requests/second | 1,000 | API Gateway throttling |
| Document processing | 100/min | Textract batch processing |
| Voice transcription | 50/min | Transcribe concurrent jobs |
| Database throughput | 10K RCU/WCU | DynamoDB on-demand |

### Performance Targets

| Operation | Target Latency | Optimization |
|-----------|----------------|--------------|
| Voice transcription | <5 seconds | Streaming transcription |
| Document extraction | <10 seconds | Async processing |
| Credit score calc | <200ms | Pre-computed scores |
| Satellite query | <15 seconds | Cached imagery |
| WhatsApp response | <3 seconds | Async workflows |

### Auto-Scaling Configuration

**Lambda:**
- Concurrent executions: 1000 (reserved)
- Provisioned concurrency: 10 (for critical functions)
- Memory: 512MB - 3GB (based on function)

**DynamoDB:**
- On-demand mode (auto-scaling)
- Burst capacity: 3000 RCU/WCU
- Global tables for multi-region

**API Gateway:**
- Throttle limit: 1000 req/sec
- Burst limit: 2000 req/sec
- Usage plans for different user tiers

## Security Architecture

### Defense in Depth

```
Layer 1: Network Security
    │ - VPC with private subnets
    │ - Security groups
    │ - NACLs
    ▼
Layer 2: API Security
    │ - API Gateway authentication
    │ - Rate limiting
    │ - Input validation
    ▼
Layer 3: Application Security
    │ - IAM roles (least privilege)
    │ - Lambda execution roles
    │ - Secrets Manager for credentials
    ▼
Layer 4: Data Security
    │ - KMS encryption
    │ - Field-level encryption
    │ - Audit logging
    ▼
Layer 5: Monitoring & Response
    │ - CloudWatch alarms
    │ - GuardDuty threat detection
    │ - Security Hub compliance
```

### Authentication & Authorization

**User Authentication:**
- Amazon Cognito User Pools
- Phone number verification (OTP)
- JWT tokens for API access

**Service Authentication:**
- IAM roles for Lambda functions
- Service-to-service via IAM
- API keys for WhatsApp webhook

**Authorization Model:**
```
Roles:
├── Farmer
│   ├── View own data
│   ├── Submit transactions
│   └── Query satellite data
├── FPO Manager
│   ├── View all farmer data in FPO
│   ├── Generate reports
│   └── Manage farmers
└── Bank Officer
    ├── View credit scores
    └── Generate credit reports
```

### Compliance

**Data Residency:**
- All data stored in India (ap-south-1)
- No cross-border data transfer

**Regulatory Compliance:**
- GDPR-compliant data handling
- Right to deletion
- Data portability

**Audit Trail:**
- All API calls logged to CloudWatch
- DynamoDB streams for change tracking
- S3 access logs enabled

## Monitoring & Observability

### Monitoring Stack

```
Application Logs → CloudWatch Logs
    │
    ▼
Metrics → CloudWatch Metrics
    │
    ▼
Traces → AWS X-Ray
    │
    ▼
Dashboards → CloudWatch Dashboards
    │
    ▼
Alerts → SNS → Email/SMS
```

### Key Metrics

**System Health:**
- Lambda error rate
- API Gateway 4xx/5xx errors
- DynamoDB throttling events
- Bedrock API latency

**Business Metrics:**
- Documents processed per day
- Credit scores calculated
- Active farmers
- Transaction volume

**Cost Metrics:**
- Daily AWS spend by service
- Cost per farmer
- Cost per transaction

### Alerting Strategy

**Critical Alerts (Immediate):**
- Lambda error rate >5%
- API Gateway 5xx errors >1%
- DynamoDB throttling
- Bedrock API failures

**Warning Alerts (15 min delay):**
- Lambda duration >80% of timeout
- S3 storage >80% of budget
- Cost anomaly detection

**Info Alerts (Daily digest):**
- Daily transaction summary
- New farmer registrations
- Credit score changes

### Logging Strategy

**Log Levels:**
- ERROR: System failures, exceptions
- WARN: Degraded performance, retries
- INFO: Business events, API calls
- DEBUG: Detailed execution flow (dev only)

**Log Retention:**
- ERROR logs: 90 days
- WARN logs: 30 days
- INFO logs: 7 days
- DEBUG logs: 1 day

**Structured Logging:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "document-processor",
  "farmer_id": "FARMER#123",
  "fpo_id": "FPO#456",
  "event": "ledger_extracted",
  "duration_ms": 8500,
  "confidence": 0.92,
  "fields_extracted": 6
}
```

## Disaster Recovery

### RTO & RPO Targets

| Scenario | RTO | RPO | Strategy |
|----------|-----|-----|----------|
| Lambda failure | 0 min | 0 min | Auto-retry, multi-AZ |
| DynamoDB failure | 5 min | 0 min | Point-in-time recovery |
| Region failure | 30 min | 5 min | Global Tables, failover |
| Data corruption | 1 hour | 1 hour | Backups, audit logs |

### Backup Strategy

**DynamoDB:**
- Point-in-time recovery (enabled)
- Daily backups (retained 35 days)
- Cross-region replication (Global Tables)

**S3:**
- Versioning enabled
- Cross-region replication
- Lifecycle policies for archival

**Lambda:**
- Code stored in Git
- Deployment packages in S3
- Infrastructure as Code (CDK)

### Failover Procedure

1. **Detection:** CloudWatch alarm triggers
2. **Assessment:** On-call engineer evaluates
3. **Decision:** Failover to backup region?
4. **Execution:** Update Route53 DNS
5. **Verification:** Smoke tests in backup region
6. **Communication:** Notify users via WhatsApp
7. **Recovery:** Fix primary region
8. **Failback:** Return to primary region

## 24-Hour Implementation Goal

### Milestone: WhatsApp Ledger Digitization MVP

**Objective:** Deploy a working WhatsApp bot that digitizes handwritten Hindi ledgers.

**Components to Deploy:**

1. **WhatsApp Integration:**
   - Set up WhatsApp Business API account
   - Configure webhook endpoint
   - Test message sending/receiving

2. **API Gateway + Lambda:**
   - Create API Gateway REST API
   - Deploy message router Lambda
   - Deploy document processor Lambda

3. **Amazon Textract:**
   - Configure Textract Queries API
   - Define extraction questions
   - Test with sample ledger images

4. **DynamoDB:**
   - Create single table
   - Define access patterns
   - Test CRUD operations

5. **Bedrock Agent:**
   - Configure Claude 3.5 Sonnet
   - Define tool schema for Textract
   - Test orchestration

**Success Criteria:**
- ✅ Receive photo via WhatsApp
- ✅ Extract quantity, moisture, price from Hindi ledger
- ✅ Store structured data in DynamoDB
- ✅ Send JSON response via WhatsApp
- ✅ End-to-end latency <15 seconds

**Deployment Steps:**

```bash
# 1. Set up AWS credentials
aws configure

# 2. Deploy infrastructure
cd kisan-setu-cdk
cdk deploy KisanSetuMVPStack

# 3. Configure WhatsApp webhook
curl -X POST https://api.whatsapp.com/webhook \
  -d "url=https://{api-gateway-url}/webhook"

# 4. Test with sample image
# Send photo via WhatsApp to test number

# 5. Verify in DynamoDB
aws dynamodb scan --table-name KisanSetuData
```

**Timeline:**
- Hours 0-4: Infrastructure setup (CDK, DynamoDB, S3)
- Hours 4-8: Lambda functions (router, processor)
- Hours 8-12: Textract integration and testing
- Hours 12-16: Bedrock Agent configuration
- Hours 16-20: WhatsApp integration
- Hours 20-24: End-to-end testing and refinement

## Future Enhancements

### Phase 2 (Months 2-3)
- Voice interface (Transcribe + Polly)
- Satellite yield prediction
- Offline tablet mode

### Phase 3 (Months 4-6)
- Credit scoring engine
- Multi-FPO support
- Analytics dashboard

### Phase 4 (Months 7-12)
- Market price integration
- Weather alerts
- Automated procurement recommendations
- Mobile app (optional)

## Conclusion

Kisan-Setu's architecture is designed for:
- **Simplicity:** Serverless, managed services
- **Scalability:** Auto-scaling, multi-region
- **Cost-efficiency:** <$50/month per FPO
- **Reliability:** 99.9% uptime target
- **Security:** Defense in depth, compliance

The 24-hour MVP goal demonstrates the core value proposition: transforming unstructured rural data into bankable digital records with zero typing required.
