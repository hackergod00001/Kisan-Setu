> **Note:** This setup guide has been updated to reflect the current implementation, which uses a 5-model APAC inference profile fallback chain. See `kisan-setu-mvp/README.md` for full architecture details.

# Kisan-Setu Setup Guide

Complete guide for deploying the Kisan-Setu WhatsApp-based agricultural assistant from scratch.

---

## Prerequisites

### Required Accounts
- AWS Account with billing enabled
- Meta WhatsApp Business Account (for WhatsApp integration)

### Required Software
- Python 3.11 or higher
- Node.js 18+ (for AWS CDK)
- AWS CLI v2
- Git

---

## Step 1: AWS Account Setup (15 minutes)

### 1.1 Create IAM User
```bash
# Create IAM user with AdministratorAccess
aws iam create-user --user-name kisan-setu-dev

# Attach admin policy
aws iam attach-user-policy \
  --user-name kisan-setu-dev \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess

# Create access keys
aws iam create-access-key --user-name kisan-setu-dev
```

Save the Access Key ID and Secret Access Key.

### 1.2 Configure AWS CLI
```bash
aws configure
# Enter your access key, secret key, region (ap-south-1), and format (json)

# Verify
aws sts get-caller-identity
```

---

## Step 2: Enable AWS Bedrock (30 minutes)

### 2.1 Request Model Access
1. Go to AWS Console → Bedrock → Model access
2. Click "Manage model access"
3. Enable these models (all used in the 5-model fallback chain):
   - **Amazon Nova Pro** (`apac.amazon.nova-pro-v1:0`) — primary text model
   - **Amazon Nova Lite** (`apac.amazon.nova-lite-v1:0`) — fast fallback
   - **Claude 3.7 Sonnet** (`apac.anthropic.claude-3-7-sonnet-20250219-v1:0`) — multimodal primary
   - **Claude 3.5 Sonnet v2** (`apac.anthropic.claude-3-5-sonnet-20241022-v2:0`)
   - **Claude 3 Haiku** (`apac.anthropic.claude-3-haiku-20240307-v1:0`)
   - **Titan Text Embeddings V2** (amazon.titan-embed-text-v2:0)
4. Click "Request model access"
5. Wait for approval (5-30 minutes, check email)

**Note:** Claude models require APAC inference profiles. Nova models are available without Marketplace subscription and are prioritized in the fallback chain.

### 2.2 Verify Access
```bash
aws bedrock list-foundation-models --region ap-south-1 \
  --query "modelSummaries[?contains(modelId, 'claude')].modelId"
```

---

## Step 3: Install Development Tools (10 minutes)

### 3.1 Install AWS CDK
```bash
npm install -g aws-cdk
cdk --version
```

### 3.2 Bootstrap CDK
```bash
# Get your AWS account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Bootstrap CDK
cdk bootstrap aws://$AWS_ACCOUNT_ID/ap-south-1
```

### 3.3 Setup Python Environment
```bash
# Clone/navigate to project
cd kisan-setu-mvp

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Step 4: Meta WhatsApp Business API Setup (15 minutes)

### 4.1 Create Meta Developer Account
1. Go to https://developers.facebook.com/
2. Create an app → Add WhatsApp product
3. Go to WhatsApp → Getting Started

### 4.2 Setup WhatsApp Business
1. Note your Phone Number ID and Business Account ID
2. Copy the temporary access token (expires in 24 hours)
3. For production, generate a permanent token

### 4.3 Store Credentials in AWS
```bash
# Store in AWS Secrets Manager
aws secretsmanager create-secret \
  --name kisan-setu/whatsapp/credentials \
  --secret-string '{"PHONE_NUMBER_ID":"your_phone_id","ACCESS_TOKEN":"your_token","VERIFY_TOKEN":"kisan-setu-verify-2026"}' \
  --region ap-south-1
```

---

## Step 5: Deploy Infrastructure (10 minutes)

### 5.1 Deploy CDK Stack
```bash
cd kisan-setu-mvp
source .venv/bin/activate

# Deploy
cdk deploy --require-approval never
```

This creates:
- S3 buckets (raw, processed, knowledge)
- DynamoDB table
- Lambda functions (router, processor, voice, credit)
- API Gateway
- IAM roles

### 5.2 Note the Outputs
Save these from the deployment output:
- `WebhookURL`: Your API Gateway webhook endpoint
- `MessageRouterFunction`: Lambda function name
- `DocumentProcessorFunction`: Lambda function name

---

## Step 6: Configure Meta WhatsApp Webhook (5 minutes)

### 6.1 Set Webhook URL
1. Go to Meta Developer Console → WhatsApp → Configuration
2. Set Callback URL to your WebhookURL (from Step 5.2)
3. Set Verify Token: `kisan-setu-verify-2026`
4. Subscribe to: messages, message_status
5. Save

---

## Step 7: Test the Integration (10 minutes)

### 7.1 Run Test Script
```bash
cd kisan-setu-mvp
source .venv/bin/activate
python3 quick_whatsapp_test.py
```

This verifies:
- WhatsApp credentials accessible
- Webhook endpoint working
- Lambda permissions correct
- Can send WhatsApp messages

### 7.2 Test End-to-End
1. Send a text message from your WhatsApp to your business number
2. Send an image (ledger photo) to the business number
3. Check CloudWatch logs:
```bash
# Get your function name from Step 5.2
aws logs tail /aws/lambda/YOUR_ROUTER_FUNCTION_NAME --follow --region ap-south-1
```

---

## Step 8: Optional - Setup Bedrock Agent (30 minutes)

### 8.1 Create Knowledge Base
```bash
cd kisan-setu-mvp
source .venv/bin/activate
python3 setup_bedrock_agent.py
```

### 8.2 Upload FPO Guidelines
1. Upload PDF documents to `s3://kisan-setu-knowledge-{account-id}/`
2. Sync knowledge base:
```bash
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id YOUR_KB_ID \
  --data-source-id YOUR_DS_ID \
  --region ap-south-1
```

---

## Troubleshooting

### Issue: Bedrock Access Denied
**Solution:** Wait for model access approval (check email), can take up to 30 minutes

### Issue: Lambda Permission Errors
**Solution:** Redeploy CDK stack:
```bash
cdk deploy --require-approval never
```

### Issue: WhatsApp Messages Not Received
**Solution:**
1. Verify webhook URL in Meta Developer Console
2. Check API Gateway is deployed
3. View CloudWatch logs for errors

### Issue: boto3 Module Not Found
**Solution:**
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Cost Estimation

### Monthly Costs (Estimated)
- Lambda: $5-10 (10M requests)
- Textract: $5-10 (1000 pages)
- Bedrock: $20-30 (5-model fallback chain via APAC inference profiles)
- DynamoDB: $2-5 (on-demand)
- S3: $1-2 (10GB storage + dashboard hosting)
- Meta WhatsApp: Free (Cloud API)

**Total: ~$33-57/month**

### Cost Optimization Tips
- Use on-demand pricing for DynamoDB
- Enable S3 lifecycle policies
- Set Lambda memory to minimum required
- Use Bedrock prompt caching
- Monitor with AWS Cost Explorer

---

## Monitoring

### View Lambda Logs
```bash
# List all Kisan-Setu functions
aws lambda list-functions --region ap-south-1 \
  --query "Functions[?contains(FunctionName, 'KisanSetu')].FunctionName"

# Tail logs
aws logs tail /aws/lambda/FUNCTION_NAME --follow --region ap-south-1
```

### Check DynamoDB Data
```bash
aws dynamodb scan --table-name KisanSetuData --max-items 10 --region ap-south-1
```

### Monitor Costs
```bash
aws ce get-cost-and-usage \
  --time-period Start=2026-03-01,End=2026-03-03 \
  --granularity DAILY \
  --metrics BlendedCost \
  --region us-east-1
```

---

## Next Steps

1. **Test with real ledgers** - Upload actual farmer ledger images
2. **Add response functionality** - Implement WhatsApp message sending
3. **Multi-language support** - Add Hindi/regional language responses
4. **Production hardening** - Add error handling, retries, monitoring
5. **Security audit** - Review IAM permissions, enable encryption

---

## Support

**Documentation:**
- AWS Bedrock: https://docs.aws.amazon.com/bedrock/
- AWS CDK: https://docs.aws.amazon.com/cdk/
- Meta WhatsApp Business API: https://developers.facebook.com/docs/whatsapp

**Common Commands:**
```bash
# Redeploy infrastructure
cdk deploy

# View all stacks
aws cloudformation list-stacks --region ap-south-1

# Delete everything (cleanup)
cdk destroy
```

---

**Setup Time:** ~90 minutes (excluding Bedrock approval wait)  
**Difficulty:** Intermediate  
**Cost:** ~$50/month
