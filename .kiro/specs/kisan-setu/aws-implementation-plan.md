> **Note:** This is a historical spec document representing the original design intent. The implementation evolved beyond this spec — notably using a 5-model APAC inference profile fallback chain (Nova Pro → Nova Lite → Claude 3.7 Sonnet → Claude 3.5 Sonnet v2 → Claude 3 Haiku), multimodal LLM-first document processing with Textract fallback, and a live S3-hosted FPO admin dashboard. See `kisan-setu-mvp/README.md` for current architecture.

# AWS Implementation Plan - Kisan-Setu

## Data Strategy on AWS

### Data Sources

#### 1. Primary Data Sources
| Source | Type | Volume (per FPO/month) | AWS Service |
|--------|------|------------------------|-------------|
| WhatsApp messages | Text | ~5,000 messages | API Gateway → Lambda |
| Voice recordings | Audio (MP3) | ~500 files, ~2GB | S3 Standard |
| Ledger photos | Images (JPG) | ~1,000 images, ~500MB | S3 Standard |
| GPS coordinates | Structured | ~1,000 locations | DynamoDB |
| Satellite imagery | GeoTIFF | ~100 queries, ~5GB | S3 + SageMaker |

#### 2. Derived Data Sources
| Data Type | Source | Storage | Processing |
|-----------|--------|---------|------------|
| Transcribed text | Voice recordings | DynamoDB | Amazon Transcribe |
| Structured ledger data | Photos | DynamoDB | Amazon Textract |
| NDVI values | Satellite imagery | DynamoDB | SageMaker Geospatial |
| Credit scores | Transaction history | DynamoDB | Lambda (custom logic) |
| Conversation context | Chat history | DynamoDB | Bedrock Agent |

### Data Storage Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA INGESTION                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  WhatsApp → API Gateway → Lambda → Route to storage         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
┌───────────────────┐                 ┌───────────────────┐
│   STRUCTURED      │                 │   UNSTRUCTURED    │
│   DATA STORAGE    │                 │   DATA STORAGE    │
├───────────────────┤                 ├───────────────────┤
│                   │                 │                   │
│  DynamoDB         │                 │  Amazon S3        │
│  ─────────        │                 │  ─────────        │
│  • Farmers        │                 │  • Images         │
│  • Transactions   │                 │  • Audio          │
│  • Credit Scores  │                 │  • Satellite      │
│  • Conversations  │                 │  • Exports        │
│  • NDVI Results   │                 │                   │
│                   │                 │  Buckets:         │
│  Single Table:    │                 │  • kisan-raw      │
│  KisanSetuData    │                 │  • kisan-processed│
│                   │                 │  • kisan-archive  │
└───────────────────┘                 └───────────────────┘
```

### Data Processing Pipeline

```
Raw Data Ingestion
    │
    ▼
┌─────────────────────────────────────┐
│  Lambda: Data Validator             │
│  • Check format                     │
│  • Validate schema                  │
│  • Enrich with metadata             │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  AI Processing Layer                │
│  ┌─────────────────────────────┐   │
│  │ Textract → Extract ledger   │   │
│  │ Transcribe → Convert voice  │   │
│  │ SageMaker → Analyze satellite│   │
│  │ Bedrock → Structure data    │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  Lambda: Data Transformer           │
│  • Convert to standard format       │
│  • Calculate derived metrics        │
│  • Update credit scores             │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  Storage Layer                      │
│  • DynamoDB (structured)            │
│  • S3 (unstructured)                │
│  • Audit logs (CloudWatch)          │
└─────────────────────────────────────┘
```

### DynamoDB Single Table Design

**Table Name:** `KisanSetuData`

**Capacity Mode:** On-Demand (pay per request)

**Key Schema:**
```
PK (Partition Key): String
SK (Sort Key): String
```

**Access Patterns & Keys:**

| Access Pattern | PK | SK | Example |
|----------------|----|----|---------|
| Get farmer profile | `FARMER#{id}` | `METADATA` | `FARMER#123`, `METADATA` |
| Get farmer transactions | `FARMER#{id}` | `TXN#{timestamp}` | `FARMER#123`, `TXN#2024-01-15T10:30:00Z` |
| Get farmer credit score | `FARMER#{id}` | `SCORE#{date}` | `FARMER#123`, `SCORE#2024-01-15` |
| Get FPO details | `FPO#{id}` | `METADATA` | `FPO#456`, `METADATA` |
| Get field satellite data | `FIELD#{gps_hash}` | `NDVI#{timestamp}` | `FIELD#abc123`, `NDVI#2024-01-15` |
| Get conversation history | `CONVERSATION#{farmer_id}` | `MSG#{timestamp}` | `CONVERSATION#123`, `MSG#2024-01-15T10:30:00Z` |
| Get pending sync items | `SYNC#{device_id}` | `PENDING#{timestamp}` | `SYNC#tablet-001`, `PENDING#2024-01-15T10:30:00Z` |

**Global Secondary Indexes:**

```
GSI-1: Query farmers by FPO
  PK: fpo_id
  SK: farmer_id
  Projection: ALL

GSI-2: Query transactions by date range
  PK: fpo_id
  SK: timestamp
  Projection: ALL

GSI-3: Query pending sync items
  PK: sync_status
  SK: timestamp
  Projection: ALL
```

**Sample Items:**

```json
// Farmer Profile
{
  "PK": "FARMER#123",
  "SK": "METADATA",
  "farmer_name": "Ramesh Kumar",
  "phone": "+919876543210",
  "fpo_id": "FPO#456",
  "gps_coords": [19.0760, 72.8777],
  "preferred_language": "hi-IN",
  "join_date": "2023-01-15",
  "created_at": "2023-01-15T10:00:00Z"
}

// Transaction
{
  "PK": "FARMER#123",
  "SK": "TXN#2024-01-15T10:30:00Z",
  "transaction_id": "TXN#abc123",
  "fpo_id": "FPO#456",
  "quantity": 500.0,
  "crop_type": "onion",
  "quality_grade": "A",
  "moisture": 13.5,
  "price": 25.0,
  "ledger_image_url": "s3://kisan-raw/ledgers/123/2024-01-15.jpg",
  "sync_status": "synced"
}

// Credit Score
{
  "PK": "FARMER#123",
  "SK": "SCORE#2024-01-15",
  "total_score": 87.10,
  "supply_consistency": 27.41,
  "quality_metrics": 22.59,
  "transaction_history": 15.88,
  "financial_behavior": 12.00,
  "operational_transparency": 9.22,
  "rating": "Good",
  "previous_score": 75.30,
  "score_change": 11.80
}
```

### S3 Bucket Strategy

**Bucket Structure:**

```
kisan-setu-raw/
├── ledger-images/
│   ├── {fpo_id}/
│   │   ├── {farmer_id}/
│   │   │   ├── 2024-01-15T10-30-00Z.jpg
│   │   │   ├── 2024-01-16T11-20-00Z.jpg
│   │   │   └── ...
├── voice-recordings/
│   ├── {fpo_id}/
│   │   ├── {farmer_id}/
│   │   │   ├── 2024-01-15T10-30-00Z.mp3
│   │   │   └── ...
└── satellite-imagery/
    ├── {gps_hash}/
    │   ├── 2024-01-15.tif
    │   └── ...

kisan-setu-processed/
├── extracted-data/
│   ├── {fpo_id}/
│   │   ├── {farmer_id}/
│   │   │   ├── 2024-01-15T10-30-00Z.json
│   │   │   └── ...
├── transcriptions/
│   ├── {fpo_id}/
│   │   ├── {farmer_id}/
│   │   │   ├── 2024-01-15T10-30-00Z.txt
│   │   │   └── ...
└── reports/
    ├── {fpo_id}/
    │   ├── credit-reports/
    │   │   ├── 2024-01-monthly.pdf
    │   │   └── ...
    │   └── transaction-summaries/
    │       ├── 2024-01-monthly.xlsx
    │       └── ...

kisan-setu-archive/
└── (Lifecycle-managed archived data)
```

**Lifecycle Policies:**

```json
{
  "Rules": [
    {
      "Id": "ArchiveLedgerImages",
      "Status": "Enabled",
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ],
      "Filter": {
        "Prefix": "ledger-images/"
      }
    },
    {
      "Id": "DeleteVoiceRecordings",
      "Status": "Enabled",
      "Expiration": {
        "Days": 30
      },
      "Filter": {
        "Prefix": "voice-recordings/"
      }
    },
    {
      "Id": "ArchiveSatelliteImagery",
      "Status": "Enabled",
      "Expiration": {
        "Days": 90
      },
      "Filter": {
        "Prefix": "satellite-imagery/"
      }
    }
  ]
}
```

### AWS AppSync for Offline Sync

**GraphQL Schema:**

```graphql
type Farmer {
  id: ID!
  name: String!
  phone: String!
  fpoId: ID!
  gpsCoords: [Float!]!
  preferredLanguage: String!
  transactions: [Transaction!]!
  creditScore: CreditScore
}

type Transaction {
  id: ID!
  farmerId: ID!
  fpoId: ID!
  quantity: Float!
  cropType: String!
  qualityGrade: String!
  moisture: Float
  price: Float!
  timestamp: AWSDateTime!
  syncStatus: SyncStatus!
}

enum SyncStatus {
  SYNCED
  PENDING
  CONFLICT
}

type CreditScore {
  totalScore: Float!
  supplyConsistency: Float!
  qualityMetrics: Float!
  transactionHistory: Float!
  financialBehavior: Float!
  operationalTransparency: Float!
  rating: String!
  calculationDate: AWSDateTime!
}

type Mutation {
  createTransaction(input: CreateTransactionInput!): Transaction!
  syncOfflineTransactions(transactions: [CreateTransactionInput!]!): SyncResult!
}

type SyncResult {
  successCount: Int!
  failureCount: Int!
  conflicts: [Transaction!]!
}

type Query {
  getFarmer(id: ID!): Farmer
  listTransactions(farmerId: ID!, limit: Int, nextToken: String): TransactionConnection
  getCreditScore(farmerId: ID!): CreditScore
}
```

**Offline Configuration:**

```javascript
// AppSync Client Configuration
const client = new AWSAppSyncClient({
  url: APPSYNC_ENDPOINT,
  region: 'ap-south-1',
  auth: {
    type: AUTH_TYPE.AMAZON_COGNITO_USER_POOLS,
    jwtToken: async () => token,
  },
  offlineConfig: {
    storage: AsyncStorage,
    keyPrefix: 'kisan-setu',
  },
  conflictResolver: ({ mutation, mutationName, variables, data, retries }) => {
    // Last-write-wins strategy
    return 'DISCARD';
  },
});
```

### Data Processing Services

#### Amazon Textract Configuration

**API:** Textract Queries (not just standard OCR)

**Why Queries?** Allows asking natural language questions to documents, essential for non-standard rural formats.

**Sample Query Configuration:**

```python
import boto3

textract = boto3.client('textract', region_name='ap-south-1')

# Queries for ledger extraction
queries = [
    {"Text": "What is the quantity?", "Alias": "QUANTITY"},
    {"Text": "What is the moisture level?", "Alias": "MOISTURE"},
    {"Text": "What is the price?", "Alias": "PRICE"},
    {"Text": "What is the date?", "Alias": "DATE"},
    {"Text": "What is the farmer name?", "Alias": "FARMER_NAME"},
    {"Text": "What is the crop type?", "Alias": "CROP_TYPE"}
]

response = textract.analyze_document(
    Document={'S3Object': {'Bucket': 'kisan-setu-raw', 'Name': 'ledger.jpg'}},
    FeatureTypes=['QUERIES'],
    QueriesConfig={'Queries': queries}
)

# Extract answers with confidence scores
for block in response['Blocks']:
    if block['BlockType'] == 'QUERY_RESULT':
        print(f"{block['Query']['Alias']}: {block['Text']} (confidence: {block['Confidence']})")
```

#### Amazon Transcribe Configuration

**Languages:** Hindi (hi-IN), Marathi (mr-IN), Tamil (ta-IN)

**Configuration:**

```python
import boto3

transcribe = boto3.client('transcribe', region_name='ap-south-1')

response = transcribe.start_transcription_job(
    TranscriptionJobName='farmer-voice-123',
    Media={'MediaFileUri': 's3://kisan-setu-raw/voice-recordings/123.mp3'},
    MediaFormat='mp3',
    LanguageCode='hi-IN',  # Auto-detect or specify
    Settings={
        'ShowSpeakerLabels': False,
        'MaxSpeakerLabels': 1,
        'ChannelIdentification': False
    },
    OutputBucketName='kisan-setu-processed'
)
```

#### Amazon SageMaker Geospatial

**Data Source:** Sentinel-2 satellite imagery

**NDVI Calculation:**

```python
import boto3
import sagemaker_geospatial_map

geospatial = boto3.client('sagemaker-geospatial', region_name='ap-south-1')

# Query satellite imagery
response = geospatial.search_raster_data_collection(
    Arn='arn:aws:sagemaker-geospatial:ap-south-1:*:raster-data-collection/sentinel-2',
    AreaOfInterest={
        'AreaOfInterestGeometry': {
            'PolygonGeometry': {
                'Coordinates': [[[lon, lat], [lon+0.01, lat], [lon+0.01, lat+0.01], [lon, lat+0.01], [lon, lat]]]
            }
        }
    },
    TimeRangeFilter={
        'StartTime': '2024-01-01T00:00:00Z',
        'EndTime': '2024-01-15T23:59:59Z'
    }
)

# Calculate NDVI
ndvi_job = geospatial.start_earth_observation_job(
    Name='ndvi-calculation-123',
    InputConfig={
        'RasterDataCollectionQuery': {
            'RasterDataCollectionArn': response['Items'][0]['Arn'],
            'AreaOfInterest': {...},
            'TimeRangeFilter': {...}
        }
    },
    JobConfig={
        'BandMathConfig': {
            'CustomIndices': {
                'Operations': [
                    {
                        'Equation': '(B8 - B4) / (B8 + B4)',  # NDVI formula
                        'Name': 'NDVI',
                        'OutputType': 'FLOAT32'
                    }
                ]
            }
        }
    }
)
```

#### AWS Bedrock Agent Configuration

**Model:** Claude 3.5 Sonnet v2 (Recommended)

**Model Selection:**
- **Claude 3.5 Sonnet v2** (anthropic.claude-3-5-sonnet-20241022-v2:0) - Recommended for best balance
- **Claude 3 Opus** (anthropic.claude-3-opus-20240229-v1:0) - Use if accuracy > cost
- **Claude 3 Haiku** (anthropic.claude-3-haiku-20240307-v1:0) - Use if cost is critical

**Note:** There is no Claude 4.6 yet. Claude 3.5 Sonnet v2 is the latest model available on AWS Bedrock.

**Agent Configuration:**
agent = bedrock_agent.create_agent(
    agentName='kisan-setu-agent',
    foundationModel='anthropic.claude-sonnet-4-6',  # Latest Claude Sonnet 4.6
    instruction='''You are an AI assistant for Kisan-Setu, an FPO operating system.
bedrock_agent = boto3.client('bedrock-agent', region_name='ap-south-1')

# Create agent with Claude 3.5 Sonnet v2
agent = bedrock_agent.create_agent(
    agentName='kisan-setu-agent',
    foundationModel='anthropic.claude-3-5-sonnet-20241022-v2:0',  # Latest model
    instruction='''You are an AI assistant for Kisan-Setu, an FPO operating system.
    You help farmers and FPO managers with:
    - Digitizing handwritten ledgers
    - Predicting crop yields using satellite data
    - Calculating credit scores
    - Answering questions about farming practices
    
    Always respond in the user's preferred language (Hindi, Marathi, or Tamil).
    Be concise and practical in your responses.''',
    agentResourceRoleArn='arn:aws:iam::ACCOUNT:role/KisanSetuAgentRole'
)

# Add action groups (tools)
bedrock_agent.create_agent_action_group(
    agentId=agent['agent']['agentId'],
    agentVersion='DRAFT',
    actionGroupName='document-processing',
    actionGroupExecutor={
        'lambda': 'arn:aws:lambda:ap-south-1:ACCOUNT:function:textract-processor'
    },
    apiSchema={
        'payload': json.dumps({
            'openapi': '3.0.0',
            'info': {'title': 'Document Processing API', 'version': '1.0.0'},
            'paths': {
                '/extract-ledger': {
                    'post': {
                        'description': 'Extract data from handwritten ledger image',
                        'parameters': [
                            {'name': 'image_url', 'in': 'query', 'required': True, 'schema': {'type': 'string'}},
                            {'name': 'language', 'in': 'query', 'required': True, 'schema': {'type': 'string'}}
                        ]
                    }
                }
            }
        })
    }
)
```

### Cost Optimization Strategies

#### 1. Bedrock Knowledge Bases (40% cost reduction)

**Setup:**
        'type': 'VECTOR',
        'vectorKnowledgeBaseConfiguration': {
            'embeddingModelArn': 'arn:aws:bedrock:ap-south-1::foundation-model/amazon.titan-embed-text-v2:0'
        }ock_agent.create_knowledge_base(
    name='fpo-guidelines-kb',
    roleArn='arn:aws:iam::ACCOUNT:role/BedrockKBRole',
    knowledgeBaseConfiguration={
        'type': 'VECTOR',
        'vectorKnowledgeBaseConfiguration': {
            'embeddingModelArn': 'arn:aws:bedrock:ap-south-1::foundation-model/amazon.titan-embed-text-v1'
        }
    },
    storageConfiguration={
        'type': 'OPENSEARCH_SERVERLESS',
        'opensearchServerlessConfiguration': {
            'collectionArn': 'arn:aws:aoss:ap-south-1:ACCOUNT:collection/kb-collection',
            'vectorIndexName': 'fpo-guidelines-index',
            'fieldMapping': {
                'vectorField': 'embedding',
                'textField': 'text',
                'metadataField': 'metadata'
            }
        }
    }
)

# Add data source (S3 bucket with FPO documents)
bedrock_agent.create_data_source(
    knowledgeBaseId=kb['knowledgeBase']['knowledgeBaseId'],
    name='fpo-documents',
    dataSourceConfiguration={
        'type': 'S3',
        's3Configuration': {
            'bucketArn': 'arn:aws:s3:::kisan-setu-knowledge'
        }
    }
)
```

**Usage in Agent:**
```python
# Query knowledge base instead of long-context prompting
response = bedrock_agent_runtime.retrieve_and_generate(
    input={'text': 'What are the moisture requirements for onions?'},
    retrieveAndGenerateConfiguration={
        'type': 'KNOWLEDGE_BASE',
        'knowledgeBaseConfiguration': {
            'knowledgeBaseId': kb_id,
            'modelArn': 'anthropic.claude-3-5-sonnet-20241022-v2:0'
        }
    }
)
```

#### 2. Request Batching

```python
# Batch multiple Textract requests
def batch_process_ledgers(image_urls, batch_size=10):
    results = []
    for i in range(0, len(image_urls), batch_size):
        batch = image_urls[i:i+batch_size]
        # Process batch concurrently
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            futures = [executor.submit(process_ledger, url) for url in batch]
            results.extend([f.result() for f in futures])
    return results
```

#### 3. Caching Strategy

```python
# Cache satellite imagery results
import redis

cache = redis.Redis(host='elasticache-endpoint', port=6379)

def get_satellite_data(gps_coords, date):
    cache_key = f"satellite:{gps_coords}:{date}"
    
    # Check cache first
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Fetch from SageMaker if not cached
    data = fetch_from_sagemaker(gps_coords, date)
    
    # Cache for 24 hours
    cache.setex(cache_key, 86400, json.dumps(data))
    
    return data
```

#### 4. DynamoDB On-Demand Pricing

```python
# No need to provision capacity
# Pay only for actual reads/writes

# Example: Create table with on-demand billing
dynamodb = boto3.client('dynamodb', region_name='ap-south-1')

table = dynamodb.create_table(
    TableName='KisanSetuData',
    KeySchema=[
        {'AttributeName': 'PK', 'KeyType': 'HASH'},
        {'AttributeName': 'SK', 'KeyType': 'RANGE'}
    ],
    AttributeDefinitions=[
        {'AttributeName': 'PK', 'AttributeType': 'S'},
        {'AttributeName': 'SK', 'AttributeType': 'S'}
    ],
    BillingMode='PAY_PER_REQUEST'  # On-demand
)
```

## 24-Hour Implementation Goal

### Objective
Deploy a working WhatsApp bot that can receive a photo of a handwritten Hindi ledger, extract structured data using Amazon Textract Queries, store it in DynamoDB, and send back a formatted JSON response.

### Success Criteria
✅ Receive photo via WhatsApp  
✅ Extract quantity, moisture, price from Hindi ledger  
✅ Store structured data in DynamoDB  
✅ Send JSON response via WhatsApp  
✅ End-to-end latency <15 seconds  

### Hour-by-Hour Implementation Plan

#### Hours 0-4: Infrastructure Setup

**Tasks:**
1. Set up AWS account and configure credentials
2. Create S3 buckets (raw, processed)
3. Create DynamoDB table
4. Set up IAM roles and policies
5. Initialize CDK project

**Commands:**

```bash
# 1. Configure AWS CLI
aws configure
# Enter: Access Key, Secret Key, Region (ap-south-1), Output (json)

# 2. Create S3 buckets
aws s3 mb s3://kisan-setu-raw-${ACCOUNT_ID} --region ap-south-1
aws s3 mb s3://kisan-setu-processed-${ACCOUNT_ID} --region ap-south-1

# 3. Create DynamoDB table
aws dynamodb create-table \
  --table-name KisanSetuData \
  --attribute-definitions \
    AttributeName=PK,AttributeType=S \
    AttributeName=SK,AttributeType=S \
  --key-schema \
    AttributeName=PK,KeyType=HASH \
    AttributeName=SK,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region ap-south-1

# 4. Initialize CDK project
mkdir kisan-setu-mvp && cd kisan-setu-mvp
cdk init app --language python
source .venv/bin/activate
pip install aws-cdk-lib constructs boto3
```

**CDK Stack (infrastructure.py):**

```python
from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_iam as iam,
    Duration
)
from constructs import Construct

class KisanSetuMVPStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # IAM role for Lambda
        lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonTextractFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonDynamoDBFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess")
            ]
        )
        
        # Message Router Lambda
        router_lambda = lambda_.Function(
            self, "MessageRouter",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="router.handler",
            code=lambda_.Code.from_asset("lambda/router"),
            role=lambda_role,
            timeout=Duration.seconds(30),
            environment={
                "DYNAMODB_TABLE": "KisanSetuData",
                "S3_BUCKET": f"kisan-setu-raw-{self.account}"
            }
        )
        
        # Document Processor Lambda
        processor_lambda = lambda_.Function(
            self, "DocumentProcessor",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="processor.handler",
            code=lambda_.Code.from_asset("lambda/processor"),
            role=lambda_role,
            timeout=Duration.seconds(60),
            memory_size=1024,
            environment={
                "DYNAMODB_TABLE": "KisanSetuData",
                "S3_BUCKET": f"kisan-setu-raw-{self.account}"
            }
        )
        
        # API Gateway
        api = apigw.RestApi(
            self, "KisanSetuAPI",
            rest_api_name="Kisan-Setu WhatsApp Webhook",
            description="Webhook for WhatsApp Business API"
        )
        
        # /webhook endpoint
        webhook = api.root.add_resource("webhook")
        webhook.add_method("POST", apigw.LambdaIntegration(router_lambda))
```

#### Hours 4-8: Lambda Functions

**Task:** Implement message router and document processor Lambda functions

**lambda/router/router.py:**

```python
import json
import boto3
import os
from datetime import datetime

s3 = boto3.client('s3')
lambda_client = boto3.client('lambda')

S3_BUCKET = os.environ['S3_BUCKET']

def handler(event, context):
    """Route WhatsApp messages to appropriate processors"""
    
    try:
        # Parse WhatsApp webhook payload
        body = json.loads(event['body'])
        
        # Extract message details
        message = body['entry'][0]['changes'][0]['value']['messages'][0]
        message_type = message['type']
        sender = message['from']
        
        if message_type == 'image':
            # Download image from WhatsApp
            image_id = message['image']['id']
            image_url = download_whatsapp_media(image_id)
            
            # Store in S3
            s3_key = f"ledger-images/{sender}/{datetime.utcnow().isoformat()}.jpg"
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=image_url
            )
            
            # Invoke document processor
            lambda_client.invoke(
                FunctionName='DocumentProcessor',
                InvocationType='Event',
                Payload=json.dumps({
                    'sender': sender,
                    's3_bucket': S3_BUCKET,
                    's3_key': s3_key
                })
            )
            
            return {
                'statusCode': 200,
                'body': json.dumps({'status': 'processing'})
            }
        
        elif message_type == 'text':
            # Handle text messages (future)
            return {
                'statusCode': 200,
                'body': json.dumps({'status': 'text_received'})
            }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def download_whatsapp_media(media_id):
    """Download media from WhatsApp Business API"""
    # Download media from Meta WhatsApp Business API
    pass
```

**lambda/processor/processor.py:**

```python
import json
import boto3
import os
from datetime import datetime

textract = boto3.client('textract')
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']
table = dynamodb.Table(DYNAMODB_TABLE)

def handler(event, context):
    """Process ledger image with Textract and store in DynamoDB"""
    
    try:
        sender = event['sender']
        s3_bucket = event['s3_bucket']
        s3_key = event['s3_key']
        
        # Call Textract Queries
        response = textract.analyze_document(
            Document={
                'S3Object': {
                    'Bucket': s3_bucket,
                    'Name': s3_key
                }
            },
            FeatureTypes=['QUERIES'],
            QueriesConfig={
                'Queries': [
                    {'Text': 'What is the quantity?', 'Alias': 'QUANTITY'},
                    {'Text': 'What is the moisture level?', 'Alias': 'MOISTURE'},
                    {'Text': 'What is the price?', 'Alias': 'PRICE'},
                    {'Text': 'What is the date?', 'Alias': 'DATE'},
                    {'Text': 'What is the farmer name?', 'Alias': 'FARMER_NAME'},
                    {'Text': 'What is the crop type?', 'Alias': 'CROP_TYPE'}
                ]
            }
        )
        
        # Extract query results
        extracted_data = {}
        for block in response['Blocks']:
            if block['BlockType'] == 'QUERY_RESULT':
                alias = block['Query']['Alias']
                text = block.get('Text', '')
                confidence = block.get('Confidence', 0)
                extracted_data[alias] = {
                    'value': text,
                    'confidence': confidence
                }
        
        # Structure data
        transaction_id = f"TXN#{datetime.utcnow().isoformat()}"
        farmer_id = f"FARMER#{sender}"
        
        structured_data = {
            'PK': farmer_id,
            'SK': transaction_id,
            'transaction_id': transaction_id,
            'quantity': float(extracted_data.get('QUANTITY', {}).get('value', 0)),
            'moisture': float(extracted_data.get('MOISTURE', {}).get('value', 0)),
            'price': float(extracted_data.get('PRICE', {}).get('value', 0)),
            'date': extracted_data.get('DATE', {}).get('value', ''),
            'farmer_name': extracted_data.get('FARMER_NAME', {}).get('value', ''),
            'crop_type': extracted_data.get('CROP_TYPE', {}).get('value', ''),
            'ledger_image_url': f"s3://{s3_bucket}/{s3_key}",
            'confidence_scores': {k: v['confidence'] for k, v in extracted_data.items()},
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Store in DynamoDB
        table.put_item(Item=structured_data)
        
        # Send response via WhatsApp
        send_whatsapp_message(
            sender,
            f"✅ Ledger digitized successfully!\n\n"
            f"📊 Data extracted:\n"
            f"Quantity: {structured_data['quantity']} kg\n"
            f"Moisture: {structured_data['moisture']}%\n"
            f"Price: ₹{structured_data['price']}\n"
            f"Crop: {structured_data['crop_type']}\n\n"
            f"JSON: {json.dumps(structured_data, indent=2)}"
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps(structured_data)
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        send_whatsapp_message(
            sender,
            f"❌ Error processing ledger: {str(e)}"
        )
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def send_whatsapp_message(phone_number, message):
    """Send message via WhatsApp Business API"""
    # Implementation depends on WhatsApp provider
    pass
```

#### Hours 8-12: Textract Integration & Testing

**Tasks:**
1. Test Textract with sample Hindi ledger images
2. Refine query prompts for better extraction
3. Handle edge cases (poor image quality, missing fields)

**Test Script (test_textract.py):**

```python
import boto3
import json

textract = boto3.client('textract', region_name='ap-south-1')

# Upload test image
s3 = boto3.client('s3')
with open('sample_hindi_ledger.jpg', 'rb') as f:
    s3.put_object(
        Bucket='kisan-setu-raw-ACCOUNT',
        Key='test/sample_ledger.jpg',
        Body=f
    )

# Test Textract
response = textract.analyze_document(
    Document={
        'S3Object': {
            'Bucket': 'kisan-setu-raw-ACCOUNT',
            'Name': 'test/sample_ledger.jpg'
        }
    },
    FeatureTypes=['QUERIES'],
    QueriesConfig={
        'Queries': [
            {'Text': 'What is the quantity?', 'Alias': 'QUANTITY'},
            {'Text': 'What is the moisture level?', 'Alias': 'MOISTURE'},
            {'Text': 'What is the price?', 'Alias': 'PRICE'}
        ]
    }
)

# Print results
for block in response['Blocks']:
    if block['BlockType'] == 'QUERY_RESULT':
        print(f"{block['Query']['Alias']}: {block.get('Text', 'N/A')} (confidence: {block.get('Confidence', 0)}%)")
```

#### Hours 12-16: Bedrock Agent Configuration

**Tasks:**
1. Set up Bedrock Agent with Claude 3.5 Sonnet
2. Configure action groups for Textract
3. Test orchestration

**bedrock_setup.py:**

agent_response = bedrock_agent.create_agent(
    agentName='kisan-setu-mvp-agent',
    foundationModel='anthropic.claude-sonnet-4-6',  # Latest Claude Sonnet 4.6
    instruction='''You are an AI assistant for Kisan-Setu.
bedrock_agent = boto3.client('bedrock-agent', region_name='ap-south-1')

# Create agent
agent_response = bedrock_agent.create_agent(
    agentName='kisan-setu-mvp-agent',
    foundationModel='anthropic.claude-3-5-sonnet-20241022-v2:0',
    instruction='''You are an AI assistant for Kisan-Setu. 
    You help digitize handwritten ledgers from farmers.
    Extract quantity, moisture, price, and other details from ledger images.
    Always respond in a structured JSON format.''',
    agentResourceRoleArn='arn:aws:iam::ACCOUNT:role/KisanSetuAgentRole'
)

agent_id = agent_response['agent']['agentId']

# Create action group for document processing
bedrock_agent.create_agent_action_group(
    agentId=agent_id,
    agentVersion='DRAFT',
    actionGroupName='document-processing',
    actionGroupExecutor={
        'lambda': 'arn:aws:lambda:ap-south-1:ACCOUNT:function:DocumentProcessor'
    },
    apiSchema={
        'payload': json.dumps({
            'openapi': '3.0.0',
            'info': {'title': 'Document Processing API', 'version': '1.0.0'},
            'paths': {
                '/extract-ledger': {
                    'post': {
                        'description': 'Extract data from handwritten ledger',
                        'requestBody': {
                            'required': True,
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'type': 'object',
                                        'properties': {
                                            'image_url': {'type': 'string'},
                                            'language': {'type': 'string'}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        })
    }
)

# Prepare agent
bedrock_agent.prepare_agent(agentId=agent_id)

print(f"Agent created: {agent_id}")
```

#### Hours 16-20: WhatsApp Integration

**Tasks:**
1. Set up Meta WhatsApp Business API account
2. Configure webhook endpoint
3. Test message sending/receiving

**WhatsApp Setup (using Meta WhatsApp Business API):**

```python
import requests

# Meta WhatsApp credentials (from AWS Secrets Manager)
PHONE_NUMBER_ID = 'your_phone_number_id'
ACCESS_TOKEN = 'your_access_token'

# Configure webhook
# Go to Meta Developer Console → WhatsApp → Configuration
# Set Callback URL: https://YOUR_API_GATEWAY_URL/webhook
# Set Verify Token: kisan-setu-verify-2026

# Test sending message
def send_whatsapp_message(to_number, message):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()

# Test
send_whatsapp_message('919876543210', 'Hello from Kisan-Setu! 🌾')
```

#### Hours 20-24: End-to-End Testing & Refinement

**Test Checklist:**

```bash
# 1. Deploy infrastructure
cd kisan-setu-mvp
cdk deploy

# 2. Get API Gateway URL
aws apigateway get-rest-apis --query "items[?name=='Kisan-Setu WhatsApp Webhook'].id" --output text

# 3. Configure WhatsApp webhook
# Set webhook URL in Meta Developer Console

# 4. Test end-to-end flow
# - Send photo of Hindi ledger via WhatsApp
# - Wait for processing (<15 seconds)
# - Receive JSON response

# 5. Verify in DynamoDB
aws dynamodb scan --table-name KisanSetuData --max-items 10

# 6. Check CloudWatch logs
aws logs tail /aws/lambda/MessageRouter --follow
aws logs tail /aws/lambda/DocumentProcessor --follow
```

**Performance Monitoring:**

```python
import time

def measure_latency():
    start = time.time()
    
    # Send image via WhatsApp
    send_test_image()
    
    # Wait for response
    response = wait_for_response(timeout=30)
    
    end = time.time()
    latency = end - start
    
    print(f"End-to-end latency: {latency:.2f} seconds")
    assert latency < 15, "Latency exceeds 15 seconds!"
    
    return latency
```

### Deployment Commands

```bash
# Complete deployment script
#!/bin/bash

echo "🚀 Deploying Kisan-Setu MVP..."

# 1. Set environment variables
export AWS_REGION=ap-south-1
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# 2. Create S3 buckets
aws s3 mb s3://kisan-setu-raw-${ACCOUNT_ID} --region ${AWS_REGION}
aws s3 mb s3://kisan-setu-processed-${ACCOUNT_ID} --region ${AWS_REGION}

# 3. Deploy CDK stack
cd kisan-setu-mvp
cdk bootstrap
cdk deploy --require-approval never

# 4. Get API Gateway URL
API_URL=$(aws apigateway get-rest-apis \
  --query "items[?name=='Kisan-Setu WhatsApp Webhook'].id" \
  --output text)
echo "API Gateway URL: https://${API_URL}.execute-api.${AWS_REGION}.amazonaws.com/prod/webhook"

# 5. Configure WhatsApp webhook
echo "⚠️  Manual step: Configure WhatsApp webhook with above URL"

echo "✅ Deployment complete!"
```

### Success Validation

**Test Cases:**

1. ✅ Send clear Hindi ledger photo → Extract all fields with >80% confidence
2. ✅ Send blurry image → Flag low confidence fields, request clarification
3. ✅ Send non-ledger image → Return error message
4. ✅ Send multiple images in sequence → Process all correctly
5. ✅ Check DynamoDB → All transactions stored correctly
6. ✅ Measure latency → <15 seconds end-to-end

**Expected Output:**

```
WhatsApp Message:
─────────────────
✅ Ledger digitized successfully!

📊 Data extracted:
Quantity: 500 kg
Moisture: 13.5%
Price: ₹25
Crop: Onion

JSON:
{
  "transaction_id": "TXN#2024-01-15T10:30:00Z",
  "quantity": 500.0,
  "moisture": 13.5,
  "price": 25.0,
  "crop_type": "onion",
  "confidence_scores": {
    "QUANTITY": 95.2,
    "MOISTURE": 89.7,
    "PRICE": 92.1
  }
}
```

### Post-24-Hour Next Steps

1. Add voice interface (Transcribe + Polly)
2. Implement credit scoring engine
3. Add satellite yield prediction
4. Deploy offline tablet mode
5. Scale to multiple FPOs

## Conclusion

This 24-hour MVP demonstrates the core value proposition of Kisan-Setu: transforming unstructured rural data (handwritten ledgers) into bankable digital records with zero typing required. The implementation uses AWS serverless services for cost-efficiency and scalability, targeting <$50/month per FPO cluster.
