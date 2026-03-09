# Kisan-Setu MVP - WhatsApp-Based Agricultural Assistant

AI-powered WhatsApp assistant for Indian farmers using AWS Bedrock, Meta WhatsApp Business API, and serverless architecture.

---

## 🎯 Overview

Kisan-Setu helps farmers through WhatsApp by:
- Processing ledger images with OCR (AWS Textract)
- Providing agricultural advice via AI (AWS Bedrock)
- Calculating credit scores based on transaction history
- Analyzing satellite imagery for crop health (SageMaker Geospatial)
- Supporting voice messages in Hindi and regional languages

---

## 🏗️ Architecture

```
WhatsApp User
    ↓
Meta WhatsApp Business API
    ↓
API Gateway → MessageRouter Lambda
    ↓
    ├─→ DocumentProcessor (Images/Ledgers)
    ├─→ VoiceAgent (Voice Messages)
    └─→ BedrockOrchestrator (Text Messages)
         ↓
         ├─→ KnowledgeBase (Agricultural Info)
         ├─→ CreditCalculator (Credit Scoring)
         └─→ SatelliteAnalyzer (Crop Health)
```

---

## 📋 Prerequisites

- AWS Account (Account ID: 682366718780, Region: ap-south-1)
- Meta WhatsApp Business Account
- Python 3.9+
- Node.js 20+ (for AWS CDK)
- AWS CLI configured

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd kisan-setu-mvp

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install CDK
npm install -g aws-cdk
```

### 2. Configure Meta WhatsApp Credentials

Get your credentials from Meta Developer Console:
- Phone Number ID: `1043444535519617`
- Business Account ID: `1249840547247394`
- Access Token: (from Meta dashboard)

```bash
# Set environment variable
export WHATSAPP_ACCESS_TOKEN="your_access_token_here"

# Deploy and configure
./deploy_meta_whatsapp.sh
```

### 3. Deploy Infrastructure

```bash
# Silence Node.js version warning (optional)
export JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1

# Bootstrap CDK (first time only)
cdk bootstrap aws://682366718780/ap-south-1

# Deploy stack
cdk deploy --require-approval never
```

### 4. Configure Webhook in Meta Dashboard

1. Go to Meta App Dashboard → Configuration → Webhooks
2. Set Callback URL: `https://061d3ls8qh.execute-api.ap-south-1.amazonaws.com/prod/webhook`
3. Set Verify Token: `kisan-setu-verify-2026`
4. Click "Verify and Save"
5. Subscribe to `messages` webhook field

---

## 📁 Project Structure

```
kisan-setu-mvp/
├── lambda/
│   ├── router/              # Message routing
│   ├── processor/           # Document/image processing
│   ├── voice/               # Voice message handling
│   ├── orchestrator/        # Bedrock AI orchestration
│   ├── credit/              # Credit score calculation
│   ├── satellite/           # Satellite imagery analysis
│   ├── knowledge/           # Knowledge base queries
│   ├── sync/                # Offline sync handler
│   ├── whatsapp/            # WhatsApp integration
│   │   ├── meta_whatsapp_interface.py
│   │   ├── webhook_handler.py
│   │   └── whatsapp_interface.py
│   └── common/              # Shared utilities
├── infrastructure_stack.py  # CDK infrastructure
├── app.py                   # CDK app entry point
├── schema.graphql           # AppSync schema
├── deploy_meta_whatsapp.sh  # Deployment script
└── requirements.txt         # Python dependencies
```

---

## 🧪 Testing

### Test Webhook Verification

```bash
curl "https://061d3ls8qh.execute-api.ap-south-1.amazonaws.com/prod/webhook?hub.mode=subscribe&hub.verify_token=kisan-setu-verify-2026&hub.challenge=test123"
```

### Send Test Message

1. Go to Meta App Dashboard → API Setup
2. Click "Send Test Message"
3. Send a message to test the integration

### Monitor Lambda Logs

```bash
# Real-time logs
aws logs tail /aws/lambda/KisanSetuMVPStack-MessageRouter8CD84FD1-h6L1m4kKPfOf \
  --follow --region ap-south-1

# Recent logs
aws logs tail /aws/lambda/KisanSetuMVPStack-MessageRouter8CD84FD1-h6L1m4kKPfOf \
  --since 1h --region ap-south-1
```

---

## 🔧 Configuration

### Update WhatsApp Access Token

```bash
# Update token in Secrets Manager
aws secretsmanager update-secret \
  --secret-id kisan-setu/whatsapp/credentials \
  --secret-string "{
    \"WHATSAPP_ACCESS_TOKEN\": \"your_new_token\",
    \"PHONE_NUMBER_ID\": \"1043444535519617\",
    \"BUSINESS_ACCOUNT_ID\": \"1249840547247394\",
    \"VERIFY_TOKEN\": \"kisan-setu-verify-2026\"
  }" \
  --region ap-south-1
```

### Environment Variables

Lambda functions use these environment variables:
- `DYNAMODB_TABLE`: KisanSetuData
- `WHATSAPP_SECRET_NAME`: kisan-setu/whatsapp/credentials
- `WEBHOOK_VERIFY_TOKEN`: kisan-setu-verify-2026
- `BEDROCK_AGENT_ID`: UUQPVM0ULJ
- `BEDROCK_AGENT_ALIAS_ID`: A2TGFPMFXZ

---

## 📊 AWS Resources

### Lambda Functions
- MessageRouter - Routes incoming messages
- DocumentProcessor - Processes images/ledgers
- VoiceHandler - Handles voice messages
- BedrockOrchestrator - AI orchestration
- CreditCalculator - Credit scoring
- SatelliteAnalyzer - Satellite analysis
- KnowledgeBase - Agricultural knowledge queries
- SyncHandler - Offline sync

### Storage
- DynamoDB: KisanSetuData (conversation history, transactions)
- S3 Buckets:
  - kisan-setu-raw-{account_id}
  - kisan-setu-processed-{account_id}
  - kisan-setu-archive-{account_id}

### API
- API Gateway: WhatsApp webhook endpoint
- AppSync: GraphQL API for offline sync

### Monitoring
- CloudWatch Logs: Lambda execution logs
- SNS Topic: kisan-setu-critical-alerts

---

## 🔐 Security

- WhatsApp credentials stored in AWS Secrets Manager
- IAM roles with least privilege access
- API Gateway throttling (100 req/s, burst 200)
- Webhook verification token validation

---

## 📚 Documentation

- `START_HERE.md` - Getting started guide
- `META_WHATSAPP_QUICKSTART.md` - Meta WhatsApp setup
- `META_WEBHOOK_SETUP.md` - Webhook configuration
- `META_SETUP_COMPLETE.md` - Complete setup overview
- `DEPLOYMENT_ORDER.md` - Deployment sequence
- `COMMON_ERRORS.md` - Troubleshooting guide
- `TESTING_GUIDE.md` - Testing procedures
- `PRODUCTION_DEPLOYMENT.md` - Production checklist

---

## 🚨 Troubleshooting

### Webhook Not Receiving Messages

1. Check `messages` field is subscribed in Meta dashboard
2. Verify webhook URL is correct
3. Check Lambda logs for errors
4. Test webhook verification endpoint

### Lambda Errors

```bash
# Check function configuration
aws lambda get-function-configuration \
  --function-name KisanSetuMVPStack-MessageRouter8CD84FD1-h6L1m4kKPfOf \
  --region ap-south-1

# View recent errors
aws logs filter-pattern "ERROR" \
  --log-group-name /aws/lambda/KisanSetuMVPStack-MessageRouter8CD84FD1-h6L1m4kKPfOf \
  --region ap-south-1
```

### Access Token Issues

- Tokens expire - regenerate in Meta dashboard
- Update in Secrets Manager immediately
- No redeployment needed - Lambda picks up new token automatically

---

## 🎯 Development Mode vs Production

### Development Mode (Current)
- Only receives test messages from Meta dashboard
- Perfect for testing and development
- No app review required

### Production Mode
- Receives messages from real users
- Requires Meta app review and approval
- Switch app to "Live" mode in Meta dashboard

---

## 📞 Support

### AWS Issues
- Check CloudWatch Logs
- Review IAM permissions
- Verify resource configurations

### Meta WhatsApp Issues
- [Meta WhatsApp Documentation](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [Webhook Reference](https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks)
- Check Meta App Dashboard for errors

---

## 📝 License

Proprietary - AI for Bharat Hackathon 2026

---

## 🙏 Acknowledgments

Built with:
- AWS Bedrock (5-model APAC inference profile fallback: Nova Pro, Nova Lite, Claude 3.7 Sonnet, Claude 3.5 Sonnet v2, Claude 3 Haiku)
- AWS Textract
- AWS Transcribe & Polly
- SageMaker Geospatial
- Meta WhatsApp Business API
- AWS CDK

---

**Status**: ✅ Production Ready | Meta WhatsApp Integration Active

**Webhook URL**: `https://061d3ls8qh.execute-api.ap-south-1.amazonaws.com/prod/webhook`

**Last Updated**: March 7, 2026
